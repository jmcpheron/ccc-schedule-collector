"""Citrus College schedule collector implementation."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urljoin, urlencode

import requests

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from collectors.base_collector import BaseCollector
from models import ScheduleData, Course, DetailedCourse
from .parser import CitrusScheduleParser


logger = logging.getLogger(__name__)


class CitrusCollector(BaseCollector):
    """Collector for Citrus College schedule data.
    
    This collector fetches schedule data from Citrus's Banner system
    and parses the HTML to extract course information.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize Citrus collector.
        
        Args:
            config_path: Path to config.json or None to use default
        """
        # Set default config path to citrus/config.json
        if config_path is None:
            config_path = Path(__file__).parent / 'config.json'
            
        super().__init__(config_path)
        self.parser = CitrusScheduleParser()
        
    def fetch_data(self, term_code: Optional[str] = None) -> str:
        """Fetch raw HTML data from Citrus's schedule system.
        
        This implements a two-phase process:
        1. Load search page with term selection
        2. Submit search to get results
        
        Args:
            term_code: Term code to fetch or None for current term
            
        Returns:
            HTML content as string
        """
        # Use provided term or get from config
        if not term_code:
            term_code = self.config['current_term']['code']
            
        logger.info(f"Fetching data for term {term_code}")
        
        # Build URLs
        base_url = self.config['base_url']
        search_endpoint = self.config['search_endpoint']
        results_endpoint = self.config.get('results_endpoint', 'az_tw_zipsched.p_list_this')
        
        # Phase 1: Load search page with term
        search_url = f"{base_url}/{search_endpoint}"
        params = {'term': term_code}
        
        logger.debug(f"Loading search page: {search_url}")
        response = self.session.get(search_url, params=params, timeout=self.config['http_config']['timeout'])
        response.raise_for_status()
        
        # Apply rate limiting
        self.rate_limit_delay()
        
        # Phase 2: Submit search form to get results
        results_url = f"{base_url}/{results_endpoint}"
        
        # Build search parameters
        search_params = self._build_search_params(term_code)
        
        logger.debug(f"Submitting search to: {results_url}")
        response = self.session.post(
            results_url,
            data=search_params,
            timeout=self.config['http_config']['timeout'],
            verify=self.config['http_config']['verify_ssl']
        )
        response.raise_for_status()
        
        return response.text
    
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
        source_url = f"{base_url}/{endpoint}?term={term_code}"
        
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
    
    def _fetch_schedule_page(self, url: str, params: Dict[str, str]) -> str:
        """Fetch a single schedule HTML page.
        
        Args:
            url: Base URL for schedule endpoint
            params: Query parameters including term
            
        Returns:
            HTML content as string
        """
        max_retries = self.config['rate_limit']['retry_attempts']
        timeout = self.config['http_config']['timeout']
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Fetching {url} with params={params}")
                response = self.session.get(
                    url,
                    params=params,
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
    
    def _build_search_params(self, term_code: str, subject: str = "ALL") -> List[Tuple[str, str]]:
        """Build search parameters for Citrus's system.
        
        Args:
            term_code: Term code
            subject: Subject code or "ALL"
            
        Returns:
            List of tuples for search parameters (to maintain order)
        """
        # Get term name
        term_name = self._get_term_name(term_code)
        
        # Build parameters as list of tuples to maintain order
        params = [
            ('TERM', term_code),
            ('TERM_DESC', term_name),
            ('sel_subj', 'dummy'),
            ('sel_day', 'dummy'),
            ('sel_schd', 'dummy'),
            ('sel_camp', 'dummy'),
            ('sel_sess', 'dummy'),
            ('sel_instr', 'dummy'),
            ('sel_ptrm', 'dummy'),
            ('sel_meth', 'dummy'),
        ]
        
        # Add all subjects
        if subject == "ALL":
            # Add all subject codes
            subjects = self.config.get('all_subjects', [
                'ACCT', 'ADS', 'ANTH', 'ART', 'AUTO', 'BIOL', 'BIOT', 'BUS', 
                'CDEV', 'CHEM', 'CIS', 'COMM', 'COUN', 'CS', 'DANC', 'DH', 
                'DS', 'ECE', 'ECON', 'EDUC', 'EET', 'ENGL', 'ENGR', 'ENV', 
                'ESL', 'ETHN', 'FN', 'FREN', 'GEOG', 'GEOL', 'GERO', 'HIST', 
                'HUM', 'ITAL', 'JAPN', 'JOUR', 'KIN', 'LAW', 'LIB', 'LING', 
                'LIT', 'MATH', 'MUS', 'NURS', 'PHIL', 'PHOT', 'PHYS', 'POLS', 
                'PORT', 'PSY', 'READ', 'SOC', 'SPAN', 'SPCH', 'STAT', 'THTR', 
                'UAS', 'VET', 'VN', 'WATR'
            ])
            for subj in subjects:
                params.append(('sel_subj', subj))
        else:
            params.append(('sel_subj', subject))
            
        # Add remaining parameters
        params.extend([
            ('sel_crse', ''),
            ('sel_camp', '%'),
            ('sel_levl', '%'),
            ('sel_schd', '%'),
            ('sel_ptrm', '%'),
            ('sel_instr', '%'),
            ('sel_meth', '%'),
            ('sel_sess', '%'),
            ('begin_hh', '1'),
            ('begin_mi', '0'),
            ('begin_ap', 'a'),
            ('end_hh', '11'),
            ('end_mi', '0'),
            ('end_ap', 'p'),
        ])
        
        return params
    
    def collect_with_post(self, term_code: Optional[str] = None) -> ScheduleData:
        """Alternative collection method using POST requests like Rio Hondo.
        
        This method might be needed if Citrus requires session-based searching.
        
        Args:
            term_code: Term code to collect or None for current term
            
        Returns:
            ScheduleData object
        """
        # Use provided term or get from config
        if not term_code:
            term_code = self.config['current_term']['code']
            
        logger.info(f"Collecting data for term {term_code} using POST method")
        
        # Build search URL
        base_url = self.config['base_url']
        search_endpoint = self.config.get('search_endpoint', 'az_tw_zipsched.P_SEARCH')
        search_url = f"{base_url}/{search_endpoint}"
        
        # Build search parameters
        search_params = self._build_search_params(term_code)
        
        try:
            # Submit search form
            logger.debug(f"Submitting search to {search_url}")
            response = self.session.post(
                search_url,
                data=search_params,
                timeout=self.config['http_config']['timeout'],
                verify=self.config['http_config']['verify_ssl']
            )
            response.raise_for_status()
            
            # Apply rate limiting
            self.rate_limit_delay()
            
            # Parse the results
            return self.parse_data(response.text, term_code)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to collect data: {e}")
            raise