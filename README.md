# Rio Hondo College Schedule Collector

[![Tests](https://github.com/jmcpheron/ccc-schedule-collector/actions/workflows/test.yml/badge.svg)](https://github.com/jmcpheron/ccc-schedule-collector/actions/workflows/test.yml)
[![Collect Schedule](https://github.com/jmcpheron/ccc-schedule-collector/actions/workflows/collect.yml/badge.svg)](https://github.com/jmcpheron/ccc-schedule-collector/actions/workflows/collect.yml)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-Package%20Manager-green?logo=python&logoColor=white)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-4-orange)](https://www.crummy.com/software/BeautifulSoup/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A GitHub Actions-powered schedule collector for Rio Hondo College, featuring automated HTML parsing and zero-dependency Python scripts using UV.

## Overview

This project implements a **cloud-based collector** that automatically gathers Rio Hondo College's course schedule data from their Banner 8 system and stores it over time in your GitHub repository. Part of the larger [CCC Schedule](https://github.com/jmcpheron/ccc-schedule) ecosystem, this collector provides the data foundation for building schedule viewers and analysis tools.

### Key Benefits

- 🚀 **Zero Infrastructure**: Runs entirely on GitHub Actions - no servers needed
- 📊 **Historical Data**: Accumulates schedule snapshots over time
- 🔄 **Automated Collection**: Runs on schedule or manual trigger
- 📋 **Structured Output**: Clean JSON data ready for the CCC Schedule viewer

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
3. **Enable collection** by editing `.github/workflows/collect.yml`:
   - Uncomment lines 5-7 (schedule trigger)
   - Uncomment lines 59-64 (actual collection)
4. **Push changes** - collection will run automatically

### For Local Development

```bash
# Clone the repository
git clone https://github.com/jmcpheron/ccc-schedule-collector.git
cd ccc-schedule-collector

# Install UV if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run setup
./setup.sh

# Test with local HTML file
./test_local.py --save --debug

# Test actual collection (be respectful of servers)
./test_collection.py --test-connection
```

### Manual Collection

Trigger collection manually from GitHub:
1. Go to Actions → "Collect Rio Hondo Schedule"
2. Click "Run workflow"
3. Check `/data` folder for results

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
Rio Hondo Website → HTML Parser → JSON Data → GitHub Storage
                                      ↓
                              CCC Schedule Viewer
```

### Key Components

- **models.py**: Pydantic models for type-safe data handling
- **utils/parser.py**: BeautifulSoup HTML parser for Banner 8
- **utils/storage.py**: JSON storage with compression support
- **collect.py**: Main collector with retry logic
- **cli.py**: Analysis and export tools

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Part of the [CCC Schedule](https://github.com/jmcpheron/ccc-schedule) ecosystem. Inspired by Simon Willison's git-scraper approach.*