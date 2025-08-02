# CCC Schedule Collector Status Dashboard

This directory contains the GitHub Pages site that displays the real-time status of the schedule collectors.

## Files

- `index.html` - Main dashboard page
- `dashboard.js` - JavaScript for loading and displaying status data
- `style.css` - Dashboard styling with light/dark mode support
- `status.json` - Auto-generated status data (updated by GitHub Actions)
- `_config.yml` - GitHub Pages configuration

## How It Works

1. Each collector workflow runs on schedule or manually
2. After collection, the `update-status.yml` workflow runs
3. It generates fresh `status.json` with latest collection info
4. GitHub Pages serves the static site at: https://jmcpheron.github.io/ccc-schedule-collector/

## Testing Locally

```bash
cd docs
python3 -m http.server 8000
# Open http://localhost:8000
```

## Status Indicators

- 🟢 **Success** - Collection completed successfully
- 🟡 **Warning** - Collection completed with issues
- 🔴 **Error** - Collection failed
- ❓ **Unknown** - No data available