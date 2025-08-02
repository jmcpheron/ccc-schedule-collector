#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pytest>=7.0",
#   "pydantic>=2.0",
#   "pyyaml"
# ]
# ///
"""Tests for Rio Hondo College collector subject code validation."""

import json
import sys
from pathlib import Path
from typing import Set, Dict, List

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import ScheduleData


class TestRioHondoSubjectValidation:
    """Test subject code validation for Rio Hondo College."""
    
    @pytest.fixture
    def config(self):
        """Load Rio Hondo configuration."""
        config_path = Path("collectors/rio_hondo/config.json")
        with open(config_path, 'r') as f:
            return json.load(f)
    
    @pytest.fixture
    def latest_data(self):
        """Load latest collected Rio Hondo data."""
        data_dir = Path("data/rio-hondo")
        
        # Find latest schedule file
        schedule_files = sorted(data_dir.glob("schedule_*_latest.json"))
        if not schedule_files:
            pytest.skip("No Rio Hondo schedule data found")
            
        with open(schedule_files[0], 'r') as f:
            data = json.load(f)
            
        return ScheduleData(**data)
    
    def test_config_has_subject_lists(self, config):
        """Test that Rio Hondo config has proper subject lists."""
        # Check all_subjects exists and is populated
        assert 'all_subjects' in config
        assert isinstance(config['all_subjects'], list)
        assert len(config['all_subjects']) > 0, "all_subjects should not be empty"
        
        # Check subject_management section
        assert 'subject_management' in config
        subject_mgmt = config['subject_management']
        
        assert 'expected_subjects' in subject_mgmt
        assert isinstance(subject_mgmt['expected_subjects'], list)
        assert len(subject_mgmt['expected_subjects']) > 0, "expected_subjects should not be empty"
        
        # Check that expected subjects are a subset of all subjects
        all_subjects = set(config['all_subjects'])
        expected_subjects = set(subject_mgmt['expected_subjects'])
        assert expected_subjects.issubset(all_subjects), \
            f"Expected subjects not in all_subjects: {expected_subjects - all_subjects}"
    
    def test_critical_subjects_in_expected(self, config):
        """Test that critical subjects are marked as expected."""
        critical_subjects = [
            'MATH', 'ENGL', 'BIOL', 'CHEM', 'PHY', 'HIST', 
            'POLS', 'PSY', 'SOC', 'ART', 'MUS', 'SPAN'
        ]
        
        expected_subjects = set(config['subject_management']['expected_subjects'])
        
        for subject in critical_subjects:
            assert subject in expected_subjects, \
                f"Critical subject {subject} should be in expected_subjects"
    
    def test_all_expected_subjects_collected(self, latest_data, config):
        """Test that all expected subjects have at least one course."""
        expected_subjects = set(config['subject_management']['expected_subjects'])
        collected_subjects = {course.subject for course in latest_data.courses}
        
        missing_expected = expected_subjects - collected_subjects
        
        assert not missing_expected, \
            f"Expected subjects not found in collection: {sorted(missing_expected)}"
    
    def test_no_unknown_subjects_collected(self, latest_data, config):
        """Test that no unknown subjects were collected."""
        all_subjects = set(config['all_subjects'])
        collected_subjects = {course.subject for course in latest_data.courses}
        
        unknown_subjects = collected_subjects - all_subjects
        
        # Unknown subjects might indicate new departments or typos
        if unknown_subjects:
            pytest.fail(
                f"Unknown subjects found in collection: {sorted(unknown_subjects)}\n"
                f"Run ./discover_subjects.py --college rio-hondo --update to add them"
            )
    
    def test_reasonable_course_counts(self, latest_data, config):
        """Test that collected course counts are reasonable."""
        # Count courses per subject
        subject_counts = {}
        for course in latest_data.courses:
            subject_counts[course.subject] = subject_counts.get(course.subject, 0) + 1
        
        # Check expected subjects have reasonable counts
        expected_subjects = config['subject_management']['expected_subjects']
        
        for subject in expected_subjects:
            count = subject_counts.get(subject, 0)
            assert count > 0, f"Expected subject {subject} has no courses"
            
            # Most core subjects should have at least 5 courses
            if subject in ['MATH', 'ENGL', 'BIOL', 'CHEM', 'HIST', 'PSY']:
                assert count >= 5, \
                    f"Core subject {subject} has only {count} courses, expected at least 5"
    
    def test_subject_consistency_across_files(self):
        """Test that subjects are consistent across multiple schedule files."""
        data_dir = Path("data/rio-hondo")
        
        # Get recent schedule files (not just latest)
        schedule_files = sorted(data_dir.glob("schedule_*.json"))[-5:]  # Last 5 files
        
        if len(schedule_files) < 2:
            pytest.skip("Need at least 2 schedule files for comparison")
        
        # Collect subjects from each file
        file_subjects = []
        for file_path in schedule_files:
            if '_latest' in file_path.name:
                continue
                
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    subjects = {course['subject'] for course in data.get('courses', [])}
                    file_subjects.append((file_path.name, subjects))
            except Exception:
                continue
        
        if len(file_subjects) < 2:
            pytest.skip("Not enough valid files for comparison")
        
        # Compare subjects between files
        base_name, base_subjects = file_subjects[0]
        
        for name, subjects in file_subjects[1:]:
            # Allow some variation but core subjects should be stable
            missing = base_subjects - subjects
            new = subjects - base_subjects
            
            # There shouldn't be huge variations
            assert len(missing) < 10, \
                f"Too many subjects missing between {base_name} and {name}: {missing}"
            assert len(new) < 10, \
                f"Too many new subjects between {base_name} and {name}: {new}"
    
    def test_subject_name_format(self, latest_data):
        """Test that all subject codes follow expected format."""
        import re
        
        # Subject codes should be uppercase letters, possibly with numbers
        subject_pattern = re.compile(r'^[A-Z]+[0-9]*$')
        
        invalid_subjects = []
        for course in latest_data.courses:
            if not subject_pattern.match(course.subject):
                invalid_subjects.append(course.subject)
        
        assert not invalid_subjects, \
            f"Invalid subject code format: {sorted(set(invalid_subjects))}"
    
    def test_metadata_includes_departments(self, latest_data):
        """Test that metadata includes department list."""
        assert latest_data.metadata is not None
        assert 'departments' in latest_data.metadata
        
        departments = latest_data.metadata['departments']
        assert isinstance(departments, list)
        assert len(departments) > 0
        
        # Should match unique subjects from courses
        course_subjects = sorted(set(course.subject for course in latest_data.courses))
        assert departments == course_subjects, \
            "Metadata departments should match unique course subjects"


