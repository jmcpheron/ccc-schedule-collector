"""Mt. San Antonio College (Mt SAC) schedule collector implementation."""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

import requests

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from collectors.base_banner9_collector import Banner9Collector
from models import ScheduleData, Course, DetailedCourse
from .parser import MtSacScheduleParser


logger = logging.getLogger(__name__)


class MtSacCollector(Banner9Collector):
    """Collector for Mt. San Antonio College schedule data.
    
    This collector fetches schedule data from Mt SAC's Banner 9 SSB system
    and processes the JSON API responses to extract course information.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize Mt SAC collector.
        
        Args:
            config_path: Path to config.json or None to use default
        """
        # Set default config path to mtsac/config.json
        if config_path is None:
            config_path = Path(__file__).parent / 'config.json'
            
        super().__init__(config_path)
        self.parser = MtSacScheduleParser()
        
    def _build_search_params(self, term_code: str, offset: int = 0, max_size: int = 500) -> Dict[str, Any]:
        """Build search parameters for Mt SAC's searchResults endpoint.
        
        Args:
            term_code: Term code
            offset: Page offset (0-based)
            max_size: Maximum results per page (Banner 9 max is typically 500)
            
        Returns:
            Dictionary of search parameters
        """
        params = {
            'txt_term': term_code,
            'pageOffset': offset,
            'pageMaxSize': min(max_size, 500),  # Enforce Banner 9 limit
            'sortColumn': self.config['search_params'].get('sortColumn', 'subjectDescription'),
            'sortDirection': self.config['search_params'].get('sortDirection', 'asc'),
        }
        
        # Add unique session ID if available
        if hasattr(self, 'unique_session_id') and self.unique_session_id:
            params['uniqueSessionId'] = self.unique_session_id
            
        # Add optional search filters
        search_params = self.config.get('search_params', {})
        
        # Subject filter
        if search_params.get('txt_subject'):
            params['txt_subject'] = search_params['txt_subject']
            
        # Course number filter
        if search_params.get('txt_courseNumber'):
            params['txt_courseNumber'] = search_params['txt_courseNumber']
            
        # Campus filter (Mt SAC specific)
        if search_params.get('txt_campus'):
            params['txt_campus'] = search_params['txt_campus']
            
        # Date filters
        if search_params.get('startDatepicker'):
            params['startDatepicker'] = search_params['startDatepicker']
        if search_params.get('endDatepicker'):
            params['endDatepicker'] = search_params['endDatepicker']
            
        logger.debug(f"Built search params: {params}")
        return params
    
    def parse_data(self, raw_data: List[Dict[str, Any]], term_code: Optional[str] = None) -> ScheduleData:
        """Parse JSON data into ScheduleData format.
        
        Args:
            raw_data: List of course dictionaries from Banner 9 API
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
        ssb_path = self.config['ssb_path']
        source_url = f"{base_url}{ssb_path}/classSearch/classSearch"
        
        # Parse the JSON data
        logger.info(f"Parsing {len(raw_data)} courses from JSON API")
        schedule_data = self.parser.parse_courses_json(
            raw_data,
            term_name,
            term_code,
            source_url
        )
        
        # Add required fields
        schedule_data.college_id = self.college_id
        schedule_data.collector_version = self.collector_version
        
        # Add metadata
        if not schedule_data.metadata:
            schedule_data.metadata = {}
            
        schedule_data.metadata.update({
            'collection_method': 'banner9_api',
            'api_version': 'Banner 9 SSB',
            'total_courses': len(schedule_data.courses),
            'departments': sorted(list(set(course.subject for course in schedule_data.courses))),
            'data_source': 'searchResults API',
            'includes_faculty_data': True,
            'includes_meeting_times': True
        })
            
        return schedule_data
    
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
    
    def collect_with_details(self, term_code: Optional[str] = None, 
                           detail_types: Optional[List[str]] = None) -> ScheduleData:
        """Collect schedule data with additional course details.
        
        This method first collects the basic course data, then optionally
        fetches additional details using Banner 9's detail endpoints.
        
        Args:
            term_code: Term code to collect or None for current term
            detail_types: List of detail types to collect (e.g., ['description', 'prerequisites'])
                         If None, collects all available details
            
        Returns:
            ScheduleData object with detailed course information
        """
        # First collect basic schedule data
        schedule_data = super().collect(term_code=term_code, save=False)
        
        # Check if detail collection is enabled
        collect_details = self.config.get('collect_details', True)
        
        if collect_details and schedule_data.courses and detail_types:
            logger.info(f"Collecting additional details for {len(schedule_data.courses)} courses")
            
            # Get detail collection settings
            detail_delay = self.config.get('detail_delay', 0.5)
            detail_batch_size = self.config.get('detail_batch_size', 50)
            
            # Collect details for each course
            detailed_courses = []
            
            for i, course in enumerate(schedule_data.courses):
                try:
                    # Fetch additional details
                    details = self._collect_course_details(course.crn, term_code, detail_types)
                    
                    # Create detailed course object
                    detailed_course = self._create_detailed_course(course, details)
                    detailed_courses.append(detailed_course)
                    
                    # Progress logging
                    if (i + 1) % detail_batch_size == 0 or (i + 1) == len(schedule_data.courses):
                        logger.info(f"Collected details for {i + 1}/{len(schedule_data.courses)} courses")
                    
                    # Rate limiting
                    if i < len(schedule_data.courses) - 1:
                        time.sleep(detail_delay)
                        
                except Exception as e:
                    logger.error(f"Failed to get details for CRN {course.crn}: {e}")
                    # Use original course if detail collection fails
                    detailed_courses.append(course)
            
            # Replace courses with detailed versions
            schedule_data.courses = detailed_courses
            
            # Update metadata
            schedule_data.metadata['details_collected'] = True
            schedule_data.metadata['detail_types'] = detail_types
            schedule_data.metadata['detail_collection_timestamp'] = datetime.now(timezone.utc).isoformat() + "Z"
            
        return schedule_data
    
    def _collect_course_details(self, crn: str, term_code: str, 
                               detail_types: List[str]) -> Dict[str, Any]:
        """Collect additional details for a specific course.
        
        Args:
            crn: Course Reference Number
            term_code: Term code
            detail_types: List of detail types to collect
            
        Returns:
            Dictionary with collected detail information
        """
        details = {}
        
        # Banner 9 detail endpoints
        endpoint_map = {
            'description': 'getCourseDescription',
            'prerequisites': 'getSectionPrerequisites', 
            'corequisites': 'getCorequisites',
            'restrictions': 'getRestrictions',
            'attributes': 'getSectionAttributes',
            'enrollment_info': 'getEnrollmentInfo',
            'fees': 'getFees',
            'catalog_details': 'getSectionCatalogDetails',
            'class_details': 'getClassDetails',
            'cross_listed': 'getXlstSections',
            'linked_sections': 'getLinkedSections',
            'mutual_exclusions': 'getCourseMutuallyExclusions'
        }
        
        # Build base URL for detail endpoints
        base_detail_url = f"{self.base_ssb_url}/searchResults"
        
        for detail_type in detail_types:
            if detail_type not in endpoint_map:
                logger.warning(f"Unknown detail type: {detail_type}")
                continue
                
            endpoint = endpoint_map[detail_type]
            url = f"{base_detail_url}/{endpoint}"
            
            try:
                # Most detail endpoints use POST with form data
                data = {
                    'term': term_code,
                    'courseReferenceNumber': crn
                }
                
                response = self.session.post(
                    url,
                    data=data,
                    timeout=self.config['http_config']['timeout'],
                    verify=self.config['http_config']['verify_ssl']
                )
                response.raise_for_status()
                
                # Most endpoints return HTML, parse as needed
                details[detail_type] = response.text
                
            except Exception as e:
                logger.debug(f"Failed to get {detail_type} for CRN {crn}: {e}")
                details[detail_type] = None
                
        return details
    
    def _create_detailed_course(self, course: Course, details: Dict[str, Any]) -> DetailedCourse:
        """Create a DetailedCourse object from a Course and additional details.
        
        Args:
            course: Base Course object
            details: Dictionary of additional detail information
            
        Returns:
            DetailedCourse object with additional fields populated
        """
        # Start with the base course data
        detailed_data = course.model_dump()
        
        # Add detail timestamp
        detailed_data['detail_fetched_at'] = datetime.now(timezone.utc)
        
        # Parse HTML details using the parser
        parsed_details = self.parser.parse_course_details(details)
        detailed_data.update(parsed_details)
        
        return DetailedCourse(**detailed_data)
    
    def discover_subjects(self, term_code: Optional[str] = None) -> List[str]:
        """Discover available subject codes for a term.
        
        This method uses Banner 9's get_subject API to find all available subjects.
        
        Args:
            term_code: Term code or None for current term
            
        Returns:
            List of subject codes
        """
        if not term_code:
            term_code = self.config['current_term']['code']
            
        logger.info(f"Discovering subjects for term {term_code}")
        
        # Initialize session if needed
        if not hasattr(self, 'base_ssb_url') or not self.base_ssb_url:
            self._init_session()
            
        # Get subjects from API
        subjects_data = self._get_subjects(term_code)
        
        # Extract subject codes
        subject_codes = []
        for subject in subjects_data:
            code = subject.get('code')
            if code:
                subject_codes.append(code)
                
        logger.info(f"Discovered {len(subject_codes)} subjects")
        return sorted(subject_codes)
    
    def collect_specific_subjects(self, subject_codes: List[str], 
                                 term_code: Optional[str] = None) -> ScheduleData:
        """Collect courses for specific subject codes.
        
        This method allows collecting data for specific departments rather than all.
        
        Args:
            subject_codes: List of subject codes to collect
            term_code: Term code or None for current term
            
        Returns:
            ScheduleData object with courses from specified subjects
        """
        if not term_code:
            term_code = self.config['current_term']['code']
            
        logger.info(f"Collecting courses for subjects: {subject_codes}")
        
        all_courses = []
        
        for subject_code in subject_codes:
            try:
                logger.info(f"Collecting subject: {subject_code}")
                
                # Temporarily modify search params to filter by subject
                original_subject = self.config['search_params'].get('txt_subject', '')
                self.config['search_params']['txt_subject'] = subject_code
                
                # Collect courses for this subject
                subject_courses = self.fetch_data(term_code)
                all_courses.extend(subject_courses)
                
                # Restore original subject filter
                self.config['search_params']['txt_subject'] = original_subject
                
            except Exception as e:
                logger.error(f"Failed to collect subject {subject_code}: {e}")
                continue
                
        # Parse all collected courses
        return self.parse_data(all_courses, term_code)