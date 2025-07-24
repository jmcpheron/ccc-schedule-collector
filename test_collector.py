#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pytest",
#   "pytest-cov",
#   "requests",
#   "beautifulsoup4",
#   "pydantic>=2.0",
#   "pyyaml",
# ]
# ///
"""Test suite for Rio Hondo College schedule collector."""

import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pytest
import yaml

from models import Course, MeetingTime, Enrollment, ScheduleData
from utils.parser import RioHondoScheduleParser
from utils.storage import ScheduleStorage
from collect import RioHondoCollector


# Sample HTML for testing
SAMPLE_COURSE_HTML = """
<table>
<tr>
<td colspan="22" class="subject_header">ACCT - Accounting</td>
</tr>
<tr>
<td colspan="22" class="crn_header">ACCT 100 - Introduction to Accounting</td>
</tr>
<tr>
<td class="default1">Open</td>
<td valign="top" class="default1">LEC</td>
<td valign="top" class="default1"><a href="JavaScript:winOpen('pw_pub_sched.p_course_popup?vsub=ACCT&vcrse=100&vterm=202570&vcrn=75065')">75065</a></td>
<td valign="top" class="default1"><a href="JavaScript:winOpen('https://www.bkstr.com/webApp/discoverView?bookstore_id-1=890&term_id-1=202570&crn-1=75065')">View Book</a></td>
<td valign="top" class="default1"><img src="https://www.riohondo.edu/wp-content/uploads/2024/12/ZeroCostTextbook_Icon.png"></td>
<td align="center" nowrap="nowrap" valign="top" class="default1">3.0</td>
<td align="center" nowrap="nowrap" valign="top" class="default1"></td>
<td align="center" nowrap="nowrap" valign="top" class="default1">MW</td>
<td align="center" nowrap="nowrap" valign="top" class="default1">9:00 AM</td>
<td align="center" nowrap="nowrap" valign="top" class="default1">-</td>
<td align="center" nowrap="nowrap" valign="top" class="default1">10:50 AM</td>
<td align="center" nowrap="nowrap" valign="top" class="default1"></td>
<td align="center" nowrap="nowrap" valign="top" class="default1"></td>
<td align="center" nowrap="nowrap" valign="top" class="default1"></td>
<td nowrap="nowrap" valign="top" class="default1">A207</td>
<td align="center" nowrap="nowrap" valign="top" class="default1">30</td>
<td align="center" nowrap="nowrap" valign="top" class="default1">25</td>
<td align="center" nowrap="nowrap" valign="top" class="default1">5</td>
<td nowrap="nowrap" valign="top" class="default1">Smith, John</td>
<td nowrap="nowrap" valign="top" class="default1">jsmith@riohondo.edu</td>
<td align="center" nowrap="nowrap" valign="top" class="default1">01/13 - 05/23</td>
<td align="center" nowrap="nowrap" valign="top" class="default1">16</td>
</tr>
</table>
"""


class TestModels:
    """Test data models."""
    
    def test_meeting_time_model(self):
        """Test MeetingTime model."""
        mt = MeetingTime(
            days="MW",
            start_time="9:00 AM",
            end_time="10:50 AM",
            is_arranged=False
        )
        assert mt.days == "MW"
        assert mt.start_time == "9:00 AM"
        assert mt.end_time == "10:50 AM"
        assert not mt.is_arranged
    
    def test_enrollment_model(self):
        """Test Enrollment model."""
        enrollment = Enrollment(capacity=30, actual=25, remaining=5)
        assert enrollment.capacity == 30
        assert enrollment.actual == 25
        assert enrollment.remaining == 5
    
    def test_course_model(self):
        """Test Course model."""
        course = Course(
            crn="75065",
            subject="ACCT",
            course_number="100",
            title="Introduction to Accounting",
            units=3.0,
            instructor="Smith, John",
            instructor_email="jsmith@riohondo.edu",
            meeting_times=[MeetingTime(days="MW", start_time="9:00 AM", end_time="10:50 AM")],
            location="A207",
            enrollment=Enrollment(capacity=30, actual=25, remaining=5),
            status="Open",
            section_type="LEC",
            zero_textbook_cost=True,
            delivery_method="In-Person",
            weeks=16,
            start_date="01/13",
            end_date="05/23"
        )
        assert course.crn == "75065"
        assert course.subject == "ACCT"
        assert course.zero_textbook_cost is True
    
    def test_schedule_data_model(self):
        """Test ScheduleData model."""
        schedule = ScheduleData(
            term="Fall 2025",
            term_code="202570",
            collection_timestamp=datetime.now(),
            source_url="https://example.com",
            courses=[],
            total_courses=0,
            departments=[]
        )
        assert schedule.term == "Fall 2025"
        assert schedule.term_code == "202570"


