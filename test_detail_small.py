#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pydantic>=2.0",
#   "rich"
# ]
# ///

"""Test detail collection with just a few courses."""

import json
from pathlib import Path
from rich.console import Console

console = Console()

# Load the basic schedule
schedule_file = Path("data/schedule_basic_202570_latest.json")
with open(schedule_file, 'r') as f:
    data = json.load(f)

# Create a small test file with just 5 courses
test_data = data.copy()
test_data['courses'] = data['courses'][:5]  # Just first 5 courses
test_data['metadata']['total_courses'] = 5

# Save test file
test_file = Path("data/test/schedule_basic_test_5_courses.json")
test_file.parent.mkdir(exist_ok=True)
with open(test_file, 'w') as f:
    json.dump(test_data, f, indent=2)

console.print(f"[green]Created test file with 5 courses: {test_file}[/green]")
console.print("\nCourses included:")
for course in test_data['courses']:
    console.print(f"  - {course['crn']}: {course['subject']} {course['course_number']} - {course['title']}")