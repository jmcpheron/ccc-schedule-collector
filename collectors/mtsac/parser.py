"""Mt. San Antonio College JSON response parser for Banner 9 API data."""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models import ScheduleData, Course, MeetingTime, Enrollment


logger = logging.getLogger(__name__)


class MtSacScheduleParser:
    """Parser for Mt SAC's Banner 9 JSON API responses."""
    
    def __init__(self):
        """Initialize the parser."""
        self.courses_parsed = 0
        self.parsing_errors = []
        
    def parse_courses_json(self, courses_data: List[Dict[str, Any]], 
                          term_name: str, term_code: str, source_url: str) -> ScheduleData:
        """Parse JSON course data from Banner 9 API into ScheduleData format.
        
        Args:
            courses_data: List of course dictionaries from API
            term_name: Human-readable term name
            term_code: Term code
            source_url: Source URL for the data
            
        Returns:
            ScheduleData object with parsed courses
        """
        logger.info(f"Parsing {len(courses_data)} courses from JSON API")
        
        courses = []
        self.courses_parsed = 0
        self.parsing_errors = []
        
        for course_data in courses_data:
            try:
                course = self._parse_single_course(course_data)
                if course:
                    courses.append(course)
                    self.courses_parsed += 1
            except Exception as e:
                crn = 'unknown'
                if course_data and hasattr(course_data, 'get'):
                    crn = course_data.get('courseReferenceNumber', 'unknown')
                error_msg = f"Error parsing course CRN {crn}: {e}"
                logger.error(error_msg)
                self.parsing_errors.append(error_msg)
                continue
        
        logger.info(f"Successfully parsed {self.courses_parsed} courses")
        if self.parsing_errors:
            logger.warning(f"Had {len(self.parsing_errors)} parsing errors")
        
        # Create schedule data
        schedule_data = ScheduleData(
            term=term_name,
            term_code=term_code,
            collection_timestamp=datetime.now(timezone.utc),
            source_url=source_url,
            college_id="mtsac",  # Will be overridden by collector
            collector_version="1.0.0",  # Will be overridden by collector
            courses=courses,
            metadata={
                'parsing_stats': {
                    'total_raw_courses': len(courses_data),
                    'successfully_parsed': self.courses_parsed,
                    'parsing_errors': len(self.parsing_errors)
                },
                'parsing_errors': self.parsing_errors if self.parsing_errors else None
            }
        )
        
        return schedule_data
    
    def _parse_single_course(self, course_data: Dict[str, Any]) -> Optional[Course]:
        """Parse a single course from JSON data.
        
        Args:
            course_data: Course dictionary from Banner 9 API
            
        Returns:
            Course object or None if parsing fails
        """
        # Handle None input
        if course_data is None:
            return None
            
        # Required fields
        crn = course_data.get('courseReferenceNumber')
        subject = course_data.get('subject')
        course_number = course_data.get('courseNumber')
        title = course_data.get('courseTitle', '')
        
        if not all([crn, subject, course_number]):
            logger.warning(f"Missing required fields for course: {course_data}")
            return None
        
        # Credits - Banner 9 has separate low/high fields
        credits_low = course_data.get('creditHourLow', 0)
        credits_high = course_data.get('creditHourHigh', 0)
        units = float(credits_high) if credits_high else float(credits_low)
        
        # Enrollment information
        max_enrollment = course_data.get('maximumEnrollment', 0)
        current_enrollment = course_data.get('enrollment', 0) 
        seats_available = course_data.get('seatsAvailable', 0)
        
        enrollment = Enrollment(
            capacity=max_enrollment,
            actual=current_enrollment,
            remaining=seats_available
        )
        
        # Course status
        is_open = course_data.get('openSection', True)
        status = "Open" if is_open else "Closed"
        
        # Instructor information from faculty array
        instructor_name = self._extract_primary_instructor(course_data.get('faculty', []))
        
        # Meeting times from meetingsFaculty array
        meeting_times = self._extract_meeting_times(course_data.get('meetingsFaculty', []))
        
        # Location - extract from meeting times or use default
        location = self._extract_location(course_data.get('meetingsFaculty', []))
        
        # Section information
        sequence_number = course_data.get('sequenceNumber', '')
        section_type = self._determine_section_type(course_data)
        
        # Additional fields
        delivery_method = self._determine_delivery_method(course_data, meeting_times)
        weeks = self._extract_weeks(course_data)
        
        # Date information
        start_date, end_date = self._extract_dates(course_data)
        
        # Create course object
        course = Course(
            crn=str(crn),
            subject=subject,
            course_number=course_number,
            title=title.strip(),
            units=units,
            instructor=instructor_name,
            instructor_email=None,  # Not typically in bulk API response
            meeting_times=meeting_times,
            location=location,
            enrollment=enrollment,
            status=status,
            section_type=section_type,
            zero_textbook_cost=False,  # Would need to check attributes
            delivery_method=delivery_method,
            weeks=weeks,
            start_date=start_date,
            end_date=end_date,
            additional_hours=None,
            book_link=None
        )
        
        return course
    
    def _extract_primary_instructor(self, faculty_list: List[Dict[str, Any]]) -> str:
        """Extract the primary instructor name from faculty array.
        
        Args:
            faculty_list: List of faculty dictionaries
            
        Returns:
            Primary instructor name or "TBA"
        """
        if not faculty_list:
            return "TBA"
        
        # Look for primary instructor first
        for faculty in faculty_list:
            if faculty.get('primaryIndicator', False):
                return faculty.get('displayName', 'TBA').strip()
        
        # If no primary, use first instructor
        if faculty_list:
            return faculty_list[0].get('displayName', 'TBA').strip()
            
        return "TBA"
    
    def _extract_meeting_times(self, meetings_faculty: List[Dict[str, Any]]) -> List[MeetingTime]:
        """Extract meeting times from meetingsFaculty array.
        
        Args:
            meetings_faculty: List of meeting/faculty dictionaries
            
        Returns:
            List of MeetingTime objects
        """
        meeting_times = []
        
        for meeting_faculty in meetings_faculty:
            meeting_time_data = meeting_faculty.get('meetingTime', {})
            
            if not meeting_time_data:
                continue
                
            days = meeting_time_data.get('days', '')
            start_time = meeting_time_data.get('beginTime', '')
            end_time = meeting_time_data.get('endTime', '')
            
            # Handle arranged times
            is_arranged = not days or days.upper() in ['ARR', 'ARRANGED', 'TBA']
            
            # Format times
            formatted_start = self._format_time(start_time) if start_time else None
            formatted_end = self._format_time(end_time) if end_time else None
            
            meeting_time = MeetingTime(
                days=days or 'ARR',
                start_time=formatted_start,
                end_time=formatted_end,
                is_arranged=is_arranged
            )
            
            meeting_times.append(meeting_time)
        
        # If no meeting times found, add arranged placeholder
        if not meeting_times:
            meeting_times.append(MeetingTime(
                days='ARR',
                start_time=None,
                end_time=None,
                is_arranged=True
            ))
            
        return meeting_times
    
    def _extract_location(self, meetings_faculty: List[Dict[str, Any]]) -> str:
        """Extract location information from meetings.
        
        Args:
            meetings_faculty: List of meeting/faculty dictionaries
            
        Returns:
            Location string
        """
        locations = set()
        
        for meeting_faculty in meetings_faculty:
            meeting_time = meeting_faculty.get('meetingTime', {})
            
            building = meeting_time.get('building', '')
            room = meeting_time.get('room', '')
            campus = meeting_time.get('campusDescription', '')
            
            # Build location string
            location_parts = []
            if building and room:
                location_parts.append(f"{building} {room}")
            elif building:
                location_parts.append(building)
            elif room:
                location_parts.append(room)
                
            if campus and campus not in location_parts:
                location_parts.append(campus)
                
            if location_parts:
                locations.add(" - ".join(location_parts))
        
        if locations:
            return ", ".join(sorted(locations))
        
        return "TBA"
    
    def _determine_section_type(self, course_data: Dict[str, Any]) -> str:
        """Determine section type from course data.
        
        Args:
            course_data: Course dictionary
            
        Returns:
            Section type string
        """
        # Check if there's a section type field
        section_type = course_data.get('scheduleTypeDescription', '')
        if section_type:
            return section_type
            
        # Check course title for lab indicators
        title = course_data.get('courseTitle', '').upper()
        if 'LAB' in title:
            return 'LAB'
        elif 'LECTURE' in title:
            return 'LEC'
        elif 'SEMINAR' in title:
            return 'SEM'
        elif 'STUDIO' in title:
            return 'STU'
            
        return 'LEC'  # Default
    
    def _determine_delivery_method(self, course_data: Dict[str, Any], 
                                  meeting_times: List[MeetingTime]) -> str:
        """Determine delivery method from course and meeting data.
        
        Args:
            course_data: Course dictionary
            meeting_times: List of meeting times
            
        Returns:
            Delivery method string
        """
        # Check for instructional method in data
        method = course_data.get('instructionalMethodDescription', '')
        if method:
            if 'ONLINE' in method.upper():
                return 'Online'
            elif 'HYBRID' in method.upper():
                return 'Hybrid'
            elif 'DISTANCE' in method.upper():
                return 'Distance'
                
        # Infer from meeting times
        all_arranged = all(mt.is_arranged for mt in meeting_times)
        if all_arranged:
            # Could be online or arranged - check title
            title = course_data.get('courseTitle', '').upper()
            if 'ONLINE' in title:
                return 'Online'
            return 'Arranged'
            
        return 'In-Person'
    
    def _extract_weeks(self, course_data: Dict[str, Any]) -> int:
        """Extract course length in weeks.
        
        Args:
            course_data: Course dictionary
            
        Returns:
            Number of weeks (default 16 for full semester)
        """
        # Check for part of term information
        part_of_term = course_data.get('partOfTermDescription', '')
        if part_of_term:
            # Common patterns
            if '8' in part_of_term and 'WEEK' in part_of_term.upper():
                return 8
            elif '12' in part_of_term and 'WEEK' in part_of_term.upper():
                return 12
            elif 'FIRST' in part_of_term.upper() or 'SECOND' in part_of_term.upper():
                return 8
                
        return 16  # Standard semester length
    
    def _extract_dates(self, course_data: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """Extract start and end dates.
        
        Args:
            course_data: Course dictionary
            
        Returns:
            Tuple of (start_date, end_date) strings or (None, None)
        """
        start_date = course_data.get('startDate')
        end_date = course_data.get('endDate')
        
        # Format dates if present
        if start_date:
            start_date = self._format_date(start_date)
        if end_date:
            end_date = self._format_date(end_date)
            
        return start_date, end_date
    
    def _format_time(self, time_str: str) -> Optional[str]:
        """Format time string to standard format.
        
        Args:
            time_str: Time string from API
            
        Returns:
            Formatted time string or None
        """
        if not time_str or time_str.upper() in ['TBA', 'ARR']:
            return None
            
        # Handle various time formats
        time_str = time_str.strip()
        
        # If already in HH:MM format, just add AM/PM if missing
        if re.match(r'^\d{1,2}:\d{2}$', time_str):
            hour = int(time_str.split(':')[0])
            if hour >= 12:
                return f"{time_str} PM"
            else:
                return f"{time_str} AM"
                
        # If in HHMM format, convert
        if re.match(r'^\d{3,4}$', time_str):
            if len(time_str) == 3:
                hour = int(time_str[0])
                minute = time_str[1:3]
            else:
                hour = int(time_str[:2])
                minute = time_str[2:4]
                
            period = "AM" if hour < 12 else "PM"
            if hour > 12:
                hour -= 12
            elif hour == 0:
                hour = 12
                
            return f"{hour}:{minute} {period}"
        
        return time_str  # Return as-is if we can't parse
    
    def _format_date(self, date_str: str) -> Optional[str]:
        """Format date string to consistent format.
        
        Args:
            date_str: Date string from API
            
        Returns:
            Formatted date string or None
        """
        if not date_str:
            return None
            
        # Try to parse common date formats and return as MM/DD/YYYY
        try:
            # Handle ISO format
            if 'T' in date_str:
                date_str = date_str.split('T')[0]
                
            # Try parsing YYYY-MM-DD
            if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                year, month, day = date_str.split('-')
                return f"{month}/{day}/{year}"
                
            return date_str  # Return as-is if we can't parse
            
        except Exception:
            return date_str
    
    def parse_course_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Parse additional course details from HTML endpoints.
        
        Args:
            details: Dictionary of HTML detail responses
            
        Returns:
            Dictionary of parsed detail fields
        """
        parsed_details = {}
        
        # Parse course description
        if details.get('description'):
            parsed_details['description'] = self._parse_description_html(details['description'])
            
        # Parse prerequisites
        if details.get('prerequisites'):
            parsed_details['prerequisites'] = self._parse_prerequisites_html(details['prerequisites'])
            
        # Parse corequisites  
        if details.get('corequisites'):
            parsed_details['corequisites'] = self._parse_corequisites_html(details['corequisites'])
            
        # Parse restrictions
        if details.get('restrictions'):
            parsed_details['restrictions'] = self._parse_restrictions_html(details['restrictions'])
            
        # Parse enrollment info
        if details.get('enrollment_info'):
            enrollment_details = self._parse_enrollment_html(details['enrollment_info'])
            parsed_details.update(enrollment_details)
            
        return parsed_details
    
    def _parse_description_html(self, html: str) -> Optional[str]:
        """Parse course description from HTML.
        
        Args:
            html: HTML response from getCourseDescription endpoint
            
        Returns:
            Course description text or None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            # Remove script and style tags
            for script in soup(["script", "style"]):
                script.decompose()
            # Get text and clean it up
            text = soup.get_text().strip()
            # Remove excessive whitespace
            text = re.sub(r'\s+', ' ', text)
            return text if text else None
        except Exception as e:
            logger.debug(f"Error parsing description HTML: {e}")
            return None
    
    def _parse_prerequisites_html(self, html: str) -> Optional[str]:
        """Parse prerequisites from HTML.
        
        Args:
            html: HTML response from getSectionPrerequisites endpoint
            
        Returns:
            Prerequisites text or None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            # Look for common prerequisite patterns
            text = soup.get_text().strip()
            text = re.sub(r'\s+', ' ', text)
            return text if text and text.lower() != 'none' else None
        except Exception as e:
            logger.debug(f"Error parsing prerequisites HTML: {e}")
            return None
    
    def _parse_corequisites_html(self, html: str) -> Optional[str]:
        """Parse corequisites from HTML.
        
        Args:
            html: HTML response from getCorequisites endpoint
            
        Returns:
            Corequisites text or None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text().strip()
            text = re.sub(r'\s+', ' ', text)
            return text if text and text.lower() != 'none' else None
        except Exception as e:
            logger.debug(f"Error parsing corequisites HTML: {e}")
            return None
    
    def _parse_restrictions_html(self, html: str) -> Optional[str]:
        """Parse restrictions from HTML.
        
        Args:
            html: HTML response from getRestrictions endpoint
            
        Returns:
            Restrictions text or None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text().strip()
            text = re.sub(r'\s+', ' ', text)
            return text if text and text.lower() != 'none' else None
        except Exception:
            return None
    
    def _parse_enrollment_html(self, html: str) -> Dict[str, Any]:
        """Parse enrollment information from HTML.
        
        Args:
            html: HTML response from getEnrollmentInfo endpoint
            
        Returns:
            Dictionary with enrollment details
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            # This would need to be customized based on the actual HTML structure
            # Return empty dict for now
            return {}
        except Exception:
            return {}