#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pydantic>=2.0",
#   "pyyaml",
#   "click>=8.0"
# ]
# ///
"""Discover and manage subject codes from collected schedule data.

This script helps maintain accurate subject lists by:
1. Discovering new subjects from collected data
2. Comparing with expected subjects in config
3. Reporting changes and anomalies
4. Optionally updating config files
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple

import click
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from models import ScheduleData


class SubjectDiscovery:
    """Handles subject code discovery and management."""
    
    def __init__(self, college_id: str):
        """Initialize discovery for a specific college.
        
        Args:
            college_id: College identifier (e.g., 'rio-hondo', 'citrus')
        """
        self.college_id = college_id
        # Handle both hyphenated and underscored directory names
        college_dir_name = college_id.replace('-', '_')
        self.college_dir = Path(f"collectors/{college_dir_name}")
        self.config_path = self.college_dir / "config.json"
        self.data_dir = Path(f"data/{college_id}")
        
    def load_config(self) -> Dict:
        """Load college configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")
            
        with open(self.config_path, 'r') as f:
            return json.load(f)
            
    def save_config(self, config: Dict) -> None:
        """Save updated configuration."""
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
            f.write('\n')  # Add trailing newline
            
    def discover_subjects_from_data(self) -> Set[str]:
        """Extract all unique subjects from collected data files.
        
        Returns:
            Set of unique subject codes found in data
        """
        subjects = set()
        
        # Find all schedule JSON files
        schedule_files = list(self.data_dir.glob("schedule_*.json"))
        if not schedule_files:
            click.echo(f"⚠️  No schedule files found in {self.data_dir}")
            return subjects
            
        # Process each file
        for file_path in schedule_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    
                # Extract subjects from courses
                for course in data.get('courses', []):
                    if subject := course.get('subject'):
                        subjects.add(subject.upper())
                        
                # Also check metadata
                if metadata_depts := data.get('metadata', {}).get('departments', []):
                    subjects.update(dept.upper() for dept in metadata_depts if dept)
                    
            except Exception as e:
                click.echo(f"⚠️  Error reading {file_path}: {e}")
                continue
                
        return subjects
        
    def analyze_subjects(self, config: Dict, discovered: Set[str]) -> Dict[str, Set[str]]:
        """Analyze discovered subjects against configuration.
        
        Args:
            config: College configuration
            discovered: Set of discovered subjects
            
        Returns:
            Dictionary with analysis results
        """
        # Get configured subjects
        all_subjects = set(config.get('all_subjects', []))
        
        # Get subject management config
        subject_mgmt = config.get('subject_management', {})
        expected_subjects = set(subject_mgmt.get('expected_subjects', []))
        optional_subjects = set(subject_mgmt.get('optional_subjects', []))
        
        previously_discovered = set()
        for date_subjects in subject_mgmt.get('discovered_subjects', {}).values():
            previously_discovered.update(date_subjects)
            
        # Analyze
        analysis = {
            'new_subjects': discovered - all_subjects,
            'missing_expected': expected_subjects - discovered,
            'missing_optional': optional_subjects - discovered,
            'missing_any': all_subjects - discovered,
            'total_discovered': discovered,
            'rediscovered': discovered & previously_discovered
        }
        
        return analysis
        
    def update_config_with_discoveries(self, config: Dict, analysis: Dict[str, Set[str]], 
                                     auto_update: bool = False) -> Tuple[Dict, bool]:
        """Update configuration with discovered subjects.
        
        Args:
            config: Current configuration
            analysis: Analysis results
            auto_update: Whether to automatically add new subjects
            
        Returns:
            Tuple of (updated_config, was_modified)
        """
        modified = False
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # Initialize subject management section if needed
        if 'subject_management' not in config:
            config['subject_management'] = {
                'expected_subjects': [],
                'optional_subjects': [],
                'discovered_subjects': {},
                'deprecated_subjects': {},
                'last_discovery': None
            }
            modified = True
            
        subject_mgmt = config['subject_management']
        
        # Update last discovery timestamp
        subject_mgmt['last_discovery'] = datetime.now(timezone.utc).isoformat() + "Z"
        
        # Handle new subjects
        if analysis['new_subjects']:
            if timestamp not in subject_mgmt['discovered_subjects']:
                subject_mgmt['discovered_subjects'][timestamp] = []
                
            # Add new subjects to discovered list
            for subject in sorted(analysis['new_subjects']):
                if subject not in subject_mgmt['discovered_subjects'][timestamp]:
                    subject_mgmt['discovered_subjects'][timestamp].append(subject)
                    modified = True
                    
            # Optionally add to all_subjects
            if auto_update:
                if 'all_subjects' not in config:
                    config['all_subjects'] = []
                    
                current_all = set(config['all_subjects'])
                updated_all = sorted(current_all | analysis['new_subjects'])
                
                if updated_all != config['all_subjects']:
                    config['all_subjects'] = updated_all
                    modified = True
                    
        # Handle missing expected subjects
        if analysis['missing_expected']:
            if timestamp not in subject_mgmt['deprecated_subjects']:
                subject_mgmt['deprecated_subjects'][timestamp] = []
                
            for subject in sorted(analysis['missing_expected']):
                if subject not in subject_mgmt['deprecated_subjects'][timestamp]:
                    subject_mgmt['deprecated_subjects'][timestamp].append(subject)
                    modified = True
                    
        return config, modified
        
    def generate_report(self, analysis: Dict[str, Set[str]]) -> str:
        """Generate human-readable report of discoveries.
        
        Args:
            analysis: Analysis results
            
        Returns:
            Formatted report string
        """
        lines = [
            f"\n📊 Subject Discovery Report for {self.college_id.title()}",
            "=" * 50
        ]
        
        # Summary
        lines.extend([
            f"Total subjects discovered: {len(analysis['total_discovered'])}",
            ""
        ])
        
        # New subjects
        if analysis['new_subjects']:
            lines.extend([
                f"🆕 NEW SUBJECTS FOUND ({len(analysis['new_subjects'])}):",
                *[f"   - {subj}" for subj in sorted(analysis['new_subjects'])],
                ""
            ])
            
        # Missing expected subjects
        if analysis['missing_expected']:
            lines.extend([
                f"⚠️  MISSING EXPECTED SUBJECTS ({len(analysis['missing_expected'])}):",
                *[f"   - {subj}" for subj in sorted(analysis['missing_expected'])],
                ""
            ])
            
        # Missing optional subjects
        if analysis['missing_optional']:
            lines.extend([
                f"ℹ️  Missing optional subjects ({len(analysis['missing_optional'])}):",
                *[f"   - {subj}" for subj in sorted(analysis['missing_optional'])],
                ""
            ])
            
        # Rediscovered subjects
        if analysis['rediscovered']:
            lines.extend([
                f"♻️  Previously discovered subjects found again ({len(analysis['rediscovered'])}):",
                *[f"   - {subj}" for subj in sorted(analysis['rediscovered'])],
                ""
            ])
            
        # All discovered subjects
        if analysis['total_discovered']:
            lines.extend([
                "\n📋 All discovered subjects:",
                ", ".join(sorted(analysis['total_discovered']))
            ])
            
        return "\n".join(lines)


