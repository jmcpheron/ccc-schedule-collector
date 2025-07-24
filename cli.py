#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "click",
#   "pydantic>=2.0",
#   "tabulate",
#   "pandas",
# ]
# ///
"""CLI tools for analyzing collected schedule data."""

import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from collections import Counter, defaultdict

import click
import pandas as pd
from tabulate import tabulate

from models import ScheduleData, Course
from utils.storage import ScheduleStorage


@click.group()
@click.pass_context
def cli(ctx):
    """Rio Hondo College Schedule Data Analysis Tools."""
    ctx.ensure_object(dict)
    ctx.obj['storage'] = ScheduleStorage()


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--subject', '-s', help='Filter by subject code')
@click.option('--instructor', '-i', help='Filter by instructor name')
@click.option('--crn', '-c', help='Filter by CRN')
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'csv']), default='table')
@click.pass_context
def info(ctx, file_path: str, subject: Optional[str], instructor: Optional[str], 
         crn: Optional[str], format: str):
    """Display information about courses in a schedule file."""
    storage = ctx.obj['storage']
    
    # Load schedule data
    schedule_data = storage.load_schedule(file_path)
    courses = schedule_data.courses
    
    # Apply filters
    if subject:
        courses = [c for c in courses if c.subject.upper() == subject.upper()]
    if instructor:
        courses = [c for c in courses if instructor.lower() in c.instructor.lower()]
    if crn:
        courses = [c for c in courses if c.crn == crn]
    
    if not courses:
        click.echo("No courses found matching criteria.")
        return
    
    # Format output
    if format == 'json':
        data = [c.model_dump() for c in courses]
        click.echo(json.dumps(data, indent=2, default=str))
    
    elif format == 'csv':
        # Convert to CSV
        rows = []
        for c in courses:
            meeting_str = ', '.join([f"{mt.days} {mt.start_time}-{mt.end_time}" 
                                   for mt in c.meeting_times if not mt.is_arranged])
            rows.append({
                'CRN': c.crn,
                'Subject': c.subject,
                'Number': c.course_number,
                'Title': c.title,
                'Units': c.units,
                'Instructor': c.instructor,
                'Meeting Times': meeting_str,
                'Location': c.location,
                'Enrollment': f"{c.enrollment.actual}/{c.enrollment.capacity}",
                'Status': c.status
            })
        
        df = pd.DataFrame(rows)
        click.echo(df.to_csv(index=False))
    
    else:  # table
        # Create table data
        headers = ['CRN', 'Course', 'Title', 'Instructor', 'Time', 'Location', 'Enrollment']
        rows = []
        
        for c in courses:
            meeting_str = ', '.join([f"{mt.days} {mt.start_time}-{mt.end_time}" 
                                   for mt in c.meeting_times if not mt.is_arranged])
            if not meeting_str:
                meeting_str = "ARR"
                
            rows.append([
                c.crn,
                f"{c.subject} {c.course_number}",
                c.title[:30] + "..." if len(c.title) > 30 else c.title,
                c.instructor[:20] + "..." if len(c.instructor) > 20 else c.instructor,
                meeting_str,
                c.location,
                f"{c.enrollment.actual}/{c.enrollment.capacity}"
            ])
        
        click.echo(f"\nSchedule: {schedule_data.term} (collected {schedule_data.collection_timestamp})")
        click.echo(f"Showing {len(courses)} courses\n")
        click.echo(tabulate(rows, headers=headers, tablefmt='grid'))


