#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pydantic>=2.0",
#   "rich"
# ]
# ///

"""Validate a single detailed course data file."""

import sys
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

def validate_single_file(file_path):
    """Validate a single schedule file."""
    console.print(f"🔍 [bold green]Validating: {file_path}[/bold green]\n")
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    courses = data.get('courses', [])
    total_courses = len(courses)
    contaminated_courses = 0
    
    contamination_patterns = [
        "Rio Hondo College",
        "Learning Outcomes", 
        "Close Window",
        "View Book",
        "Important Section Information",
        "Course Corequisites: NONE",
        "Section Information as of",
        "screencaptureui",
        "[ Close Window ]",
        "winOpen(",
        "JavaScript:",
    ]
    
    contaminated_list = []
    
    for course in courses:
        issues = []
        
        fields_to_check = [
            ('description', course.get('description')),
            ('advisory', course.get('advisory')),
            ('prerequisites', course.get('prerequisites')),
            ('transfers_to', course.get('transfers_to')),
        ]
        
        for field_name, field_value in fields_to_check:
            if field_value:
                for pattern in contamination_patterns:
                    if pattern in field_value:
                        issues.append(f"{field_name}: {pattern}")
        
        if issues:
            contaminated_courses += 1
            contaminated_list.append({
                'crn': course.get('crn'),
                'subject': course.get('subject'),
                'course_number': course.get('course_number'),
                'title': course.get('title'),
                'issues': issues
            })
    
    # Display results
    console.print(f"📊 [bold blue]Validation Results[/bold blue]")
    console.print(f"Total Courses: {total_courses}")
    console.print(f"Clean Courses: {total_courses - contaminated_courses} ({(total_courses - contaminated_courses) / total_courses * 100:.1f}%)")
    console.print(f"Contaminated: {contaminated_courses} ({contaminated_courses / total_courses * 100:.1f}%)")
    
    if contaminated_list:
        console.print(f"\n🚨 [bold red]Contaminated Courses:[/bold red]")
        
        table = Table(show_header=True, header_style="bold red")
        table.add_column("Course", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Issues", style="red")
        
        for course in contaminated_list:
            table.add_row(
                f"{course['subject']} {course['course_number']} ({course['crn']})",
                course['title'][:50] + "..." if len(course['title']) > 50 else course['title'],
                "\n".join(course['issues'][:3]) + ("..." if len(course['issues']) > 3 else "")
            )
        
        console.print(table)
    else:
        console.print(f"\n✅ [bold green]All courses are clean![/bold green]")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        console.print("Usage: python validate_single_file.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    validate_single_file(file_path)