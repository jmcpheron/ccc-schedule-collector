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

"""Test script for Rio Hondo course detail collection."""

import sys
import json
import time
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent))

from collectors.rio_hondo.collector import RioHondoCollector
from collectors.rio_hondo.parser import RioHondoScheduleParser
from models import Course, DetailedCourse, Enrollment

console = Console()


def test_single_course_detail():
    """Test fetching and parsing a single course detail page."""
    console.print("🧪 [bold cyan]Testing single course detail collection[/bold cyan]")
    
    # Test with the example from user: ACCT 101, CRN 71278, Fall 2025 (202570)
    test_course = Course(
        crn="71278",
        subject="ACCT",
        course_number="101",
        title="Financial Accounting",
        units=3.0,
        instructor="Edward Jimenez",
        meeting_times=[],
        location="Online ASYNC",
        enrollment=Enrollment(capacity=45, actual=11, remaining=34),
        status="Open",
        section_type="LEC",
        delivery_method="Online ASYNC",
        weeks=16
    )
    
    term_code = "202570"
    
    # Initialize collector and parser
    collector = RioHondoCollector()
    parser = RioHondoScheduleParser()
    
    try:
        # Build detail URL
        detail_url = parser.build_course_detail_url(test_course, term_code)
        console.print(f"📍 Detail URL: {detail_url}")
        
        # Fetch detail page
        console.print("📥 Fetching detail page...")
        response = collector.session.get(
            detail_url,
            timeout=collector.config['http_config']['timeout'],
            verify=collector.config['http_config']['verify_ssl']
        )
        response.raise_for_status()
        
        # Save raw HTML for debugging
        html_file = Path("debug_detail_page.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        console.print(f"💾 Raw HTML saved to: {html_file}")
        
        # Parse details
        console.print("🔍 Parsing course details...")
        detailed_course = parser.parse_course_detail(response.text, test_course)
        
        # Display results
        display_course_details(detailed_course)
        
        # Save parsed result as JSON
        json_file = Path("debug_detailed_course.json")
        with open(json_file, 'w') as f:
            json.dump(detailed_course.model_dump(mode='json'), f, indent=2, default=str)
        console.print(f"💾 Parsed details saved to: {json_file}")
        
        return detailed_course
        
    except Exception as e:
        console.print(f"❌ [red]Error: {str(e)}[/red]")
        raise


def display_course_details(course: DetailedCourse):
    """Display course details in a nice table format."""
    
    # Main course info table
    main_table = Table(title="Course Information", show_header=True, header_style="bold magenta")
    main_table.add_column("Field", style="cyan")
    main_table.add_column("Value", style="white")
    
    main_table.add_row("CRN", course.crn)
    main_table.add_row("Course", f"{course.subject} {course.course_number}")
    main_table.add_row("Title", course.title)
    main_table.add_row("Units", str(course.units))
    main_table.add_row("Instructor", course.instructor or "TBA")
    
    if course.description:
        main_table.add_row("Description", course.description[:100] + "..." if len(course.description) > 100 else course.description)
    
    console.print(main_table)
    
    # Academic requirements table
    if any([course.prerequisites, course.advisory, course.transfers_to]):
        req_table = Table(title="Academic Requirements", show_header=True, header_style="bold green")
        req_table.add_column("Type", style="cyan")
        req_table.add_column("Requirement", style="white")
        
        if course.prerequisites:
            req_table.add_row("Prerequisites", course.prerequisites)
        if course.advisory:
            req_table.add_row("Advisory", course.advisory)
        if course.transfers_to:
            req_table.add_row("Transfers to", course.transfers_to)
            
        console.print(req_table)
    
    # Additional details table
    details_table = Table(title="Additional Details", show_header=True, header_style="bold yellow")
    details_table.add_column("Field", style="cyan")
    details_table.add_column("Value", style="white")
    
    if course.instructional_method:
        details_table.add_row("Instructional Method", course.instructional_method)
    if course.former_course_number:
        details_table.add_row("Former Number", course.former_course_number)
    if course.section_corequisites:
        details_table.add_row("Section Corequisites", course.section_corequisites)
    if course.syllabus_link:
        details_table.add_row("Syllabus Link", course.syllabus_link)
    if course.detail_fetched_at:
        details_table.add_row("Detail Fetched", str(course.detail_fetched_at))
    
    if details_table.rows:
        console.print(details_table)
    
    # Seating details
    if course.seating_detail:
        seat_table = Table(title="Seating Information", show_header=True, header_style="bold blue")
        seat_table.add_column("Capacity", style="green")
        seat_table.add_column("Taken", style="red")
        seat_table.add_column("Available", style="cyan")
        
        seat_table.add_row(
            str(course.seating_detail.get('capacity', 'N/A')),
            str(course.seating_detail.get('taken', 'N/A')),
            str(course.seating_detail.get('available', 'N/A'))
        )
        console.print(seat_table)
    
    # Critical dates
    if course.critical_dates:
        dates_table = Table(title="Critical Dates", show_header=True, header_style="bold red")
        dates_table.add_column("Event", style="cyan")
        dates_table.add_column("Date", style="white")
        
        for event, date in course.critical_dates.items():
            dates_table.add_row(event, date)
        
        console.print(dates_table)


def test_url_construction():
    """Test the URL construction for different course examples."""
    console.print("\n🔗 [bold cyan]Testing URL construction[/bold cyan]")
    
    parser = RioHondoScheduleParser()
    term_code = "202570"
    
    test_courses = [
        {"subject": "ACCT", "course_number": "101", "crn": "71278"},
        {"subject": "MATH", "course_number": "150", "crn": "12345"},
        {"subject": "ENGL", "course_number": "101", "crn": "54321"},
    ]
    
    for course_data in test_courses:
        course = Course(
            crn=course_data["crn"],
            subject=course_data["subject"],
            course_number=course_data["course_number"],
            title="Test Course",
            units=3.0,
            instructor="Test Instructor",
            meeting_times=[],
            location="TBA",
            enrollment=Enrollment(capacity=30, actual=15, remaining=15),
            status="Open",
            section_type="LEC",
            delivery_method="In-Person",
            weeks=16
        )
        
        url = parser.build_course_detail_url(course, term_code)
        console.print(f"  {course.subject} {course.course_number} (CRN {course.crn}): {url}")


def test_with_existing_schedule():
    """Test with courses from an existing schedule file if available."""
    console.print("\n📚 [bold cyan]Testing with existing schedule data[/bold cyan]")
    
    # Look for recent schedule files
    data_dir = Path("data/rio-hondo")
    if data_dir.exists():
        json_files = list(data_dir.glob("schedule_*.json"))
        if json_files:
            # Use most recent file
            latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
            console.print(f"📖 Using schedule file: {latest_file}")
            
            with open(latest_file, 'r') as f:
                schedule_data = json.load(f)
            
            courses = [Course(**course_data) for course_data in schedule_data['courses'][:3]]  # Test first 3
            console.print(f"🎯 Testing with {len(courses)} courses from schedule")
            
            collector = RioHondoCollector()
            parser = RioHondoScheduleParser()
            
            for i, course in enumerate(courses):
                console.print(f"\n📋 Course {i+1}: {course.subject} {course.course_number} ({course.crn})")
                
                try:
                    url = parser.build_course_detail_url(course, schedule_data['term_code'])
                    console.print(f"   URL: {url}")
                    
                    # Test rate limiting
                    if i > 0:
                        console.print("   ⏳ Rate limiting...")
                        time.sleep(1.5)
                    
                except Exception as e:
                    console.print(f"   ❌ Error with course {course.crn}: {e}")
        else:
            console.print("⚠️  No schedule files found in data/rio-hondo/")
    else:
        console.print("⚠️  data/rio-hondo/ directory not found")


def main():
    """Main test function."""
    console.print("🚀 [bold green]Rio Hondo Course Detail Collection Test[/bold green]\n")
    
    try:
        # Test URL construction
        test_url_construction()
        
        # Test single course detail
        detailed_course = test_single_course_detail()
        
        # Test with existing schedule if available
        test_with_existing_schedule()
        
        console.print("\n✅ [bold green]All tests completed successfully![/bold green]")
        
    except Exception as e:
        console.print(f"\n❌ [bold red]Test failed: {str(e)}[/bold red]")
        raise


if __name__ == "__main__":
    main()