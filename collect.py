#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "requests",
#   "beautifulsoup4",
#   "pydantic>=2.0",
#   "pyyaml",
# ]
# ///
"""Main collector script for Rio Hondo College schedule data."""

import sys
import time
import logging
import yaml
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlencode, urljoin

from models import ScheduleData, CollectionMetadata
from utils.parser import RioHondoScheduleParser
from utils.storage import ScheduleStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RioHondoCollector:
    """Collector for Rio Hondo College schedule data."""
    
    def __init__(self, config_path: str = "config.yml"):
        """Initialize collector with configuration."""
        self.config = self._load_config(config_path)
        self.parser = RioHondoScheduleParser()
        self.storage = ScheduleStorage(
            data_dir=self.config['output']['data_dir'],
            compression=self.config['output']['compression']
        )
        self.session = self._create_session()
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with configured settings."""
        session = requests.Session()
        session.headers.update({
            'User-Agent': self.config['collection']['user_agent']
        })
        return session
    
    def collect_schedule(self, term_code: Optional[str] = None) -> ScheduleData:
        """Collect schedule data for a specific term."""
        start_time = datetime.now()
        errors = []
        
        try:
            # Use provided term or get from config
            if not term_code:
                term_code = self.config['rio_hondo']['current_term']['code']
            
            term_name = self._get_term_name(term_code)
            
            logger.info(f"Starting collection for {term_name} (code: {term_code})")
            
            # Build URL for schedule search
            base_url = self.config['rio_hondo']['base_url']
            endpoint = self.config['rio_hondo']['schedule_endpoint']
            url = f"{base_url}/{endpoint}"
            
            # Get departments to collect
            departments = self.config['rio_hondo']['departments']
            
            if departments == ["ALL"]:
                # Collect all departments in one request
                html_content = self._fetch_schedule_page(url, term_code, subject="ALL")
                schedule_data = self.parser.parse_schedule_html(
                    html_content, 
                    term_name,
                    term_code,
                    url
                )
            else:
                # Collect specific departments and merge results
                all_courses = []
                for dept in departments:
                    try:
                        logger.info(f"Collecting department: {dept}")
                        html_content = self._fetch_schedule_page(url, term_code, subject=dept)
                        dept_data = self.parser.parse_schedule_html(
                            html_content, 
                            term_name,
                            term_code,
                            url
                        )
                        all_courses.extend(dept_data.courses)
                        
                        # Delay between requests
                        time.sleep(self.config['collection']['request_delay'])
                        
                    except Exception as e:
                        error_msg = f"Failed to collect {dept}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                
                # Create combined schedule data
                schedule_data = ScheduleData(
                    term=term_name,
                    term_code=term_code,
                    collection_timestamp=datetime.now(),
                    source_url=url,
                    courses=all_courses,
                    total_courses=len(all_courses),
                    departments=sorted(list(set(c.subject for c in all_courses)))
                )
            
            # Save schedule data
            filepath = self.storage.save_schedule(
                schedule_data,
                filename_pattern=self.config['output']['filename_pattern'],
                create_latest_link=self.config['output']['create_latest_link']
            )
            
            logger.info(f"Collection complete. Saved {len(schedule_data.courses)} courses to {filepath}")
            
            # Save collection metadata
            end_time = datetime.now()
            metadata = CollectionMetadata(
                start_time=start_time,
                end_time=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
                courses_collected=len(schedule_data.courses),
                errors=errors,
                success=len(errors) == 0
            )
            self.storage.save_metadata(metadata)
            
            # Cleanup old files if configured
            if hasattr(self.config['output'], 'keep_files'):
                self.storage.cleanup_old_files(self.config['output']['keep_files'])
            
            return schedule_data
            
        except Exception as e:
            logger.error(f"Collection failed: {e}")
            # Save error metadata
            end_time = datetime.now()
            metadata = CollectionMetadata(
                start_time=start_time,
                end_time=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
                courses_collected=0,
                errors=[str(e)],
                success=False
            )
            self.storage.save_metadata(metadata)
            raise
    
    def _fetch_schedule_page(self, url: str, term_code: str, subject: str = "ALL") -> str:
        """Fetch schedule HTML page."""
        # Build request parameters
        params = {
            'term': term_code,
            'sel_subj': ['dummy', subject] if subject != "ALL" else 'dummy',
            **self.config['rio_hondo']['search_params']
        }
        
        # Special handling for ALL subjects
        if subject == "ALL":
            # Include all subject codes
            params['sel_subj'] = ['dummy'] + self._get_all_subject_codes()
        
        max_retries = self.config['collection']['max_retries']
        timeout = self.config['collection']['timeout']
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Fetching {url} with params: {params}")
                response = self.session.post(
                    url, 
                    data=params,
                    timeout=timeout,
                    verify=self.config['collection']['verify_ssl']
                )
                response.raise_for_status()
                return response.text
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
    
    def _get_term_name(self, term_code: str) -> str:
        """Get term name from code."""
        for term in self.config['rio_hondo']['terms']:
            if term['code'] == term_code:
                return term['name']
        return f"Term {term_code}"
    
    def _get_all_subject_codes(self) -> list:
        """Get list of all possible subject codes."""
        # Common community college subject codes
        # This list can be expanded or loaded from config
        return [
            'ACCT', 'ADM', 'ADS', 'ANTH', 'ARCH', 'ART', 'ASL', 'ASTR', 'AT', 'AUTO',
            'BIOL', 'BIOT', 'BUS', 'CDEV', 'CHEM', 'CIT', 'CJLE', 'COMM', 'COUN', 'CS',
            'DANC', 'DH', 'DMBA', 'DRAM', 'DS', 'ECE', 'ECON', 'EDUC', 'EET', 'EMGT',
            'EMS', 'ENGL', 'ENGR', 'ENV', 'ESL', 'ETHN', 'FAID', 'FIN', 'FIRE', 'FN',
            'FREN', 'GEOG', 'GEOL', 'GERO', 'GRIT', 'HCD', 'HIST', 'HIT', 'HORT', 'HST',
            'HUM', 'IDF', 'ITAL', 'JAPN', 'JOUR', 'KIN', 'LAW', 'LIB', 'LING', 'LIT',
            'MGMT', 'MKTG', 'MATH', 'MET', 'MFT', 'MICRO', 'MUS', 'NURS', 'NUTR', 'OTA',
            'PHIL', 'PHOT', 'PHYS', 'POLS', 'PORT', 'PSY', 'PSYC', 'PTA', 'READ', 'RT',
            'SOC', 'SPAN', 'SPCH', 'STAT', 'SW', 'THTR', 'VET', 'WELD', 'WEXP', 'WS'
        ]


def main():
    """Main entry point."""
    try:
        collector = RioHondoCollector()
        schedule_data = collector.collect_schedule()
        
        # Print summary
        print(f"\nCollection Summary:")
        print(f"- Term: {schedule_data.term}")
        print(f"- Total courses: {schedule_data.total_courses}")
        print(f"- Departments: {len(schedule_data.departments)}")
        print(f"- Timestamp: {schedule_data.collection_timestamp}")
        
    except Exception as e:
        logger.error(f"Collection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()