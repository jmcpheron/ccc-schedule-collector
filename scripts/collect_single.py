#!/usr/bin/env python3
"""Script to collect schedule data for a single college."""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.rio_hondo.collector import RioHondoCollector


# Map of college IDs to collector classes
COLLECTORS = {
    'rio-hondo': RioHondoCollector,
    # Add more colleges here as they are implemented
    # 'north-orange-county': NorthOrangeCountyCollector,
    # 'west-valley-mission': WestValleyMissionCollector,
}


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Collect schedule data for a single college'
    )
    parser.add_argument(
        'college',
        choices=list(COLLECTORS.keys()),
        help='College ID to collect data for'
    )
    parser.add_argument(
        '--term-code',
        help='Term code to collect (e.g., 202570 for Fall 2025)'
    )
    parser.add_argument(
        '--config',
        help='Path to custom config file'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save output to file (print to stdout instead)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get collector class
        CollectorClass = COLLECTORS[args.college]
        
        # Initialize collector
        collector = CollectorClass(config_path=args.config)
        
        # Collect data
        logger.info(f"Starting collection for {args.college}")
        schedule_data = collector.collect(
            term_code=args.term_code,
            save=not args.no_save
        )
        
        # Print summary
        print(f"\nCollection Summary for {args.college}:")
        print(f"- Term: {schedule_data.term}")
        print(f"- Term Code: {schedule_data.term_code}")
        print(f"- College ID: {schedule_data.college_id}")
        print(f"- Collector Version: {schedule_data.collector_version}")
        print(f"- Total Courses: {len(schedule_data.courses)}")
        
        if schedule_data.metadata:
            if 'departments' in schedule_data.metadata:
                print(f"- Departments: {len(schedule_data.metadata['departments'])}")
            if 'collection_errors' in schedule_data.metadata:
                errors = schedule_data.metadata['collection_errors']
                if errors:
                    print(f"- Errors: {len(errors)}")
        
        print(f"- Timestamp: {schedule_data.collection_timestamp}")
        
        if args.no_save:
            # Print full data to stdout
            print("\nFull Schedule Data:")
            print(json.dumps(schedule_data.model_dump(), indent=2, default=str))
        else:
            if hasattr(collector, 'collection_metadata') and collector.collection_metadata:
                meta = collector.collection_metadata
                print(f"\nCollection took {meta.duration_seconds:.2f} seconds")
                if meta.errors:
                    print(f"Errors encountered: {len(meta.errors)}")
                    for error in meta.errors[:5]:  # Show first 5 errors
                        print(f"  - {error}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Collection failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())