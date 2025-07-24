"""Tests for the base collector class."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.base_collector import BaseCollector
from models import ScheduleData, Course


class TestCollector(BaseCollector):
    """Test implementation of BaseCollector."""
    
    def fetch_data(self, term_code=None):
        """Test implementation of fetch_data."""
        return "<html><body>Test HTML</body></html>"
    
    def parse_data(self, raw_data, term_code=None):
        """Test implementation of parse_data."""
        return ScheduleData(
            term="Test Term",
            term_code="202570",
            collection_timestamp=datetime.now(),
            source_url="https://test.edu",
            college_id=self.college_id,
            collector_version=self.collector_version,
            courses=[
                Course(
                    crn="12345",
                    subject="TEST",
                    course_number="101",
                    title="Test Course",
                    units=3.0,
                    instructor="Test Instructor",
                    meeting_times=[],
                    location="Test Location",
                    enrollment={
                        "capacity": 30,
                        "actual": 25,
                        "remaining": 5
                    },
                    status="Open",
                    section_type="LEC",
                    zero_textbook_cost=False,
                    delivery_method="In-Person",
                    weeks=16
                )
            ]
        )


class TestBaseCollector:
    """Test the BaseCollector abstract class."""
    
    @pytest.fixture
    def config_file(self, tmp_path):
        """Create a temporary config file."""
        config = {
            "college_id": "test-college",
            "collector_version": "1.0.0",
            "base_url": "https://test.edu",
            "rate_limit": {
                "requests_per_second": 2,
                "retry_attempts": 3
            },
            "user_agent": "Test Agent"
        }
        config_path = tmp_path / "config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f)
        return config_path
    
    def test_initialization(self, config_file):
        """Test collector initialization."""
        collector = TestCollector(config_path=str(config_file))
        
        assert collector.college_id == "test-college"
        assert collector.collector_version == "1.0.0"
        assert collector.session is not None
    
    def test_collect_method(self, config_file):
        """Test the main collect method."""
        collector = TestCollector(config_path=str(config_file))
        
        # Mock save_output to avoid file operations
        with patch.object(collector, 'save_output'):
            schedule_data = collector.collect(save=False)
        
        assert schedule_data is not None
        assert schedule_data.college_id == "test-college"
        assert schedule_data.collector_version == "1.0.0"
        assert len(schedule_data.courses) == 1
        assert schedule_data.courses[0].crn == "12345"
    
    def test_validate_output_success(self, config_file):
        """Test successful validation."""
        collector = TestCollector(config_path=str(config_file))
        
        schedule_data = ScheduleData(
            term="Fall 2025",
            term_code="202570",
            collection_timestamp=datetime.now(),
            source_url="https://test.edu",
            college_id="test-college",
            collector_version="1.0.0",
            courses=[
                Course(
                    crn="12345",
                    subject="TEST",
                    course_number="101",
                    title="Test Course",
                    units=3.0,
                    instructor="Test Instructor",
                    meeting_times=[],
                    location="Test Location",
                    enrollment={
                        "capacity": 30,
                        "actual": 25,
                        "remaining": 5
                    },
                    status="Open",
                    section_type="LEC",
                    zero_textbook_cost=False,
                    delivery_method="In-Person",
                    weeks=16
                )
            ]
        )
        
        # Should not raise an exception
        collector.validate_output(schedule_data)
    
    def test_validate_output_missing_field(self, config_file):
        """Test validation with missing required field."""
        collector = TestCollector(config_path=str(config_file))
        
        # Create data missing college_id
        schedule_data = ScheduleData(
            term="Fall 2025",
            term_code="202570",
            collection_timestamp=datetime.now(),
            source_url="https://test.edu",
            college_id="",  # Empty college_id
            collector_version="1.0.0",
            courses=[]
        )
        
        with pytest.raises(ValueError, match="Missing required field: college_id"):
            collector.validate_output(schedule_data)
    
    def test_rate_limit_delay(self, config_file):
        """Test rate limiting delay."""
        collector = TestCollector(config_path=str(config_file))
        
        start_time = datetime.now()
        collector.rate_limit_delay()
        end_time = datetime.now()
        
        # With 2 requests per second, delay should be ~0.5 seconds
        duration = (end_time - start_time).total_seconds()
        assert duration >= 0.4  # Allow some tolerance
    
    def test_save_output(self, config_file, tmp_path):
        """Test saving output to file."""
        collector = TestCollector(config_path=str(config_file))
        
        schedule_data = ScheduleData(
            term="Fall 2025",
            term_code="202570",
            collection_timestamp=datetime.now(),
            source_url="https://test.edu",
            college_id="test-college",
            collector_version="1.0.0",
            courses=[]
        )
        
        # Change to tmp directory for test
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(tmp_path)
            
            filepath = collector.save_output(schedule_data)
            
            assert filepath.exists()
            assert filepath.name.startswith("schedule_202570_")
            assert filepath.suffix == ".json"
            
            # Check latest symlink
            latest_path = filepath.parent / "schedule_202570_latest.json"
            assert latest_path.exists()
            
            # Verify content
            with open(filepath, 'r') as f:
                data = json.load(f)
            assert data['college_id'] == "test-college"
            assert data['term_code'] == "202570"
            
        finally:
            os.chdir(original_cwd)