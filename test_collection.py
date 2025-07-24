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
"""Test the full collection process locally."""

import sys
from pathlib import Path
import click

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from collectors.rio_hondo.collector import RioHondoCollector


@click.command()
@click.option('--config', default='collectors/rio_hondo/config.json', help='Config file to use')
@click.option('--term-code', help='Specific term code to collect')
@click.option('--test-connection', is_flag=True, help='Just test the connection')
def test_collection(config: str, term_code: str, test_connection: bool):
    """Test the web collection process locally."""
    
    print(f"🌐 Testing web collection with {config}")
    
    # Create test data directory
    Path("data/test").mkdir(parents=True, exist_ok=True)
    
    try:
        collector = RioHondoCollector(config_path=config)
        
        if test_connection:
            # Just test that we can connect
            print("🔗 Testing connection to Rio Hondo...")
            import requests
            
            base_url = collector.config['base_url']
            endpoint = collector.config['schedule_endpoint']
            url = f"{base_url}/{endpoint}"
            
            print(f"   URL: {url}")
            
            # Try a simple GET request first
            response = collector.session.get(base_url, timeout=10)
            print(f"✅ Connection successful! Status: {response.status_code}")
            
            return
        
        # Run the collection
        print("\n🚀 Starting collection...")
        print(f"   Departments: {collector.config['departments']}")
        
        schedule_data = collector.collect(term_code=term_code, save=True)
        
        print(f"\n✅ Collection complete!")
        print(f"   Courses collected: {len(schedule_data.courses)}")
        
        # Get departments from metadata
        departments = schedule_data.metadata.get('departments', []) if schedule_data.metadata else []
        print(f"   Departments found: {len(departments)}")
        
        # Show some statistics
        if schedule_data.courses:
            online_courses = sum(1 for c in schedule_data.courses if 'online' in c.location.lower())
            full_courses = sum(1 for c in schedule_data.courses if c.enrollment.remaining == 0)
            
            print(f"\n📊 Quick stats:")
            print(f"   Online courses: {online_courses}")
            print(f"   Full courses: {full_courses}")
            print(f"   Courses with TBA instructor: {sum(1 for c in schedule_data.courses if c.instructor == 'TBA')}")
        
    except Exception as e:
        print(f"\n❌ Error during collection: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n✨ Test complete! Check data/test/ for results.")


if __name__ == "__main__":
    test_collection()