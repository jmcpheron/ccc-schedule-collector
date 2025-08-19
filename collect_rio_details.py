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
        
    def get_detailed_filename(self, term_code: str) -> Path:
        """Get the standard detailed schedule filename for a term.
        
        Args:
            term_code: Term code (e.g., "202570")
            
        Returns:
            Path to the detailed schedule file
        """
        return Path(f"data/rio-hondo/schedule_detailed_{term_code}.json")
    
    def load_existing_detailed(self, term_code: str) -> Optional[ScheduleData]:
        """Load existing detailed schedule if it exists.
        
        Args:
            term_code: Term code to load
            
        Returns:
            ScheduleData object if file exists, None otherwise
        """
        file_path = self.get_detailed_filename(term_code)
        if file_path.exists():
            console.print(f"📖 [cyan]Loading existing detailed schedule: {file_path}[/cyan]")
            with open(file_path, 'r') as f:
                data = json.load(f)
                return ScheduleData(**data)
        return None
    
    def merge_course_details(self, 
                           base_schedule: ScheduleData,
                           new_detailed_courses: List[DetailedCourse],
                           completed_crns: set,
                           errors: List[str]) -> ScheduleData:
        """Merge new detailed courses into existing schedule.
        
        Args:
            base_schedule: Base schedule to merge into
            new_detailed_courses: New detailed courses to merge in
            completed_crns: Set of CRNs that have been processed
            errors: List of errors encountered during collection
            
        Returns:
            Updated ScheduleData with merged details
        """
        # Create CRN mapping from new details
        new_details_map = {c.crn: c for c in new_detailed_courses}
        
        # Update courses - merge new details with existing courses
        merged_courses = []
        for course in base_schedule.courses:
            if course.crn in new_details_map:
                # Use the new detailed version
                merged_courses.append(new_details_map[course.crn])
            else:
                # Keep existing course (may already have details or be unprocessed)
                merged_courses.append(course)
        
        # Count detailed courses
        detailed_count = sum(1 for c in merged_courses 
                           if hasattr(c, 'detail_fetched_at') and c.detail_fetched_at is not None)
        
        # Update metadata
        updated_metadata = {
            **(base_schedule.metadata or {}),
            'details_collected': True,
            'detail_collection_timestamp': datetime.now(timezone.utc).isoformat() + "Z",
            'courses_with_details': detailed_count,
            'total_courses': len(merged_courses),
            'detail_collection_errors': errors if errors else None,
            'detail_rate_limit': self.rate_limit,
            'courses_processed_this_run': len(completed_crns)
        }
        
        return ScheduleData(
            term=base_schedule.term,
            term_code=base_schedule.term_code,
            collection_timestamp=base_schedule.collection_timestamp,
            source_url=base_schedule.source_url,
            college_id=base_schedule.college_id,
            collector_version=base_schedule.collector_version,
            courses=merged_courses,
            metadata=updated_metadata
        )
    
    def save_merged_results(self, schedule_data: ScheduleData):
        """Save the merged schedule to the standard location.
        
        Args:
            schedule_data: Schedule data to save
        """
        output_path = self.get_detailed_filename(schedule_data.term_code)
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the merged schedule
        with open(output_path, 'w') as f:
            json.dump(schedule_data.model_dump(mode='json'), f, indent=2, default=str)
        
        console.print(f"💾 [green]Saved merged results to: {output_path}[/green]")
        
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
        """Collect detailed information for courses in a schedule using incremental merge approach.
        
        Args:
            schedule_data: Basic schedule data to enhance
            limit: Maximum number of courses to process (None for all)
            resume: Whether to resume from previous progress
            batch_size: Number of courses to process before saving progress
            
        Returns:
            Enhanced ScheduleData with DetailedCourse objects
        """
        # Start with existing detailed file if available, otherwise use input schedule
        base_schedule = self.load_existing_detailed(schedule_data.term_code)
        if base_schedule is None:
            console.print(f"📝 [blue]No existing detailed file found, starting fresh[/blue]")
            base_schedule = schedule_data
        else:
            # Update base schedule with any new courses from input (in case basic schedule was updated)
            input_crns = {c.crn for c in schedule_data.courses}
            base_crns = {c.crn for c in base_schedule.courses}
            
            if input_crns != base_crns:
                console.print(f"⚠️  [yellow]Schedule differences detected, merging with input[/yellow]")
                # Merge any new courses from input into base schedule
                merged_courses = list(base_schedule.courses)
                existing_crns = {c.crn for c in merged_courses}
                
                for course in schedule_data.courses:
                    if course.crn not in existing_crns:
                        merged_courses.append(course)
                        
                base_schedule.courses = merged_courses
        
        courses_to_process = base_schedule.courses[:limit] if limit else base_schedule.courses
        total_courses = len(courses_to_process)
        
        console.print(f"🎯 [yellow]Processing {total_courses} courses[/yellow]")
        
        # Load progress if resuming
        progress = {}
        completed_crns = set()
        if resume:
            progress = self.load_progress()
            if progress.get('term_code') == schedule_data.term_code:
                completed_crns = set(progress.get('completed_crns', []))
                console.print(f"🔄 [green]Resuming: {len(completed_crns)} already completed[/green]")
            else:
                progress = {}
        
        # Find courses that need details (don't have detail_fetched_at or are in remaining list)
        remaining_courses = []
        for course in courses_to_process:
            # Skip if already completed in this session
            if course.crn in completed_crns:
                continue
                
            # Skip if course already has details (unless we're re-processing)
            has_details = (hasattr(course, 'detail_fetched_at') and 
                          course.detail_fetched_at is not None)
            if has_details and not progress.get('reprocess_all', False):
                continue
                
            remaining_courses.append(course)
        
        if not remaining_courses:
            console.print("✅ [green]All courses already have details![/green]")
            return base_schedule
            
        console.print(f"📋 [blue]{len(remaining_courses)} courses need detail collection[/blue]")
        
        # Track newly detailed courses and errors for this run
        newly_detailed_courses = []
        errors = []
        run_completed_crns = set()
        
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
                    
                    newly_detailed_courses.append(detailed_course)
                    run_completed_crns.add(course.crn)
                    completed_crns.add(course.crn)
                    
                    # Update progress
                    progress_bar.update(task, advance=1)
                    
                    # Save progress periodically using merge approach
                    if (i + 1) % batch_size == 0:
                        self._save_batch_results(
                            base_schedule, newly_detailed_courses, completed_crns, errors
                        )
                        
                    # Rate limiting - be respectful to the server
                    if i < len(remaining_courses) - 1:
                        time.sleep(self.rate_limit)
                        
                except Exception as e:
                    error_msg = f"Failed to get details for {course.crn} ({course.subject} {course.course_number}): {str(e)}"
                    console.print(f"[red]❌ {error_msg}[/red]")
                    errors.append(error_msg)
                    
                    # Continue without details for this course
                    run_completed_crns.add(course.crn)
                    completed_crns.add(course.crn)
                    progress_bar.update(task, advance=1)
        
        # Create final merged schedule
        final_schedule = self.merge_course_details(
            base_schedule, newly_detailed_courses, run_completed_crns, errors
        )
        
        # Save final results using standard filename
        self.save_merged_results(final_schedule)
        
        detailed_count = final_schedule.metadata.get('courses_with_details', 0)
        total_count = len(final_schedule.courses)
        console.print(f"📊 [blue]Results: {detailed_count}/{total_count} courses have detailed information[/blue]")
        
        if errors:
            console.print(f"⚠️  [yellow]{len(errors)} errors occurred during collection[/yellow]")
            
        # Clean up progress file on successful completion
        if self.progress_file.exists():
            self.progress_file.unlink()
            
        return final_schedule
    
    def _save_batch_results(self, base_schedule: ScheduleData, newly_detailed_courses: List[DetailedCourse], 
                           completed_crns: set, errors: List):
        """Save batch results using merge approach.
        
        Args:
            base_schedule: Base schedule to merge into
            newly_detailed_courses: New detailed courses from this batch
            completed_crns: Set of CRNs completed so far
            errors: List of errors encountered
        """
        # Update progress tracking
        progress = {
            'term_code': base_schedule.term_code,
            'completed_crns': list(completed_crns),
            'total_processed': len(completed_crns),
            'last_update': datetime.now(timezone.utc).isoformat() + "Z",
        }
        self.save_progress(progress)
        
        # Merge results and save to main file
        merged_schedule = self.merge_course_details(
            base_schedule, newly_detailed_courses, completed_crns, errors
        )
        
        self.save_merged_results(merged_schedule)
        
        detailed_count = merged_schedule.metadata.get('courses_with_details', 0)
        console.print(f"💾 [dim]Batch saved: {detailed_count} courses with details[/dim]")
    
    def find_latest_schedule(self) -> Optional[str]:
        """Find the latest Rio Hondo basic schedule file (not detailed)."""
        data_dir = Path("data/rio-hondo")
        if not data_dir.exists():
            return None
            
        # Look for basic schedule files (exclude detailed files)
        json_files = list(data_dir.glob("schedule_*.json"))
        basic_files = [f for f in json_files if "detailed" not in f.name]
        
        if not basic_files:
            return None
            
        # Return the most recent basic schedule file
        latest_file = max(basic_files, key=lambda f: f.stat().st_mtime)
        console.print(f"🔍 [blue]Auto-detected basic schedule: {latest_file}[/blue]")
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