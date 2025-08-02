#!/usr/bin/env python3
"""Storage utility for saving and loading schedule data."""

import json
import gzip
import bz2
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
import logging

from models import ScheduleData, CollectionMetadata

logger = logging.getLogger(__name__)


class ScheduleStorage:
    """Handles storage operations for schedule data."""
    
    def __init__(self, data_dir: str = "data", compression: str = "none", college_id: Optional[str] = None):
        """Initialize storage with data directory and compression settings.
        
        Args:
            data_dir: Base data directory
            compression: Compression type (none, gzip, bzip2)
            college_id: Optional college ID for college-specific subdirectory
        """
        self.data_dir = Path(data_dir)
        self.compression = compression
        self.college_id = college_id
        
        # Create college-specific subdirectory if college_id provided
        if college_id:
            self.data_dir = self.data_dir / college_id
            
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def save_schedule(self, schedule_data: ScheduleData) -> str:
        """Save schedule data to file."""
        # Generate fixed filename
        filename = f"schedule_{schedule_data.term_code}_latest.json"
        
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
                # Handle both with and without 'Z' suffix
                timestamp_str = data['collection_timestamp']
                if timestamp_str.endswith('Z'):
                    timestamp_str = timestamp_str[:-1] + '+00:00'
                data['collection_timestamp'] = datetime.fromisoformat(timestamp_str)
                
            return ScheduleData(**data)
            
        except Exception as e:
            logger.error(f"Failed to load schedule data from {filepath}: {e}")
            raise
    
    def list_schedules(self, term_code: Optional[str] = None) -> List[Path]:
        """List all saved schedule files, optionally filtered by term."""
        pattern = f"schedule_{term_code}_latest.json*" if term_code else "schedule_*_latest.json*"
        files = list(self.data_dir.glob(pattern))
        return sorted(files)  # Alphabetical order by term code
    
    def get_latest_schedule(self, term_code: Optional[str] = None) -> Optional[Path]:
        """Get the latest schedule file for a given term."""
        if term_code:
            filename = f"schedule_{term_code}_latest.json"
        else:
            # If no term specified, find any latest file
            pattern = "schedule_*_latest.json"
            if self.compression == "gzip":
                pattern += ".gz"
            elif self.compression == "bzip2":
                pattern += ".bz2"
            files = list(self.data_dir.glob(pattern))
            return files[0] if files else None
            
        # Add compression extension if needed
        if self.compression == "gzip":
            filename += ".gz"
        elif self.compression == "bzip2":
            filename += ".bz2"
            
        filepath = self.data_dir / filename
        return filepath if filepath.exists() else None
    
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
    
    
    def cleanup_old_files(self, keep_count: int = 30):
        """No longer needed - keeping only latest file per term."""
        # This method is kept for backward compatibility but does nothing
        # since we now overwrite the same file each time
        pass