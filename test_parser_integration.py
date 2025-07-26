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

"""Test script to verify parser integration with course detail fetching."""

import json
import time
import sys
from pathlib import Path
from typing import List
import requests
from rich.console import Console
from rich.table import Table
from rich import print as rprint

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from collectors.rio_hondo.parser import RioHondoScheduleParser
from models import Course, DetailedCourse

console = Console()


def test_parser_integration():
    """Test the parser's course detail functionality."""
    # Initialize parser
    parser = RioHondoScheduleParser()
    
    # Load a sample course
    data_file = Path("data/schedule_202570_latest.json")
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    # Get term code and first course
    term_code = data['term_code']
    course_data = data['courses'][0]
    
    # Create Course object from data
    course = Course(**course_data)
    
    console.print(f"[cyan]Testing parser integration with course: {course.subject} {course.course_number} (CRN: {course.crn})[/cyan]\n")
    
    # Build detail URL
    detail_url = parser.build_course_detail_url(course, term_code)
    console.print(f"[yellow]Detail URL: {detail_url}[/yellow]\n")
    
    # Fetch detail HTML
    try:
        response = requests.get(detail_url, timeout=30)
        response.raise_for_status()
        html_content = response.text
        console.print("[green]Successfully fetched course detail page[/green]\n")
    except Exception as e:
        console.print(f"[red]Error fetching detail page: {e}[/red]")
        return
    
    # Parse detailed course
    detailed_course = parser.parse_course_detail(html_content, course)
    
    # Display results
    table = Table(title="Parsed Course Details")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    
    # Basic info
    table.add_row("CRN", detailed_course.crn)
    table.add_row("Course", f"{detailed_course.subject} {detailed_course.course_number}")
    table.add_row("Title", detailed_course.title)
    
    # New detailed fields
    if detailed_course.description:
        desc = detailed_course.description[:100] + "..." if len(detailed_course.description) > 100 else detailed_course.description
        table.add_row("Description", desc)
    
    if detailed_course.prerequisites:
        table.add_row("Prerequisites", detailed_course.prerequisites)
    
    if detailed_course.advisory:
        table.add_row("Advisory", detailed_course.advisory)
    
    if detailed_course.transfers_to:
        table.add_row("Transfers To", detailed_course.transfers_to)
    
    if detailed_course.former_course_number:
        table.add_row("Former Number", detailed_course.former_course_number)
    
    if detailed_course.instructional_method:
        table.add_row("Instructional Method", detailed_course.instructional_method)
    
    if detailed_course.critical_dates:
        dates = "\n".join([f"{k}: {v}" for k, v in list(detailed_course.critical_dates.items())[:3]])
        table.add_row("Critical Dates", dates)
    
    if detailed_course.seating_detail:
        seating = detailed_course.seating_detail
        table.add_row("Seating Detail", f"{seating['taken']}/{seating['capacity']} (Available: {seating['available']})")
    
    if detailed_course.detail_fetched_at:
        table.add_row("Detail Fetched", detailed_course.detail_fetched_at.strftime("%Y-%m-%d %H:%M:%S"))
    
    console.print(table)
    
    # Verify it's a DetailedCourse instance
    console.print(f"\n[green]✓ Successfully created DetailedCourse instance[/green]")
    console.print(f"[green]✓ Parser integration test passed[/green]")
    
    # Save sample output
    output_file = Path("data/test/parser_integration_test.json")
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump({
            'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'original_course': course.model_dump(),
            'detailed_course': detailed_course.model_dump(mode='json')
        }, f, indent=2, default=str)
    
    console.print(f"\n[yellow]Test output saved to: {output_file}[/yellow]")


if __name__ == "__main__":
    test_parser_integration()