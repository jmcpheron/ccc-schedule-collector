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

"""Batch collection of detailed course information for Rio Hondo College."""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
import argparse
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent))

from collectors.rio_hondo.collector import RioHondoCollector
from models import Course, ScheduleData, DetailedCourse, Enrollment
from utils.storage import ScheduleStorage

console = Console()


class RioHondoDetailCollector:
    """Specialized collector for Rio Hondo course details with enhanced progress tracking."""
    
    def __init__(self, rate_limit: float = 1.5):
        """Initialize the detail collector.
        
        Args:
            rate_limit: Seconds to wait between requests (default 1.5 to be respectful)
        """
        self.collector = RioHondoCollector()
        self.rate_limit = rate_limit
        self.progress_file = Path("data/.rio_detail_progress.json")
        
    def load_schedule(self, schedule_file: str) -> ScheduleData:
        """Load a schedule JSON file and return ScheduleData object."""
        console.print(f"📖 [cyan]Loading schedule from: {schedule_file}[/cyan]")
        
        with open(schedule_file, 'r') as f:
            data = json.load(f)
            
        # Convert to ScheduleData object
        schedule_data = ScheduleData(**data)
        
        console.print(f"✅ Loaded {len(schedule_data.courses)} courses from {schedule_data.term} ({schedule_data.term_code})")
        return schedule_data
    
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
            
    def collect_details_batch(self, schedule_data: ScheduleData, 
                             limit: Optional[int] = None,
                             resume: bool = True,
                             batch_size: int = 50) -> ScheduleData:
        """Collect detailed information for courses in a schedule.
        
        Args:
            schedule_data: Basic schedule data to enhance
            limit: Maximum number of courses to process (None for all)
            resume: Whether to resume from previous progress
            batch_size: Number of courses to process before saving progress
            
        Returns:
            Enhanced ScheduleData with DetailedCourse objects
        """
        courses_to_process = schedule_data.courses[:limit] if limit else schedule_data.courses
        total_courses = len(courses_to_process)
        
        console.print(f"🎯 [yellow]Processing {total_courses} courses[/yellow]")
        
        # Load progress if resuming
        progress = {}
        completed_crns = set()
        if resume:
            progress = self.load_progress()
            if progress.get('schedule_file') == str(schedule_data.source_url):
                completed_crns = set(progress.get('completed_crns', []))
                console.print(f"🔄 [green]Resuming: {len(completed_crns)} already completed[/green]")
            else:
                progress = {}
                
        # Filter out already completed courses
        remaining_courses = [c for c in courses_to_process if c.crn not in completed_crns]
        
        if not remaining_courses:
            console.print("✅ [green]All courses already processed![/green]")
            if progress.get('output_file') and Path(progress['output_file']).exists():
                with open(progress['output_file'], 'r') as f:
                    return ScheduleData(**json.load(f))
            return schedule_data
            
        console.print(f"📋 [blue]{len(remaining_courses)} courses remaining to process[/blue]")
        
        # Initialize results
        detailed_courses = []
        errors = []
        
        # Load previously completed courses if resuming
        if resume and progress.get('output_file') and Path(progress['output_file']).exists():
            with open(progress['output_file'], 'r') as f:
                existing_data = json.load(f)
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
                f"Collecting details...",
                total=len(remaining_courses)
            )
            
            for i, course in enumerate(remaining_courses):
                try:
                    # Update progress description
                    progress_bar.update(task, description=f"Processing {course.subject} {course.course_number}")
                    
                    # Fetch details using the collector
                    detailed_course = self.collector.collect_course_details(
                        [course],
                        schedule_data.term_code,
                        batch_size=1,
                        detail_delay=0  # We handle delay ourselves
                    )[0]
                    
                    detailed_courses.append(detailed_course)
                    completed_crns.add(course.crn)
                    
                    # Update progress
                    progress_bar.update(task, advance=1)
                    
                    # Save progress periodically
                    if (i + 1) % batch_size == 0:
                        self._save_intermediate_results(
                            schedule_data, detailed_courses, completed_crns, errors
                        )
                        
                    # Rate limiting - be respectful to the server
                    if i < len(remaining_courses) - 1:
                        time.sleep(self.rate_limit)
                        
                except Exception as e:
                    error_msg = f"Failed to get details for {course.crn} ({course.subject} {course.course_number}): {str(e)}"
                    console.print(f"[red]❌ {error_msg}[/red]")
                    errors.append(error_msg)
                    
                    # Add course without details on error
                    detailed_courses.append(Course(**course.model_dump()))
                    completed_crns.add(course.crn)
                    progress_bar.update(task, advance=1)
        
        # Create final detailed schedule
        enhanced_schedule = ScheduleData(
            term=schedule_data.term,
            term_code=schedule_data.term_code,
            collection_timestamp=schedule_data.collection_timestamp,
            source_url=schedule_data.source_url,
            college_id=schedule_data.college_id,
            collector_version=schedule_data.collector_version,
            courses=detailed_courses,
            metadata={
                **(schedule_data.metadata or {}),
                'details_collected': True,
                'detail_collection_timestamp': datetime.now(timezone.utc).isoformat() + "Z",
                'courses_with_details': sum(1 for c in detailed_courses if isinstance(c, DetailedCourse)),
                'total_courses': len(detailed_courses),
                'detail_collection_errors': errors if errors else None,
                'detail_rate_limit': self.rate_limit
            }
        )
        
        # Save final results
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"schedule_detailed_{schedule_data.term_code}_{timestamp}.json"
        output_path = Path("data") / filename
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the enhanced schedule
        with open(output_path, 'w') as f:
            json.dump(enhanced_schedule.model_dump(mode='json'), f, indent=2, default=str)
        
        console.print(f"\n✅ [green]Detailed schedule saved to: {output_path}[/green]")
        
        detailed_count = enhanced_schedule.metadata['courses_with_details']
        total_count = len(enhanced_schedule.courses)
        console.print(f"📊 [blue]Results: {detailed_count}/{total_count} courses have detailed information[/blue]")
        
        if errors:
            console.print(f"⚠️  [yellow]{len(errors)} errors occurred during collection[/yellow]")
            
        # Clean up progress file on successful completion
        if self.progress_file.exists():
            self.progress_file.unlink()
            
        return enhanced_schedule
    
    def _save_intermediate_results(self, schedule_data: ScheduleData, detailed_courses: List, 
                                   completed_crns: set, errors: List):
        """Save intermediate results and progress."""
        # Update progress
        progress = {
            'schedule_file': str(schedule_data.source_url),
            'completed_crns': list(completed_crns),
            'total_processed': len(completed_crns),
            'last_update': datetime.now(timezone.utc).isoformat() + "Z",
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
                **(schedule_data.metadata or {}),
                'partial': True,
                'details_collected': True,
                'courses_processed': len(completed_crns),
                'detail_collection_errors': errors if errors else None
            }
        )
        
        with open(progress['output_file'], 'w') as f:
            json.dump(partial_schedule.model_dump(mode='json'), f, indent=2, default=str)
    
    def find_latest_schedule(self) -> Optional[str]:
        """Find the latest Rio Hondo schedule file."""
        data_dir = Path("data/rio-hondo")
        if not data_dir.exists():
            return None
            
        json_files = list(data_dir.glob("schedule_*.json"))
        if not json_files:
            return None
            
        # Return the most recent file
        latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
        return str(latest_file)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Collect detailed course information for Rio Hondo")
    parser.add_argument("--input", "-i", help="Input schedule JSON file (auto-detected if not provided)")
    parser.add_argument("--limit", "-l", type=int, help="Limit number of courses to process (for testing)")
    parser.add_argument("--rate-limit", "-r", type=float, default=1.5, help="Seconds between requests (default: 1.5)")
    parser.add_argument("--batch-size", "-b", type=int, default=50, help="Save progress every N courses (default: 50)")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh, don't resume previous run")
    
    args = parser.parse_args()
    
    # Initialize collector
    collector = RioHondoDetailCollector(rate_limit=args.rate_limit)
    
    # Find input file
    input_file = args.input
    if not input_file:
        input_file = collector.find_latest_schedule()
        if not input_file:
            console.print("❌ [red]No schedule file found. Please specify --input or run schedule collection first.[/red]")
            sys.exit(1)
        console.print(f"🔍 [blue]Auto-detected schedule file: {input_file}[/blue]")
    
    if not Path(input_file).exists():
        console.print(f"❌ [red]Input file not found: {input_file}[/red]")
        sys.exit(1)
    
    try:
        # Load schedule
        schedule_data = collector.load_schedule(input_file)
        
        # Show rate limiting info
        console.print(f"⏱️  [yellow]Rate limit: {args.rate_limit} seconds between requests[/yellow]")
        if args.limit:
            console.print(f"🎯 [blue]Processing only first {args.limit} courses[/blue]")
        
        # Collect details
        enhanced_schedule = collector.collect_details_batch(
            schedule_data,
            limit=args.limit,
            resume=not args.no_resume,
            batch_size=args.batch_size
        )
        
        console.print("\n🎉 [bold green]Detail collection completed successfully![/bold green]")
        
    except KeyboardInterrupt:
        console.print("\n⚠️  [yellow]Collection interrupted by user. Progress has been saved.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n❌ [bold red]Error: {str(e)}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()