"""Abstract base class for Banner 9 (SSB) college schedule collectors."""

import json
import logging
import re
import time
import uuid
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from collectors.base_collector import BaseCollector
from models import ScheduleData

logger = logging.getLogger(__name__)


class Banner9Collector(BaseCollector):
    """Abstract base class for Banner 9 (SSB) college collectors.
    
    This class provides common functionality for Banner 9 systems including:
    - Session management with cookies
    - CSRF token handling 
    - Required term declaration handshake
    - Paginated JSON API responses
    - Error handling for Banner 9 specific issues
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize Banner 9 collector.
        
        Args:
            config_path: Path to config.json file
        """
        super().__init__(config_path)
        self.csrf_token = None
        self.unique_session_id = None
        self.base_ssb_url = None
        
    def fetch_data(self, term_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch raw JSON data from Banner 9 system.
        
        This implements the Banner 9 API workflow:
        1. Initialize session and get CSRF token
        2. Declare term (required handshake)
        3. Fetch paginated course data
        
        Args:
            term_code: Term code to fetch or None for current term
            
        Returns:
            List of course dictionaries from JSON API
        """
        # Use provided term or get from config
        if not term_code:
            term_code = self.config['current_term']['code']
            
        logger.info(f"Fetching Banner 9 data for term {term_code}")
        
        # Step 1: Initialize session
        self._init_session()
        
        # Step 2: Declare term (required handshake)
        self._declare_term(term_code)
        
        # Step 3: Fetch all course data with pagination
        courses = self._fetch_all_courses(term_code)
        
        logger.info(f"Fetched {len(courses)} courses from Banner 9 API")
        return courses
    
    def _init_session(self) -> None:
        """Initialize Banner 9 session and extract CSRF token."""
        # Generate unique session ID for this collection run
        self.unique_session_id = str(int(datetime.now().timestamp() * 1000))
        
        # Build SSB base URL
        self.base_ssb_url = f"{self.config['base_url']}/StudentRegistrationSsb/ssb"
        
        # Load term selection page to get session cookies and CSRF token
        term_selection_url = f"{self.base_ssb_url}/term/termSelection?mode=search"
        
        logger.debug(f"Initializing session at {term_selection_url}")
        response = self.session.get(
            term_selection_url,
            timeout=self.config['http_config']['timeout'],
            verify=self.config['http_config']['verify_ssl']
        )
        response.raise_for_status()
        
        # Extract CSRF token from meta tag
        soup = BeautifulSoup(response.text, 'html.parser')
        csrf_meta = soup.find('meta', {'name': 'synchronizerToken'})
        if csrf_meta:
            self.csrf_token = csrf_meta.get('content')
            logger.debug(f"Extracted CSRF token: {self.csrf_token[:20]}...")
        else:
            logger.warning("No CSRF token found in response")
            
        # Apply rate limiting
        self.rate_limit_delay()
    
    def _declare_term(self, term_code: str) -> None:
        """Declare the term to enable search (required Banner 9 handshake).
        
        Args:
            term_code: Term code to declare
        """
        url = f"{self.base_ssb_url}/term/search?mode=search"
        
        data = {
            'term': term_code,
            'studyPath': '',
            'studyPathText': '',
            'startDatepicker': '',
            'endDatepicker': '',
            'uniqueSessionId': self.unique_session_id
        }
        
        headers = {}
        if self.csrf_token:
            headers['X-Synchronizer-Token'] = self.csrf_token
            
        logger.debug(f"Declaring term {term_code}")
        response = self.session.post(
            url,
            data=data,
            headers=headers,
            timeout=self.config['http_config']['timeout'],
            verify=self.config['http_config']['verify_ssl']
        )
        response.raise_for_status()
        
        # Verify the response indicates success
        try:
            result = response.json()
            if not result.get('success', True):
                raise ValueError(f"Term declaration failed: {result}")
        except ValueError:
            # Response might not be JSON, that's OK if status is 200
            pass
            
        logger.debug("Term declaration successful")
        self.rate_limit_delay()
    
    def _fetch_all_courses(self, term_code: str) -> List[Dict[str, Any]]:
        """Fetch all courses using pagination.
        
        Args:
            term_code: Term code to fetch courses for
            
        Returns:
            List of all course dictionaries
        """
        all_courses = []
        page_offset = 0
        page_size = self.config.get('page_size', 500)  # Banner 9 max is typically 500
        
        while True:
            courses_page = self._fetch_courses_page(term_code, page_offset, page_size)
            
            if not courses_page:
                break
                
            all_courses.extend(courses_page)
            
            # If we got fewer courses than page size, we're done
            if len(courses_page) < page_size:
                break
                
            page_offset += page_size
            logger.info(f"Collected {len(all_courses)} courses so far...")
            
        return all_courses
    
    def _fetch_courses_page(self, term_code: str, offset: int = 0, max_size: int = 500) -> List[Dict[str, Any]]:
        """Fetch a single page of courses from the searchResults endpoint.
        
        Args:
            term_code: Term code
            offset: Page offset (0-based)
            max_size: Maximum number of results per page
            
        Returns:
            List of course dictionaries for this page
        """
        url = f"{self.base_ssb_url}/searchResults/searchResults"
        
        # Build search parameters - subclasses can override this
        params = self._build_search_params(term_code, offset, max_size)
        
        headers = {}
        if self.csrf_token:
            headers['X-Synchronizer-Token'] = self.csrf_token
            
        max_retries = self.config['rate_limit']['retry_attempts']
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Fetching page at offset {offset}, size {max_size}")
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.config['http_config']['timeout'],
                    verify=self.config['http_config']['verify_ssl']
                )
                response.raise_for_status()
                
                # Parse JSON response
                result = response.json()
                
                if not result.get('success', True):
                    raise ValueError(f"Search failed: {result}")
                    
                courses = result.get('data')
                if courses is None:
                    courses = []
                logger.debug(f"Got {len(courses)} courses in this page")
                
                self.rate_limit_delay()
                return courses
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
                    
        return []
    
    @abstractmethod
    def _build_search_params(self, term_code: str, offset: int = 0, max_size: int = 500) -> Dict[str, Any]:
        """Build search parameters for the searchResults endpoint.
        
        This must be implemented by each college as they may have different
        parameter requirements (e.g., campus filters, subject filters).
        
        Args:
            term_code: Term code
            offset: Page offset
            max_size: Maximum results per page
            
        Returns:
            Dictionary of search parameters
        """
        pass
    
    def _get_terms(self) -> List[Dict[str, str]]:
        """Get available terms from the Banner 9 API.
        
        Returns:
            List of term dictionaries with 'code' and 'description' keys
        """
        # Try the common endpoints for term lists
        endpoints = [
            'classSearch/getTerms',
            'classRegistration/getTerms'
        ]
        
        headers = {}
        if self.csrf_token:
            headers['X-Synchronizer-Token'] = self.csrf_token
            
        for endpoint in endpoints:
            try:
                url = f"{self.base_ssb_url}/{endpoint}"
                params = {
                    'offset': 1,
                    'max': 10,
                    'searchTerm': ''
                }
                
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.config['http_config']['timeout']
                )
                
                if response.status_code == 200:
                    terms = response.json()
                    logger.debug(f"Got {len(terms)} terms from {endpoint}")
                    return terms
                    
            except Exception as e:
                logger.debug(f"Failed to get terms from {endpoint}: {e}")
                continue
                
        logger.warning("Could not fetch terms from any endpoint")
        return []
    
    def _get_subjects(self, term_code: str) -> List[Dict[str, str]]:
        """Get available subjects for a term.
        
        Args:
            term_code: Term code
            
        Returns:
            List of subject dictionaries with 'code' and 'description' keys
        """
        url = f"{self.base_ssb_url}/classSearch/get_subject"
        
        params = {
            'searchTerm': '',
            'term': term_code,
            'offset': 1,
            'max': 500,
            'uniqueSessionId': self.unique_session_id
        }
        
        headers = {}
        if self.csrf_token:
            headers['X-Synchronizer-Token'] = self.csrf_token
            
        try:
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.config['http_config']['timeout']
            )
            response.raise_for_status()
            
            subjects = response.json()
            logger.debug(f"Got {len(subjects)} subjects for term {term_code}")
            return subjects
            
        except Exception as e:
            logger.error(f"Failed to get subjects: {e}")
            return []
    
    def _fetch_course_details(self, crn: str, term_code: str) -> Dict[str, Any]:
        """Fetch detailed information for a specific course.
        
        Args:
            crn: Course Reference Number
            term_code: Term code
            
        Returns:
            Dictionary with detailed course information
        """
        # Banner 9 has multiple detail endpoints - implement as needed
        details = {}
        
        # Faculty/Meeting Times (JSON endpoint)
        meeting_details = self._fetch_faculty_meeting_times(crn, term_code)
        if meeting_details:
            details['meeting_times'] = meeting_details
            
        # Other detail endpoints return HTML - implement as needed by subclasses
        
        return details
    
    def _fetch_faculty_meeting_times(self, crn: str, term_code: str) -> Optional[Dict[str, Any]]:
        """Fetch faculty and meeting time details for a course.
        
        Args:
            crn: Course Reference Number  
            term_code: Term code
            
        Returns:
            Dictionary with faculty/meeting time data or None if failed
        """
        url = f"{self.base_ssb_url}/searchResults/getFacultyMeetingTimes"
        params = {
            'term': term_code,
            'courseReferenceNumber': crn
        }
        
        max_retries = 2  # This endpoint sometimes returns 302, retry once
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.config['http_config']['timeout'],
                    allow_redirects=False  # Don't follow 302 to SSO
                )
                
                if response.status_code == 302:
                    logger.debug(f"Got 302 for CRN {crn}, retrying...")
                    time.sleep(1)
                    continue
                    
                response.raise_for_status()
                return response.json()
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.debug(f"Faculty/meeting times failed for CRN {crn}, retrying: {e}")
                    time.sleep(1)
                else:
                    logger.warning(f"Could not get faculty/meeting times for CRN {crn}: {e}")
                    
        return None