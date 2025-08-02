# Adding New Colleges to CCC Schedule Collector

This guide explains how to add support for a new California Community College to the schedule collector.

## Overview

The collector uses a plugin-like architecture where each college has its own:
- Collector class (extends `BaseCollector`)
- Parser class (specific to the college's HTML format)
- Configuration file
- GitHub Actions workflow

## Step-by-Step Guide

### 1. Create College Directory Structure

```bash
mkdir -p collectors/your_college
touch collectors/your_college/__init__.py
touch collectors/your_college/collector.py
touch collectors/your_college/parser.py
touch collectors/your_college/config.json
```

### 2. Analyze the College's Schedule System

Before implementing, research the college's schedule system:

1. **Find the schedule URL**: Look for terms like "class schedule", "course search", or "Banner"
2. **Identify the system**: Most use Banner (Ellucian) but with different versions
3. **Note the term code format**: Each college uses different patterns
   - Rio Hondo: `202570` (year + season code)
   - Citrus: `202620` (year + different season code)
4. **Test the endpoints**: Use browser developer tools to see request/response

### 3. Create the Configuration File

Create `collectors/your_college/config.json`:

```json
{
  "college_id": "your-college",
  "collector_version": "1.0.0",
  "base_url": "https://ssb.yourcollege.edu/PROD",
  "search_endpoint": "endpoint_for_search",
  "schedule_endpoint": "endpoint_for_results",
  "parser_type": "beautifulsoup",
  
  "current_term": {
    "code": "202570",
    "name": "Fall 2025"
  },
  
  "terms": [
    {"code": "202570", "name": "Fall 2025"},
    {"code": "202520", "name": "Spring 2025"}
  ],
  
  "departments": ["ALL"],
  
  "rate_limit": {
    "requests_per_second": 0.5,
    "retry_attempts": 3
  },
  
  "http_config": {
    "timeout": 60,
    "verify_ssl": true
  },
  
  "user_agent": "CCC-Schedule-Collector/1.0",
  
  "selectors": {
    "schedule_table": "table.datadisplaytable",
    "course_rows": "tr",
    "crn": "td:nth-child(1)"
    // Add more selectors as needed
  }
}
```

### 4. Implement the Parser

Create `collectors/your_college/parser.py`:

```python
from models import Course, MeetingTime, Enrollment, ScheduleData
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class YourCollegeScheduleParser:
    """Parser for Your College's HTML schedule format."""
    
    def parse_schedule_html(self, html_content: str, term_name: str, 
                           term_code: str, source_url: str) -> ScheduleData:
        """Parse the HTML schedule page into structured data."""
        soup = BeautifulSoup(html_content, 'html.parser')
        courses = []
        
        # Find and parse the schedule table
        # This will vary based on the college's HTML structure
        
        return ScheduleData(
            term=term_name,
            term_code=term_code,
            collection_timestamp=datetime.now(),
            source_url=source_url,
            college_id='your-college',
            collector_version='1.0.0',
            courses=courses
        )
```

### 5. Implement the Collector

Create `collectors/your_college/collector.py`:

```python
from collectors.base_collector import BaseCollector
from .parser import YourCollegeScheduleParser

class YourCollegeCollector(BaseCollector):
    """Collector for Your College schedule data."""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent / 'config.json'
        super().__init__(config_path)
        self.parser = YourCollegeScheduleParser()
    
    def fetch_data(self, term_code: Optional[str] = None) -> str:
        """Fetch raw HTML data from the college's schedule system."""
        # Implement the data fetching logic
        pass
    
    def parse_data(self, raw_data: str, term_code: Optional[str] = None) -> ScheduleData:
        """Parse HTML data into ScheduleData format."""
        # Use the parser to convert HTML to structured data
        return self.parser.parse_schedule_html(raw_data, term_name, term_code, source_url)
```

### 6. Register the Collector

Update `collect.py` to add your college:

```python
COLLECTORS = {
    'rio-hondo': RioHondoCollector,
    'citrus': get_citrus_collector,
    'your-college': get_your_college_collector,
}

def get_your_college_collector():
    """Lazy import of YourCollegeCollector."""
    from collectors.your_college.collector import YourCollegeCollector
    return YourCollegeCollector
```

### 7. Create GitHub Actions Workflow

Create `.github/workflows/collect-your-college.yml`:

```yaml
name: Collect Your College Schedule

on:
  workflow_dispatch:
    inputs:
      term_code:
        description: 'Term code to collect'
        required: false
        type: string
  # Uncomment after testing
  # schedule:
  #   - cron: '26 8,16,0 * * *'  # Use different times than other colleges

jobs:
  collect:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
      with:
        token: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    
    - name: Install uv
      uses: yezz123/setup-uv@v4
      with:
        uv-version: "0.5.16"
    
    - name: Create data directory
      run: mkdir -p data/your-college
    
    - name: Collect schedule data
      run: |
        chmod +x collect.py
        uv run collect.py --college your-college
    
    - name: Commit and push changes
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add data/your-college/
        if git diff --staged --quiet; then
          echo "No changes to commit"
        else
          TIMESTAMP=$(date -u)
          git commit -m "Latest Your College data: ${TIMESTAMP}"
          git push
        fi
```

### 8. Test Your Implementation

1. **Test locally first**:
   ```bash
   ./collect.py --college your-college --no-save
   ```

2. **Create test fixtures**:
   - Save sample HTML to `tests/fixtures/your-college-fall-2025.html`
   - Write unit tests in `tests/test_your_college_collector.py`

3. **Test the GitHub workflow**:
   - Push your changes
   - Go to Actions → "Collect Your College Schedule"
   - Run workflow manually
   - Check for errors in the logs

### 9. Document College-Specific Details

Create `docs/colleges/your-college.md` with:
- Term code patterns
- Known quirks or issues
- Special parsing requirements
- Maintenance windows
- Contact information for issues

## Common Patterns

### Banner Systems

Most California Community Colleges use Banner by Ellucian. Common endpoints:

- Search: `bwckschd.p_get_crse_unsec` or `az_tw_zipsched.P_SEARCH`
- Results: `bwckschd.p_disp_dyn_sched` or similar
- Details: `bwckschd.p_disp_detail_sched`

### Term Code Patterns

Common patterns for term codes:

- Year + Season: `202570` where last two digits indicate term
  - `10` = Winter
  - `20` = Spring  
  - `30` = Summer
  - `70` = Fall
- Variations exist - always verify with the college

### HTML Structure

Most Banner systems use similar HTML:
- Table with class `datadisplaytable`
- Subject headers in separate rows
- Course data in regular table rows
- Enrollment data in specific columns

## Troubleshooting

### Common Issues

1. **SSL Certificate Errors**: Some colleges have certificate issues
   - Set `verify_ssl: false` in config (not recommended for production)

2. **Session Requirements**: Some systems require maintaining session
   - May need to implement cookie handling

3. **Rate Limiting**: Be respectful of college servers
   - Keep `requests_per_second` low (0.5 or less)
   - Add delays between requests

4. **Dynamic Content**: Some use JavaScript to load data
   - May need Selenium or similar for these cases

### Testing Tips

1. Start with a small department before trying "ALL"
2. Test during off-peak hours
3. Use browser developer tools to understand the requests
4. Save sample HTML for unit tests
5. Check robots.txt and terms of service

## Getting Help

If you need help adding a new college:

1. Open an issue with the college name and schedule URL
2. Provide sample HTML if possible
3. Note any specific requirements or challenges
4. Join the discussions in the Issues section

## Contributing Back

Once your college collector is working:

1. Ensure all tests pass
2. Document any college-specific quirks
3. Submit a pull request
4. Help maintain the collector over time

Remember: The goal is to help students access public schedule information more easily!