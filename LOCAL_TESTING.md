# Local Testing Guide

This guide helps you test the Rio Hondo Schedule Collector locally before deploying to GitHub.

## Two Testing Approaches

### 1. Test with Local HTML File (Recommended First)

If you have `rio-hondo-fall-2025.html` in the project root:

```bash
# Basic test - just parse and display results
./test_local.py

# Parse and save to data directory
./test_local.py --save

# Show debug information
./test_local.py --debug

# Use a different HTML file
./test_local.py --html-file path/to/your/file.html
```

This approach:
- ✅ Tests the parser without hitting the web server
- ✅ Fast and repeatable
- ✅ Good for development and debugging
- ✅ No rate limiting concerns

### 2. Test Web Collection

Test actual collection from Rio Hondo's servers:

```bash
# First, test the connection
./test_collection.py --test-connection

# If connection works, try collecting a few departments
./test_collection.py

# The local config (config_local.yml) is set to collect only:
# - ACCT, MATH, ENGL, CS
# Edit config_local.yml to add more departments or use "ALL"
```

## Local Testing Workflow

1. **Start with local HTML testing:**
   ```bash
   ./test_local.py --save --debug
   ```
   Check that courses are parsed correctly.

2. **Examine the parsed data:**
   ```bash
   # View saved data
   uv run cli.py info data/schedule_*.json
   
   # Validate data quality
   uv run cli.py validate data/schedule_*.json
   ```

3. **Test web collection (carefully):**
   ```bash
   # Test connection first
   ./test_collection.py --test-connection
   
   # Then try a small collection
   ./test_collection.py
   ```

4. **Analyze collected data:**
   ```bash
   # View courses by department
   uv run cli.py info data/test/schedule_test_*.json --subject MATH
   
   # Export to CSV for inspection
   uv run cli.py export data/test/schedule_test_*.json test_output.csv
   ```

## Tips for Local Testing

- **Start small**: Test with a few departments before trying "ALL"
- **Check the parser**: Make sure it extracts all fields correctly
- **Monitor requests**: Be respectful of the server - use delays
- **Save test data**: Keep examples for regression testing

## Troubleshooting

### Parser Issues
- Check if HTML structure has changed
- Use `--debug` flag to see what's being extracted
- Look at `utils/parser.py` for parsing logic

### Connection Issues
- Verify the base URL in config_local.yml
- Check if you need to be on campus network/VPN
- Try increasing timeout values

### Data Issues
- Use `cli.py validate` to check data quality
- Export to CSV to inspect in spreadsheet
- Check for missing fields or malformed data

## Setting Up Git

When ready to track your changes:

```bash
./init_git.sh
```

This will initialize git and create your first commit.