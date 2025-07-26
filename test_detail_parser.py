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

"""Test script to fetch and parse course detail pages from Rio Hondo."""

import json
import time
import sys
from pathlib import Path
from typing import Optional, Dict, List, Any
import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from pydantic import BaseModel, Field

console = Console()


class CourseDetails(BaseModel):
    """Additional course details from the popup page."""
    crn: str
    description: Optional[str] = None
    prerequisites: Optional[str] = None
    advisory: Optional[str] = None
    transfers_to: Optional[str] = None
    former_course_number: Optional[str] = None
    critical_dates: Optional[Dict[str, str]] = None
    instructional_method: Optional[str] = None
    section_corequisites: Optional[str] = None
    book_link: Optional[str] = None
    syllabus_link: Optional[str] = None
    seating: Optional[Dict[str, int]] = None  # capacity, taken, available


def fetch_course_details(subject: str, course_number: str, term_code: str, crn: str) -> Optional[str]:
    """Fetch course detail HTML from Rio Hondo."""
    url = f"https://ssb.riohondo.edu:8443/prodssb/pw_pub_sched.p_course_popup"
    params = {
        'vsub': subject,
        'vcrse': course_number,
        'vterm': term_code,
        'vcrn': crn
    }
    
    try:
        console.print(f"[yellow]Fetching details for {subject} {course_number} (CRN: {crn})...[/yellow]")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        console.print(f"[red]Error fetching {crn}: {e}[/red]")
        return None


