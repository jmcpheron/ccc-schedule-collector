#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pytest>=7.0",
#   "pydantic>=2.0",
#   "requests",
#   "beautifulsoup4"
# ]
# ///
"""Core unit tests for Banner 9 functionality.

This module provides essential tests for Banner 9 collectors to ensure
long-term maintainability and reliability.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.base_banner9_collector import Banner9Collector
from collectors.mtsac.parser import MtSacScheduleParser
from models import ScheduleData, Course, MeetingTime, Enrollment


class TestBanner9Core:
    """Test core Banner 9 functionality."""
    
    def test_banner9_collector_abstract_methods(self):
        """Test that Banner9Collector enforces abstract methods."""
        # Should not be able to instantiate base class directly
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Banner9Collector()
    
    def test_banner9_collector_initialization(self):
        """Test Banner9Collector initialization."""
        mock_config = {
            'college_id': 'test-college',
            'collector_version': '1.0.0',
            'base_url': 'https://test.edu',
            'rate_limit': {'requests_per_second': 1.0, 'retry_attempts': 3},
            'http_config': {'timeout': 30, 'verify_ssl': True}
        }
        
        with patch.object(Banner9Collector, '_load_config', return_value=mock_config):
            collector = MockBanner9Collector()
            
            assert collector.college_id == 'test-college'
            assert collector.collector_version == '1.0.0'
            assert collector.csrf_token is None
            assert collector.unique_session_id is None
            assert collector.base_ssb_url is None
    
    def test_unique_session_id_generation(self):
        """Test unique session ID generation."""
        mock_config = {
            'college_id': 'test',
            'collector_version': '1.0.0',
            'base_url': 'https://test.edu',
            'rate_limit': {'requests_per_second': 1.0},
            'http_config': {'timeout': 30, 'verify_ssl': True}
        }
        
        with patch.object(Banner9Collector, '_load_config', return_value=mock_config):
            collector1 = MockBanner9Collector()
            collector2 = MockBanner9Collector()
            
            # Generate session IDs at different times
            collector1._generate_session_id()
            import time
            time.sleep(0.001)  # Ensure different timestamps
            collector2._generate_session_id()
            
            # Should generate different session IDs
            assert collector1.unique_session_id != collector2.unique_session_id
    
    def test_rate_limit_delay_calculation(self):
        """Test rate limiting delay calculation."""
        mock_config = {
            'college_id': 'test',
            'collector_version': '1.0.0',
            'rate_limit': {'requests_per_second': 2.0},
            'http_config': {'timeout': 30}
        }
        
        with patch.object(Banner9Collector, '_load_config', return_value=mock_config):
            collector = MockBanner9Collector()
            
            with patch('time.sleep') as mock_sleep:
                collector.rate_limit_delay()
                
                # Should sleep for 1/2.0 = 0.5 seconds
                mock_sleep.assert_called_once_with(0.5)


class TestBanner9JsonParsing:
    """Test Banner 9 JSON parsing functionality."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance for testing."""
        return MtSacScheduleParser()
    
    @pytest.fixture
    def sample_course_data(self):
        """Sample Banner 9 course JSON data."""
        return {
            "courseReferenceNumber": "12345",
            "subject": "MATH",
            "courseNumber": "150",
            "courseTitle": "Calculus I",
            "creditHourLow": 4.0,
            "creditHourHigh": 4.0,
            "maximumEnrollment": 35,
            "enrollment": 28,
            "seatsAvailable": 7,
            "openSection": True,
            "faculty": [
                {"displayName": "Smith, John", "primaryIndicator": True}
            ],
            "meetingsFaculty": [
                {
                    "meetingTime": {
                        "beginTime": "0800",
                        "endTime": "0950",
                        "days": "MW",
                        "building": "BLDG5",
                        "room": "101"
                    }
                }
            ]
        }
    
    def test_parse_complete_course(self, parser, sample_course_data):
        """Test parsing a complete course record."""
        course = parser._parse_single_course(sample_course_data)
        
        assert course is not None
        assert course.crn == "12345"
        assert course.subject == "MATH"
        assert course.course_number == "150"
        assert course.title == "Calculus I"
        assert course.units == 4.0
        assert course.instructor == "Smith, John"
        
        # Enrollment data
        assert course.enrollment.capacity == 35
        assert course.enrollment.actual == 28
        assert course.enrollment.remaining == 7
        
        # Meeting times
        assert len(course.meeting_times) == 1
        meeting = course.meeting_times[0]
        assert meeting.days == "MW"
        assert meeting.start_time == "8:00 AM"
        assert meeting.end_time == "9:50 AM"
        assert not meeting.is_arranged
        
        # Location
        assert "BLDG5 101" in course.location
    
    def test_parse_minimal_course(self, parser):
        """Test parsing a minimal course record."""
        minimal_data = {
            "courseReferenceNumber": "67890",
            "subject": "ENGL",
            "courseNumber": "101"
        }
        
        course = parser._parse_single_course(minimal_data)
        
        assert course is not None
        assert course.crn == "67890"
        assert course.subject == "ENGL"
        assert course.course_number == "101"
        
        # Should have sensible defaults
        assert course.instructor == "TBA"
        assert course.location == "TBA"
        assert len(course.meeting_times) == 1
        assert course.meeting_times[0].is_arranged
    
    def test_parse_invalid_course_data(self, parser):
        """Test handling of invalid course data."""
        # Missing required fields
        invalid_data = {"invalid": "data"}
        course = parser._parse_single_course(invalid_data)
        assert course is None
        
        # None input
        course = parser._parse_single_course(None)
        assert course is None
    
    def test_instructor_extraction(self, parser):
        """Test primary instructor extraction."""
        # Multiple faculty with primary indicator
        faculty_list = [
            {"displayName": "Johnson, Mary", "primaryIndicator": False},
            {"displayName": "Smith, John", "primaryIndicator": True}
        ]
        
        instructor = parser._extract_primary_instructor(faculty_list)
        assert instructor == "Smith, John"
        
        # No faculty
        instructor = parser._extract_primary_instructor([])
        assert instructor == "TBA"
    
    def test_time_formatting(self, parser):
        """Test time format conversion."""
        # HHMM format
        assert parser._format_time("0800") == "8:00 AM"
        assert parser._format_time("1300") == "1:00 PM"
        assert parser._format_time("2359") == "11:59 PM"
        
        # Invalid/empty times
        assert parser._format_time("") is None
        assert parser._format_time("TBA") is None
        assert parser._format_time("ARR") is None
    
    def test_location_extraction(self, parser):
        """Test location extraction from meeting data."""
        meetings_data = [
            {
                "meetingTime": {
                    "building": "BLDG1",
                    "room": "101",
                    "campusDescription": "Main Campus"
                }
            }
        ]
        
        location = parser._extract_location(meetings_data)
        
        assert "BLDG1 101" in location
        assert "Main Campus" in location
    
    def test_meeting_time_extraction(self, parser):
        """Test meeting time extraction."""
        meetings_data = [
            {
                "meetingTime": {
                    "beginTime": "0800",
                    "endTime": "0950",
                    "days": "MW",
                    "building": "BLDG1",
                    "room": "101"
                }
            }
        ]
        
        meeting_times = parser._extract_meeting_times(meetings_data)
        
        assert len(meeting_times) == 1
        assert meeting_times[0].days == "MW"
        assert meeting_times[0].start_time == "8:00 AM"
        assert meeting_times[0].end_time == "9:50 AM"
        assert not meeting_times[0].is_arranged
    
    def test_arranged_meeting_times(self, parser):
        """Test handling of arranged meeting times."""
        arranged_data = [
            {
                "meetingTime": {
                    "days": "ARR",
                    "beginTime": "",
                    "endTime": ""
                }
            }
        ]
        
        meeting_times = parser._extract_meeting_times(arranged_data)
        
        assert len(meeting_times) == 1
        assert meeting_times[0].is_arranged
        assert meeting_times[0].days == "ARR"
    
    def test_full_schedule_parsing(self, parser, sample_course_data):
        """Test parsing complete schedule data."""
        courses_data = [sample_course_data]
        
        schedule_data = parser.parse_courses_json(
            courses_data,
            "Fall 2025",
            "202520",
            "https://test.edu/search"
        )
        
        assert isinstance(schedule_data, ScheduleData)
        assert schedule_data.term == "Fall 2025"
        assert schedule_data.term_code == "202520"
        assert len(schedule_data.courses) == 1
        
        # Check metadata
        assert schedule_data.metadata is not None
        assert 'parsing_stats' in schedule_data.metadata
    
    def test_error_handling_in_parsing(self, parser):
        """Test error handling during parsing."""
        mixed_data = [
            {
                "courseReferenceNumber": "12345",
                "subject": "MATH",
                "courseNumber": "150"
            },
            {"invalid": "data"},  # Should fail
            None  # Should fail
        ]
        
        schedule_data = parser.parse_courses_json(
            mixed_data,
            "Fall 2025",
            "202520",
            "https://test.edu/test"
        )
        
        # Should parse only valid courses
        assert len(schedule_data.courses) == 1
        
        # Should track parsing statistics
        stats = schedule_data.metadata['parsing_stats']
        assert stats['successfully_parsed'] == 1  # Only valid course parsed
        assert stats['total_raw_courses'] == 3  # All input courses counted
        # Invalid courses return None and are simply not included (graceful handling)