@cli.command()
@click.argument('file_paths', nargs=-1, type=click.Path(exists=True), required=True)
@click.pass_context
def validate(ctx, file_paths: tuple):
    """Validate schedule data files for completeness and quality."""
    storage = ctx.obj['storage']
    
    for file_path in file_paths:
        click.echo(f"\nValidating {file_path}...")
        
        try:
            schedule_data = storage.load_schedule(file_path)
            
            # Validation checks
            issues = []
            warnings = []
            
            # Check for courses without instructors
            no_instructor = [c for c in schedule_data.courses if not c.instructor or c.instructor == "TBA"]
            if no_instructor:
                warnings.append(f"{len(no_instructor)} courses without assigned instructors")
            
            # Check for courses without meeting times
            no_times = [c for c in schedule_data.courses if not c.meeting_times or 
                       all(mt.is_arranged for mt in c.meeting_times)]
            if no_times:
                warnings.append(f"{len(no_times)} courses with arranged/TBA meeting times")
            
            # Check for overenrolled courses
            overenrolled = [c for c in schedule_data.courses if c.enrollment.actual > c.enrollment.capacity]
            if overenrolled:
                issues.append(f"{len(overenrolled)} courses are overenrolled")
            
            # Check for zero capacity courses
            zero_cap = [c for c in schedule_data.courses if c.enrollment.capacity == 0]
            if zero_cap:
                issues.append(f"{len(zero_cap)} courses have zero capacity")
            
            # Check for missing essential fields
            missing_fields = []
            for c in schedule_data.courses:
                if not c.crn:
                    missing_fields.append("CRN")
                if not c.title:
                    missing_fields.append("title")
                if not c.subject:
                    missing_fields.append("subject")
            
            if missing_fields:
                issues.append(f"Missing required fields: {', '.join(set(missing_fields))}")
            
            # Report results
            click.echo(f"  Total courses: {len(schedule_data.courses)}")
            click.echo(f"  Departments: {len(schedule_data.departments)}")
            
            if issues:
                click.echo("  Issues found:")
                for issue in issues:
                    click.echo(f"    ❌ {issue}")
            
            if warnings:
                click.echo("  Warnings:")
                for warning in warnings:
                    click.echo(f"    ⚠️  {warning}")
            
            if not issues and not warnings:
                click.echo("  ✅ No issues found")
                
        except Exception as e:
            click.echo(f"  ❌ Error loading file: {e}")


