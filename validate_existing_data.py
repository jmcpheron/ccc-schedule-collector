#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pydantic>=2.0",
#   "rich"
# ]
# ///

"""Validate existing detailed course data to identify contamination issues."""

import sys
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, track
from typing import List, Dict, Tuple

console = Console()


def validate_course_data(course_data: dict, course_index: int) -> List[Tuple[str, str]]:
    """Validate a single course and return list of contamination issues."""
    issues = []
    
    # Contamination patterns to detect
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
    
    # Fields to check
    fields_to_check = [
        ('description', course_data.get('description')),
        ('advisory', course_data.get('advisory')),
        ('prerequisites', course_data.get('prerequisites')),
        ('transfers_to', course_data.get('transfers_to')),
    ]
    
    for field_name, field_value in fields_to_check:
        if field_value:
            # Check for contamination patterns
            for pattern in contamination_patterns:
                if pattern in field_value:
                    issues.append((field_name, f"contamination: {pattern}"))
            
            # Check for suspiciously long descriptions
            if field_name == 'description' and len(field_value) > 1000:
                issues.append((field_name, f"excessive_length: {len(field_value)} chars"))
            
            # Check for description content in other fields
            if field_name in ['advisory', 'prerequisites', 'transfers_to']:
                if 'This course' in field_value or 'This introductory' in field_value:
                    issues.append((field_name, "description_mixed"))
    
    return issues


def validate_schedule_file(file_path: Path) -> Dict:
    """Validate a single schedule file and return results."""
    console.print(f"📖 [cyan]Validating: {file_path.name}[/cyan]")
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return {
            'file': file_path.name,
            'error': f"Failed to load: {e}",
            'total_courses': 0,
            'contaminated_courses': 0,
            'issues': []
        }
    
    courses = data.get('courses', [])
    total_courses = len(courses)
    contaminated_courses = 0
    all_issues = []
    
    for i, course in enumerate(courses):
        issues = validate_course_data(course, i)
        if issues:
            contaminated_courses += 1
            crn = course.get('crn', 'Unknown')
            subject = course.get('subject', 'Unknown')
            course_number = course.get('course_number', 'Unknown')
            
            all_issues.append({
                'course_id': f"{subject} {course_number} (CRN: {crn})",
                'issues': issues
            })
    
    return {
        'file': file_path.name,
        'total_courses': total_courses,
        'contaminated_courses': contaminated_courses,
        'contamination_rate': contaminated_courses / total_courses if total_courses > 0 else 0,
        'issues': all_issues
    }


def main():
    """Main validation function."""
    console.print("🔍 [bold green]Validating Existing Rio Hondo Detailed Data[/bold green]\n")
    
    # Find detailed schedule files
    data_dir = Path("data/rio-hondo")
    if not data_dir.exists():
        console.print("❌ [red]data/rio-hondo directory not found[/red]")
        return
    
    detailed_files = list(data_dir.glob("schedule_detailed_*.json"))
    if not detailed_files:
        console.print("⚠️  [yellow]No detailed schedule files found[/yellow]")
        return
    
    console.print(f"📁 Found {len(detailed_files)} detailed schedule files")
    
    # Validate each file
    results = []
    for file_path in track(detailed_files, description="Validating files..."):
        result = validate_schedule_file(file_path)
        results.append(result)
    
    # Display summary
    console.print("\n📊 [bold blue]Validation Summary[/bold blue]")
    
    summary_table = Table(title="File Validation Results", show_header=True, header_style="bold magenta")
    summary_table.add_column("File", style="cyan")
    summary_table.add_column("Total Courses", style="green", justify="right")
    summary_table.add_column("Contaminated", style="red", justify="right")
    summary_table.add_column("Rate", style="yellow", justify="right")
    
    total_courses_all = 0
    total_contaminated_all = 0
    
    for result in results:
        if 'error' in result:
            summary_table.add_row(
                result['file'],
                "ERROR",
                result.get('error', ''),
                ""
            )
        else:
            total_courses_all += result['total_courses']
            total_contaminated_all += result['contaminated_courses']
            
            rate_str = f"{result['contamination_rate']:.1%}"
            summary_table.add_row(
                result['file'],
                str(result['total_courses']),
                str(result['contaminated_courses']),
                rate_str
            )
    
    console.print(summary_table)
    
    # Overall statistics
    if total_courses_all > 0:
        overall_rate = total_contaminated_all / total_courses_all
        console.print(f"\n📈 [bold yellow]Overall Statistics[/bold yellow]")
        console.print(f"Total Courses: {total_courses_all}")
        console.print(f"Contaminated Courses: {total_contaminated_all}")
        console.print(f"Overall Contamination Rate: {overall_rate:.1%}")
    
    # Show detailed issues for the worst files
    console.print(f"\n🔍 [bold red]Detailed Issues (Top 10 Most Contaminated Courses)[/bold red]")
    
    all_course_issues = []
    for result in results:
        if not result.get('error'):
            for issue in result.get('issues', []):
                all_course_issues.append({
                    'file': result['file'],
                    'course': issue['course_id'],
                    'issue_count': len(issue['issues']),
                    'issues': issue['issues']
                })
    
    # Sort by issue count and show top 10
    all_course_issues.sort(key=lambda x: x['issue_count'], reverse=True)
    
    if all_course_issues:
        issues_table = Table(title="Most Contaminated Courses", show_header=True, header_style="bold red")
        issues_table.add_column("File", style="dim")
        issues_table.add_column("Course", style="cyan")
        issues_table.add_column("Issues", style="red")
        issues_table.add_column("Details", style="white")
        
        for issue_data in all_course_issues[:10]:
            issue_details = []
            for field, issue_type in issue_data['issues']:
                issue_details.append(f"{field}: {issue_type}")
            
            issues_table.add_row(
                issue_data['file'],
                issue_data['course'],
                str(issue_data['issue_count']),
                "\n".join(issue_details[:3]) + ("..." if len(issue_details) > 3 else "")
            )
        
        console.print(issues_table)
    
    # Generate a summary report
    report_file = Path("data/validation_report.json")
    with open(report_file, 'w') as f:
        json.dump({
            'validation_timestamp': '2025-08-19T04:30:00Z',
            'summary': {
                'total_files': len(results),
                'total_courses': total_courses_all,
                'contaminated_courses': total_contaminated_all,
                'contamination_rate': overall_rate if total_courses_all > 0 else 0
            },
            'file_results': results
        }, f, indent=2)
    
    console.print(f"\n💾 [green]Detailed validation report saved to: {report_file}[/green]")
    
    if total_contaminated_all > 0:
        console.print(f"\n⚠️  [bold yellow]Found contamination in {total_contaminated_all} courses across {len(results)} files[/bold yellow]")
        console.print("🔧 [blue]Re-run detail collection with the updated parser to fix these issues[/blue]")
    else:
        console.print(f"\n✅ [bold green]No contamination detected in any detailed course data![/bold green]")


if __name__ == "__main__":
    main()