"""Rio Hondo College schedule collector implementation."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

import requests

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from collectors.base_collector import BaseCollector
from models import ScheduleData, Course, DetailedCourse
from .parser import RioHondoScheduleParser


logger = logging.getLogger(__name__)


class RioHondoCollector(BaseCollector):
    """Collector for Rio Hondo College schedule data.
    
    This collector fetches schedule data from Rio Hondo's Banner 8 system
    and parses the HTML to extract course information.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize Rio Hondo collector.
        
        Args:
            config_path: Path to config.json or None to use default
        """
        # Set default config path to rio_hondo/config.json
        if config_path is None:
            config_path = Path(__file__).parent / 'config.json'
            
        super().__init__(config_path)
        self.parser = RioHondoScheduleParser()
        
    def fetch_data(self, term_code: Optional[str] = None) -> str:
        """Fetch raw HTML data from Rio Hondo's schedule system.
        
        This implements a two-phase process:
        1. POST to p_search endpoint to select term
        2. POST to p_listthislist endpoint to get course data
        
        Args:
            term_code: Term code to fetch or None for current term
            
        Returns:
            HTML content as string
        """
        # Use provided term or get from config
        if not term_code:
            term_code = self.config['current_term']['code']
            
        logger.info(f"Fetching data for term {term_code}")
        
        # Phase 1: Select term
        self._select_term(term_code)
        
        # Phase 2: Fetch schedule data
        base_url = self.config['base_url']
        endpoint = self.config['schedule_endpoint']
        url = f"{base_url}/{endpoint}"
        
        # Get departments to collect
        departments = self.config['departments']
        
        if departments == ["ALL"]:
            # Collect all departments in one request
            return self._fetch_schedule_page(url, term_code, subject="ALL")
        else:
            # For specific departments, we'll need to handle this differently
            # For now, just collect the first department
            if departments:
                return self._fetch_schedule_page(url, term_code, subject=departments[0])
            else:
                raise ValueError("No departments configured")
    
    def parse_data(self, raw_data: str, term_code: Optional[str] = None) -> ScheduleData:
        """Parse HTML data into ScheduleData format.
        
        Args:
            raw_data: HTML content from fetch_data
            term_code: Term code being processed
            
        Returns:
            ScheduleData object with parsed courses
        """
        # Get term info
        if not term_code:
            term_code = self.config['current_term']['code']
            
        term_name = self._get_term_name(term_code)
        
        # Build source URL for reference
        base_url = self.config['base_url']
        endpoint = self.config['schedule_endpoint']
        source_url = f"{base_url}/{endpoint}"
        
        # Parse the HTML
        logger.info("Parsing schedule HTML")
        schedule_data = self.parser.parse_schedule_html(
            raw_data,
            term_name,
            term_code,
            source_url
        )
        
        # Add required fields
        schedule_data.college_id = self.college_id
        schedule_data.collector_version = self.collector_version
        
        # Move total_courses and departments to metadata
        if not schedule_data.metadata:
            schedule_data.metadata = {}
            
        if hasattr(schedule_data, 'total_courses') and schedule_data.total_courses:
            schedule_data.metadata['total_courses'] = schedule_data.total_courses
            
        if hasattr(schedule_data, 'departments') and schedule_data.departments:
            schedule_data.metadata['departments'] = schedule_data.departments
            
        return schedule_data
    
    def _select_term(self, term_code: str) -> None:
        """Select the term in the search interface.
        
        This is the first phase of the two-phase collection process.
        
        Args:
            term_code: Term code to select
        """
        base_url = self.config['base_url']
        search_endpoint = self.config.get('search_endpoint', 'pw_pub_sched.p_search')
        url = f"{base_url}/{search_endpoint}"
        
        params = {
            'p_menu2use': 'A',
            'term': term_code
        }
        
        try:
            logger.debug(f"Selecting term {term_code} at {url}")
            response = self.session.post(
                url,
                data=params,
                timeout=self.config['http_config']['timeout'],
                verify=self.config['http_config']['verify_ssl']
            )
            response.raise_for_status()
            logger.debug("Term selection successful")
            
            # Apply rate limiting
            self.rate_limit_delay()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to select term: {e}")
            raise
    
    def _fetch_schedule_page(self, url: str, term_code: str, subject: str = "ALL") -> str:
        """Fetch a single schedule HTML page.
        
        This is the second phase of the two-phase collection process.
        
        Args:
            url: Base URL for schedule endpoint
            term_code: Term code
            subject: Subject code or "ALL"
            
        Returns:
            HTML content as string
        """
        # Get term name for TERM_DESC parameter
        term_name = self._get_term_name(term_code)
        
        # Build request parameters as list of tuples to maintain order and allow duplicates
        params_list = [
            ('TERM', term_code),
            ('TERM_DESC', term_name),
            ('sel_subj', 'dummy'),
            ('sel_day', 'dummy'),
            ('sel_schd', 'dummy'),
            ('sel_camp', 'dummy'),
            ('sel_ism', 'dummy'),
            ('sel_sess', 'dummy'),
            ('sel_instr', 'dummy'),
            ('sel_ptrm', 'dummy'),
            ('sel_attrib', 'dummy'),
        ]
        
        # Add subject selection
        if subject == "ALL":
            params_list.append(('sel_subj', '%'))  # Use % not %25 - requests will encode it
        else:
            params_list.append(('sel_subj', subject))
            
        # Add remaining parameters
        params_list.extend([
            ('sel_crse', ''),
            ('sel_crn', ''),
            ('sel_title', ''),
            ('sel_ptrm', '%'),
            ('sel_ism', '%'),
            ('sel_instr', '%'),
            ('sel_attrib', '%'),
            ('sel_sess', '%'),
            ('begin_hh', self.config['search_params'].get('begin_hh', '5')),
            ('begin_mi', self.config['search_params'].get('begin_mi', '0')),
            ('begin_ap', self.config['search_params'].get('begin_ap', 'a')),
            ('end_hh', self.config['search_params'].get('end_hh', '11')),
            ('end_mi', self.config['search_params'].get('end_mi', '0')),
            ('end_ap', self.config['search_params'].get('end_ap', 'p')),
            ('aa', 'N'),
            ('sel_zero', self.config['search_params'].get('sel_zero', 'N')),
            ('ee', 'N'),
            ('sel_camp', '%')
        ])
        
        max_retries = self.config['rate_limit']['retry_attempts']
        timeout = self.config['http_config']['timeout']
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Fetching {url} with subject={subject}")
                response = self.session.post(
                    url,
                    data=params_list,
                    timeout=timeout,
                    verify=self.config['http_config']['verify_ssl']
                )
                response.raise_for_status()
                
                # Apply rate limiting
                self.rate_limit_delay()
                
                return response.text
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
    
    def _get_term_name(self, term_code: str) -> str:
        """Get term name from code.
        
        Args:
            term_code: Term code
            
        Returns:
            Human-readable term name
        """
        for term in self.config['terms']:
            if term['code'] == term_code:
                return term['name']
        return f"Term {term_code}"
    
    def _get_all_subject_codes(self) -> List[str]:
        """Get list of all possible subject codes.
        
        Returns:
            List of subject codes
        """
        # Common community college subject codes
        # This could be expanded or loaded from config
        return [
            'ACCT', 'ADM', 'ADS', 'ANTH', 'ARCH', 'ART', 'ASL', 'ASTR', 'AT', 'AUTO',
            'BIOL', 'BIOT', 'BUS', 'CDEV', 'CHEM', 'CIT', 'CJLE', 'COMM', 'COUN', 'CS',
            'DANC', 'DH', 'DMBA', 'DRAM', 'DS', 'ECE', 'ECON', 'EDUC', 'EET', 'EMGT',
            'EMS', 'ENGL', 'ENGR', 'ENV', 'ESL', 'ETHN', 'FAID', 'FIN', 'FIRE', 'FN',
            'FREN', 'GEOG', 'GEOL', 'GERO', 'GRIT', 'HCD', 'HIST', 'HIT', 'HORT', 'HST',
            'HUM', 'IDF', 'ITAL', 'JAPN', 'JOUR', 'KIN', 'LAW', 'LIB', 'LING', 'LIT',
            'MGMT', 'MKTG', 'MATH', 'MET', 'MFT', 'MICRO', 'MUS', 'NURS', 'NUTR', 'OTA',
            'PHIL', 'PHOT', 'PHYS', 'POLS', 'PORT', 'PSY', 'PSYC', 'PTA', 'READ', 'RT',
            'SOC', 'SPAN', 'SPCH', 'STAT', 'SW', 'THTR', 'VET', 'WELD', 'WEXP', 'WFT', 'WS'
        ]
    
    def collect_all_departments(self, term_code: Optional[str] = None) -> ScheduleData:
        """Collect schedule data for all configured departments.
        
        This method handles collecting multiple departments and merging the results.
        
        Args:
            term_code: Term code to collect or None for current term
            
        Returns:
            Combined ScheduleData object
        """
        # Use provided term or get from config
        if not term_code:
            term_code = self.config['current_term']['code']
            
        term_name = self._get_term_name(term_code)
        
        # Build URL
        base_url = self.config['base_url']
        endpoint = self.config['schedule_endpoint']
        url = f"{base_url}/{endpoint}"
        source_url = url
        
        departments = self.config['departments']
        all_courses = []
        errors = []
        
        if departments == ["ALL"]:
            # Collect all in one request
            html_content = self._fetch_schedule_page(url, term_code, subject="ALL")
            schedule_data = self.parser.parse_schedule_html(
                html_content,
                term_name,
                term_code,
                source_url
            )
            all_courses = schedule_data.courses
        else:
            # Collect specific departments
            for dept in departments:
                try:
                    logger.info(f"Collecting department: {dept}")
                    html_content = self._fetch_schedule_page(url, term_code, subject=dept)
                    dept_data = self.parser.parse_schedule_html(
                        html_content,
                        term_name,
                        term_code,
                        source_url
                    )
                    all_courses.extend(dept_data.courses)
                    
                except Exception as e:
                    error_msg = f"Failed to collect {dept}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        
        # Create combined schedule data
        schedule_data = ScheduleData(
            term=term_name,
            term_code=term_code,
            collection_timestamp=datetime.now(),
            source_url=source_url,
            college_id=self.college_id,
            collector_version=self.collector_version,
            courses=all_courses,
            metadata={
                'total_courses': len(all_courses),
                'departments': sorted(list(set(c.subject for c in all_courses))),
                'collection_errors': errors if errors else None
            }
        )
        
        return schedule_data
    
    def collect_course_details(self, courses: List[Course], term_code: str, 
                               batch_size: Optional[int] = None,
                               detail_delay: Optional[float] = None) -> List[DetailedCourse]:
        """Collect detailed information for a list of courses.
        
        Args:
            courses: List of Course objects to get details for
            term_code: Term code for the courses
            batch_size: Number of courses to process before showing progress
            detail_delay: Seconds to wait between detail requests
            
        Returns:
            List of DetailedCourse objects with additional information
        """
        # Get config values or use defaults
        if batch_size is None:
            batch_size = self.config.get('detail_batch_size', 50)
        if detail_delay is None:
            detail_delay = self.config.get('detail_delay', 1.0)
            
        detailed_courses = []
        total = len(courses)
        
        for i, course in enumerate(courses):
            try:
                # Build detail URL
                detail_url = self.parser.build_course_detail_url(course, term_code)
                
                # Fetch detail page
                logger.debug(f"Fetching details for {course.subject} {course.course_number} (CRN: {course.crn})")
                response = self.session.get(
                    detail_url,
                    timeout=self.config['http_config']['timeout'],
                    verify=self.config['http_config']['verify_ssl']
                )
                response.raise_for_status()
                
                # Parse details
                detailed_course = self.parser.parse_course_detail(response.text, course)
                detailed_courses.append(detailed_course)
                
                # Progress logging
                if (i + 1) % batch_size == 0 or (i + 1) == total:
                    logger.info(f"Collected details for {i + 1}/{total} courses")
                
                # Rate limiting
                if i < total - 1:  # Don't delay after last request
                    time.sleep(detail_delay)
                    
            except Exception as e:
                logger.error(f"Failed to get details for {course.crn}: {e}")
                # Add course without details on error
                detailed_courses.append(DetailedCourse(**course.model_dump()))
        
        return detailed_courses
    
    def collect_all_departments_with_details(self, term_code: Optional[str] = None) -> ScheduleData:
        """Collect schedule data with optional course details.
        
        This method collects all departments and optionally fetches detailed
        information for each course based on configuration.
        
        Args:
            term_code: Term code to collect or None for current term
            
        Returns:
            ScheduleData object with courses (detailed or regular based on config)
        """
        # First collect basic schedule data
        schedule_data = self.collect_all_departments(term_code)
        
        # Check if detail collection is enabled
        collect_details = self.config.get('collect_details', False)
        
        if collect_details and schedule_data.courses:
            logger.info(f"Collecting detailed information for {len(schedule_data.courses)} courses")
            
            # Get detail collection settings
            detail_batch_size = self.config.get('detail_batch_size', 50)
            detail_delay = self.config.get('detail_delay', 1.0)
            
            # Collect details
            detailed_courses = self.collect_course_details(
                schedule_data.courses,
                schedule_data.term_code,
                batch_size=detail_batch_size,
                detail_delay=detail_delay
            )
            
            # Replace courses with detailed versions
            schedule_data.courses = detailed_courses
            
            # Update metadata
            if not schedule_data.metadata:
                schedule_data.metadata = {}
            schedule_data.metadata['details_collected'] = True
            schedule_data.metadata['detail_collection_timestamp'] = datetime.now().isoformat()
            
        return schedule_data
    
    def collect(self, term_code: Optional[str] = None, save: bool = True) -> ScheduleData:
        """Override base collect to use detailed collection if configured.
        
        Args:
            term_code: Term code to collect or None for current term
            save: Whether to save the output (handled by base class)
            
        Returns:
            ScheduleData object with courses (detailed or regular based on config)
        """
        # Use the detailed collection method which checks config internally
        schedule_data = self.collect_all_departments_with_details(term_code)
        
        # The base class handles validation and saving
        if save:
            from utils.storage import ScheduleStorage
            storage = ScheduleStorage(
                data_dir=self.config.get('output_dir', 'data'),
                compression=self.config.get('compression', 'none')
            )
            storage.save_schedule(schedule_data)
        
        return schedule_data