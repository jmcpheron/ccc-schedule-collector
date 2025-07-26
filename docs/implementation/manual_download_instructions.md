# Manual Schedule Download Instructions

Since the automated web collection is currently returning empty results, here's the manual process to download the full schedule:

## Steps to Download Schedule HTML

1. **Visit the search page:**
   ```
   https://ssb.riohondo.edu:8443/prodssb/pw_pub_sched.p_search
   ```

2. **Select Term:**
   - The page should default to "Fall 2025"
   - Click the "Select Term" button if needed

3. **Configure Search (use defaults):**
   - Leave all dropdowns on their default values
   - Subject: Leave as-is (should select all)
   - Days: Leave as-is
   - Schedule Type: Leave as-is
   - All other fields: Leave as defaults

4. **Submit Search:**
   - Click the "Search" button at the bottom
   - Wait for the results to load (may take 10-30 seconds)

5. **Save the HTML:**
   - Once loaded, save the complete page as HTML
   - In Chrome/Firefox: Ctrl+S (or Cmd+S on Mac)
   - Save as: `rio_hondo_fall_2025_manual.html`
   - Save to: `data/raw/`

## Alternative: Use Browser Developer Tools

1. Open Developer Tools (F12)
2. Go to Network tab
3. Do the search as above
4. Find the POST request to `pw_pub_sched.p_listthislist`
5. Right-click → Copy → Copy as cURL
6. Convert to Python requests

## Temporary Workflow

Until we resolve the automated collection issue:

1. **Phase 1:** Manual download (weekly/bi-weekly)
   - Follow steps above
   - Save HTML to `data/raw/YYYY-MM-DD_rio_hondo_fall_2025.html`

2. **Phase 2:** Parse and collect details
   ```bash
   # Parse the downloaded HTML
   ./parse_manual_download.py data/raw/YYYY-MM-DD_rio_hondo_fall_2025.html
   
   # Collect details for all courses
   ./collect_details.py --input data/schedule_basic_*.json
   ```

## Notes

- The manual download captures the complete schedule (~5MB HTML)
- Contains all ~1600 courses for the term
- Includes all departments in one file
- The parser already works perfectly with this format