class TestRioHondoCollectorConfiguration:
    """Test Rio Hondo collector configuration specifics."""
    
    def test_config_structure(self):
        """Test that Rio Hondo config has all required fields."""
        config_path = Path("collectors/rio_hondo/config.json")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Required top-level fields
        required_fields = [
            'college_id', 'collector_version', 'base_url', 
            'all_subjects', 'subject_management'
        ]
        
        for field in required_fields:
            assert field in config, f"Missing required field: {field}"
        
        # Check subject_management structure
        subject_mgmt = config['subject_management']
        required_mgmt_fields = [
            'expected_subjects', 'optional_subjects', 
            'discovered_subjects', 'deprecated_subjects'
        ]
        
        for field in required_mgmt_fields:
            assert field in subject_mgmt, f"Missing subject_management field: {field}"
    
    def test_discovered_subjects_tracking(self):
        """Test that discovered subjects are properly tracked with dates."""
        config_path = Path("collectors/rio_hondo/config.json")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        discovered = config['subject_management']['discovered_subjects']
        
        if discovered:
            # Should be a dict with date keys
            for date_key, subjects in discovered.items():
                # Date should be in YYYY-MM-DD format
                assert len(date_key) == 10 and date_key[4] == '-' and date_key[7] == '-'
                
                # Subjects should be a list
                assert isinstance(subjects, list)
                assert all(isinstance(s, str) for s in subjects)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])