@cli.command()
@click.option('--file1', '-f1', type=click.Path(exists=True), help='First schedule file')
@click.option('--file2', '-f2', type=click.Path(exists=True), help='Second schedule file')
@click.option('--weeks', '-w', type=int, help='Compare schedules from N weeks ago to latest')
@click.pass_context
def compare(ctx, file1: Optional[str], file2: Optional[str], weeks: Optional[int]):
    """Compare two schedule files to find changes."""
    storage = ctx.obj['storage']
    
    # Determine files to compare
    if weeks:
        # Compare with file from N weeks ago
        latest = storage.get_latest_schedule()
        if not latest:
            click.echo("No schedule files found.")
            return
            
        all_files = storage.list_schedules()
        # Simple approximation: assume 3 collections per week
        target_index = min(weeks * 3, len(all_files) - 1)
        if target_index >= len(all_files):
            click.echo(f"Not enough historical data for {weeks} weeks comparison.")
            return
            
        file1 = str(all_files[target_index])
        file2 = str(latest)
    
    elif not file1 or not file2:
        click.echo("Please provide two files to compare or use --weeks option.")
        return
    
    # Load schedules
    schedule1 = storage.load_schedule(file1)
    schedule2 = storage.load_schedule(file2)
    
    # Create CRN maps
    courses1 = {c.crn: c for c in schedule1.courses}
    courses2 = {c.crn: c for c in schedule2.courses}
    
    # Find changes
    crns1 = set(courses1.keys())
    crns2 = set(courses2.keys())
    
    added = crns2 - crns1
    removed = crns1 - crns2
    common = crns1 & crns2
    
    # Check for changes in common courses
    enrollment_changes = []
    instructor_changes = []
    location_changes = []
    time_changes = []
    
    for crn in common:
        c1 = courses1[crn]
        c2 = courses2[crn]
        
        if c1.enrollment.actual != c2.enrollment.actual:
            enrollment_changes.append((crn, c1, c2))
        
        if c1.instructor != c2.instructor:
            instructor_changes.append((crn, c1, c2))
            
        if c1.location != c2.location:
            location_changes.append((crn, c1, c2))
            
        # Compare meeting times
        times1 = {(mt.days, mt.start_time, mt.end_time) for mt in c1.meeting_times}
        times2 = {(mt.days, mt.start_time, mt.end_time) for mt in c2.meeting_times}
        if times1 != times2:
            time_changes.append((crn, c1, c2))
    
    # Display results
    click.echo(f"\nComparing schedules:")
    click.echo(f"  File 1: {Path(file1).name} ({schedule1.collection_timestamp})")
    click.echo(f"  File 2: {Path(file2).name} ({schedule2.collection_timestamp})")
    click.echo()
    
    if added:
        click.echo(f"✨ {len(added)} new courses added:")
        for crn in sorted(added)[:10]:  # Show first 10
            c = courses2[crn]
            click.echo(f"   - {crn}: {c.subject} {c.course_number} - {c.title}")
        if len(added) > 10:
            click.echo(f"   ... and {len(added) - 10} more")
    
    if removed:
        click.echo(f"\n🗑️  {len(removed)} courses removed:")
        for crn in sorted(removed)[:10]:
            c = courses1[crn]
            click.echo(f"   - {crn}: {c.subject} {c.course_number} - {c.title}")
        if len(removed) > 10:
            click.echo(f"   ... and {len(removed) - 10} more")
    
    if enrollment_changes:
        click.echo(f"\n📊 {len(enrollment_changes)} enrollment changes:")
        for crn, c1, c2 in enrollment_changes[:10]:
            change = c2.enrollment.actual - c1.enrollment.actual
            sign = "+" if change > 0 else ""
            click.echo(f"   - {crn}: {c1.subject} {c1.course_number} - "
                      f"{c1.enrollment.actual} → {c2.enrollment.actual} ({sign}{change})")
    
    if instructor_changes:
        click.echo(f"\n👥 {len(instructor_changes)} instructor changes:")
        for crn, c1, c2 in instructor_changes[:5]:
            click.echo(f"   - {crn}: {c1.subject} {c1.course_number} - "
                      f"{c1.instructor} → {c2.instructor}")
    
    if not any([added, removed, enrollment_changes, instructor_changes, location_changes, time_changes]):
        click.echo("No significant changes found.")


