#!/usr/bin/env python3
"""Script to collect schedule data for all configured colleges."""

import argparse
import concurrent.futures
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

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


def collect_college(college_id: str, term_code: str = None) -> Tuple[str, bool, Dict[str, Any]]:
    """Collect data for a single college.
    
    Args:
        college_id: College ID to collect
        term_code: Optional term code
        
    Returns:
        Tuple of (college_id, success, result_data)
    """
    logger = logging.getLogger(__name__)
    
    try:
        CollectorClass = COLLECTORS[college_id]
        collector = CollectorClass()
        
        logger.info(f"Starting collection for {college_id}")
        schedule_data = collector.collect(term_code=term_code, save=True)
        
        result = {
            'term': schedule_data.term,
            'courses_collected': len(schedule_data.courses),
            'timestamp': schedule_data.collection_timestamp,
            'metadata': schedule_data.metadata
        }
        
        if hasattr(collector, 'collection_metadata') and collector.collection_metadata:
            result['duration'] = collector.collection_metadata.duration_seconds
            result['errors'] = collector.collection_metadata.errors
        
        return (college_id, True, result)
        
    except Exception as e:
        logger.error(f"Collection failed for {college_id}: {e}")
        return (college_id, False, {'error': str(e)})


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Collect schedule data for all configured colleges'
    )
    parser.add_argument(
        '--colleges',
        nargs='+',
        choices=list(COLLECTORS.keys()),
        help='Specific colleges to collect (default: all)'
    )
    parser.add_argument(
        '--term-code',
        help='Term code to collect (e.g., 202570 for Fall 2025)'
    )
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Run collections in parallel'
    )
    parser.add_argument(
        '--max-workers',
        type=int,
        default=3,
        help='Maximum number of parallel workers (default: 3)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    
    # Determine which colleges to collect
    colleges = args.colleges if args.colleges else list(COLLECTORS.keys())
    
    logger.info(f"Collecting data for {len(colleges)} colleges")
    
    results = []
    
    if args.parallel and len(colleges) > 1:
        # Parallel collection
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(collect_college, college_id, args.term_code): college_id
                for college_id in colleges
            }
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
    else:
        # Sequential collection
        for college_id in colleges:
            result = collect_college(college_id, args.term_code)
            results.append(result)
    
    # Print summary
    print("\nCollection Summary:")
    print("-" * 60)
    
    successful = 0
    failed = 0
    total_courses = 0
    total_duration = 0.0
    
    for college_id, success, data in results:
        status = "✓" if success else "✗"
        print(f"\n{status} {college_id}:")
        
        if success:
            successful += 1
            courses = data.get('courses_collected', 0)
            total_courses += courses
            print(f"  - Term: {data.get('term', 'N/A')}")
            print(f"  - Courses: {courses}")
            print(f"  - Timestamp: {data.get('timestamp', 'N/A')}")
            
            if 'duration' in data:
                duration = data['duration']
                total_duration += duration
                print(f"  - Duration: {duration:.2f} seconds")
                
            if 'errors' in data and data['errors']:
                print(f"  - Warnings: {len(data['errors'])}")
        else:
            failed += 1
            print(f"  - Error: {data.get('error', 'Unknown error')}")
    
    print("\n" + "-" * 60)
    print(f"Total: {successful} successful, {failed} failed")
    print(f"Total courses collected: {total_courses}")
    if total_duration > 0:
        print(f"Total time: {total_duration:.2f} seconds")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())