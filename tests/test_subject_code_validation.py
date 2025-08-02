#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pytest",
#   "pydantic>=2.0",
# ]
# ///
"""Tests for validating subject code accuracy and completeness.

This module contains tests to ensure that:
1. Subject codes we search for match what colleges actually use
2. We collect a reasonable percentage of expected subjects
3. Known subject code differences are properly mapped
"""

import json
from pathlib import Path
from typing import Dict, Set, Optional, Tuple

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import ScheduleData


class TestSubjectCodeValidation:
    """Tests for validating subject codes match between config and actual data."""
    
    def test_subject_collection_completeness(self, schedule_data: Optional[ScheduleData] = None,
                                           config_path: Optional[Path] = None,
                                           min_percentage: float = 0.90):
        """Test that we collect at least X% of expected subjects.
        
        Args:
            schedule_data: ScheduleData object to test
            config_path: Path to college config.json
            min_percentage: Minimum percentage of subjects that must be collected (default: 90%)
        """
        if schedule_data is None or config_path is None:
            pytest.skip("Schedule data or config path not provided")
            
        if not config_path.exists():
            pytest.skip(f"Config file not found: {config_path}")
            
        # Load expected subjects
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        expected_subjects = set(config.get('expected_subjects', []))
        if not expected_subjects:
            expected_subjects = set(config.get('all_subjects', []))
            
        if not expected_subjects:
            pytest.skip("No expected subjects defined in config")
            
        # Get collected subjects
        collected_subjects = self._extract_subjects(schedule_data)
        
        # Calculate collection percentage
        collection_percentage = len(collected_subjects) / len(expected_subjects)
        
        # Check if we meet minimum threshold
        if collection_percentage < min_percentage:
            missing = expected_subjects - collected_subjects
            pytest.fail(
                f"Only collected {len(collected_subjects)}/{len(expected_subjects)} subjects "
                f"({collection_percentage:.1%}), below minimum threshold of {min_percentage:.0%}. "
                f"Missing: {sorted(missing)}"
            )
    
    def test_no_unexpected_subject_codes(self, schedule_data: Optional[ScheduleData] = None,
                                       config_path: Optional[Path] = None):
        """Test that collected subjects are all in our expected list.
        
        This helps identify when a college uses different subject codes than expected.
        """
        if schedule_data is None or config_path is None:
            pytest.skip("Schedule data or config path not provided")
            
        if not config_path.exists():
            pytest.skip(f"Config file not found: {config_path}")
            
        # Load config
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        expected_subjects = set(config.get('expected_subjects', []))
        if not expected_subjects:
            expected_subjects = set(config.get('all_subjects', []))
            
        # Get mappings if available
        mappings = config.get('subject_code_mappings', {})
        mapped_subjects = set(mappings.values()) if isinstance(mappings, dict) else set()
        
        # Combine expected and mapped subjects
        all_valid_subjects = expected_subjects | mapped_subjects
        
        # Get collected subjects
        collected_subjects = self._extract_subjects(schedule_data)
        
        # Find unexpected subjects
        unexpected = collected_subjects - all_valid_subjects
        
        if unexpected:
            # This is a warning, not a failure - it helps identify mapping needs
            print(f"\nWARNING: Found unexpected subject codes: {sorted(unexpected)}")
            print("Consider adding these to subject_code_mappings if they're variants of expected subjects")
    
    def test_critical_subjects_present(self, schedule_data: Optional[ScheduleData] = None,
                                     critical_subjects: Optional[Set[str]] = None):
        """Test that critical subjects are present in collected data.
        
        Args:
            schedule_data: ScheduleData object to test
            critical_subjects: Set of subjects that must be present
        """
        if schedule_data is None:
            pytest.skip("No schedule data provided")
            
        # Default critical subjects if none provided
        if critical_subjects is None:
            critical_subjects = {'ENGL', 'MATH', 'CHEM', 'BIOL', 'PHYS'}
            
        collected_subjects = self._extract_subjects(schedule_data)
        
        missing_critical = critical_subjects - collected_subjects
        
        if missing_critical:
            pytest.fail(
                f"Critical subjects missing from collection: {sorted(missing_critical)}. "
                f"This may indicate subject code mismatches or collection issues."
            )
    
    def test_subject_code_mapping_validity(self, config_path: Optional[Path] = None):
        """Test that subject code mappings are valid and don't conflict."""
        if config_path is None:
            pytest.skip("No config path provided")
            
        if not config_path.exists():
            pytest.skip(f"Config file not found: {config_path}")
            
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        mappings = config.get('subject_code_mappings', {})
        if not mappings or mappings.get('comments'):
            # Skip if no mappings or only comments
            return
            
        # Check for conflicts
        all_subjects = set(config.get('all_subjects', []))
        
        for old_code, new_code in mappings.items():
            if old_code == 'comments':
                continue
                
            # Old code should be in our subject list
            if old_code not in all_subjects:
                pytest.fail(
                    f"Mapping source '{old_code}' not found in all_subjects. "
                    f"Mappings should map FROM codes in our list TO actual college codes."
                )
    
    def test_known_subject_variations(self, schedule_data: Optional[ScheduleData] = None,
                                    known_variations: Optional[Dict[str, str]] = None):
        """Test for known subject code variations between our list and college usage.
        
        Args:
            schedule_data: ScheduleData object to test
            known_variations: Dict mapping our codes to college codes (e.g., {'THTR': 'THEA'})
        """
        if schedule_data is None:
            pytest.skip("No schedule data provided")
            
        if known_variations is None:
            # Common known variations across colleges
            known_variations = {
                'THTR': 'THEA',  # Theatre vs Theater
                'PSYC': 'PSY',   # Psychology variations
                'COMM': 'SPCH',  # Communication vs Speech
            }
            
        collected_subjects = self._extract_subjects(schedule_data)
        
        issues = []
        for our_code, college_code in known_variations.items():
            # Check if we have our code but not the college code
            if our_code not in collected_subjects and college_code in collected_subjects:
                issues.append(f"Found '{college_code}' but searching for '{our_code}'")
            # Check if neither is present (might be OK if subject not offered)
            elif our_code not in collected_subjects and college_code not in collected_subjects:
                # This is OK - subject might not be offered this term
                pass
                
        if issues:
            pytest.fail(
                "Subject code mismatches detected:\n" + "\n".join(issues) + 
                "\nUpdate config to use actual college codes or add mappings."
            )
    
    def _extract_subjects(self, schedule_data: ScheduleData) -> Set[str]:
        """Extract unique subject codes from schedule data."""
        subjects = set()
        
        # Get from courses
        for course in schedule_data.courses:
            if course.subject:
                subjects.add(course.subject.upper())
                
        # Also check metadata if available
        if hasattr(schedule_data, 'metadata') and schedule_data.metadata:
            if 'departments' in schedule_data.metadata:
                for dept in schedule_data.metadata['departments']:
                    if dept:
                        subjects.add(dept.upper())
                        
        return subjects


