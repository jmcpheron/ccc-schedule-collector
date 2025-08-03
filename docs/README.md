# CCC Schedule Collector Status Dashboard

This directory contains the GitHub Pages site that displays the real-time status of the schedule collectors.

## Files

- `index.html` - Main dashboard page
- `dashboard.js` - JavaScript for loading and displaying status data from collected JSON files
- `style.css` - Dashboard styling with light/dark mode support
- `_config.yml` - GitHub Pages configuration

## How It Works

1. Each collector workflow runs on schedule or manually, generating `data/*/schedule_*_latest.json` files
2. The dashboard JavaScript directly fetches these JSON files to display real-time status
3. Status is determined from the actual collected data (course counts, timestamps, metadata)
4. GitHub Pages serves the static site at: https://jmcpheron.github.io/ccc-schedule-collector/

## Data Sources

The dashboard reads directly from GitHub raw content:
- `https://raw.githubusercontent.com/jmcpheron/ccc-schedule-collector/main/data/rio-hondo/schedule_202570_latest.json` - Rio Hondo College data
- `https://raw.githubusercontent.com/jmcpheron/ccc-schedule-collector/main/data/citrus/schedule_202620_latest.json` - Citrus College data  
- `https://raw.githubusercontent.com/jmcpheron/ccc-schedule-collector/main/data/mtsac/schedule_202520_latest.json` - Mt. San Antonio College data

## Testing Locally

```bash
cd docs
python3 -m http.server 8000
# Open http://localhost:8000
```

Or test from project root:
```bash
python3 -m http.server 8000
# Open http://localhost:8000/docs/
```

## Status Indicators

- 🟢 **Success** - Collection completed successfully, data is current
- 🟡 **Warning** - Collection completed with issues or data is stale (>7 days)
- 🔴 **Error** - Failed to load collection data
- ❓ **Unknown** - No data available

## Benefits of Direct Data Access

- **Real-time accuracy** - Status reflects actual collected data
- **No workflow dependencies** - No intermediate processing required
- **Simpler maintenance** - No status.json conflicts or generation workflows
- **Always current** - Shows exactly what's in the data files