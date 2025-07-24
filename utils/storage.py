#!/usr/bin/env python3
"""Storage utility for saving and loading schedule data."""

import json
import gzip
import bz2
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import logging

from models import ScheduleData, CollectionMetadata

logger = logging.getLogger(__name__)


class ScheduleStorage:
    """Handles storage operations for schedule data."""
    
    def __init__(self, data_dir: str = "data", compression: str = "none"):
        """Initialize storage with data directory and compression settings."""
        self.data_dir = Path(data_dir)
        self.compression = compression
        self.data_dir.mkdir(exist_ok=True)
        
    def save_schedule(self, schedule_data: ScheduleData, 
                     filename_pattern: str = "schedule_{term_code}_{timestamp}.json",
                     create_latest_link: bool = True) -> str:
        """Save schedule data to file."""
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filename_pattern.format(
            term_code=schedule_data.term_code,
            timestamp=timestamp
        )
        
        # Add compression extension if needed
        if self.compression == "gzip":
            filename += ".gz"
        elif self.compression == "bzip2":
            filename += ".bz2"
            
        filepath = self.data_dir / filename
        
        # Convert to dict using Pydantic's model_dump
        data_dict = schedule_data.model_dump(mode='json')
        
        # Save file with appropriate compression
        try:
            if self.compression == "gzip":
                with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                    json.dump(data_dict, f, indent=2)
            elif self.compression == "bzip2":
                with bz2.open(filepath, 'wt', encoding='utf-8') as f:
                    json.dump(data_dict, f, indent=2)
            else:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data_dict, f, indent=2)
                    
            logger.info(f"Saved schedule data to {filepath}")
            
            # Create latest symlink
            if create_latest_link:
                self._create_latest_link(filepath, schedule_data.term_code)
                
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to save schedule data: {e}")
            raise
    
    def load_schedule(self, filepath: str) -> ScheduleData:
        """Load schedule data from file."""
        filepath = Path(filepath)
        
        try:
            # Determine compression from extension
            if filepath.suffix == '.gz':
                with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            elif filepath.suffix == '.bz2':
                with bz2.open(filepath, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
            # Convert collection_timestamp string back to datetime
            if isinstance(data.get('collection_timestamp'), str):
                data['collection_timestamp'] = datetime.fromisoformat(data['collection_timestamp'])
                
            return ScheduleData(**data)
            
        except Exception as e:
            logger.error(f"Failed to load schedule data from {filepath}: {e}")
            raise
    
    def list_schedules(self, term_code: Optional[str] = None) -> List[Path]:
        """List all saved schedule files, optionally filtered by term."""
        pattern = f"schedule_{term_code}_*.json*" if term_code else "schedule_*.json*"
        files = list(self.data_dir.glob(pattern))
        return sorted(files, reverse=True)  # Most recent first
    
    def get_latest_schedule(self, term_code: Optional[str] = None) -> Optional[Path]:
        """Get the most recent schedule file."""
        files = self.list_schedules(term_code)
        return files[0] if files else None
    
    def save_metadata(self, metadata: CollectionMetadata, 
                     filename: str = "collection_metadata.json") -> str:
        """Save collection metadata."""
        filepath = self.data_dir / filename
        
        # Append to existing metadata if file exists
        existing_data = []
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    existing_data = json.load(f)
            except:
                pass
                
        # Add new metadata
        existing_data.append(metadata.model_dump(mode='json'))
        
        # Keep only last 100 entries
        if len(existing_data) > 100:
            existing_data = existing_data[-100:]
            
        with open(filepath, 'w') as f:
            json.dump(existing_data, f, indent=2, default=str)
            
        return str(filepath)
    
    def _create_latest_link(self, filepath: Path, term_code: str):
        """Create a 'latest' symlink to the most recent file."""
        link_name = f"schedule_{term_code}_latest.json"
        if self.compression == "gzip":
            link_name += ".gz"
        elif self.compression == "bzip2":
            link_name += ".bz2"
            
        link_path = self.data_dir / link_name
        
        # Remove existing link if it exists
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
            
        # Create new symlink (relative path)
        try:
            link_path.symlink_to(filepath.name)
            logger.info(f"Created latest symlink: {link_path}")
        except Exception as e:
            logger.warning(f"Could not create symlink: {e}")
    
    def cleanup_old_files(self, keep_count: int = 30):
        """Remove old schedule files, keeping the most recent ones."""
        all_files = self.list_schedules()
        
        if len(all_files) <= keep_count:
            return
            
        # Sort by modification time
        files_with_time = [(f, f.stat().st_mtime) for f in all_files]
        files_with_time.sort(key=lambda x: x[1], reverse=True)
        
        # Remove old files
        for filepath, _ in files_with_time[keep_count:]:
            try:
                filepath.unlink()
                logger.info(f"Removed old file: {filepath}")
            except Exception as e:
                logger.error(f"Failed to remove {filepath}: {e}")