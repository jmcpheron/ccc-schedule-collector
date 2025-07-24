# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rio Hondo College Schedule Collector - A GitHub Actions-powered system that automatically collects and stores course schedule data from Rio Hondo College's Banner 8 system. Uses UV package management with inline dependencies (PEP 723) and BeautifulSoup for HTML parsing.

## Key Commands

### Testing & Development

```bash
# Test with local HTML file (rio-hondo-fall-2025.html)
./test_local.py --save --debug

# Test web collection locally (uses config_local.yml)
./test_collection.py --test-connection  # Check connection first
./test_collection.py                    # Actually collect data

# Run test suite
uv run test_collector.py

# Run specific test
uv run pytest test_collector.py::TestParser::test_parse_schedule_html -v
```

### CLI Analysis Tools

```bash
# View courses
uv run cli.py info data/schedule_*.json --subject MATH
uv run cli.py info data/schedule_*.json --instructor "Smith"

# Validate data quality
uv run cli.py validate data/schedule_*.json

# Compare schedules
uv run cli.py compare --weeks 2
uv run cli.py compare -f1 old.json -f2 new.json

# Generate reports
uv run cli.py report --days 30

# Export data
uv run cli.py export data/schedule_*.json output.csv
uv run cli.py export data/schedule_*.json output.xlsx --format excel
```

### Deployment

```bash
# Initialize git (if needed)
./init_git.sh

# Manual collection trigger
# Go to GitHub Actions → "Collect Rio Hondo Schedule" → "Run workflow"
```

## Architecture

### Core Components

1. **collect.py** - Main collector that fetches HTML from Rio Hondo and saves JSON data
   - Uses `RioHondoCollector` class configured via YAML
   - Creates timestamped JSON files in `/data`
   - Supports retry logic and configurable delays

2. **utils/parser.py** - HTML parser using BeautifulSoup
   - `RioHondoScheduleParser` handles Banner 8 HTML structure
   - Parses course rows with complex colspan handling for meeting times
   - Maintains subject/course context while processing rows sequentially

3. **utils/storage.py** - Data persistence layer
   - Saves as JSON with optional gzip/bzip2 compression
   - Creates "latest" symlinks for easy access
   - Tracks collection metadata

4. **models.py** - Pydantic data models
   - `Course`, `MeetingTime`, `Enrollment`, `ScheduleData`
   - Strict validation and type safety

### GitHub Actions Workflows

- **collect.yml**: Currently DISABLED for testing. When enabled:
  - Runs Mon/Wed/Fri at 6 AM UTC
  - Can be manually triggered
  - Commits collected data automatically
  
- **test.yml**: Runs on push/PR
  - Tests Python 3.9, 3.10, 3.11
  - Validates YAML syntax
  - Runs test suite

### Configuration

- **config.yml**: Production settings (all departments, full collection)
- **config_local.yml**: Test settings (limited departments, test output dir)

Key config sections:
- `rio_hondo.departments`: List of departments or "ALL"
- `rio_hondo.current_term`: Active term code/name
- `collection.request_delay`: Seconds between requests
- `output.compression`: none/gzip/bzip2

## Important Context

### HTML Parsing Specifics

The Rio Hondo HTML has quirks:
- Subject headers use `class = "subject_header"` (note the space)
- Course data rows alternate between `default1` and `default2` classes
- Meeting times can have `colspan="8"` for arranged/online courses
- Some courses have zero capacity (online sections)

### Current State

- **Collection is DISABLED** in GitHub Actions (see collect.yml lines 40-66)
- Schedule trigger is commented out (lines 4-7)
- To enable: Uncomment the relevant sections in collect.yml

### Local Testing Setup

Two test scripts for development:
- `test_local.py`: Parse saved HTML without hitting servers
- `test_collection.py`: Test actual web collection with rate limiting

Test data goes to `data/test/` when using `config_local.yml`.

### UV Package Management

All Python scripts use UV with inline dependencies:
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
```

This ensures zero-dependency execution in GitHub Actions.