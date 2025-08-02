#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pytest",
#   "requests",
#   "beautifulsoup4",
#   "pydantic>=2.0",
#   "pyyaml"
# ]
# ///
"""Integration test to verify THEA courses are collected correctly."""

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.citrus.collector import CitrusCollector


def test_citrus_collects_thea_courses():
    """Integration test that Citrus collector includes THEA in subject list."""
    collector = CitrusCollector()
    
    # Verify THEA is in the subject list
    all_subjects = collector.config.get('all_subjects', [])
    assert 'THEA' in all_subjects, "THEA should be in all_subjects list"
    assert 'THTR' not in all_subjects, "THTR should not be in list (use THEA)"
    
    # Verify search params include THEA
    params = collector._build_search_params("202620", "ALL")
    subject_params = [val for key, val in params if key == 'sel_subj' and val != 'dummy']
    
    assert 'THEA' in subject_params, "THEA should be in search parameters"
    assert 'THTR' not in subject_params, "THTR should not be in search parameters"
    
    print("✓ Citrus collector correctly configured to search for THEA courses")


def test_verify_thea_in_latest_collection():
    """Verify THEA courses exist in the most recent collection."""
    data_dir = Path('data/citrus')
    if not data_dir.exists():
        pytest.skip("No Citrus data directory - run collection first")
        
    latest_file = data_dir / 'schedule_202620_latest.json'
    if not latest_file.exists():
        pytest.skip("No latest Citrus data - run collection first")
        
    with open(latest_file, 'r') as f:
        data = json.load(f)
        
    # Check if THEA courses exist
    thea_courses = [
        course for course in data.get('courses', [])
        if course.get('subject') == 'THEA'
    ]
    
    if thea_courses:
        print(f"✓ Found {len(thea_courses)} THEA courses in latest collection")
        print(f"  Sample courses: {', '.join(c['course_number'] for c in thea_courses[:5])}")
    else:
        print("✗ No THEA courses found - collection may need to be re-run")
        
    # Check metadata
    departments = data.get('metadata', {}).get('departments', [])
    if 'THEA' in departments:
        print("✓ THEA listed in departments metadata")
    else:
        print("✗ THEA not in departments metadata")


if __name__ == "__main__":
    print("Testing Citrus THEA integration...")
    test_citrus_collects_thea_courses()
    test_verify_thea_in_latest_collection()
    
    # Also run with pytest
    pytest.main([__file__, "-v", "-s"])