def parse_course_details(html_content: str, crn: str) -> CourseDetails:
    """Parse course details from HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    details = CourseDetails(crn=crn)
    
    # Extract course description
    desc_text = soup.get_text()
    if "Course Description:" in desc_text:
        desc_start = desc_text.find("Course Description:") + len("Course Description:")
        desc_end = desc_text.find("View Book", desc_start)
        if desc_end == -1:
            desc_end = desc_text.find("Course Corequisites:", desc_start)
        if desc_end != -1:
            description = desc_text[desc_start:desc_end].strip()
            
            # Parse out components
            if "(Formerly" in description:
                former_start = description.find("(Formerly")
                former_end = description.find(")", former_start) + 1
                details.former_course_number = description[former_start:former_end]
                description = description.replace(details.former_course_number, "").strip()
            
            if "Advisory:" in description:
                adv_start = description.find("Advisory:")
                adv_end = description.find("Transfers to:", adv_start) if "Transfers to:" in description else len(description)
                details.advisory = description[adv_start:adv_end].replace("Advisory:", "").strip()
            
            if "Transfers to:" in description:
                trans_start = description.find("Transfers to:")
                trans_end = description.find("This course", trans_start) if "This course" in description else len(description)
                details.transfers_to = description[trans_start:trans_end].replace("Transfers to:", "").strip()
            
            # Clean description to just the main text
            main_desc_start = description.find("This course") if "This course" in description else 0
            details.description = description[main_desc_start:].strip()
    
    # Extract instructional method
    for li in soup.find_all('li'):
        text = li.get_text()
        if "Weekly Instructional Method" in text:
            details.instructional_method = text.strip()
        elif "Section Corequisites:" in text:
            details.section_corequisites = text.replace("Section Corequisites:", "").strip()
    
    # Extract book link
    book_link = soup.find('a', string=lambda x: x and 'View Book' in x)
    if book_link and book_link.get('href'):
        href = book_link['href']
        if "winOpen('" in href:
            start = href.find("winOpen('") + 9
            end = href.find("')", start)
            details.book_link = href[start:end]
    
    # Extract syllabus link
    syllabus_link = soup.find('a', string=lambda x: x and 'Learning Outcomes' in x)
    if syllabus_link and syllabus_link.get('href'):
        details.syllabus_link = syllabus_link['href']
    
    # Extract seating information
    seating_table = None
    for table in soup.find_all('table'):
        if table.find('td', string='Capacity'):
            seating_table = table
            break
    
    if seating_table:
        rows = seating_table.find_all('tr')
        for row in rows:
            cells = row.find_all('td', class_='default3')
            if len(cells) == 3:
                details.seating = {
                    'capacity': int(cells[0].get_text()),
                    'taken': int(cells[1].get_text()),
                    'available': int(cells[2].get_text())
                }
    
    # Extract critical dates
    dates_table = None
    for table in soup.find_all('table'):
        if table.find('td', string=lambda x: x and 'Critical Dates' in x):
            dates_table = table
            break
    
    if dates_table:
        details.critical_dates = {}
        for row in dates_table.find_all('tr'):
            cells = row.find_all('td', class_='default1')
            if len(cells) == 2:
                key = cells[0].get_text().strip().rstrip(':')
                value = cells[1].get_text().strip()
                if key and value and key != 'Term':
                    details.critical_dates[key] = value
    
    return details


def load_sample_courses(data_file: str, count: int = 3) -> List[Dict[str, Any]]:
    """Load sample courses from existing data file."""
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    courses = data['courses']
    
    # Get diverse samples: online, in-person, and lab if possible
    samples = []
    
    # Try to get one online course
    online_courses = [c for c in courses if 'online' in c.get('location', '').lower()]
    if online_courses:
        samples.append(online_courses[0])
    
    # Try to get one in-person course
    in_person_courses = [c for c in courses if c.get('location', '') and 'online' not in c.get('location', '').lower()]
    if in_person_courses:
        samples.append(in_person_courses[0])
    
    # Try to get one lab course
    lab_courses = [c for c in courses if c.get('section_type', '') == 'LAB']
    if lab_courses:
        samples.append(lab_courses[0])
    
    # Fill up to count with any courses
    for course in courses:
        if len(samples) >= count:
            break
        if course not in samples:
            samples.append(course)
    
    return samples[:count]


def display_results(course: Dict[str, Any], details: CourseDetails):
    """Display parsed details in a nice format."""
    table = Table(title=f"Course Details: {course['subject']} {course['course_number']} - {course['title']}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("CRN", details.crn)
    table.add_row("Subject", course['subject'])
    table.add_row("Course", course['course_number'])
    table.add_row("Title", course['title'])
    table.add_row("Instructor", course.get('instructor', 'N/A'))
    
    if details.description:
        table.add_row("Description", details.description[:100] + "..." if len(details.description) > 100 else details.description)
    
    if details.former_course_number:
        table.add_row("Former Number", details.former_course_number)
    
    if details.advisory:
        table.add_row("Advisory", details.advisory)
    
    if details.transfers_to:
        table.add_row("Transfers To", details.transfers_to)
    
    if details.instructional_method:
        table.add_row("Instructional Method", details.instructional_method)
    
    if details.seating:
        table.add_row("Seating", f"{details.seating['taken']}/{details.seating['capacity']} (Available: {details.seating['available']})")
    
    if details.book_link:
        table.add_row("Book Link", "Available")
    
    if details.critical_dates:
        dates_str = "\n".join([f"{k}: {v}" for k, v in list(details.critical_dates.items())[:3]])
        table.add_row("Critical Dates", dates_str + "\n..." if len(details.critical_dates) > 3 else dates_str)
    
    console.print(table)
    console.print()


def main():
    """Main function to test detail parsing."""
    # Find the latest schedule data
    data_dir = Path("data")
    schedule_files = list(data_dir.glob("schedule_*.json"))
    
    if not schedule_files:
        console.print("[red]No schedule data files found in data/ directory[/red]")
        sys.exit(1)
    
    latest_file = max(schedule_files, key=lambda f: f.stat().st_mtime)
    console.print(f"[green]Using schedule data: {latest_file}[/green]\n")
    
    # Load sample courses
    samples = load_sample_courses(str(latest_file))
    
    if not samples:
        console.print("[red]No courses found in schedule data[/red]")
        sys.exit(1)
    
    # Extract term code from the data
    with open(latest_file, 'r') as f:
        data = json.load(f)
    term_code = data.get('term_code', '202570')
    
    console.print(f"[cyan]Testing with {len(samples)} sample courses from term {term_code}[/cyan]\n")
    
    # Process each sample
    all_details = []
    for i, course in enumerate(samples):
        if i > 0:
            console.print("[dim]Waiting 2 seconds between requests...[/dim]")
            time.sleep(2)  # Rate limiting
        
        html = fetch_course_details(
            course['subject'],
            course['course_number'],
            term_code,
            course['crn']
        )
        
        if html:
            details = parse_course_details(html, course['crn'])
            all_details.append({
                'course': course,
                'details': details
            })
            display_results(course, details)
    
    # Save results
    if all_details:
        output_file = Path("data/test/course_details_sample.json")
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'term_code': term_code,
                'samples': [
                    {
                        'course': d['course'],
                        'details': d['details'].model_dump()
                    }
                    for d in all_details
                ]
            }, f, indent=2)
        
        console.print(f"\n[green]Results saved to: {output_file}[/green]")
        console.print(f"[yellow]Note: This is a test implementation. Integration with the main collector is pending.[/yellow]")


if __name__ == "__main__":
    main()