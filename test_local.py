#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "beautifulsoup4",
#   "pydantic>=2.0",
#   "pyyaml",
#   "click",
# ]
# ///
"""Test the collector locally with saved HTML file."""

import sys
from pathlib import Path
import json
import click
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from models import ScheduleData
from collectors.rio_hondo.parser import RioHondoScheduleParser
from utils.storage import ScheduleStorage


@click.command()
@click.option('--html-file', default='tests/fixtures/rio-hondo-fall-2025.html', help='Path to HTML file')
@click.option('--save', is_flag=True, help='Save parsed data to data directory')
@click.option('--debug', is_flag=True, help='Show debug information')
def test_parser(html_file: str, save: bool, debug: bool):
    """Test the parser with a local HTML file."""
    
    print(f"🔍 Testing parser with {html_file}")
    
    # Check if file exists
    if not Path(html_file).exists():
        print(f"❌ File not found: {html_file}")
        print("Make sure you have the HTML file in the project root")
        return
    
    # Read HTML content
    print(f"📖 Reading HTML file...")
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    print(f"📄 File size: {len(html_content):,} bytes")
    
    # Initialize parser
    parser = RioHondoScheduleParser()
    
    # Parse the HTML
    print(f"🔧 Parsing HTML...")
    try:
        schedule_data = parser.parse_schedule_html(
            html_content,
            term="Fall 2025",
            term_code="202570",
            source_url=f"file://{Path(html_file).absolute()}"
        )
        
        print(f"✅ Parsing successful!")
        print(f"\n📊 Results:")
        print(f"  - Total courses: {len(schedule_data.courses)}")
        
        # Get departments from metadata
        departments = schedule_data.metadata.get('departments', []) if schedule_data.metadata else []
        print(f"  - Departments: {len(departments)}")
        print(f"  - Department list: {', '.join(departments[:10])}")
        if len(departments) > 10:
            print(f"    ... and {len(departments) - 10} more")
        
        # Show sample courses
        print(f"\n📚 Sample courses:")
        for course in schedule_data.courses[:5]:
            meeting_str = ', '.join([f"{mt.days} {mt.start_time}-{mt.end_time}" 
                                   for mt in course.meeting_times if not mt.is_arranged])
            if not meeting_str:
                meeting_str = "ARR"
            
            print(f"  - {course.crn}: {course.subject} {course.course_number} - {course.title}")
            print(f"    Instructor: {course.instructor}")
            print(f"    Time: {meeting_str}, Location: {course.location}")
            print(f"    Enrollment: {course.enrollment.actual}/{course.enrollment.capacity}")
            print()
        
        if debug:
            # Show more detailed information
            print("\n🔍 Debug Information:")
            print(f"  - Courses with no instructor: {sum(1 for c in schedule_data.courses if c.instructor == 'TBA' or not c.instructor)}")
            print(f"  - Online courses: {sum(1 for c in schedule_data.courses if 'online' in c.location.lower())}")
            print(f"  - Zero textbook cost: {sum(1 for c in schedule_data.courses if c.zero_textbook_cost)}")
            print(f"  - Courses with arranged times: {sum(1 for c in schedule_data.courses if any(mt.is_arranged for mt in c.meeting_times))}")
        
        if save:
            # Save to data directory
            storage = ScheduleStorage()
            filepath = storage.save_schedule(schedule_data)
            print(f"\n💾 Saved to: {filepath}")
            
            # Also save a pretty-printed sample
            sample_path = Path("data/sample_parsed_data.json")
            sample_data = {
                "metadata": {
                    "term": schedule_data.term,
                    "term_code": schedule_data.term_code,
                    "total_courses": len(schedule_data.courses),
                    "departments": departments,
                    "collection_timestamp": schedule_data.collection_timestamp.isoformat(),
                    "college_id": schedule_data.college_id,
                    "collector_version": schedule_data.collector_version
                },
                "sample_courses": [c.model_dump() for c in schedule_data.courses[:10]]
            }
            with open(sample_path, 'w') as f:
                json.dump(sample_data, f, indent=2)
            print(f"📝 Sample data saved to: {sample_path}")
        
    except Exception as e:
        print(f"❌ Error parsing HTML: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return
    
    print("\n✨ Test complete!")


if __name__ == "__main__":
    test_parser()