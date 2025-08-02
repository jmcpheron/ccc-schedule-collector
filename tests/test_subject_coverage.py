#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pytest",
#   "pydantic>=2.0",
# ]
# ///
"""Tests for verifying complete subject coverage in collected data.

This module contains general tests that can be used for any college collector
to ensure that subjects at the end of the alphabet are not missed due to
truncation, pagination issues, or incomplete subject lists.
"""

import json
from pathlib import Path
from typing import List, Set, Optional

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import ScheduleData


class TestSubjectCoverage:
    """General tests for subject coverage that apply to all colleges."""
    
    # Common end-of-alphabet subjects that are often missed
    COMMON_END_SUBJECTS = {
        'STAT',   # Statistics
        'THTR',   # Theatre/Theater
        'WATR',   # Water Technology
        'WELD',   # Welding
        'VET',    # Veterinary
        'VN',     # Vocational Nursing
        'UAS',    # Uncrewed Aerial Systems
        'WORK',   # Work Experience
        'YOGA',   # Yoga
        'ZOOL',   # Zoology
    }
    
    def test_no_alphabetical_gaps_in_subjects(self, schedule_data: Optional[ScheduleData] = None):
        """Test that there are no unexpected gaps in the alphabetical subject list.
        
        This test checks if subjects are distributed across the alphabet without
        suspicious gaps that might indicate truncation.
        
        Args:
            schedule_data: ScheduleData object to test, or None to skip
        """
        if schedule_data is None:
            pytest.skip("No schedule data provided")
            
        subjects = self._extract_subjects(schedule_data)
        if not subjects:
            pytest.skip("No subjects found in data")
            
        # Get first letter of each subject
        first_letters = {subj[0].upper() for subj in subjects if subj}
        
        # Check for suspicious gaps in later alphabet
        late_letters = {'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'}
        found_late_letters = first_letters & late_letters
        
        # If we have any subjects starting with S or later, we should have
        # a reasonable distribution, not just stopping at S
        if 'S' in found_late_letters and len(found_late_letters) < 3:
            pytest.fail(
                f"Suspicious gap in subjects after 'S'. "
                f"Only found subjects starting with: {sorted(found_late_letters)}. "
                f"This might indicate truncation."
            )
    
    def test_includes_common_end_subjects(self, schedule_data: Optional[ScheduleData] = None,
                                        expected_end_subjects: Optional[Set[str]] = None):
        """Test that common end-of-alphabet subjects are included if expected.
        
        Args:
            schedule_data: ScheduleData object to test
            expected_end_subjects: Set of subjects that should be present, 
                                 or None to use COMMON_END_SUBJECTS
        """
        if schedule_data is None:
            pytest.skip("No schedule data provided")
            
        subjects = self._extract_subjects(schedule_data)
        if not subjects:
            pytest.skip("No subjects found in data")
            
        # Use provided expected subjects or common ones
        expected = expected_end_subjects or self.COMMON_END_SUBJECTS
        
        # Find which expected subjects are missing
        missing_subjects = expected - subjects
        
        # It's OK if some subjects are missing (college might not offer them)
        # but if ALL end subjects are missing, that's suspicious
        if missing_subjects == expected:
            pytest.fail(
                f"None of the expected end-of-alphabet subjects were found. "
                f"Expected at least one of: {sorted(expected)}. "
                f"Found subjects: {sorted(subjects)}"
            )
    
    def test_subject_count_reasonable(self, schedule_data: Optional[ScheduleData] = None,
                                    min_expected: int = 20):
        """Test that the number of unique subjects is reasonable.
        
        Most community colleges offer at least 20-30 different subjects.
        Fewer might indicate truncation.
        
        Args:
            schedule_data: ScheduleData object to test
            min_expected: Minimum number of subjects expected (default: 20)
        """
        if schedule_data is None:
            pytest.skip("No schedule data provided")
            
        subjects = self._extract_subjects(schedule_data)
        
        if len(subjects) < min_expected:
            pytest.fail(
                f"Only found {len(subjects)} unique subjects, "
                f"expected at least {min_expected}. "
                f"This might indicate incomplete collection. "
                f"Subjects found: {sorted(subjects)}"
            )
    
    def test_validate_against_config_subjects(self, schedule_data: Optional[ScheduleData] = None,
                                            config_path: Optional[Path] = None):
        """Test that all subjects defined in config are present in collected data.
        
        Args:
            schedule_data: ScheduleData object to test
            config_path: Path to the college's config.json file
        """
        if schedule_data is None or config_path is None:
            pytest.skip("Schedule data or config path not provided")
            
        if not config_path.exists():
            pytest.skip(f"Config file not found: {config_path}")
            
        # Load expected subjects from config
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        expected_subjects = set(config.get('expected_subjects', []))
        if not expected_subjects:
            # Try all_subjects as fallback
            expected_subjects = set(config.get('all_subjects', []))
            
        if not expected_subjects:
            pytest.skip("No expected_subjects or all_subjects defined in config")
            
        # Get collected subjects
        collected_subjects = self._extract_subjects(schedule_data)
        
        # Find missing subjects
        missing = expected_subjects - collected_subjects
        
        if missing:
            pytest.fail(
                f"Missing {len(missing)} subjects defined in config: "
                f"{sorted(missing)}. "
                f"Total expected: {len(expected_subjects)}, "
                f"Total collected: {len(collected_subjects)}"
            )
    
    def _extract_subjects(self, schedule_data: ScheduleData) -> Set[str]:
        """Extract unique subject codes from schedule data.
        
        Args:
            schedule_data: ScheduleData object
            
        Returns:
            Set of unique subject codes
        """
        subjects = set()
        
        # Get from courses
        for course in schedule_data.courses:
            if course.subject:
                subjects.add(course.subject.upper())
                
        # Also check metadata if available
        if hasattr(schedule_data, 'metadata') and schedule_data.metadata:
            if 'departments' in schedule_data.metadata:
                for dept in schedule_data.metadata['departments']:
                    if dept:
                        subjects.add(dept.upper())
                        
        return subjects


def create_validation_test(schedule_json_path: Path, 
                         expected_subjects: Optional[Set[str]] = None,
                         min_subjects: int = 20) -> None:
    """Convenience function to create and run validation tests on a JSON file.
    
    Args:
        schedule_json_path: Path to the schedule JSON file
        expected_subjects: Set of expected subjects or None
        min_subjects: Minimum expected number of subjects
    """
    # Load the schedule data
    with open(schedule_json_path, 'r') as f:
        data = json.load(f)
        
    schedule_data = ScheduleData(**data)
    
    # Create test instance and run tests
    tester = TestSubjectCoverage()
    
    print(f"Testing {schedule_json_path.name}...")
    
    # Run all tests
    try:
        tester.test_no_alphabetical_gaps_in_subjects(schedule_data)
        print("✓ No alphabetical gaps detected")
    except AssertionError as e:
        print(f"✗ Alphabetical gap test failed: {e}")
        
    try:
        tester.test_includes_common_end_subjects(schedule_data, expected_subjects)
        print("✓ Common end subjects found")
    except AssertionError as e:
        print(f"✗ End subjects test failed: {e}")
        
    try:
        tester.test_subject_count_reasonable(schedule_data, min_subjects)
        print("✓ Subject count is reasonable")
    except AssertionError as e:
        print(f"✗ Subject count test failed: {e}")


if __name__ == "__main__":
    # Run pytest if called directly
    pytest.main([__file__, "-v"])