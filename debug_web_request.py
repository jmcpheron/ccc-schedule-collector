#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "requests",
#   "beautifulsoup4"
# ]
# ///

"""Debug script to test web requests to Rio Hondo."""

import requests
from bs4 import BeautifulSoup

# Test URL from the sample detail link
base_url = "https://ssb.riohondo.edu:8443/prodssb"
schedule_url = f"{base_url}/pw_pub_sched.p_listthislist"

# Parameters based on config
params = {
    'TERM': '202570',  # Note: uppercase TERM
    'TERM_DESC': 'Fall 2025',
    'sel_subj': ['dummy', 'ACCT'],  # Try just ACCT first
    'sel_day': 'dummy',
    'sel_schd': 'dummy',
    'sel_camp': '%',
    'sel_ism': '%',
    'sel_sess': '%',
    'sel_instr': '%',
    'sel_ptrm': '%',
    'sel_zero': 'N',
    'sel_attrib': '%',
    'begin_hh': '5',
    'begin_mi': '0',
    'begin_ap': 'a',
    'end_hh': '11',
    'end_mi': '0',
    'end_ap': 'p'
}

print(f"Testing URL: {schedule_url}")
print(f"Term: {params['TERM']}")
print(f"Subject: {params['sel_subj']}")

# Try POST request
print("\nTrying POST request...")
try:
    response = requests.post(schedule_url, data=params, timeout=30)
    print(f"Status code: {response.status_code}")
    print(f"Content length: {len(response.text)}")
    
    if response.status_code == 200:
        # Parse to check for courses
        soup = BeautifulSoup(response.text, 'html.parser')
        course_rows = soup.find_all('tr', class_=['default1', 'default2'])
        print(f"Course rows found: {len(course_rows)}")
        
        # Save response for inspection
        with open('/tmp/rio_hondo_response.html', 'w') as f:
            f.write(response.text)
        print("Response saved to /tmp/rio_hondo_response.html")
        
        # Show first few lines
        lines = response.text.split('\n')[:20]
        print("\nFirst 20 lines:")
        for line in lines:
            print(line)
    else:
        print(f"Error response: {response.text[:500]}")
        
except Exception as e:
    print(f"Error: {e}")

# Also test a known working URL (the detail page)
print("\n\nTesting known working detail URL...")
detail_url = f"{base_url}/pw_pub_sched.p_course_popup?vsub=ACCT&vcrse=100&vterm=202570&vcrn=75065"
try:
    response = requests.get(detail_url, timeout=30)
    print(f"Detail page status: {response.status_code}")
    print(f"Detail page content length: {len(response.text)}")
except Exception as e:
    print(f"Detail page error: {e}")