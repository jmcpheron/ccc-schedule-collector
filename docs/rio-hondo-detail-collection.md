# Rio Hondo Course Detail Collection

This document explains the two-phase collection system for Rio Hondo College course data.

## Overview

The system now uses a **two-phase approach** to balance efficiency and server-friendliness:

1. **Basic Collection** (`collect.yml`) - Runs 3x daily, collects essential course info quickly
2. **Detail Collection** (`collect-rio-details.yml`) - Runs 1x daily, fetches comprehensive course details

## Workflows

### Basic Collection (`collect.yml`)
- **Schedule**: 3 times daily at 6:26 AM, 2:26 PM, 10:26 PM UTC
- **Runtime**: ~2-3 minutes
- **Data**: Core course info (CRN, title, instructor, times, enrollment)
- **Files**: `data/rio-hondo/schedule_YYYYMM_latest.json`

### Detail Collection (`collect-rio-details.yml`)
- **Schedule**: Daily at 3:26 AM UTC (low traffic time)
- **Runtime**: ~40-50 minutes for full collection (1.5s × 1600+ courses)
- **Data**: Enhanced course info (descriptions, prerequisites, transfer info, critical dates)
- **Files**: `data/rio-hondo/schedule_detailed_YYYYMM_YYYYMMDD_HHMMSS.json`

## Manual Usage

### Test Detail Collection (Small Subset)
```bash
# Test with 5 courses
./collect_rio_details.py --limit 5 --rate-limit 2.0

# Test specific schedule file
./collect_rio_details.py --input data/rio-hondo/schedule_202570_latest.json --limit 10
```

### Full Detail Collection
```bash
# Collect all course details
./collect_rio_details.py

# With custom rate limiting (be respectful!)
./collect_rio_details.py --rate-limit 2.0
```

### Resume Interrupted Collection
```bash
# Resume automatically (default behavior)
./collect_rio_details.py

# Start fresh (ignore previous progress)
./collect_rio_details.py --no-resume
```

## GitHub Actions Manual Triggers

### Detail Collection Workflows

**Main Workflow**: Go to **Actions** → **Collect Rio Hondo Course Details** → **Run workflow**

**Test Workflow**: Go to **Actions** → **Test Rio Hondo Detail Collection** → **Run workflow** (for testing with small datasets)

Options:
- **schedule_file**: Specific file to process (optional - auto-detects latest)
- **limit**: Number of courses to process (for testing)
- **rate_limit**: Seconds between requests (default: 1.5)
- **no_resume**: Start fresh instead of resuming

### Test Examples
```yaml
# Test with 10 courses
schedule_file: (leave blank)
limit: 10
rate_limit: 2.0
no_resume: false

# Process specific file
schedule_file: data/rio-hondo/schedule_202570_latest.json
limit: (leave blank for all)
rate_limit: 1.5
no_resume: true
```

## Output Files

### Basic Schedule
```json
{
  "term": "Fall 2025",
  "courses": [...],
  "metadata": {
    "total_courses": 1648,
    "departments": ["ACCT", "MATH", ...]
  }
}
```

### Detailed Schedule
```json
{
  "term": "Fall 2025", 
  "courses": [...],  // Enhanced Course objects
  "metadata": {
    "details_collected": true,
    "courses_with_details": 1640,
    "detail_collection_timestamp": "2025-08-17T05:21:10Z",
    "detail_rate_limit": 1.5,
    "detail_collection_errors": [...]
  }
}
```

### Enhanced Course Fields
- `description`: Full course description
- `prerequisites`: Course prerequisites  
- `advisory`: Advisory recommendations
- `transfers_to`: UC/CSU transfer information
- `critical_dates`: Add/drop/withdraw deadlines
- `additional_hours`: Weekly instructional hours
- `syllabus_link`: Learning outcomes link
- `seating_detail`: Live enrollment numbers
- `detail_fetched_at`: Timestamp of detail collection

## Configuration

### Main Config (`config.yml`)
```yaml
# Basic collection only - details handled separately
collect_details: false
```

### Detail Config (`config_details.yml`)
```yaml
detail_collection:
  rate_limit: 1.5
  batch_size: 50
  continue_on_error: true
```

## Monitoring

### Collection Reports
- Basic: `data/rio-hondo/latest_report.md`
- Details: `data/detail_collection_report.md`

### Error Handling
- Individual course failures are logged but don't stop collection
- GitHub Issues created on workflow failures (scheduled runs only)
- Progress tracking allows resuming interrupted collections

## Server Considerations

**Rate Limiting**: 1.5 seconds between detail requests
- Total time: ~40 minutes for 1600 courses
- Respectful to Rio Hondo's servers
- Adjustable via workflow inputs

**Timing**: Detail collection runs at 3:26 AM UTC
- Low traffic time
- Separate from basic collection
- Can be adjusted in workflow schedule

## Troubleshooting

### Common Issues
1. **No basic schedule found**: Run basic collection first
2. **Collection timeout**: Increase rate limit or run in smaller batches
3. **Parser errors**: Check if Rio Hondo changed their HTML structure
4. **Resume not working**: Delete `data/.rio_detail_progress.json` and restart

### Debug Commands
```bash
# Test single course detail page
./test_rio_detail.py

# Check specific course details
./collect_rio_details.py --limit 1 --rate-limit 3.0

# Validate collected data
./cli.py validate data/rio-hondo/schedule_detailed_*.json
```