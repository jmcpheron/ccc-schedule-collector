#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "requests",
#   "beautifulsoup4",
#   "pydantic>=2.0",
#   "pyyaml",
#   "click",
# ]
# ///
"""Main collector script for California Community College schedule data."""

import sys
import logging
import click
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from collectors.rio_hondo.collector import RioHondoCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Registry of available collectors
COLLECTORS = {
    'rio-hondo': RioHondoCollector,
    # Future collectors can be added here:
    # 'pasadena': PasadenaCollector,
    # 'mt-sac': MtSacCollector,
}


@click.command()
@click.option('--college', 
              type=click.Choice(list(COLLECTORS.keys())), 
              default='rio-hondo',
              help='Which college to collect data from')
@click.option('--config', 
              help='Path to config file (defaults to college-specific config.json)')
@click.option('--term-code', 
              help='Specific term code to collect (e.g., 202570)')
@click.option('--save/--no-save', 
              default=True,
              help='Whether to save the collected data')
def collect(college: str, config: Optional[str], term_code: Optional[str], save: bool):
    """Collect schedule data from California Community Colleges."""
    
    logger.info(f"Starting collection for {college}")
    
    try:
        # Get the appropriate collector class
        CollectorClass = COLLECTORS[college]
        
        # Initialize collector
        if config:
            collector = CollectorClass(config_path=config)
        else:
            collector = CollectorClass()
        
        # Run the collection
        schedule_data = collector.collect(term_code=term_code, save=save)
        
        # Print summary
        print(f"\n✅ Collection Summary:")
        print(f"- College: {schedule_data.college_id}")
        print(f"- Term: {schedule_data.term}")
        print(f"- Total courses: {len(schedule_data.courses)}")
        
        # Get departments from metadata
        departments = schedule_data.metadata.get('departments', []) if schedule_data.metadata else []
        print(f"- Departments: {len(departments)}")
        print(f"- Timestamp: {schedule_data.collection_timestamp}")
        
        if save:
            print(f"\n💾 Data saved to data/")
        
    except Exception as e:
        logger.error(f"Collection failed: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    collect()


if __name__ == "__main__":
    main()