@cli.command()
@click.option('--term', '-t', help='Filter by term code')
@click.option('--days', '-d', type=int, default=30, help='Number of days to analyze')
@click.pass_context
def report(ctx, term: Optional[str], days: int):
    """Generate summary report of collected data."""
    storage = ctx.obj['storage']
    
    # Get recent files
    files = storage.list_schedules(term_code=term)
    if not files:
        click.echo("No schedule files found.")
        return
    
    # Filter by date
    cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
    recent_files = [f for f in files if f.stat().st_mtime > cutoff_date]
    
    if not recent_files:
        click.echo(f"No files found in the last {days} days.")
        return
    
    click.echo(f"\n📊 Schedule Collection Report")
    click.echo(f"Period: Last {days} days")
    click.echo(f"Files analyzed: {len(recent_files)}")
    
    # Aggregate statistics
    all_departments = Counter()
    all_instructors = Counter()
    enrollment_trends = defaultdict(list)
    course_counts = []
    
    for file_path in recent_files:
        try:
            schedule = storage.load_schedule(file_path)
            course_counts.append(len(schedule.courses))
            
            for dept in schedule.departments:
                all_departments[dept] += 1
            
            for course in schedule.courses:
                all_instructors[course.instructor] += 1
                enrollment_trends[course.crn].append(course.enrollment.actual)
                
        except Exception as e:
            click.echo(f"Error loading {file_path}: {e}")
    
    # Display statistics
    click.echo(f"\n📈 Collection Statistics:")
    click.echo(f"  Average courses per collection: {sum(course_counts) / len(course_counts):.1f}")
    click.echo(f"  Min/Max courses: {min(course_counts)} / {max(course_counts)}")
    
    click.echo(f"\n🏫 Top Departments:")
    for dept, count in all_departments.most_common(10):
        click.echo(f"  {dept}: appeared in {count} collections")
    
    click.echo(f"\n👨‍🏫 Most Active Instructors:")
    instructor_courses = Counter()
    # Get latest file for current instructor count
    latest_schedule = storage.load_schedule(recent_files[0])
    for course in latest_schedule.courses:
        instructor_courses[course.instructor] += 1
    
    for instructor, count in instructor_courses.most_common(10):
        if instructor and instructor != "TBA":
            click.echo(f"  {instructor}: {count} courses")
    
    # Find courses with biggest enrollment changes
    click.echo(f"\n📊 Largest Enrollment Changes:")
    enrollment_changes = []
    for crn, enrollments in enrollment_trends.items():
        if len(enrollments) > 1:
            change = enrollments[-1] - enrollments[0]
            if abs(change) > 0:
                enrollment_changes.append((crn, change, enrollments[0], enrollments[-1]))
    
    enrollment_changes.sort(key=lambda x: abs(x[1]), reverse=True)
    
    for crn, change, start, end in enrollment_changes[:10]:
        # Find course details
        for course in latest_schedule.courses:
            if course.crn == crn:
                sign = "+" if change > 0 else ""
                click.echo(f"  {crn}: {course.subject} {course.course_number} - "
                          f"{start} → {end} ({sign}{change})")
                break


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.argument('output_path', type=click.Path())
@click.option('--format', '-f', type=click.Choice(['csv', 'excel', 'json']), default='csv')
@click.pass_context
def export(ctx, file_path: str, output_path: str, format: str):
    """Export schedule data to different formats."""
    storage = ctx.obj['storage']
    
    # Load schedule
    schedule = storage.load_schedule(file_path)
    
    # Convert to dataframe
    rows = []
    for c in schedule.courses:
        meeting_times = []
        for mt in c.meeting_times:
            if mt.is_arranged:
                meeting_times.append("ARR")
            else:
                meeting_times.append(f"{mt.days} {mt.start_time}-{mt.end_time}")
        
        rows.append({
            'CRN': c.crn,
            'Subject': c.subject,
            'Course Number': c.course_number,
            'Title': c.title,
            'Units': c.units,
            'Instructor': c.instructor,
            'Instructor Email': c.instructor_email,
            'Meeting Times': ', '.join(meeting_times),
            'Location': c.location,
            'Capacity': c.enrollment.capacity,
            'Enrolled': c.enrollment.actual,
            'Available': c.enrollment.remaining,
            'Status': c.status,
            'Section Type': c.section_type,
            'Zero Textbook Cost': c.zero_textbook_cost,
            'Delivery Method': c.delivery_method,
            'Weeks': c.weeks,
            'Start Date': c.start_date,
            'End Date': c.end_date
        })
    
    df = pd.DataFrame(rows)
    
    # Export based on format
    if format == 'csv':
        df.to_csv(output_path, index=False)
        click.echo(f"Exported {len(rows)} courses to {output_path}")
    
    elif format == 'excel':
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Schedule', index=False)
            
            # Add metadata sheet
            metadata = pd.DataFrame([{
                'Term': schedule.term,
                'Term Code': schedule.term_code,
                'Collection Date': schedule.collection_timestamp,
                'Total Courses': schedule.total_courses,
                'Departments': ', '.join(schedule.departments)
            }])
            metadata.to_excel(writer, sheet_name='Metadata', index=False)
        
        click.echo(f"Exported {len(rows)} courses to {output_path}")
    
    elif format == 'json':
        data = {
            'metadata': {
                'term': schedule.term,
                'term_code': schedule.term_code,
                'collection_timestamp': schedule.collection_timestamp.isoformat(),
                'total_courses': schedule.total_courses,
                'departments': schedule.departments
            },
            'courses': [c.model_dump() for c in schedule.courses]
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        click.echo(f"Exported {len(rows)} courses to {output_path}")


if __name__ == '__main__':
    cli()