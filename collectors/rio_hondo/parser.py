#!/usr/bin/env python3
"""HTML parser for Rio Hondo College schedule pages."""

import re
import logging
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup, Tag
from datetime import datetime

from models import Course, MeetingTime, Enrollment, ScheduleData

logger = logging.getLogger(__name__)


class RioHondoScheduleParser:
    """Parser for Rio Hondo College schedule HTML pages."""
    
    def __init__(self):
        self.current_subject = None
        self.current_course_title = None
        
    def parse_schedule_html(self, html_content: str, term: str, term_code: str, source_url: str) -> ScheduleData:
        """Parse the entire schedule HTML and return ScheduleData object."""
        soup = BeautifulSoup(html_content, 'html.parser')
        courses = []
        
        # Process the entire document in order to maintain subject/course context
        all_rows = soup.find_all('tr')
        
        for row in all_rows:
            # Check for subject header
            subject_header = row.find('td', attrs={'class': re.compile(r'subject_header')})
            if subject_header:
                self._parse_subject_header(subject_header)
                continue
                
            # Check for course header
            course_header = row.find('td', class_='crn_header')
            if course_header:
                self._parse_course_header(course_header)
                continue
                
            # Check if it's a course data row
            if self._is_course_row(row):
                course = self._parse_course_row(row)
                if course:
                    courses.append(course)
        
        return ScheduleData(
            term=term,
            term_code=term_code,
            collection_timestamp=datetime.now(),
            source_url=source_url,
            college_id='rio-hondo',
            collector_version='1.0.0',
            courses=courses,
            total_courses=len(courses),
            departments=sorted(list(set(c.subject for c in courses)))
        )
    
    def _parse_subject_header(self, header: Tag):
        """Extract subject code from subject header."""
        text = header.get_text(strip=True)
        # Format: "ACCT - Accounting"
        match = re.match(r'^(\w+)\s*-', text)
        if match:
            self.current_subject = match.group(1)
            logger.debug(f"Found subject: {self.current_subject}")
    
    def _parse_course_header(self, header: Tag):
        """Extract course title from course header."""
        text = header.get_text(strip=True)
        # Format: "ACCT 101 - Financial Accounting"
        self.current_course_title = text
        logger.debug(f"Found course title: {self.current_course_title}")
    
    def _is_course_row(self, row: Tag) -> bool:
        """Check if a row contains course data."""
        # Look for rows with CRN links
        crn_link = row.find('a', href=re.compile(r'p_course_popup'))
        if crn_link:
            return True
        
        # Also check for td elements with class default1 or default2
        tds = row.find_all('td', class_=re.compile(r'default[12]'))
        # Course rows have many columns (20+) and include a CRN link
        return len(tds) >= 15 and crn_link is not None
    
    def _parse_course_row(self, row: Tag) -> Optional[Course]:
        """Parse a single course row."""
        try:
            tds = row.find_all('td')
            if len(tds) < 10:
                return None
            
            # Find all td elements
            tds = row.find_all('td')
            if len(tds) < 15:
                return None
                
            # Extract CRN from link (usually in 3rd column)
            crn_link = None
            crn = None
            for i, td in enumerate(tds[:5]):  # Check first 5 columns
                link = td.find('a', href=re.compile(r'p_course_popup'))
                if link:
                    crn = link.get_text(strip=True)
                    crn_link = link
                    break
            
            if not crn:
                return None
            
            # Parse course code and number from current course title
            subject, course_number = self._parse_course_code(self.current_course_title)
            if not subject:
                subject = self.current_subject or "UNKNOWN"
            
            # Rio Hondo format typically:
            # 0: Status, 1: Type, 2: CRN, 3: Book, 4: Zero cost, 5: Units,
            # 6-13: Meeting time info, 14: Location, 15: Cap, 16: Act, 17: Rem,
            # 18: Instructor, 19: Email, 20: Dates, 21: Weeks
            
            status = self._get_td_text(tds, 0)
            
            # Book link (column 3)
            book_link = None
            if len(tds) > 3:
                book_link_tag = tds[3].find('a')
                book_link = book_link_tag.get('href') if book_link_tag else None
            
            # Zero textbook cost (column 4)
            zero_textbook_cost = False
            if len(tds) > 4:
                ztc_img = tds[4].find('img')
                zero_textbook_cost = ztc_img is not None and 'ZeroCostTextbook' in ztc_img.get('src', '')
            
            # Units (column 5)
            units = self._parse_units(self._get_td_text(tds, 5))
            
            # Meeting time columns (columns 6-13)
            # Check if there's a colspan on the meeting time
            meeting_info = []
            if len(tds) > 6:
                # Check for colspan
                if tds[6].get('colspan'):
                    # This is a special case (like online courses with arranged hours)
                    meeting_text = self._get_td_text(tds, 6)
                    meeting_info = ['', '', '', '', '', '', '', meeting_text]
                else:
                    # Normal case - collect all 8 columns
                    for i in range(6, min(14, len(tds))):
                        meeting_info.append(self._get_td_text(tds, i))
            
            # Location (column 14)
            location = self._get_td_text(tds, 14) if len(tds) > 14 else ""
            
            # Enrollment info (columns 15, 16, 17)
            capacity = self._parse_int(self._get_td_text(tds, 15)) if len(tds) > 15 else 0
            actual = self._parse_int(self._get_td_text(tds, 16)) if len(tds) > 16 else 0
            remaining = self._parse_int(self._get_td_text(tds, 17)) if len(tds) > 17 else 0
            
            # Instructor (column 18)
            instructor = self._get_td_text(tds, 18) if len(tds) > 18 else "TBA"
            if not instructor or instructor.strip() == "":
                instructor = "TBA"
            
            # Instructor email (column 19)
            instructor_email = None
            if len(tds) > 19:
                email_link = tds[19].find('a', href=re.compile(r'mailto:'))
                if email_link:
                    instructor_email = email_link.get('href').replace('mailto:', '')
            
            # Dates (column 20)
            date_range = self._get_td_text(tds, 20) if len(tds) > 20 else ""
            start_date, end_date = self._parse_date_range(date_range)
            
            # Weeks (column 21)
            weeks = 16  # Default
            if len(tds) > 21:
                weeks_text = self._get_td_text(tds, 21)
                weeks = self._parse_int(weeks_text) or 16
            
            # Parse meeting times
            meeting_times = self._parse_meeting_times(meeting_info, location)
            
            # Determine delivery method
            delivery_method = self._determine_delivery_method(location, meeting_times)
            
            # Extract title from course header
            title = self._extract_course_title(self.current_course_title)
            
            # Determine section type
            section_type = "LEC"  # Default, could be enhanced to detect LAB, etc.
            
            return Course(
                crn=crn,
                subject=subject,
                course_number=course_number,
                title=title,
                units=units,
                instructor=instructor,
                instructor_email=instructor_email,
                meeting_times=meeting_times,
                location=location,
                enrollment=Enrollment(
                    capacity=capacity,
                    actual=actual,
                    remaining=remaining
                ),
                status=status,
                section_type=section_type,
                zero_textbook_cost=zero_textbook_cost,
                delivery_method=delivery_method,
                weeks=weeks,
                start_date=start_date,
                end_date=end_date,
                book_link=book_link
            )
            
        except Exception as e:
            logger.error(f"Error parsing course row: {e}")
            return None
    
    def _get_td_text(self, tds: List[Tag], index: int) -> str:
        """Safely get text from td element."""
        if index < len(tds):
            return tds[index].get_text(strip=True)
        return ""
    
    def _parse_course_code(self, course_header: str) -> tuple[str, str]:
        """Parse subject and course number from course header."""
        if not course_header:
            return ("", "")
        
        # Format: "ACCT 101 - Financial Accounting"
        match = re.match(r'^(\w+)\s+(\w+)\s*-', course_header)
        if match:
            return (match.group(1), match.group(2))
        return ("", "")
    
    def _extract_course_title(self, course_header: str) -> str:
        """Extract course title from course header."""
        if not course_header:
            return "Unknown Course"
        
        # Format: "ACCT 101 - Financial Accounting"
        parts = course_header.split(' - ', 1)
        if len(parts) > 1:
            return parts[1].strip()
        return course_header
    
    def _parse_units(self, units_text: str) -> float:
        """Parse units from text."""
        try:
            # Remove any non-numeric characters except decimal point
            clean_text = re.sub(r'[^\d.]', '', units_text)
            return float(clean_text) if clean_text else 0.0
        except:
            return 0.0
    
    def _parse_int(self, text: str) -> int:
        """Parse integer from text."""
        try:
            # Remove any non-numeric characters
            clean_text = re.sub(r'[^\d]', '', text)
            return int(clean_text) if clean_text else 0
        except:
            return 0
    
    def _parse_meeting_times(self, meeting_info: List[str], location: str) -> List[MeetingTime]:
        """Parse meeting time information from Rio Hondo format."""
        meeting_times = []
        
        # Check if this is an arranged/online course with special format
        meeting_text = ' '.join(meeting_info)
        if 'arr' in meeting_text.lower() or 'arr in addition' in meeting_text.lower():
            meeting_times.append(MeetingTime(
                days="ARR",
                start_time=None,
                end_time=None,
                is_arranged=True
            ))
            return meeting_times
        
        # Rio Hondo format: 8 columns for meeting time
        # Pattern: blank, day1, blank, day2, blank, blank, blank, time range
        # Example: ['', 'T', '', 'R', '', '', '', '11:10am - 12:35pm']
        
        if len(meeting_info) >= 8:
            # Extract days
            days_parts = []
            for i in [1, 3, 5]:  # Typical positions for day codes
                if i < len(meeting_info) and meeting_info[i].strip():
                    day = meeting_info[i].strip()
                    # Only add if it looks like a day code (M, T, W, R, F, S)
                    if day in ['M', 'T', 'W', 'R', 'F', 'S', 'MW', 'TR', 'MWF', 'MTWR', 'MTWRF']:
                        days_parts.append(day)
            
            days = ''.join(days_parts)
            
            # Extract time (usually in last position)
            time_str = meeting_info[7] if len(meeting_info) > 7 else ""
            
            # Parse regular scheduled times
            if days and time_str and '-' in time_str and ':' in time_str:
                # Parse time range like "11:10am - 12:35pm"
                time_parts = time_str.split('-')
                if len(time_parts) == 2:
                    start_time = time_parts[0].strip()
                    end_time = time_parts[1].strip()
                    meeting_times.append(MeetingTime(
                        days=days,
                        start_time=start_time,
                        end_time=end_time,
                        is_arranged=False
                    ))
        
        # If no meeting times found, mark as TBA/Arranged
        if not meeting_times:
            # Check location for online async
            if 'online' in location.lower() and 'async' in location.lower():
                meeting_times.append(MeetingTime(
                    days="ASYNC",
                    start_time=None,
                    end_time=None,
                    is_arranged=True
                ))
            else:
                meeting_times.append(MeetingTime(
                    days="TBA",
                    start_time=None,
                    end_time=None,
                    is_arranged=True
                ))
        
        return meeting_times
    
    def _parse_date_range(self, date_text: str) -> tuple[Optional[str], Optional[str]]:
        """Parse start and end dates from date range text."""
        if not date_text:
            return (None, None)
        
        # Format: "01/13 - 05/23"
        match = re.match(r'(\d{2}/\d{2})\s*-\s*(\d{2}/\d{2})', date_text)
        if match:
            return (match.group(1), match.group(2))
        
        return (None, None)
    
    def _determine_delivery_method(self, location: str, meeting_times: List[MeetingTime]) -> str:
        """Determine the delivery method based on location and meeting times."""
        location_lower = location.lower()
        
        if 'online' in location_lower and 'async' in location_lower:
            return "Online ASYNC"
        elif 'online' in location_lower and 'sync' in location_lower:
            return "Online SYNC"
        elif 'online' in location_lower:
            return "Online"
        elif 'hybrid' in location_lower:
            return "Hybrid"
        elif any(mt.is_arranged for mt in meeting_times):
            return "Arranged"
        else:
            return "In-Person"