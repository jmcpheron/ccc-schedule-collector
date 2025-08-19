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

"""Debug script for Rio Hondo course detail HTML structure analysis."""

import sys
import json
import time
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print
from bs4 import BeautifulSoup

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent))

from collectors.rio_hondo.collector import RioHondoCollector
from collectors.rio_hondo.parser import RioHondoScheduleParser
from models import Course, DetailedCourse, Enrollment

console = Console()


def debug_etec_101():
    """Debug the problematic ETEC 101 course (CRN 78474)."""
    console.print("🧪 [bold cyan]Debugging ETEC 101 HTML Structure[/bold cyan]")
    
    # Create the problematic course
    test_course = Course(
        crn="78474",
        subject="ETEC",
        course_number="101",
        title="Electrician Fundamentals",
        units=3.0,
        instructor="To Be Assigned",
        meeting_times=[],
        location="Technology 118A",
        enrollment=Enrollment(capacity=24, actual=16, remaining=8),
        status="Open",
        section_type="LEC",
        delivery_method="Arranged",
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
        
        # Save raw HTML for analysis
        html_file = Path("debug_etec_101_raw.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        console.print(f"💾 Raw HTML saved to: {html_file}")
        
        # Analyze HTML structure
        analyze_html_structure(response.text)
        
        # Test current parser
        console.print("\n🔍 [bold yellow]Testing current parser...[/bold yellow]")
        detailed_course = parser.parse_course_detail(response.text, test_course)
        display_parsing_results(detailed_course)
        
        # Save parsed result
        json_file = Path("debug_etec_101_parsed.json")
        with open(json_file, 'w') as f:
            json.dump(detailed_course.model_dump(mode='json'), f, indent=2, default=str)
        console.print(f"💾 Parsed details saved to: {json_file}")
        
        return response.text, detailed_course
        
    except Exception as e:
        console.print(f"❌ [red]Error: {str(e)}[/red]")
        raise


def analyze_html_structure(html_content):
    """Analyze the HTML structure to understand the layout."""
    console.print("\n🔬 [bold green]HTML Structure Analysis[/bold green]")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all paragraphs
    paragraphs = soup.find_all('p')
    console.print(f"📄 Found {len(paragraphs)} paragraph elements")
    
    # Analyze each paragraph
    for i, p in enumerate(paragraphs):
        text = p.get_text().strip()
        if text:
            console.print(f"\n[cyan]Paragraph {i + 1}:[/cyan]")
            console.print(f"  Length: {len(text)} characters")
            console.print(f"  Content preview: {text[:100]}...")
            
            # Check for description patterns
            if "Course Description:" in text:
                console.print("  [yellow]⚠️  Contains 'Course Description:'[/yellow]")
            if "This course" in text:
                console.print("  [green]✅ Contains 'This course'[/green]")
            if "Advisory:" in text:
                console.print("  [blue]📋 Contains 'Advisory:'[/blue]")
            if "Prerequisite:" in text:
                console.print("  [blue]📋 Contains 'Prerequisite:'[/blue]")
            if "Transfers to:" in text:
                console.print("  [blue]📋 Contains 'Transfers to:'[/blue]")
            if "Rio Hondo College" in text:
                console.print("  [red]❌ Contains 'Rio Hondo College' (footer contamination)[/red]")
            if "Learning Outcomes" in text:
                console.print("  [red]❌ Contains 'Learning Outcomes' (navigation contamination)[/red]")
    
    # Look for specific structure elements
    console.print("\n🏗️  [bold blue]Structural Elements[/bold blue]")
    
    # Find tables
    tables = soup.find_all('table')
    console.print(f"📊 Found {len(tables)} table elements")
    
    # Find list items
    list_items = soup.find_all('li')
    console.print(f"📝 Found {len(list_items)} list item elements")
    
    # Check for specific course info patterns
    course_info_elements = soup.find_all(string=lambda text: text and any(
        pattern in text for pattern in [
            "Course Description:",
            "Advisory:",
            "Prerequisite:",
            "Transfers to:",
            "This course"
        ]
    ))
    
    console.print(f"🎯 Found {len(course_info_elements)} course info text elements")
    
    # Show footer/navigation contamination
    footer_elements = soup.find_all(string=lambda text: text and any(
        pattern in text for pattern in [
            "Rio Hondo College",
            "Learning Outcomes",
            "Close Window",
            "Important Section Information"
        ]
    ))
    
    if footer_elements:
        console.print(f"[red]🚨 Found {len(footer_elements)} potential contamination elements[/red]")
        for elem in footer_elements[:3]:  # Show first 3
            console.print(f"  - {elem.strip()[:50]}...")


def display_parsing_results(course: DetailedCourse):
    """Display the results of parsing to identify issues."""
    console.print("\n📋 [bold magenta]Current Parser Results[/bold magenta]")
    
    # Check for contamination in key fields
    fields_to_check = {
        'description': course.description,
        'advisory': course.advisory,
        'prerequisites': course.prerequisites,
        'transfers_to': course.transfers_to
    }
    
    contamination_patterns = [
        "Rio Hondo College",
        "Learning Outcomes",
        "Close Window",
        "Important Section Information",
        "View Book",
        "screencaptureui",
        "Course Corequisites: NONE",
        "Section Information as of"
    ]
    
    for field_name, field_value in fields_to_check.items():
        if field_value:
            console.print(f"\n[cyan]{field_name.title()}:[/cyan]")
            console.print(f"  Length: {len(field_value)} characters")
            console.print(f"  Content: {field_value[:200]}...")
            
            # Check for contamination
            contaminated = any(pattern in field_value for pattern in contamination_patterns)
            if contaminated:
                console.print(f"  [red]❌ CONTAMINATED - Contains footer/navigation elements[/red]")
                for pattern in contamination_patterns:
                    if pattern in field_value:
                        console.print(f"    - Contains: '{pattern}'")
            else:
                console.print(f"  [green]✅ Clean[/green]")
        else:
            console.print(f"\n[cyan]{field_name.title()}:[/cyan] [yellow]None/Empty[/yellow]")


def test_improved_parsing(html_content, course):
    """Test improved parsing logic."""
    console.print("\n🔧 [bold cyan]Testing Improved Parsing Logic[/bold cyan]")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try to find the main content area and avoid footer/navigation
    console.print("🎯 Looking for course description paragraph...")
    
    # Look for paragraph containing course description
    desc_paragraph = None
    for p in soup.find_all('p'):
        text = p.get_text()
        if "Course Description:" in text and "This course" in text:
            desc_paragraph = p
            break
    
    if desc_paragraph:
        console.print("✅ Found description paragraph")
        
        # Extract just the description part, stopping at known boundaries
        p_text = desc_paragraph.get_text()
        
        # Find the start of the description
        desc_start = p_text.find("This course")
        if desc_start != -1:
            desc_text = p_text[desc_start:]
            
            # Try different ending patterns
            ending_patterns = [
                r'This course.*?majors\.',
                r'This course.*?students\.',
                r'This course.*?training\.',
                r'This course.*?provided\.',
                r'This course.*?\. View',  # Stop at ". View" 
                r'This course.*?\. Course',  # Stop at ". Course"
            ]
            
            import re
            
            for pattern in ending_patterns:
                match = re.search(pattern, desc_text, re.DOTALL)
                if match:
                    clean_desc = match.group(0)
                    # Remove ". View" or ". Course" endings
                    clean_desc = re.sub(r'\. (View|Course)$', '.', clean_desc)
                    console.print(f"[green]✅ Extracted with pattern: {pattern}[/green]")
                    console.print(f"Length: {len(clean_desc)} characters")
                    console.print(f"Content: {clean_desc}")
                    break
            else:
                console.print("[yellow]⚠️  No ending pattern matched[/yellow]")
    else:
        console.print("[red]❌ Description paragraph not found[/red]")


def main():
    """Main debug function."""
    console.print("🚀 [bold green]Rio Hondo Detail Collection Debug Tool[/bold green]\n")
    
    try:
        html_content, detailed_course = debug_etec_101()
        
        # Test improved parsing approach
        test_improved_parsing(html_content, detailed_course)
        
        console.print("\n✅ [bold green]Debug analysis completed![/bold green]")
        console.print("📁 Check debug_etec_101_raw.html and debug_etec_101_parsed.json for details")
        
    except Exception as e:
        console.print(f"\n❌ [bold red]Debug failed: {str(e)}[/bold red]")
        raise


if __name__ == "__main__":
    main()