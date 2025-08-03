#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pytest>=7.0",
#   "pydantic>=2.0",
#   "requests",
#   "beautifulsoup4",
#   "requests-mock"
# ]
# ///
"""Tests for Mt. San Antonio College (Mt SAC) collector.

This module tests Mt SAC-specific functionality including:
- Banner 9 API workflow
- JSON response parsing  
- Session management with CSRF tokens
- Subject discovery
- Integration with base collector framework
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

import pytest
import requests_mock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.mtsac.collector import MtSacCollector
from collectors.mtsac.parser import MtSacScheduleParser
from models import ScheduleData, Course, MeetingTime, Enrollment


class TestMtSacCollector:
    """Tests for Mt SAC collector implementation."""
    
    # Expected subjects for Mt SAC
    MTSAC_EXPECTED_SUBJECTS = {
        'ACCT', 'ANTH', 'ART', 'ASTR', 'AUTO', 'BIOL', 'BUS', 'CHEM', 'COMM',
        'CS', 'ECON', 'ENGL', 'GEOL', 'HIST', 'MATH', 'MUS', 'PHIL', 'PHYS',
        'POLS', 'PSY', 'SOC', 'SPAN'
    }
    
    @pytest.fixture
    def config(self):
        """Load Mt SAC configuration."""
        config_path = Path("collectors/mtsac/config.json")
        with open(config_path, 'r') as f:
            return json.load(f)
    
    @pytest.fixture
    def collector(self):
        """Create Mt SAC collector instance."""
        return MtSacCollector()
    
    @pytest.fixture
    def parser(self):
        """Create Mt SAC parser instance."""
        return MtSacScheduleParser()
    
    @pytest.fixture
    def sample_banner9_course(self):
        """Sample Banner 9 course JSON response."""
        return {
            "courseReferenceNumber": "12345",
            "subject": "MATH",
            "courseNumber": "150",
            "sequenceNumber": "01",
            "courseTitle": "Calculus I",
            "creditHourLow": 4.0,
            "creditHourHigh": 4.0,
            "maximumEnrollment": 35,
            "enrollment": 28,
            "seatsAvailable": 7,
            "openSection": True,
            "faculty": [
                {
                    "displayName": "Smith, John",
                    "primaryIndicator": True
                }
            ],
            "meetingsFaculty": [
                {
                    "meetingTime": {
                        "beginTime": "0800",
                        "endTime": "0950",
                        "days": "MW",
                        "building": "BLDG5",
                        "room": "101",
                        "campusDescription": "Main Campus"
                    }
                }
            ],
            "scheduleTypeDescription": "LEC",
            "instructionalMethodDescription": "In-Person",
            "partOfTermDescription": "Full Semester",
            "startDate": "2025-08-25",
            "endDate": "2025-12-15"
        }
    
    def test_config_has_banner9_settings(self, config):
        """Test that Mt SAC config has Banner 9 specific settings."""
        # Check college ID
        assert config['college_id'] == 'mtsac'
        
        # Check Banner 9 specific URLs
        assert config['base_url'] == 'https://prodrg.mtsac.edu'
        assert config['ssb_path'] == '/StudentRegistrationSsb/ssb'
        
        # Check API configuration
        assert 'api_config' in config
        api_config = config['api_config']
        assert api_config['page_size'] == 500
        assert 'max_pages' in api_config
        
        # Check Banner 9 features
        assert 'banner9_features' in config
        banner9_features = config['banner9_features']
        assert banner9_features['requires_csrf_token'] is True
        assert banner9_features['requires_term_handshake'] is True
        assert banner9_features['supports_pagination'] is True
        
        # Check endpoints
        assert 'endpoints' in config
        endpoints = config['endpoints']
        assert 'search_results' in endpoints
        assert 'term_search' in endpoints
        assert 'course_details' in endpoints
    
    def test_config_has_subject_lists(self, config):
        """Test that Mt SAC config has proper subject lists."""
        # Check all_subjects exists and is populated
        assert 'all_subjects' in config
        assert isinstance(config['all_subjects'], list)
        assert len(config['all_subjects']) > 0
        
        # Check subject_management section
        assert 'subject_management' in config
        subject_mgmt = config['subject_management']
        
        assert 'expected_subjects' in subject_mgmt
        assert isinstance(subject_mgmt['expected_subjects'], list)
        assert len(subject_mgmt['expected_subjects']) > 0
        
        # Check that expected subjects are a subset of all subjects
        all_subjects = set(config['all_subjects'])
        expected_subjects = set(subject_mgmt['expected_subjects'])
        assert expected_subjects.issubset(all_subjects), \
            f"Expected subjects not in all_subjects: {expected_subjects - all_subjects}"
    
    def test_collector_initialization(self, collector):
        """Test that collector initializes properly."""
        assert collector.college_id == 'mtsac'
        assert collector.collector_version == '1.0.0'
        assert collector.parser is not None
        assert isinstance(collector.parser, MtSacScheduleParser)
    
    def test_build_search_params(self, collector):
        """Test search parameter building for Banner 9 API."""
        term_code = "202580"
        offset = 0
        max_size = 500
        
        params = collector._build_search_params(term_code, offset, max_size)
        
        # Check required parameters
        assert params['txt_term'] == term_code
        assert params['pageOffset'] == offset
        assert params['pageMaxSize'] == max_size
        assert 'sortColumn' in params
        assert 'sortDirection' in params
        
        # Check that page size is capped at 500
        large_params = collector._build_search_params(term_code, 0, 1000)
        assert large_params['pageMaxSize'] == 500
    
    def test_get_term_name(self, collector):
        """Test term name lookup."""
        # Test known term
        term_name = collector._get_term_name("202580")
        assert term_name == "Fall 2025"
        
        # Test unknown term  
        unknown_term = collector._get_term_name("999999")
        assert unknown_term == "Term 999999"
    
    @patch('collectors.mtsac.collector.MtSacCollector._init_session')
    @patch('collectors.mtsac.collector.MtSacCollector._declare_term')
    @patch('collectors.mtsac.collector.MtSacCollector._fetch_all_courses')
    def test_fetch_data_workflow(self, mock_fetch_courses, mock_declare_term, 
                                mock_init_session, collector, sample_banner9_course):
        """Test the Banner 9 API workflow."""
        # Setup mocks
        mock_fetch_courses.return_value = [sample_banner9_course]
        
        # Call fetch_data
        result = collector.fetch_data("202580")
        
        # Verify workflow steps were called
        mock_init_session.assert_called_once()
        mock_declare_term.assert_called_once_with("202580")
        mock_fetch_courses.assert_called_once_with("202580")
        
        # Verify result
        assert result == [sample_banner9_course]
    
    def test_parser_json_course_parsing(self, parser, sample_banner9_course):
        """Test parsing a single Banner 9 course JSON."""
        course = parser._parse_single_course(sample_banner9_course)
        
        assert course is not None
        assert course.crn == "12345"
        assert course.subject == "MATH"
        assert course.course_number == "150"
        assert course.title == "Calculus I"
        assert course.units == 4.0
        assert course.instructor == "Smith, John"
        assert course.status == "Open"
        assert course.section_type == "LEC"
        
        # Check enrollment
        assert course.enrollment.capacity == 35
        assert course.enrollment.actual == 28
        assert course.enrollment.remaining == 7
        
        # Check meeting times
        assert len(course.meeting_times) == 1
        meeting = course.meeting_times[0]
        assert meeting.days == "MW"
        assert meeting.start_time == "8:00 AM"
        assert meeting.end_time == "9:50 AM"
        assert not meeting.is_arranged
        
        # Check location
        assert "BLDG5 101" in course.location
    
    def test_parser_handles_missing_fields(self, parser):
        """Test parser handles courses with missing fields gracefully."""
        minimal_course = {
            "courseReferenceNumber": "54321",
            "subject": "ENGL",
            "courseNumber": "101"
        }
        
        course = parser._parse_single_course(minimal_course)
        
        assert course is not None
        assert course.crn == "54321"
        assert course.subject == "ENGL"
        assert course.course_number == "101"
        assert course.title == ""
        assert course.instructor == "TBA"
        assert len(course.meeting_times) == 1
        assert course.meeting_times[0].is_arranged
    
    def test_parser_time_formatting(self, parser):
        """Test time formatting in parser."""
        # Test HHMM format
        assert parser._format_time("0800") == "8:00 AM"
        assert parser._format_time("1300") == "1:00 PM"
        assert parser._format_time("2359") == "11:59 PM"
        
        # Test H:MM format  
        assert parser._format_time("8:00") == "8:00 AM"
        assert parser._format_time("13:30") == "13:30 PM"
        
        # Test missing/arranged times
        assert parser._format_time("") is None
        assert parser._format_time("TBA") is None
        assert parser._format_time("ARR") is None
    
    def test_parser_full_schedule_parsing(self, parser, sample_banner9_course):
        """Test parsing full schedule data."""
        courses_data = [sample_banner9_course, sample_banner9_course.copy()]
        courses_data[1]["courseReferenceNumber"] = "67890"
        courses_data[1]["subject"] = "ENGL"
        
        schedule_data = parser.parse_courses_json(
            courses_data, 
            "Fall 2025", 
            "202580", 
            "https://example.com"
        )
        
        assert isinstance(schedule_data, ScheduleData)
        assert schedule_data.term == "Fall 2025"
        assert schedule_data.term_code == "202580"
        assert schedule_data.source_url == "https://example.com"
        assert len(schedule_data.courses) == 2
        
        # Check metadata
        assert schedule_data.metadata is not None
        assert 'parsing_stats' in schedule_data.metadata
        stats = schedule_data.metadata['parsing_stats']
        assert stats['total_raw_courses'] == 2
        assert stats['successfully_parsed'] == 2
    
    def test_parser_handles_parsing_errors(self, parser):
        """Test parser handles malformed course data."""
        bad_courses = [
            {"invalid": "data"},
            None,
            {"courseReferenceNumber": None}
        ]
        
        schedule_data = parser.parse_courses_json(
            bad_courses,
            "Fall 2025",
            "202580", 
            "https://example.com"
        )
        
        assert len(schedule_data.courses) == 0
        assert schedule_data.metadata['parsing_stats']['parsing_errors'] > 0
    
    @requests_mock.Mocker()
    def test_session_initialization_workflow(self, m, collector):
        """Test Banner 9 session initialization workflow."""
        # Mock term selection page with CSRF token
        csrf_html = '''
        <html>
        <head>
            <meta name="synchronizerToken" content="test-csrf-token-123">
        </head>
        <body>Term Selection</body>
        </html>
        '''
        
        m.get(
            "https://prodrg.mtsac.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search",
            text=csrf_html
        )
        
        # Call initialization
        collector._init_session()
        
        # Verify CSRF token was extracted
        assert collector.csrf_token == "test-csrf-token-123"
        assert collector.unique_session_id is not None
        assert collector.base_ssb_url == "https://prodrg.mtsac.edu/StudentRegistrationSsb/ssb"
    
    @requests_mock.Mocker()
    def test_term_declaration_workflow(self, m, collector):
        """Test Banner 9 term declaration workflow."""
        # Setup collector state
        collector.csrf_token = "test-token"
        collector.unique_session_id = "12345"
        collector.base_ssb_url = "https://prodrg.mtsac.edu/StudentRegistrationSsb/ssb"
        
        # Mock term declaration endpoint
        m.post(
            "https://prodrg.mtsac.edu/StudentRegistrationSsb/ssb/term/search",
            json={"success": True}
        )
        
        # Call term declaration
        collector._declare_term("202580")
        
        # Verify request was made with correct data
        assert m.called
        request = m.request_history[0]
        assert "X-Synchronizer-Token" in request.headers
        assert request.headers["X-Synchronizer-Token"] == "test-token"
        
        # Check form data
        assert "term=202580" in request.text
        assert "uniqueSessionId=12345" in request.text
    
    @requests_mock.Mocker()
    def test_course_search_pagination(self, m, collector, sample_banner9_course):
        """Test paginated course search."""
        # Setup collector state
        collector.csrf_token = "test-token"
        collector.unique_session_id = "12345"
        collector.base_ssb_url = "https://prodrg.mtsac.edu/StudentRegistrationSsb/ssb"
        
        # Mock first page (full page)
        page1_courses = [sample_banner9_course] * 500
        m.get(
            "https://prodrg.mtsac.edu/StudentRegistrationSsb/ssb/searchResults/searchResults",
            json={
                "success": True,
                "totalCount": 750,
                "data": page1_courses
            }
        )
        
        # Call fetch courses page
        result = collector._fetch_courses_page("202580", offset=0, max_size=500)
        
        # Verify result
        assert len(result) == 500
        assert result[0]["courseReferenceNumber"] == "12345"
        
        # Verify request parameters
        request = m.request_history[0]
        assert "txt_term=202580" in request.url
        assert "pageOffset=0" in request.url
        assert "pageMaxSize=500" in request.url
    
    def test_discover_subjects_functionality(self, collector):
        """Test subject discovery functionality."""
        with patch.object(collector, '_init_session'), \
             patch.object(collector, '_get_subjects') as mock_get_subjects:
            
            # Mock subjects response
            mock_subjects = [
                {"code": "MATH", "description": "Mathematics"},
                {"code": "ENGL", "description": "English"},
                {"code": "HIST", "description": "History"}
            ]
            mock_get_subjects.return_value = mock_subjects
            
            # Call discover subjects
            subjects = collector.discover_subjects("202580")
            
            # Verify result
            assert subjects == ["ENGL", "HIST", "MATH"]  # Should be sorted
            mock_get_subjects.assert_called_once_with("202580")
    
    def test_critical_subjects_in_expected(self, config):
        """Test that critical subjects are marked as expected."""
        critical_subjects = [
            'MATH', 'ENGL', 'BIOL', 'CHEM', 'PHYS', 'HIST', 
            'POLS', 'PSY', 'SOC', 'ART', 'MUS', 'SPAN'
        ]
        
        expected_subjects = set(config['subject_management']['expected_subjects'])
        
        for subject in critical_subjects:
            assert subject in expected_subjects, \
                f"Critical subject {subject} should be in expected_subjects"
    
    def test_integration_with_main_collector(self):
        """Test integration with main collect.py script."""
        from collect import COLLECTORS
        
        # Verify Mt SAC is in registry
        assert 'mtsac' in COLLECTORS
        
        # Test lazy loading
        collector_factory = COLLECTORS['mtsac']
        assert callable(collector_factory)
        
        collector_class = collector_factory()
        assert collector_class == MtSacCollector
        
        # Test instantiation
        collector = collector_class()
        assert isinstance(collector, MtSacCollector)


class TestMtSacParserEdgeCases:
    """Test Mt SAC parser edge cases and error handling."""
    
    @pytest.fixture
    def parser(self):
        return MtSacScheduleParser()
    
    def test_parse_arranged_meeting_times(self, parser):
        """Test parsing courses with arranged meeting times."""
        course_data = {
            "courseReferenceNumber": "11111",
            "subject": "MATH",
            "courseNumber": "999",
            "courseTitle": "Independent Study",
            "meetingsFaculty": [
                {
                    "meetingTime": {
                        "days": "ARR",
                        "beginTime": "",
                        "endTime": "",
                        "building": "",
                        "room": "",
                        "campusDescription": "Main Campus"
                    }
                }
            ]
        }
        
        course = parser._parse_single_course(course_data)
        assert course is not None
        assert len(course.meeting_times) == 1
        assert course.meeting_times[0].is_arranged
        assert course.meeting_times[0].days == "ARR"
    
    def test_parse_multiple_instructors(self, parser):
        """Test parsing courses with multiple instructors."""
        course_data = {
            "courseReferenceNumber": "22222",
            "subject": "ENGL", 
            "courseNumber": "100",
            "courseTitle": "English Composition",
            "faculty": [
                {"displayName": "Smith, John", "primaryIndicator": False},
                {"displayName": "Doe, Jane", "primaryIndicator": True},
                {"displayName": "Johnson, Bob", "primaryIndicator": False}
            ]
        }
        
        course = parser._parse_single_course(course_data)
        assert course is not None
        assert course.instructor == "Doe, Jane"  # Should pick primary instructor
    
    def test_parse_online_course(self, parser):
        """Test parsing online course delivery method.""" 
        course_data = {
            "courseReferenceNumber": "33333",
            "subject": "CS",
            "courseNumber": "101", 
            "courseTitle": "Intro to Programming",
            "instructionalMethodDescription": "ONLINE ASYNCHRONOUS",
            "meetingsFaculty": []
        }
        
        course = parser._parse_single_course(course_data)
        assert course is not None
        assert course.delivery_method == "Online"
        assert len(course.meeting_times) == 1
        assert course.meeting_times[0].is_arranged
    
    def test_parse_hybrid_course(self, parser):
        """Test parsing hybrid course delivery method."""
        course_data = {
            "courseReferenceNumber": "44444",
            "subject": "BIOL",
            "courseNumber": "101",
            "courseTitle": "Biology Fundamentals", 
            "instructionalMethodDescription": "HYBRID",
            "meetingsFaculty": [
                {
                    "meetingTime": {
                        "days": "W",
                        "beginTime": "1400",
                        "endTime": "1650", 
                        "building": "SCI",
                        "room": "201"
                    }
                }
            ]
        }
        
        course = parser._parse_single_course(course_data)
        assert course is not None
        assert course.delivery_method == "Hybrid"