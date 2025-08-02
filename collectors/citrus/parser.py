"""HTML parser for Citrus College schedule data."""

import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from bs4 import BeautifulSoup

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models import Course, MeetingTime, Enrollment, ScheduleData

logger = logging.getLogger(__name__)


class CitrusScheduleParser:
    """Parser for Citrus College's HTML schedule format."""
    
    def parse_schedule_html(self, html_content: str, term_name: str, 
                           term_code: str, source_url: str) -> ScheduleData:
        """Parse the HTML schedule page into structured data.
        
        Args:
            html_content: Raw HTML content from the schedule page
            term_name: Human-readable term name
            term_code: Term code
            source_url: URL where the data was fetched from
            
        Returns:
            ScheduleData object with parsed courses
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        courses = []
        
        # Find the main schedule table
        schedule_table = soup.find('table', class_='datadisplaytable')
        
        if not schedule_table:
            logger.warning("Could not find schedule table in HTML")
            return ScheduleData(
                term=term_name,
                term_code=term_code,
                collection_timestamp=datetime.now(),
                source_url=source_url,
                college_id='citrus',
                collector_version='1.0.0',
                courses=[]
            )
        
        # Parse table rows
        rows = schedule_table.find_all('tr')
        current_subject = None
        current_course_info = None
        
        for i, row in enumerate(rows):
            try:
                # Check if this is a subject header row (MATH - Mathematics)
                cells = row.find_all('td')
                if cells and 'deheader' in cells[0].get('class', []):
                    header_text = cells[0].get_text(strip=True)
                    
                    # Check for subject line (e.g., "MATH - Mathematics")
                    subject_match = re.match(r'^([A-Z]+)\s*-\s*(.+)$', header_text)
                    if subject_match:
                        current_subject = subject_match.group(1)
                        continue
                    
                    # Check for course header (e.g., "MATH 075 - Co-Req Support for Pre-Calc")
                    course_match = re.match(r'^([A-Z]+)\s+(\d+[A-Z]?)\s*-\s*(.+)$', header_text)
                    if course_match:
                        current_course_info = {
                            'subject': course_match.group(1),
                            'course_number': course_match.group(2),
                            'title': course_match.group(3)
                        }
                        continue
                
                # Skip header rows with th elements
                if row.find('th'):
                    continue
                    
                # Parse course data row - must have the status cell
                if cells and len(cells) >= 15 and cells[0].get_text(strip=True):
                    # Check if this looks like a course row (has CRN in second cell)
                    crn_text = cells[1].get_text(strip=True)
                    if crn_text and crn_text.isdigit():
                        course = self._parse_course_row(cells, current_subject, current_course_info)
                        if course:
                            courses.append(course)
                        
            except Exception as e:
                logger.error(f"Error parsing row {i}: {e}")
                continue
        
        logger.info(f"Parsed {len(courses)} courses")
        
        return ScheduleData(
            term=term_name,
            term_code=term_code,
            collection_timestamp=datetime.now(),
            source_url=source_url,
            college_id='citrus',
            collector_version='1.0.0',
            courses=courses
        )
    
    def _parse_course_row(self, cells: List, current_subject: Optional[str], 
                         current_course_info: Optional[Dict[str, str]]) -> Optional[Course]:
        """Parse a single course row.
        
        Args:
            cells: List of td elements from the row
            current_subject: Current subject context
            current_course_info: Current course info (subject, number, title)
            
        Returns:
            Course object or None if parsing fails
        """
        try:
            # Extract cell texts
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            
            # Citrus format has these columns:
            # 0: Status (OPEN, CLOSED, etc)
            # 1: CRN
            # 2: Subject
            # 3: Course Number
            # 4: Section
            # 5: Credits
            # 6: Meeting Time
            # 7: Location
            # 8: Capacity
            # 9: Actual (enrolled)
            # 10: Remaining
            # 11: Instructor
            # 12: Date
            # 13: Weeks
            # 14: Bookstore
            # 15: Zero Textbook Cost (if present)
            
            status_text = cell_texts[0] if len(cell_texts) > 0 else ""
            crn = cell_texts[1] if len(cell_texts) > 1 else ""
            subject = cell_texts[2] if len(cell_texts) > 2 else current_subject
            course_num = cell_texts[3] if len(cell_texts) > 3 else ""
            section = cell_texts[4] if len(cell_texts) > 4 else ""
            units = cell_texts[5] if len(cell_texts) > 5 else "0"
            meeting_time = cell_texts[6] if len(cell_texts) > 6 else ""
            location = cell_texts[7] if len(cell_texts) > 7 else ""
            capacity = cell_texts[8] if len(cell_texts) > 8 else "0"
            actual = cell_texts[9] if len(cell_texts) > 9 else "0"
            remaining = cell_texts[10] if len(cell_texts) > 10 else "0"
            instructor = cell_texts[11] if len(cell_texts) > 11 else "Staff"
            dates = cell_texts[12] if len(cell_texts) > 12 else ""
            weeks = cell_texts[13] if len(cell_texts) > 13 else "16"
            
            # Skip if no CRN
            if not crn or not crn.isdigit():
                return None
            
            # Use course info if available
            if current_course_info:
                title = current_course_info.get('title', '')
                if not subject:
                    subject = current_course_info.get('subject', '')
                if not course_num:
                    course_num = current_course_info.get('course_number', '')
            else:
                title = f"{subject} {course_num}"
            
            # Parse meeting times from the combined time string
            days, time = self._split_meeting_time(meeting_time)
            meeting_times = self._parse_meeting_times(days, time)
            
            # Parse enrollment
            try:
                cap = int(capacity) if capacity.isdigit() else 30
                act = int(actual) if actual.isdigit() else 0
                rem = int(remaining) if remaining.isdigit() else 0
            except:
                cap, act, rem = 30, 0, 30
                
            enrollment = Enrollment(
                capacity=cap,
                actual=act,
                remaining=rem
            )
            
            # Determine status from status text
            status = "Open" if "OPEN" in status_text.upper() else "Closed"
            
            # Determine delivery method
            delivery_method = self._determine_delivery_method(location, days, time)
            
            # Check for zero textbook cost
            ztc = self._check_zero_textbook_cost(cells, cell_texts)
            
            # Parse weeks
            try:
                weeks_num = int(weeks) if weeks.isdigit() else 16
            except:
                weeks_num = 16
            
            # Create course object
            return Course(
                crn=crn,
                subject=subject or current_subject or "UNK",
                course_number=course_num,
                title=title,
                units=float(units) if units.replace('.', '').isdigit() else 0.0,
                instructor=instructor,
                meeting_times=meeting_times,
                location=location,
                enrollment=enrollment,
                status=status,
                section_type=self._determine_section_type(course_num),
                zero_textbook_cost=ztc,
                delivery_method=delivery_method,
                weeks=weeks_num,
                start_date=self._parse_date(dates, True) if dates else None,
                end_date=self._parse_date(dates, False) if dates else None
            )
            
        except Exception as e:
            logger.error(f"Error parsing course row: {e}")
            return None
    
    def _parse_meeting_times(self, days: str, time: str) -> List[MeetingTime]:
        """Parse meeting days and times.
        
        Args:
            days: Days string (e.g., "MW", "TR")
            time: Time string (e.g., "9:00 AM - 10:50 AM")
            
        Returns:
            List of MeetingTime objects
        """
        meeting_times = []
        
        # Handle arranged/TBA times
        if 'arr' in time.lower() or 'tba' in time.lower() or not time:
            meeting_times.append(MeetingTime(
                days=days or "TBA",
                start_time=None,
                end_time=None,
                is_arranged=True
            ))
            return meeting_times
        
        # Parse time range
        time_match = re.match(r'(\d{1,2}:\d{2}\s*[APap][Mm])\s*-\s*(\d{1,2}:\d{2}\s*[APap][Mm])', time)
        if time_match:
            start_time = time_match.group(1).upper()
            end_time = time_match.group(2).upper()
            
            meeting_times.append(MeetingTime(
                days=days,
                start_time=start_time,
                end_time=end_time,
                is_arranged=False
            ))
        else:
            # Couldn't parse time, mark as arranged
            meeting_times.append(MeetingTime(
                days=days or "TBA",
                start_time=None,
                end_time=None,
                is_arranged=True
            ))
        
        return meeting_times
    
    def _parse_enrollment(self, cells: List) -> Enrollment:
        """Parse enrollment information from cells.
        
        Args:
            cells: List of td elements
            
        Returns:
            Enrollment object
        """
        # Default values
        capacity = 30
        actual = 0
        remaining = 30
        
        # Try to find enrollment data in cells
        for i, cell in enumerate(cells):
            text = cell.get_text(strip=True)
            
            # Look for patterns like "25/30" or "Closed"
            enrollment_match = re.search(r'(\d+)/(\d+)', text)
            if enrollment_match:
                actual = int(enrollment_match.group(1))
                capacity = int(enrollment_match.group(2))
                remaining = capacity - actual
                break
            
            # Check for individual capacity/enrolled cells
            if i < len(cells) - 2:
                try:
                    # Some systems have separate cells for cap/enrolled/available
                    if text.isdigit():
                        next_text = cells[i+1].get_text(strip=True) if i+1 < len(cells) else ""
                        if next_text.isdigit():
                            capacity = int(text)
                            actual = int(next_text)
                            remaining = capacity - actual
                            break
                except:
                    pass
        
        return Enrollment(
            capacity=capacity,
            actual=actual,
            remaining=max(0, remaining)
        )
    
    def _determine_delivery_method(self, location: str, days: str, time: str) -> str:
        """Determine the delivery method based on location and schedule.
        
        Args:
            location: Location string
            days: Days string
            time: Time string
            
        Returns:
            Delivery method string
        """
        location_lower = location.lower()
        
        if 'online' in location_lower:
            if 'sync' in location_lower:
                return "Online Synchronous"
            else:
                return "Online Asynchronous"
        elif 'hybrid' in location_lower:
            return "Hybrid"
        elif 'arr' in time.lower() or 'tba' in time.lower():
            return "Arranged"
        else:
            return "In-Person"
    
    def _determine_section_type(self, course_num: str) -> str:
        """Determine section type from course number.
        
        Args:
            course_num: Course number string
            
        Returns:
            Section type (LEC, LAB, etc.)
        """
        # Check for suffix indicators
        if course_num.endswith('L'):
            return "LAB"
        elif course_num.endswith('D'):
            return "DISC"
        else:
            return "LEC"
    
    def _check_zero_textbook_cost(self, cells: List, cell_texts: List[str]) -> bool:
        """Check if course has zero textbook cost.
        
        Args:
            cells: List of td elements
            cell_texts: List of cell text contents
            
        Returns:
            True if zero textbook cost
        """
        # Check for ZTC indicators in text
        for text in cell_texts:
            if 'ztc' in text.lower() or 'zero textbook' in text.lower():
                return True
        
        # Check for ZTC images or icons
        for cell in cells:
            img = cell.find('img', alt=re.compile('zero|ztc', re.I))
            if img:
                return True
        
        return False
    
    def _split_meeting_time(self, meeting_time: str) -> Tuple[str, str]:
        """Split meeting time into days and time components.
        
        Args:
            meeting_time: Combined string like "MW  02:25PM - 03:30PM"
            
        Returns:
            Tuple of (days, time)
        """
        if not meeting_time or meeting_time.strip() == "TBA":
            return "TBA", ""
            
        # Split by first space that's followed by a digit (time)
        match = re.match(r'^([A-Z]+)\s+(.+)$', meeting_time.strip())
        if match:
            return match.group(1), match.group(2)
        
        return "", meeting_time
    
    def _parse_date(self, date_str: str, start: bool) -> Optional[str]:
        """Parse start or end date from date string.
        
        Args:
            date_str: Date string like "08/19 - 12/13"
            start: True for start date, False for end date
            
        Returns:
            Date string or None
        """
        if not date_str or date_str == "TBA":
            return None
            
        # Split by dash
        parts = date_str.split('-')
        if len(parts) == 2:
            return parts[0].strip() if start else parts[1].strip()
            
        return None
    
    def build_course_detail_url(self, course: Course, term_code: str) -> str:
        """Build URL for course detail page.
        
        Args:
            course: Course object
            term_code: Term code
            
        Returns:
            URL string for course details
        """
        # This would need to be implemented based on Citrus's actual detail page structure
        # For now, return a placeholder
        base_url = "https://ssb.citruscollege.edu/PROD"
        return f"{base_url}/bwckschd.p_disp_detail_sched?term_in={term_code}&crn_in={course.crn}"