@click.command()
@click.option('--college', '-c', required=True, 
              help='College ID (e.g., rio-hondo, citrus)')
@click.option('--update', '-u', is_flag=True,
              help='Update config with discoveries')
@click.option('--output', '-o', type=click.Choice(['text', 'json', 'yaml']), 
              default='text', help='Output format')
@click.option('--quiet', '-q', is_flag=True,
              help='Suppress output except errors')
def main(college: str, update: bool, output: str, quiet: bool):
    """Discover and manage subject codes from collected schedule data."""
    discovery = SubjectDiscovery(college)
    
    try:
        # Load config
        config = discovery.load_config()
        
        # Discover subjects
        discovered = discovery.discover_subjects_from_data()
        
        if not discovered:
            click.echo("❌ No subjects found in collected data", err=True)
            sys.exit(1)
            
        # Analyze
        analysis = discovery.analyze_subjects(config, discovered)
        
        # Update config if requested
        if update:
            config, modified = discovery.update_config_with_discoveries(
                config, analysis, auto_update=True
            )
            
            if modified:
                discovery.save_config(config)
                if not quiet:
                    click.echo("✅ Configuration updated")
            else:
                if not quiet:
                    click.echo("ℹ️  No configuration changes needed")
                    
        # Output results
        if not quiet:
            if output == 'text':
                click.echo(discovery.generate_report(analysis))
            elif output == 'json':
                # Convert sets to lists for JSON serialization
                json_analysis = {k: sorted(list(v)) for k, v in analysis.items()}
                click.echo(json.dumps(json_analysis, indent=2))
            elif output == 'yaml':
                yaml_analysis = {k: sorted(list(v)) for k, v in analysis.items()}
                click.echo(yaml.dump(yaml_analysis, default_flow_style=False))
                
        # Exit with appropriate code
        if analysis['new_subjects']:
            sys.exit(2)  # New subjects found
        elif analysis['missing_expected']:
            sys.exit(3)  # Missing expected subjects
        else:
            sys.exit(0)  # All good
            
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()