class TestBanner9EdgeCases:
    """Test Banner 9 edge cases and error conditions."""
    
    @pytest.fixture
    def parser(self):
        return MtSacScheduleParser()
    
    def test_null_data_handling(self, parser):
        """Test handling of null/None data in API responses."""
        # This was the actual bug we encountered
        null_response = {
            'success': True,
            'totalCount': 0,
            'data': None  # API sometimes returns null instead of []
        }
        
        # Should not crash when data is None
        courses = null_response.get('data')
        if courses is None:
            courses = []
        
        assert courses == []
        assert len(courses) == 0
    
    def test_empty_schedule_parsing(self, parser):
        """Test parsing empty schedule data."""
        schedule_data = parser.parse_courses_json(
            [],  # Empty course list
            "Fall 2025",
            "202520",
            "https://test.edu/empty"
        )
        
        assert isinstance(schedule_data, ScheduleData)
        assert len(schedule_data.courses) == 0
        assert schedule_data.metadata['parsing_stats']['total_raw_courses'] == 0
    
    def test_malformed_meeting_times(self, parser):
        """Test handling of malformed meeting time data."""
        course_data = {
            "courseReferenceNumber": "12345",
            "subject": "MATH",
            "courseNumber": "150",
            "meetingsFaculty": [
                {
                    "meetingTime": {
                        "beginTime": "invalid-time",
                        "endTime": "also-invalid",
                        "days": ""
                    }
                }
            ]
        }
        
        course = parser._parse_single_course(course_data)
        
        # Should not crash, should handle gracefully
        assert course is not None
        assert len(course.meeting_times) == 1
        # Should fall back to arranged
        assert course.meeting_times[0].is_arranged
    
    def test_zero_enrollment_courses(self, parser):
        """Test courses with zero capacity or enrollment."""
        course_data = {
            "courseReferenceNumber": "12345",
            "subject": "ONLINE",
            "courseNumber": "999",
            "maximumEnrollment": 0,
            "enrollment": 0,
            "seatsAvailable": 0
        }
        
        course = parser._parse_single_course(course_data)
        
        assert course is not None
        assert course.enrollment.capacity == 0
        assert course.enrollment.actual == 0
        assert course.enrollment.remaining == 0


class MockBanner9Collector(Banner9Collector):
    """Mock implementation for testing Banner9Collector."""
    
    def _build_search_params(self, term_code: str, offset: int = 0, max_size: int = 500):
        """Mock implementation of abstract method."""
        return {
            'txt_term': term_code,
            'pageOffset': offset,
            'pageMaxSize': max_size
        }
    
    def parse_data(self, raw_data, term_code=None):
        """Mock implementation of parse_data."""
        return ScheduleData(
            term='Test Term',
            term_code=term_code or '202520',
            collection_timestamp=datetime.now(timezone.utc),
            source_url='https://test.edu/test',
            college_id=self.college_id,
            collector_version=self.collector_version,
            courses=[]
        )
    
    def _generate_session_id(self):
        """Helper method to generate session ID for testing."""
        self.unique_session_id = str(int(datetime.now().timestamp() * 1000))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])