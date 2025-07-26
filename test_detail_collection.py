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

"""Test script for the integrated detail collection."""

import json
import sys
import time
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from collectors.rio_hondo.collector import RioHondoCollector
from utils.storage import ScheduleStorage

console = Console()


def test_detail_collection():
    """Test collecting course data with details for small departments."""
    console.print("[cyan]Testing Rio Hondo collector with detail collection enabled[/cyan]\n")
    
    # Initialize collector with test config
    config_path = Path("collectors/rio_hondo/config_test.json")
    collector = RioHondoCollector(config_path)
    
    # Display configuration
    console.print("[yellow]Configuration:[/yellow]")
    console.print(f"  Departments: {collector.config['departments']}")
    console.print(f"  Collect Details: {collector.config.get('collect_details', False)}")
    console.print(f"  Detail Delay: {collector.config.get('detail_delay', 1)} seconds")
    console.print(f"  Detail Batch Size: {collector.config.get('detail_batch_size', 50)}\n")
    
    # Collect data with details
    start_time = time.time()
    console.print("[green]Starting collection with details...[/green]")
    
    try:
        schedule_data = collector.collect_all_departments_with_details()
        elapsed_time = time.time() - start_time
        
        console.print(f"\n[green]✓ Collection completed in {elapsed_time:.1f} seconds[/green]")
        
        # Display summary
        table = Table(title="Collection Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Total Courses", str(len(schedule_data.courses)))
        table.add_row("Departments", ", ".join(schedule_data.metadata.get('departments', [])))
        table.add_row("Details Collected", str(schedule_data.metadata.get('details_collected', False)))
        table.add_row("Term", f"{schedule_data.term} ({schedule_data.term_code})")
        
        # Count courses with details
        detailed_count = 0
        for course in schedule_data.courses:
            if hasattr(course, 'description') and course.description:
                detailed_count += 1
        
        table.add_row("Courses with Details", f"{detailed_count}/{len(schedule_data.courses)}")
        
        console.print(table)
        
        # Show sample detailed course
        if detailed_count > 0:
            console.print("\n[yellow]Sample Detailed Course:[/yellow]")
            for course in schedule_data.courses:
                if hasattr(course, 'description') and course.description:
                    detail_table = Table()
                    detail_table.add_column("Field", style="cyan")
                    detail_table.add_column("Value", style="white")
                    
                    detail_table.add_row("Course", f"{course.subject} {course.course_number}")
                    detail_table.add_row("Title", course.title)
                    detail_table.add_row("CRN", course.crn)
                    
                    if course.description:
                        desc = course.description[:100] + "..." if len(course.description) > 100 else course.description
                        detail_table.add_row("Description", desc)
                    
                    if hasattr(course, 'advisory') and course.advisory:
                        detail_table.add_row("Advisory", course.advisory)
                    
                    if hasattr(course, 'transfers_to') and course.transfers_to:
                        detail_table.add_row("Transfers To", course.transfers_to)
                    
                    if hasattr(course, 'critical_dates') and course.critical_dates:
                        dates = list(course.critical_dates.items())[:2]
                        for key, value in dates:
                            detail_table.add_row(key, value)
                    
                    console.print(detail_table)
                    break
        
        # Save the data
        storage = ScheduleStorage(data_dir="data/test")
        output_path = storage.save_schedule(
            schedule_data,
            filename_pattern="schedule_detailed_{term_code}_{timestamp}.json"
        )
        console.print(f"\n[green]✓ Data saved to: {output_path}[/green]")
        
        # Verify the saved data
        with open(output_path, 'r') as f:
            saved_data = json.load(f)
        
        console.print(f"[dim]File size: {Path(output_path).stat().st_size / 1024:.1f} KB[/dim]")
        
        # Show errors if any
        if schedule_data.metadata.get('collection_errors'):
            console.print("\n[red]Collection Errors:[/red]")
            for error in schedule_data.metadata['collection_errors']:
                console.print(f"  - {error}")
        
    except Exception as e:
        console.print(f"\n[red]Error during collection: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_detail_collection()