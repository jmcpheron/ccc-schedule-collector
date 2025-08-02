#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pytest>=7.0",
#   "pydantic>=2.0",
#   "pyyaml",
#   "click>=8.0"
# ]
# ///
"""Tests for subject discovery functionality."""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Set, Dict

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from discover_subjects import SubjectDiscovery
from models import ScheduleData, Course, MeetingTime, Enrollment


class TestSubjectDiscovery:
    """Test subject discovery functionality."""
    
    @pytest.fixture
    def temp_college_structure(self, tmp_path):
        """Create temporary college directory structure."""
        # Create directories
        collectors_dir = tmp_path / "collectors" / "test_college"
        collectors_dir.mkdir(parents=True)
        
        data_dir = tmp_path / "data" / "test-college"
        data_dir.mkdir(parents=True)
        
        # Create config
        config = {
            "college_id": "test-college",
            "all_subjects": ["MATH", "ENGL", "BIOL"],
            "subject_management": {
                "expected_subjects": ["MATH", "ENGL"],
                "optional_subjects": ["BIOL"],
                "discovered_subjects": {},
                "deprecated_subjects": {}
            }
        }
        
        config_path = collectors_dir / "config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Create sample schedule data
        schedule_data = {
            "term": "Spring 2025",
            "term_code": "202520",
            "college_id": "test-college",
            "collection_timestamp": datetime.now().isoformat(),
            "courses": [
                {
                    "crn": "12345",
                    "subject": "MATH",
                    "course_number": "101",
                    "title": "College Algebra",
                    "credits": 3.0,
                    "meeting_times": [{
                        "days": "MW",
                        "start_time": "10:00 AM",
                        "end_time": "11:50 AM",
                        "location": "MATH 101",
                        "weeks": 16
                    }],
                    "enrollment": {
                        "capacity": 30,
                        "actual": 25,
                        "remaining": 5
                    },
                    "instructors": ["Smith, J"]
                },
                {
                    "crn": "23456",
                    "subject": "CHEM",  # New subject not in config
                    "course_number": "101",
                    "title": "General Chemistry",
                    "credits": 4.0,
                    "meeting_times": [{
                        "days": "TTh",
                        "start_time": "2:00 PM",
                        "end_time": "3:50 PM",
                        "location": "SCI 201",
                        "weeks": 16
                    }],
                    "enrollment": {
                        "capacity": 24,
                        "actual": 20,
                        "remaining": 4
                    },
                    "instructors": ["Johnson, M"]
                }
            ],
            "metadata": {
                "total_courses": 2,
                "departments": ["MATH", "CHEM"]
            }
        }
        
        schedule_path = data_dir / "schedule_202520_20250802_120000.json"
        with open(schedule_path, 'w') as f:
            json.dump(schedule_data, f, indent=2)
        
        return {
            'root': tmp_path,
            'config_path': config_path,
            'data_dir': data_dir,
            'schedule_path': schedule_path
        }
    
    def test_discovery_initialization(self, temp_college_structure):
        """Test SubjectDiscovery initialization."""
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_college_structure['root'])
            
            discovery = SubjectDiscovery("test-college")
            
            assert discovery.college_id == "test-college"
            assert discovery.config_path.exists()
            assert discovery.data_dir.exists()
            
        finally:
            os.chdir(old_cwd)
    
    def test_load_config(self, temp_college_structure):
        """Test loading college configuration."""
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_college_structure['root'])
            
            discovery = SubjectDiscovery("test-college")
            config = discovery.load_config()
            
            assert config['college_id'] == "test-college"
            assert 'all_subjects' in config
            assert 'subject_management' in config
            
        finally:
            os.chdir(old_cwd)
    
    def test_discover_subjects_from_data(self, temp_college_structure):
        """Test discovering subjects from schedule data."""
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_college_structure['root'])
            
            discovery = SubjectDiscovery("test-college")
            subjects = discovery.discover_subjects_from_data()
            
            assert subjects == {"MATH", "CHEM"}
            
        finally:
            os.chdir(old_cwd)
    
    def test_analyze_subjects(self, temp_college_structure):
        """Test subject analysis functionality."""
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_college_structure['root'])
            
            discovery = SubjectDiscovery("test-college")
            config = discovery.load_config()
            discovered = {"MATH", "CHEM", "PHYS"}
            
            analysis = discovery.analyze_subjects(config, discovered)
            
            # CHEM and PHYS are new (not in all_subjects)
            assert analysis['new_subjects'] == {"CHEM", "PHYS"}
            
            # ENGL is expected but missing
            assert analysis['missing_expected'] == {"ENGL"}
            
            # BIOL is optional and missing
            assert analysis['missing_optional'] == {"BIOL"}
            
            # Total discovered
            assert analysis['total_discovered'] == {"MATH", "CHEM", "PHYS"}
            
        finally:
            os.chdir(old_cwd)
    
    def test_update_config_with_discoveries(self, temp_college_structure):
        """Test updating config with discovered subjects."""
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_college_structure['root'])
            
            discovery = SubjectDiscovery("test-college")
            config = discovery.load_config()
            
            analysis = {
                'new_subjects': {"CHEM", "PHYS"},
                'missing_expected': {"ENGL"},
                'missing_optional': set(),
                'missing_any': set(),
                'total_discovered': {"MATH", "CHEM", "PHYS"},
                'rediscovered': set()
            }
            
            updated_config, modified = discovery.update_config_with_discoveries(
                config, analysis, auto_update=True
            )
            
            assert modified is True
            
            # Check that new subjects were added to all_subjects
            assert set(updated_config['all_subjects']) == {"MATH", "ENGL", "BIOL", "CHEM", "PHYS"}
            
            # Check that discovered subjects were tracked
            subject_mgmt = updated_config['subject_management']
            today = datetime.now().strftime('%Y-%m-%d')
            assert today in subject_mgmt['discovered_subjects']
            assert set(subject_mgmt['discovered_subjects'][today]) == {"CHEM", "PHYS"}
            
            # Check that missing expected subjects were tracked
            assert today in subject_mgmt['deprecated_subjects']
            assert "ENGL" in subject_mgmt['deprecated_subjects'][today]
            
        finally:
            os.chdir(old_cwd)
    
    def test_generate_report(self, temp_college_structure):
        """Test report generation."""
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_college_structure['root'])
            
            discovery = SubjectDiscovery("test-college")
            
            analysis = {
                'new_subjects': {"CHEM", "PHYS"},
                'missing_expected': {"ENGL"},
                'missing_optional': {"BIOL"},
                'missing_any': {"ENGL", "BIOL"},
                'total_discovered': {"MATH", "CHEM", "PHYS"},
                'rediscovered': set()
            }
            
            report = discovery.generate_report(analysis)
            
            # Check report contains expected sections
            assert "Subject Discovery Report" in report
            assert "NEW SUBJECTS FOUND" in report
            assert "CHEM" in report
            assert "PHYS" in report
            assert "MISSING EXPECTED SUBJECTS" in report
            assert "ENGL" in report
            assert "Missing optional subjects" in report
            assert "BIOL" in report
            
        finally:
            os.chdir(old_cwd)
    
    def test_discovery_with_empty_data(self, temp_college_structure):
        """Test discovery when no schedule files exist."""
        import os
        import shutil
        
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_college_structure['root'])
            
            # Remove schedule files
            shutil.rmtree(temp_college_structure['data_dir'])
            temp_college_structure['data_dir'].mkdir()
            
            discovery = SubjectDiscovery("test-college")
            subjects = discovery.discover_subjects_from_data()
            
            assert subjects == set()
            
        finally:
            os.chdir(old_cwd)
    
    def test_discovery_with_malformed_data(self, temp_college_structure):
        """Test discovery handles malformed schedule data gracefully."""
        import os
        
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_college_structure['root'])
            
            # Create malformed JSON
            bad_file = temp_college_structure['data_dir'] / "schedule_bad.json"
            with open(bad_file, 'w') as f:
                f.write("{invalid json")
            
            discovery = SubjectDiscovery("test-college")
            subjects = discovery.discover_subjects_from_data()
            
            # Should still find subjects from valid files
            assert "MATH" in subjects
            assert "CHEM" in subjects
            
        finally:
            os.chdir(old_cwd)


class TestSubjectDiscoveryIntegration:
    """Integration tests using actual college data."""
    
    @pytest.mark.parametrize("college_id,college_dir", [
        ("citrus", "citrus"),
        ("rio-hondo", "rio_hondo")
    ])
    def test_real_college_discovery(self, college_id, college_dir):
        """Test discovery on real college data if available."""
        # Check if college exists
        config_path = Path(f"collectors/{college_dir}/config.json")
        if not config_path.exists():
            pytest.skip(f"College {college_id} not configured")
        
        data_dir = Path(f"data/{college_id}")
        if not data_dir.exists() or not list(data_dir.glob("schedule_*.json")):
            pytest.skip(f"No data available for {college_id}")
        
        discovery = SubjectDiscovery(college_id)
        
        # Test that we can discover subjects
        subjects = discovery.discover_subjects_from_data()
        assert len(subjects) > 0, f"No subjects discovered for {college_id}"
        
        # Test that we can load config
        config = discovery.load_config()
        assert config['college_id'] == college_id
        
        # Test analysis
        analysis = discovery.analyze_subjects(config, subjects)
        
        # Generate report (should not raise)
        report = discovery.generate_report(analysis)
        assert isinstance(report, str)
        assert len(report) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])