#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "beautifulsoup4",
#   "pydantic>=2.0",
#   "rich"
# ]
# ///

"""Parse manually downloaded Rio Hondo schedule HTML."""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from collectors.rio_hondo.parser import RioHondoScheduleParser
from models import ScheduleData
from utils.storage import ScheduleStorage

console = Console()


def parse_manual_download(html_file: str, save: bool = True):
    """Parse a manually downloaded schedule HTML file.
    
    Args:
        html_file: Path to the HTML file
        save: Whether to save the parsed data
    """
    html_path = Path(html_file)
    
    if not html_path.exists():
        console.print(f"[red]Error: File not found: {html_path}[/red]")
        sys.exit(1)
    
    console.print(f"[cyan]📖 Parsing: {html_path}[/cyan]")
    console.print(f"[dim]File size: {html_path.stat().st_size:,} bytes[/dim]\n")
    
    # Read HTML content
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Initialize parser
    parser = RioHondoScheduleParser()
    
    # Parse the HTML
    try:
        schedule_data = parser.parse_schedule_html(
            html_content,
            term="Fall 2025",
            term_code="202570",
            source_url=f"file://{html_path.absolute()}"
        )
        
        # Add metadata
        schedule_data.college_id = "rio-hondo"
        schedule_data.collector_version = "1.0.0"
        schedule_data.collection_timestamp = datetime.now()
        
        if not schedule_data.metadata:
            schedule_data.metadata = {}
        
        schedule_data.metadata.update({
            'total_courses': len(schedule_data.courses),
            'departments': sorted(list(set(c.subject for c in schedule_data.courses))),
            'source_type': 'manual_download',
            'source_file': html_path.name
        })
        
        # Display results
        table = Table(title="Parse Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Total Courses", str(len(schedule_data.courses)))
        table.add_row("Departments", str(len(schedule_data.metadata['departments'])))
        table.add_row("Term", f"{schedule_data.term} ({schedule_data.term_code})")
        
        # Count by delivery method
        delivery_methods = {}
        for course in schedule_data.courses:
            method = course.delivery_method or "Unknown"
            delivery_methods[method] = delivery_methods.get(method, 0) + 1
        
        for method, count in sorted(delivery_methods.items()):
            table.add_row(f"  {method}", str(count))
        
        console.print(table)
        
        # Show sample courses
        console.print("\n[yellow]Sample Courses:[/yellow]")
        for course in schedule_data.courses[:3]:
            console.print(f"  • {course.crn}: {course.subject} {course.course_number} - {course.title}")
            console.print(f"    Instructor: {course.instructor}, Location: {course.location}")
        
        # Save if requested
        if save:
            storage = ScheduleStorage(data_dir="data")
            output_path = storage.save_schedule(
                schedule_data,
                filename_pattern="schedule_basic_{term_code}_{timestamp}.json"
            )
            console.print(f"\n[green]✓ Data saved to: {output_path}[/green]")
            
            # Also save uncompressed for easy inspection
            basic_path = Path("data") / f"schedule_basic_{schedule_data.term_code}_latest.json"
            with open(basic_path, 'w') as f:
                json.dump(schedule_data.model_dump(mode='json'), f, indent=2, default=str)
            console.print(f"[green]✓ Latest symlink: {basic_path}[/green]")
            
            return output_path
        
    except Exception as e:
        console.print(f"[red]Error parsing HTML: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        console.print("[red]Usage: ./parse_manual_download.py <html_file> [--no-save][/red]")
        console.print("\nExample:")
        console.print("  ./parse_manual_download.py data/raw/2025-01-26_rio_hondo_fall_2025.html")
        sys.exit(1)
    
    html_file = sys.argv[1]
    save = "--no-save" not in sys.argv
    
    parse_manual_download(html_file, save)


if __name__ == "__main__":
    main()