class TestParser:
    """Test HTML parser."""
    
    def setup_method(self):
        """Set up test parser."""
        self.parser = RioHondoScheduleParser()
    
    def test_parse_subject_header(self):
        """Test parsing subject header."""
        from bs4 import BeautifulSoup
        html = '<td class="subject_header">ACCT - Accounting</td>'
        soup = BeautifulSoup(html, 'html.parser')
        header = soup.find('td', class_='subject_header')
        
        self.parser._parse_subject_header(header)
        assert self.parser.current_subject == "ACCT"
    
    def test_parse_course_header(self):
        """Test parsing course header."""
        from bs4 import BeautifulSoup
        html = '<td class="crn_header">ACCT 100 - Introduction to Accounting</td>'
        soup = BeautifulSoup(html, 'html.parser')
        header = soup.find('td', class_='crn_header')
        
        self.parser._parse_course_header(header)
        assert self.parser.current_course_title == "ACCT 100 - Introduction to Accounting"
    
    def test_parse_course_code(self):
        """Test parsing course code."""
        subject, number = self.parser._parse_course_code("ACCT 100 - Introduction to Accounting")
        assert subject == "ACCT"
        assert number == "100"
    
    def test_extract_course_title(self):
        """Test extracting course title."""
        title = self.parser._extract_course_title("ACCT 100 - Introduction to Accounting")
        assert title == "Introduction to Accounting"
    
    def test_parse_units(self):
        """Test parsing units."""
        assert self.parser._parse_units("3.0") == 3.0
        assert self.parser._parse_units("  4.0  ") == 4.0
        assert self.parser._parse_units("invalid") == 0.0
    
    def test_parse_date_range(self):
        """Test parsing date range."""
        start, end = self.parser._parse_date_range("01/13 - 05/23")
        assert start == "01/13"
        assert end == "05/23"
    
    def test_determine_delivery_method(self):
        """Test determining delivery method."""
        assert self.parser._determine_delivery_method("Online ASYNC", []) == "Online ASYNC"
        assert self.parser._determine_delivery_method("A207", []) == "In-Person"
        assert self.parser._determine_delivery_method("Hybrid", []) == "Hybrid"
    
    def test_parse_schedule_html(self):
        """Test parsing complete schedule HTML."""
        schedule_data = self.parser.parse_schedule_html(
            SAMPLE_COURSE_HTML,
            "Fall 2025",
            "202570",
            "https://example.com"
        )
        
        assert len(schedule_data.courses) == 1
        course = schedule_data.courses[0]
        assert course.crn == "75065"
        assert course.subject == "ACCT"
        assert course.course_number == "100"
        assert course.units == 3.0
        assert course.zero_textbook_cost is True


class TestStorage:
    """Test storage utility."""
    
    def setup_method(self):
        """Set up test storage."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = ScheduleStorage(data_dir=self.temp_dir)
    
    def teardown_method(self):
        """Clean up test storage."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_save_and_load_schedule(self):
        """Test saving and loading schedule data."""
        # Create sample schedule data
        schedule = ScheduleData(
            term="Fall 2025",
            term_code="202570",
            collection_timestamp=datetime.now(),
            source_url="https://example.com",
            courses=[],
            total_courses=0,
            departments=[]
        )
        
        # Save schedule
        filepath = self.storage.save_schedule(schedule)
        assert Path(filepath).exists()
        
        # Load schedule
        loaded_schedule = self.storage.load_schedule(filepath)
        assert loaded_schedule.term == schedule.term
        assert loaded_schedule.term_code == schedule.term_code
    
    def test_list_schedules(self):
        """Test listing schedule files."""
        # Save multiple schedules
        for i in range(3):
            schedule = ScheduleData(
                term="Fall 2025",
                term_code="202570",
                collection_timestamp=datetime.now(),
                source_url="https://example.com",
                courses=[],
                total_courses=0,
                departments=[]
            )
            self.storage.save_schedule(schedule)
        
        # List schedules
        files = self.storage.list_schedules()
        assert len(files) >= 3
        
        # List by term code
        files = self.storage.list_schedules(term_code="202570")
        assert len(files) >= 3
    
    def test_get_latest_schedule(self):
        """Test getting latest schedule file."""
        # Initially no files
        assert self.storage.get_latest_schedule() is None
        
        # Save a schedule
        schedule = ScheduleData(
            term="Fall 2025",
            term_code="202570",
            collection_timestamp=datetime.now(),
            source_url="https://example.com",
            courses=[],
            total_courses=0,
            departments=[]
        )
        self.storage.save_schedule(schedule)
        
        # Should find the file
        latest = self.storage.get_latest_schedule()
        assert latest is not None


class TestCollector:
    """Test main collector."""
    
    def setup_method(self):
        """Set up test collector."""
        # Create temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.yml"
        
        config = {
            'rio_hondo': {
                'base_url': 'https://example.com',
                'schedule_endpoint': 'schedule',
                'current_term': {'code': '202570', 'name': 'Fall 2025'},
                'terms': [{'code': '202570', 'name': 'Fall 2025'}],
                'departments': ['ACCT'],
                'search_params': {}
            },
            'collection': {
                'max_retries': 3,
                'timeout': 60,
                'request_delay': 0,
                'user_agent': 'Test',
                'verify_ssl': True
            },
            'output': {
                'data_dir': str(Path(self.temp_dir) / 'data'),
                'filename_pattern': 'schedule_{term_code}_{timestamp}.json',
                'create_latest_link': True,
                'compression': 'none'
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def teardown_method(self):
        """Clean up test collector."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('collect.requests.Session')
    def test_collector_init(self, mock_session):
        """Test collector initialization."""
        collector = RioHondoCollector(self.config_path)
        assert collector.config is not None
        assert collector.parser is not None
        assert collector.storage is not None
    
    @patch('collect.RioHondoCollector._fetch_schedule_page')
    def test_collect_schedule(self, mock_fetch):
        """Test schedule collection."""
        mock_fetch.return_value = SAMPLE_COURSE_HTML
        
        collector = RioHondoCollector(self.config_path)
        schedule_data = collector.collect_schedule()
        
        assert schedule_data is not None
        assert len(schedule_data.courses) == 1
        assert schedule_data.term == "Fall 2025"


def test_integration():
    """Basic integration test."""
    # This would test the full flow with a real HTML file
    # For now, just verify imports work
    assert RioHondoCollector is not None
    assert RioHondoScheduleParser is not None
    assert ScheduleStorage is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])