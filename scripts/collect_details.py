#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "requests",
#   "beautifulsoup4",
#   "pydantic>=2.0",
#   "pyyaml",
#   "rich"
# ]
# ///

"""Collect detailed course information from parsed schedule data."""

import sys
import json
import time
import yaml
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from collectors.rio_hondo.collector import RioHondoCollector
from models import Course, ScheduleData, DetailedCourse
from utils.storage import ScheduleStorage

console = Console()


class DetailCollector:
    """Collector for course details with progress tracking and resume capability."""
    
    def __init__(self, config_path: str = "config_detail_test.yml"):
        """Initialize the detail collector.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path)
        self.load_config()
        
        # Initialize Rio Hondo collector for detail fetching
        self.collector = RioHondoCollector()
        self.progress_file = Path("data/.detail_collection_progress.json")
        
    def load_config(self):
        """Load configuration from YAML file."""
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
    def load_progress(self) -> dict:
        """Load progress from previous run if exists."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {}
        
    def save_progress(self, progress: dict):
        """Save current progress."""
        self.progress_file.parent.mkdir(exist_ok=True)
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)
            
    def collect_details_for_schedule(self, schedule_file: str, resume: bool = True) -> str:
        """Collect details for all courses in a schedule file.
        
        Args:
            schedule_file: Path to basic schedule JSON file
            resume: Whether to resume from previous progress
            
        Returns:
            Path to detailed schedule file
        """
        # Load schedule data
        console.print(f"[cyan]📖 Loading schedule from: {schedule_file}[/cyan]")
        with open(schedule_file, 'r') as f:
            data = json.load(f)
            
        schedule_data = ScheduleData(**data)
        total_courses = len(schedule_data.courses)
        
        console.print(f"[yellow]Found {total_courses} courses to process[/yellow]")
        
        # Load progress if resuming
        progress = {}
        if resume:
            progress = self.load_progress()
            if progress.get('schedule_file') == schedule_file:
                completed_crns = set(progress.get('completed_crns', []))
                console.print(f"[green]Resuming from previous run: {len(completed_crns)} already completed[/green]")
            else:
                progress = {}
                completed_crns = set()
        else:
            completed_crns = set()
            
        # Prepare courses to process
        courses_to_process = [c for c in schedule_data.courses if c.crn not in completed_crns]
        
        if not courses_to_process:
            console.print("[green]All courses already processed![/green]")
            return progress.get('output_file', '')
            
        # Collection settings
        detail_delay = self.config['collection'].get('detail_delay', 1.5)
        batch_size = self.config['collection'].get('detail_batch_size', 50)
        
        # Progress tracking
        detailed_courses = []
        errors = []
        
        # Load previously collected details if resuming
        if resume and progress.get('output_file') and Path(progress['output_file']).exists():
            with open(progress['output_file'], 'r') as f:
                existing_data = json.load(f)
                # Convert existing courses to DetailedCourse objects
                for course_data in existing_data.get('courses', []):
                    if 'detail_fetched_at' in course_data:
                        detailed_courses.append(DetailedCourse(**course_data))
                    else:
                        detailed_courses.append(Course(**course_data))
        
        # Collect details with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress_bar:
            
            task = progress_bar.add_task(
                f"Collecting details for {len(courses_to_process)} courses...",
                total=len(courses_to_process)
            )
            
            for i, course in enumerate(courses_to_process):
                try:
                    # Fetch details
                    detailed = self.collector.collect_course_details(
                        [course],
                        schedule_data.term_code,
                        batch_size=1,
                        detail_delay=0  # We'll handle delay ourselves
                    )[0]
                    
                    detailed_courses.append(detailed)
                    completed_crns.add(course.crn)
                    
                    # Update progress
                    progress_bar.update(task, advance=1)
                    
                    # Save progress periodically
                    if (i + 1) % batch_size == 0:
                        self._save_intermediate_results(
                            schedule_data, detailed_courses, completed_crns, 
                            schedule_file, errors
                        )
                        
                    # Rate limiting
                    if i < len(courses_to_process) - 1:
                        time.sleep(detail_delay)
                        
                except Exception as e:
                    error_msg = f"Failed to get details for {course.crn}: {str(e)}"
                    console.print(f"[red]{error_msg}[/red]")
                    errors.append(error_msg)
                    # Add course without details
                    detailed_courses.append(Course(**course.model_dump()))
                    completed_crns.add(course.crn)
                    progress_bar.update(task, advance=1)
        
        # Create final detailed schedule
        detailed_schedule = ScheduleData(
            term=schedule_data.term,
            term_code=schedule_data.term_code,
            collection_timestamp=datetime.now(),
            source_url=schedule_data.source_url,
            college_id=schedule_data.college_id,
            collector_version=schedule_data.collector_version,
            courses=detailed_courses,
            metadata={
                **schedule_data.metadata,
                'details_collected': True,
                'detail_collection_timestamp': datetime.now().isoformat(),
                'courses_with_details': sum(1 for c in detailed_courses if isinstance(c, DetailedCourse)),
                'collection_errors': errors if errors else None
            }
        )
        
        # Save final results
        storage = ScheduleStorage(data_dir="data")
        output_path = storage.save_schedule(
            detailed_schedule,
            filename_pattern="schedule_detailed_{term_code}_{timestamp}.json"
        )
        
        console.print(f"\n[green]✓ Detailed schedule saved to: {output_path}[/green]")
        console.print(f"[green]✓ Courses with details: {detailed_schedule.metadata['courses_with_details']}/{total_courses}[/green]")
        
        # Clean up progress file
        if self.progress_file.exists():
            self.progress_file.unlink()
            
        return output_path
        
    def _save_intermediate_results(self, schedule_data, detailed_courses, 
                                   completed_crns, schedule_file, errors):
        """Save intermediate results and progress."""
        # Update progress
        progress = {
            'schedule_file': schedule_file,
            'completed_crns': list(completed_crns),
            'last_update': datetime.now().isoformat(),
            'output_file': f"data/schedule_detailed_{schedule_data.term_code}_partial.json"
        }
        self.save_progress(progress)
        
        # Save partial results
        partial_schedule = ScheduleData(
            term=schedule_data.term,
            term_code=schedule_data.term_code,
            collection_timestamp=schedule_data.collection_timestamp,
            source_url=schedule_data.source_url,
            college_id=schedule_data.college_id,
            collector_version=schedule_data.collector_version,
            courses=detailed_courses,
            metadata={
                **schedule_data.metadata,
                'partial': True,
                'details_collected': True,
                'courses_processed': len(completed_crns),
                'collection_errors': errors if errors else None
            }
        )
        
        with open(progress['output_file'], 'w') as f:
            json.dump(partial_schedule.model_dump(mode='json'), f, indent=2, default=str)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Collect course details from basic schedule")
    parser.add_argument("--input", "-i", required=True, help="Input schedule JSON file")
    parser.add_argument("--config", "-c", default="config_detail_test.yml", help="Config file")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh, don't resume")
    
    args = parser.parse_args()
    
    if not Path(args.input).exists():
        console.print(f"[red]Error: Input file not found: {args.input}[/red]")
        sys.exit(1)
        
    collector = DetailCollector(args.config)
    collector.collect_details_for_schedule(args.input, resume=not args.no_resume)


if __name__ == "__main__":
    main()