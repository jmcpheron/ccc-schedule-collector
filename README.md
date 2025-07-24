# Rio Hondo College Schedule Collector

**A GitHub Actions-powered schedule collector for Rio Hondo College, featuring automated HTML parsing and zero-dependency Python scripts using UV.**

## What This Does

This project implements a **cloud-based collector** that automatically gathers Rio Hondo College's course schedule data and stores it over time in your GitHub repository. No servers to maintain, no hosting costs - just GitHub Actions running your collector in the cloud on a schedule you define.

The collected data accumulates in your repo's `/data` folder, creating a historical record of schedule changes, new courses, and enrollment updates that you can analyze or build applications on top of.

## Features

- 🤖 **Automated Collection**: Runs 3x per week via GitHub Actions
- 📊 **Rich Data Models**: Structured Pydantic models for all course data
- 🔍 **HTML Parsing**: BeautifulSoup-based parser for Rio Hondo's schedule format
- 💾 **Smart Storage**: JSON files with optional compression and symlinks
- 🛠️ **CLI Tools**: Analyze, compare, validate, and export collected data
- 📈 **Historical Tracking**: Compare schedules over time to spot trends
- 🧪 **Comprehensive Tests**: Full test suite with pytest

## Quick Start

1. **Clone or fork this repository**
2. **Push to GitHub**: The collector will start running automatically
3. **Watch it work**: Check the Actions tab to see your collector in action

That's it! Your collector is now running in the cloud, gathering Rio Hondo's schedule data 3x per week.

## How It Works

### Cloud-First Architecture

All data collection happens in **GitHub Actions runners** - ephemeral Linux containers that spin up, run your collector, commit the results, and disappear. You never need to run anything locally except for development.

```yaml
# .github/workflows/collect.yml - The heart of your cloud collector
name: Collect Rio Hondo Schedule
on:
  schedule:
    - cron: '0 6 * * 1,3,5'  # Runs in the cloud 3x/week
  workflow_dispatch:         # Manual trigger button

jobs:
  collect:
    runs-on: ubuntu-latest   # Fresh Linux container every time
    steps:
    - name: Install uv       # Modern Python tooling
    - name: Run collector    # Your Python script with inline deps
    - name: Commit results   # Git stores the data automatically
```

### Self-Contained Python Scripts

Each script declares its dependencies inline using modern Python standards (PEP 723). GitHub Actions runners install these automatically:

```python
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "requests",
#   "beautifulsoup4",
#   "pydantic>=2.0",
#   "pyyaml"
# ]
# ///

# Your collection code here - runs in the cloud
```

### Traditional HTML Parsing

The collector uses BeautifulSoup for reliable HTML parsing:

```python
class RioHondoScheduleParser:
    def parse_schedule_html(self, html_content: str) -> ScheduleData:
        # Parses course tables, headers, and rows
        # Handles enrollment data, meeting times, locations
        # Returns structured Pydantic models
```

### Robust Parsing Strategy

The parser is designed to handle Rio Hondo's specific HTML structure:
- Extracts course data from nested tables
- Handles multiple course sections and labs
- Parses complex meeting time formats
- Gracefully handles missing or malformed data

## Project Structure

```
ccc-schedule-collector/
├── collect.py             # Main collector with UV inline deps
├── test_collector.py      # Pytest test suite
├── cli.py                 # Rich CLI tools (info, validate, compare, etc.)
├── config.yml             # Rio Hondo configuration
├── models.py              # Pydantic data models
├── utils/
│   ├── parser.py          # BeautifulSoup HTML parser
│   └── storage.py         # JSON storage with compression
├── .github/workflows/
│   ├── collect.yml        # Scheduled collection (Mon/Wed/Fri)
│   └── test.yml           # CI/CD tests on push/PR
└── data/                  # Collected schedule data
    ├── schedule_202570_latest.json  # Symlink to latest
    └── schedule_202570_20250124_120000.json
```

## Customization

### Change the Collection Schedule

Edit `.github/workflows/collect.yml`:

