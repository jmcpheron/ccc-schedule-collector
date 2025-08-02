# CCC Schedule Collector

[![Tests](https://github.com/jmcpheron/ccc-schedule-collector/actions/workflows/test.yml/badge.svg)](https://github.com/jmcpheron/ccc-schedule-collector/actions/workflows/test.yml)
[![Schedule Collection](https://github.com/jmcpheron/ccc-schedule-collector/actions/workflows/collect.yml/badge.svg)](https://github.com/jmcpheron/ccc-schedule-collector/actions/workflows/collect.yml)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-Package%20Manager-green?logo=python&logoColor=white)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-4-orange)](https://www.crummy.com/software/BeautifulSoup/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A GitHub Actions-powered schedule collector for California Community Colleges, featuring automated HTML parsing and zero-dependency Python scripts using UV. Supports multiple colleges including Rio Hondo and Citrus College, with a framework designed for easy expansion.

## Overview

This project implements a **cloud-based collector** that automatically gathers course schedule data from California Community College Banner 8 systems and stores it over time in your GitHub repository. Part of the larger [CCC Schedule](https://github.com/jmcpheron/ccc-schedule) ecosystem, this collector provides the data foundation for building schedule viewers and analysis tools.

Currently supports:
- **Rio Hondo College** - Full implementation with automated collection
- **Citrus College** - New implementation ready for testing

The framework is designed to easily add support for additional California Community Colleges.

### Key Benefits

- 🚀 **Zero Infrastructure**: Runs entirely on GitHub Actions - no servers needed
- 📊 **Historical Data**: Accumulates schedule snapshots over time
- 🔄 **Automated Collection**: Runs on schedule or manual trigger
- 📋 **Structured Output**: Clean JSON data ready for the CCC Schedule viewer

## Features

- 🤖 **Automated Collection**: Designed to run 3x per week via GitHub Actions (currently in development)
- 📊 **Rich Data Models**: Structured Pydantic models for all course data
- 🔍 **HTML Parsing**: BeautifulSoup-based parser for Banner 8 schedule formats
- 💾 **Smart Storage**: JSON files with optional compression and symlinks
- 🛠️ **CLI Tools**: Analyze, compare, validate, and export collected data
- 📈 **Historical Tracking**: Compare schedules over time to spot trends
- 🧪 **Comprehensive Tests**: Full test suite with pytest

## Quick Start

1. **Clone or fork this repository**
2. **Push to GitHub**: The collector will start running automatically
3. **Watch it work**: Check the Actions tab to see your collector in action

That's it! Once enabled, your collector will run in the cloud, gathering schedule data 3x per week.

## How It Works

### Cloud-First Architecture

All data collection happens in **GitHub Actions runners** - ephemeral Linux containers that spin up, run your collector, commit the results, and disappear. You never need to run anything locally except for development.

```yaml
# .github/workflows/collect.yml - The heart of your cloud collector
name: Collect Schedule
on:
  schedule:
    - cron: '0 6 * * 1,3,5'  # Will run in the cloud 3x/week when enabled
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
class ScheduleParser:
    def parse_schedule_html(self, html_content: str) -> ScheduleData:
        # Parses course tables, headers, and rows
        # Handles enrollment data, meeting times, locations
        # Returns structured Pydantic models
```

### Robust Parsing Strategy

The parser is designed to handle Banner 8 HTML structures:
- Extracts course data from nested tables
- Handles multiple course sections and labs
- Parses complex meeting time formats
- Gracefully handles missing or malformed data
- Currently configured for Rio Hondo College's specific format

## Project Structure

```
ccc-schedule-collector/
├── collect.py             # Main collector with UV inline deps
├── test_collector.py      # Pytest test suite
├── cli.py                 # Rich CLI tools (info, validate, compare, etc.)
├── config.yml             # College configuration (currently Rio Hondo)
├── models.py              # Pydantic data models
├── utils/
│   ├── parser.py          # BeautifulSoup HTML parser
│   └── storage.py         # JSON storage with compression
├── .github/workflows/
│   ├── collect.yml        # Scheduled collection (Mon/Wed/Fri - currently disabled for testing)
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
# College-specific configuration
rio_hondo:  # First supported college
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

## CLI Commands

The project includes powerful command-line tools for data analysis:

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

## Quick Start

### For Schedule Collection (GitHub)

1. **Fork this repository**
2. **Enable Actions** in your fork (Settings → Actions → Enable)
3. **Choose your college(s)**:
   - Rio Hondo: Already configured, just enable the workflow
   - Citrus: Enable `.github/workflows/collect-citrus.yml`
   - Both: Enable both workflows
4. **Enable collection** by editing the workflow files:
   - Uncomment the schedule trigger to enable automatic collection
   - Or use manual triggers via the Actions tab
5. **Push changes** - collection will run automatically on the schedule or via manual trigger

### For Local Development

```bash
# Clone the repository
git clone https://github.com/jmcpheron/ccc-schedule-collector.git
cd ccc-schedule-collector

# Install UV if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run setup
./setup.sh

# Test Rio Hondo with local HTML file
./test_local.py --save --debug

# Test actual collection (be respectful of servers)
./test_collection.py --test-connection

# Collect from specific colleges
./collect.py --college rio-hondo
./collect.py --college citrus
```

### Manual Collection

Trigger collection manually from GitHub:
1. Go to Actions → Choose your workflow:
   - "Collect Rio Hondo Schedule" for Rio Hondo
   - "Collect Citrus Schedule" for Citrus
2. Click "Run workflow"
3. Check the appropriate folder for results:
   - Rio Hondo: `/data/rio-hondo/`
   - Citrus: `/data/citrus/`

## Testing

The project includes comprehensive tests using pytest:

```bash
# Run all tests
uv run test_collector.py

# Run specific test
uv run pytest test_collector.py::TestParser::test_parse_schedule_html -v

# Run with coverage
uv run pytest --cov

# Lint code
uv run ruff check .

# Type checking
uv run mypy .
```

## Documentation

- [Local Testing Guide](LOCAL_TESTING.md) - Detailed guide for testing locally
- [Contributing Guidelines](CONTRIBUTING.md) - How to contribute to the project
- [Claude Code Instructions](CLAUDE.md) - AI assistant guidance

## Integration with CCC Schedule

This collector is designed to work with the [CCC Schedule](https://github.com/jmcpheron/ccc-schedule) viewer:

1. **Collect data** using this repository
2. **Transform data** to the unified schema format
3. **Display data** using the CCC Schedule web interface

## Architecture

### Data Flow

```
CCC Website → HTML Parser → JSON Data → GitHub Storage
                                   ↓
                           CCC Schedule Viewer
```

### Key Components

- **models.py**: Pydantic models for type-safe data handling
- **collectors/**: College-specific implementations
  - **base_collector.py**: Abstract base class for all collectors
  - **rio_hondo/**: Rio Hondo specific parser and collector
  - **citrus/**: Citrus College specific parser and collector
- **utils/storage.py**: JSON storage with compression and college-specific directories
- **collect.py**: Main collector with college selection
- **cli.py**: Analysis and export tools

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Part of the [CCC Schedule](https://github.com/jmcpheron/ccc-schedule) ecosystem. Inspired by Simon Willison's [git-scraper](https://github.com/simonw/git-scraper-template) approach for using Git as a data store.*