def validate_citrus_specific_codes():
    """Specific validation for Citrus College subject codes."""
    # Known Citrus-specific mappings
    CITRUS_MAPPINGS = {
        'THTR': 'THEA',  # Theatre Arts uses THEA not THTR
        # Add more as discovered
    }
    
    # Load latest Citrus data
    citrus_data_path = Path('data/citrus/schedule_202620_latest.json')
    citrus_config_path = Path('collectors/citrus/config.json')
    
    if not citrus_data_path.exists():
        print("No Citrus data found to validate")
        return
        
    with open(citrus_data_path, 'r') as f:
        data = json.load(f)
        
    # Handle potential missing fields
    from datetime import datetime
    if 'collection_timestamp' not in data:
        data['collection_timestamp'] = datetime.now().isoformat()
        
    schedule_data = ScheduleData(**data)
    
    # Run validation
    validator = TestSubjectCodeValidation()
    
    print("\nValidating Citrus College subject codes...")
    
    # Check completeness
    try:
        validator.test_subject_collection_completeness(schedule_data, citrus_config_path, 0.50)
        print("✓ Subject collection completeness check passed")
    except AssertionError as e:
        print(f"✗ Subject collection issue: {e}")
        
    # Check for unexpected codes
    validator.test_no_unexpected_subject_codes(schedule_data, citrus_config_path)
    
    # Check known variations
    try:
        validator.test_known_subject_variations(schedule_data, CITRUS_MAPPINGS)
        print("✓ Known subject variations check passed")
    except AssertionError as e:
        print(f"✗ Subject code mismatch: {e}")


if __name__ == "__main__":
    # Run validation if called directly
    validate_citrus_specific_codes()
    
    # Also run pytest
    pytest.main([__file__, "-v"])