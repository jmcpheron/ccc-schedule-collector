# Utility Scripts

This directory contains utility scripts for special operations outside the main collection workflow.

## Scripts

### parse_manual_download.py
Parses manually downloaded Rio Hondo schedule HTML files into structured JSON format.

**Usage:**
```bash
./scripts/parse_manual_download.py <html_file> [--no-save]
```

**Example:**
```bash
./scripts/parse_manual_download.py data/raw/2025-01-26_rio_hondo_fall_2025.html
```

### collect_details.py
Collects detailed course information from a parsed basic schedule JSON file.

**Usage:**
```bash
./scripts/collect_details.py --input <schedule_json> [--config <config_file>] [--no-resume]
```

**Example:**
```bash
# Collect details for all courses (with progress tracking)
./scripts/collect_details.py --input data/schedule_basic_202570_latest.json

# Use custom config
./scripts/collect_details.py --input data/schedule_basic_202570_latest.json \
                            --config config_local.yml
```

**Features:**
- Progress tracking with resume capability
- Configurable rate limiting (default: 1.5 seconds between requests)
- Saves intermediate results periodically
- Graceful error handling

### collect_all.py
Collects data from all configured colleges (main collection script).

### collect_single.py
Collects data from a single specified college.

### validate_output.py
Validates the structure and content of collected JSON data files.

## Note

These scripts are temporary utilities for specific use cases. The main collection workflow uses the `collect.py` script in the project root.