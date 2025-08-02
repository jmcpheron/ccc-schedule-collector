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
        # Citrus might use different table structure than Rio Hondo
        schedule_table = soup.find('table', class_='datadisplaytable')
        if not schedule_table:
            # Try alternative selectors
            schedule_table = soup.find('table', {'summary': re.compile('schedule|course', re.I)})
        
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
        
        for row in rows:
            try:
                # Skip header rows
                if row.find('th'):
                    continue
                    
                # Check if this is a subject header row
                subject_header = row.find('td', class_='ddheader')
                if subject_header:
                    # Extract subject from header text
                    header_text = subject_header.get_text(strip=True)
                    subject_match = re.search(r'^([A-Z]+)', header_text)
                    if subject_match:
                        current_subject = subject_match.group(1)
                    continue
                
                # Parse course data row
                cells = row.find_all('td')
                if len(cells) >= 10:  # Minimum expected columns
                    course = self._parse_course_row(cells, current_subject)
                    if course:
                        courses.append(course)
                        
            except Exception as e:
                logger.error(f"Error parsing row: {e}")
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
    
    def _parse_course_row(self, cells: List, current_subject: Optional[str]) -> Optional[Course]:
        """Parse a single course row.
        
        Args:
            cells: List of td elements from the row
            current_subject: Current subject context
            
        Returns:
            Course object or None if parsing fails
        """
        try:
            # Extract cell texts
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            
            # Map cells to expected positions (may need adjustment based on actual HTML)
            crn = cell_texts[0] if len(cell_texts) > 0 else ""
            subject = cell_texts[1] if len(cell_texts) > 1 else current_subject
            course_num = cell_texts[2] if len(cell_texts) > 2 else ""
            section = cell_texts[3] if len(cell_texts) > 3 else ""
            units = cell_texts[4] if len(cell_texts) > 4 else "0"
            title = cell_texts[5] if len(cell_texts) > 5 else ""
            days = cell_texts[6] if len(cell_texts) > 6 else ""
            time = cell_texts[7] if len(cell_texts) > 7 else ""
            instructor = cell_texts[8] if len(cell_texts) > 8 else "Staff"
            location = cell_texts[9] if len(cell_texts) > 9 else ""
            
            # Skip if no CRN
            if not crn or not crn.isdigit():
                return None
            
            # Parse meeting times
            meeting_times = self._parse_meeting_times(days, time)
            
            # Parse enrollment (if available)
            enrollment = self._parse_enrollment(cells)
            
            # Determine delivery method
            delivery_method = self._determine_delivery_method(location, days, time)
            
            # Check for zero textbook cost
            ztc = self._check_zero_textbook_cost(cells, cell_texts)
            
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
                status="Open" if enrollment.remaining > 0 else "Closed",
                section_type=self._determine_section_type(course_num),
                zero_textbook_cost=ztc,
                delivery_method=delivery_method,
                weeks=16,  # Default, may need to parse from dates
                start_date=None,  # Would need to parse from schedule
                end_date=None
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