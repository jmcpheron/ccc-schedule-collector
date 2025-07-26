"""Abstract base class for all college schedule collectors."""

import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from models import ScheduleData, CollectionMetadata


logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """Abstract base class for college schedule collectors.
    
    This class provides common functionality for all collectors including:
    - HTTP session management with retry logic
    - Rate limiting
    - Output formatting
    - Error handling
    - Validation
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize collector with configuration.
        
        Args:
            config_path: Path to config.json file. If not provided,
                        looks for config.json in the collector's directory.
        """
        self.config = self._load_config(config_path)
        self.college_id = self.config['college_id']
        self.collector_version = self.config.get('collector_version', '1.0.0')
        self.session = self._create_session()
        self.collection_metadata = None
        
    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from JSON file.
        
        Args:
            config_path: Path to config file or None to use default
            
        Returns:
            Configuration dictionary
        """
        if config_path is None:
            # Default to config.json in the collector's directory
            module_dir = Path(__file__).parent
            college_dir = module_dir / self.__class__.__module__.split('.')[-1]
            config_path = college_dir / 'config.json'
            
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry logic and rate limiting.
        
        Returns:
            Configured requests Session
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_config = self.config.get('rate_limit', {})
        retry_strategy = Retry(
            total=retry_config.get('retry_attempts', 3),
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            'User-Agent': self.config.get('user_agent', 
                'CCC-Schedule-Collector/1.0 (https://github.com/jmcpheron/ccc-schedule-collector)')
        })
        
        return session
    
    def collect(self, term_code: Optional[str] = None, save: bool = True) -> ScheduleData:
        """Main collection method that orchestrates the collection process.
        
        Args:
            term_code: Term code to collect or None for current term
            save: Whether to save the collected data
            
        Returns:
            ScheduleData object with collected courses
        """
        start_time = datetime.now()
        errors = []
        
        try:
            # Fetch the data
            logger.info(f"Starting collection for {self.college_id}")
            raw_data = self.fetch_data(term_code)
            
            # Parse the data
            logger.info("Parsing collected data")
            schedule_data = self.parse_data(raw_data, term_code)
            
            # Add required fields
            schedule_data.college_id = self.college_id
            schedule_data.collector_version = self.collector_version
            
            # Validate the output
            logger.info("Validating output format")
            self.validate_output(schedule_data)
            
            # Save if requested
            if save:
                self.save_output(schedule_data)
                
        except Exception as e:
            logger.error(f"Collection failed: {e}")
            errors.append(str(e))
            raise
            
        finally:
            # Record metadata
            end_time = datetime.now()
            self.collection_metadata = CollectionMetadata(
                start_time=start_time,
                end_time=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
                courses_collected=len(schedule_data.courses) if 'schedule_data' in locals() else 0,
                errors=errors,
                success=len(errors) == 0
            )
            
        return schedule_data
    
    @abstractmethod
    def fetch_data(self, term_code: Optional[str] = None) -> Any:
        """Fetch raw data from the college website.
        
        This method must be implemented by each college collector.
        
        Args:
            term_code: Term code to fetch or None for current term
            
        Returns:
            Raw data (HTML, JSON, etc.) to be parsed
        """
        pass
    
    @abstractmethod
    def parse_data(self, raw_data: Any, term_code: Optional[str] = None) -> ScheduleData:
        """Parse raw data into ScheduleData format.
        
        This method must be implemented by each college collector.
        
        Args:
            raw_data: Raw data from fetch_data
            term_code: Term code being processed
            
        Returns:
            ScheduleData object with parsed courses
        """
        pass
    
    def validate_output(self, data: ScheduleData) -> None:
        """Validate that output meets the integration contract.
        
        Args:
            data: ScheduleData to validate
            
        Raises:
            ValueError: If validation fails
        """
        # Check required top-level fields
        required_fields = ['term', 'term_code', 'collection_timestamp', 
                          'source_url', 'college_id', 'collector_version', 'courses']
        
        data_dict = data.model_dump()
        for field in required_fields:
            if field not in data_dict or data_dict[field] is None:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate courses
        if not isinstance(data.courses, list):
            raise ValueError("Courses must be a list")
            
        if len(data.courses) == 0:
            logger.warning("No courses found in collection")
            
        # Validate each course has minimum required fields
        for i, course in enumerate(data.courses):
            course_dict = course.model_dump()
            if 'crn' not in course_dict or not course_dict['crn']:
                raise ValueError(f"Course at index {i} missing CRN")
            if 'subject' not in course_dict or not course_dict['subject']:
                raise ValueError(f"Course {course_dict.get('crn', 'unknown')} missing subject")
                
        logger.info(f"Validation passed. {len(data.courses)} courses collected.")
    
    def save_output(self, data: ScheduleData) -> Path:
        """Save output data to the output directory.
        
        Args:
            data: ScheduleData to save
            
        Returns:
            Path to saved file
        """
        # Create output directory structure
        output_dir = Path('data')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"schedule_{data.term_code}_{timestamp}.json"
        filepath = output_dir / filename
        
        # Save with proper formatting
        with open(filepath, 'w') as f:
            json.dump(data.model_dump(), f, indent=2, default=str)
            
        # Update latest symlink
        latest_path = output_dir / f"schedule_{data.term_code}_latest.json"
        with open(latest_path, 'w') as f:
            json.dump(data.model_dump(), f, indent=2, default=str)
            
        logger.info(f"Saved output to {filepath}")
        return filepath
    
    def rate_limit_delay(self) -> None:
        """Apply rate limiting delay between requests."""
        delay = 1.0 / self.config.get('rate_limit', {}).get('requests_per_second', 2)
        time.sleep(delay)