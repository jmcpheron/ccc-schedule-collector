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
from models import ScheduleData, Course
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
        
        Args:
            term_code: Term code to fetch or None for current term
            
        Returns:
            HTML content as string
        """
        # Use provided term or get from config
        if not term_code:
            term_code = self.config['current_term']['code']
            
        logger.info(f"Fetching data for term {term_code}")
        
        # Build URL
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
    
    def _fetch_schedule_page(self, url: str, term_code: str, subject: str = "ALL") -> str:
        """Fetch a single schedule HTML page.
        
        Args:
            url: Base URL for schedule endpoint
            term_code: Term code
            subject: Subject code or "ALL"
            
        Returns:
            HTML content as string
        """
        # Build request parameters
        params = {
            'term': term_code,
            'sel_subj': ['dummy', subject] if subject != "ALL" else 'dummy',
            **self.config['search_params']
        }
        
        # Special handling for ALL subjects
        if subject == "ALL":
            # Include all subject codes
            params['sel_subj'] = ['dummy'] + self._get_all_subject_codes()
        
        max_retries = self.config['rate_limit']['retry_attempts']
        timeout = self.config['http_config']['timeout']
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Fetching {url} with subject={subject}")
                response = self.session.post(
                    url,
                    data=params,
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