```yaml
schedule:
  - cron: '0 6 * * *'        # Daily at 6 AM
  - cron: '0 6,18 * * 1-5'   # Twice daily, weekdays only
  - cron: '0 6 * * 1'        # Weekly on Mondays
```

### Modify Target Pages

Edit `config.yml`:

```yaml
rio_hondo:
  # Current term configuration
  current_term:
    code: "202570"  # Fall 2025
    name: "Fall 2025"
  
  # Collect all departments or specify specific ones
  departments:
    - "ALL"  # Change to specific departments like ["MATH", "CS", "ENGL"]
  
  # Collection parameters
  search_params:
    begin_hh: "5"   # Start time filter
    end_hh: "11"    # End time filter
```

### Analyze Your Collected Data

The CLI provides powerful analysis tools:

```bash
# View courses by subject or instructor
uv run cli.py info data/schedule_202570_latest.json --subject MATH
uv run cli.py info data/schedule_202570_latest.json --instructor "Smith"

# Validate data quality
uv run cli.py validate data/schedule_*.json

# Compare schedules to track changes
uv run cli.py compare --weeks 2  # Compare with 2 weeks ago
uv run cli.py compare -f1 old.json -f2 new.json

# Generate summary reports
uv run cli.py report --days 30

# Export to CSV or Excel
uv run cli.py export data/latest.json output.csv
uv run cli.py export data/latest.json output.xlsx --format excel
```

## Why This Approach Works

**Zero Infrastructure**: No servers, databases, or hosting accounts needed. GitHub provides the compute and storage.

**Automatic Backups**: Every collection creates a git commit, so you have a complete history of changes.

**Collaborative**: Multiple people can contribute collectors for different colleges by forking and submitting PRs.

**Scalable**: Want to collect from 10 colleges? Create 10 repositories from this template.

**Cost Effective**: GitHub Actions provides 2,000 free minutes per month - more than enough for schedule collection.

**Educational Focus**: Designed specifically for collecting public course schedule information to help students, researchers, and developers build useful tools.

## Getting Started

### Option 1: Quick Start (Recommended)
1. Fork or clone this repository
2. Push to your GitHub account
3. The collector will automatically run on schedule (Mon/Wed/Fri at 6 AM UTC)
4. Check the `/data` folder for collected schedules

### Option 2: Local Development
1. Clone the repository
2. Run the setup script:
   ```bash
   ./setup.sh
   ```
3. Test the collector locally:
   ```bash
   uv run collect.py
   ```
4. Explore the data:
   ```bash
   uv run cli.py info data/schedule_*.json
   ```

### Manual Collection
You can trigger a collection manually from GitHub:
1. Go to Actions → "Collect Rio Hondo Schedule"
2. Click "Run workflow"
3. Watch the progress and check `/data` for results

---

## Implementation Details

### Data Models

The project uses comprehensive Pydantic models:
- **Course**: CRN, subject, title, units, instructor, meeting times, enrollment
- **MeetingTime**: Days, times, arranged/TBA handling  
- **Enrollment**: Capacity, actual, remaining seats
- **ScheduleData**: Complete collection with metadata

### Parser Features

- Handles complex table structures
- Extracts enrollment numbers and instructor info
- Parses meeting times and locations
- Identifies zero-textbook-cost courses
- Detects online/hybrid/in-person delivery methods

### Storage Options

- JSON format with optional gzip/bzip2 compression
- Automatic "latest" symlinks for easy access
- Metadata tracking for collection runs
- Configurable retention policies

### Configuration Options

The `config.yml` file controls:
- **Term settings**: Which semester to collect
- **Departments**: All or specific departments
- **Collection frequency**: Via GitHub Actions cron
- **Storage**: Compression, retention, file naming
- **Network**: Timeouts, retries, delays

### Future Enhancements

- **API Support**: The config includes disabled Claude API settings for potential future LLM-enhanced parsing
- **Multi-campus**: Extend to other California Community Colleges
- **Notifications**: Webhook support for collection status
- **Advanced Analytics**: Enrollment predictions, waitlist analysis

---

*Inspired by Simon Willison's git-scraper approach but built specifically for California Community College schedules with modern Python tooling.*