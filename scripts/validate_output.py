#!/usr/bin/env python3
"""Script to validate collector output against the integration contract."""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import ScheduleData


# Required top-level fields according to integration guide
REQUIRED_TOP_LEVEL_FIELDS = [
    'term',
    'term_code', 
    'collection_timestamp',
    'source_url',
    'college_id',
    'collector_version',
    'courses'
]

# Required course fields (minimum)
REQUIRED_COURSE_FIELDS = [
    'crn',
    'subject'
]

# Recommended course fields
RECOMMENDED_COURSE_FIELDS = [
    'course_number',
    'title',
    'units',
    'instructor',
    'meeting_times',
    'location',
    'enrollment',
    'status'
]


def validate_file(filepath: Path) -> Tuple[bool, List[str], List[str]]:
    """Validate a single output file.
    
    Args:
        filepath: Path to JSON file to validate
        
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    try:
        # Load the JSON file
        with open(filepath, 'r') as f:
            data = json.load(f)
            
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return False, errors, warnings
    except Exception as e:
        errors.append(f"Failed to read file: {e}")
        return False, errors, warnings
    
    # Check required top-level fields
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in data:
            errors.append(f"Missing required top-level field: '{field}'")
        elif data[field] is None:
            errors.append(f"Required field '{field}' is null")
    
    # Check courses structure
    if 'courses' in data:
        if not isinstance(data['courses'], list):
            errors.append("'courses' must be an array")
        else:
            if len(data['courses']) == 0:
                warnings.append("No courses found in collection")
            else:
                # Validate first few courses as samples
                sample_size = min(5, len(data['courses']))
                for i in range(sample_size):
                    course = data['courses'][i]
                    
                    # Check required course fields
                    for field in REQUIRED_COURSE_FIELDS:
                        if field not in course:
                            errors.append(f"Course at index {i} missing required field: '{field}'")
                        elif not course[field]:
                            errors.append(f"Course at index {i} has empty '{field}'")
                    
                    # Check recommended fields
                    for field in RECOMMENDED_COURSE_FIELDS:
                        if field not in course:
                            warnings.append(f"Course at index {i} missing recommended field: '{field}'")
    
    # Check for deprecated fields at top level
    if 'total_courses' in data and data['total_courses'] is not None:
        warnings.append("'total_courses' should be in metadata, not at top level")
    if 'departments' in data and data['departments'] is not None:
        warnings.append("'departments' should be in metadata, not at top level")
    
    # Validate against Pydantic model
    try:
        schedule_data = ScheduleData(**data)
        # Model validation passed
    except Exception as e:
        errors.append(f"Pydantic validation failed: {e}")
    
    # Additional checks
    if 'metadata' in data and data['metadata']:
        if not isinstance(data['metadata'], dict):
            errors.append("'metadata' must be a dictionary")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def print_validation_report(filepath: Path, is_valid: bool, errors: List[str], warnings: List[str]):
    """Print a validation report for a file."""
    status = "✓ VALID" if is_valid else "✗ INVALID"
    print(f"\n{status}: {filepath.name}")
    print("-" * 60)
    
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for error in errors:
            print(f"  ✗ {error}")
    
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for warning in warnings:
            print(f"  ⚠ {warning}")
    
    if is_valid and not warnings:
        print("  No issues found - output meets all requirements!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Validate collector output files against the integration contract'
    )
    parser.add_argument(
        'files',
        nargs='+',
        type=Path,
        help='JSON files to validate'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Only show summary, not detailed errors'
    )
    
    args = parser.parse_args()
    
    total_files = len(args.files)
    valid_files = 0
    files_with_warnings = 0
    
    for filepath in args.files:
        if not filepath.exists():
            print(f"✗ File not found: {filepath}")
            continue
            
        is_valid, errors, warnings = validate_file(filepath)
        
        if args.strict and warnings:
            is_valid = False
            errors.extend(warnings)
            warnings = []
        
        if is_valid:
            valid_files += 1
        if warnings:
            files_with_warnings += 1
        
        if not args.quiet:
            print_validation_report(filepath, is_valid, errors, warnings)
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total files: {total_files}")
    print(f"Valid files: {valid_files}")
    print(f"Invalid files: {total_files - valid_files}")
    print(f"Files with warnings: {files_with_warnings}")
    
    if valid_files == total_files:
        print("\n✓ All files are valid!")
        return 0
    else:
        print(f"\n✗ {total_files - valid_files} file(s) failed validation")
        return 1


if __name__ == '__main__':
    sys.exit(main())