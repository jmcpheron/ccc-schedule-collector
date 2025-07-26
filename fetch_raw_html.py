#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "requests",
#   "beautifulsoup4"
# ]
# ///

"""Fetch raw HTML from Rio Hondo for a specific term."""

import requests
from pathlib import Path

# URL and parameters
base_url = "https://ssb.riohondo.edu:8443/prodssb"
schedule_url = f"{base_url}/pw_pub_sched.p_listthislist"

# Parameters for ALL subjects
params = {
    'TERM': '202570',
    'TERM_DESC': 'Fall 2025',
    'sel_subj': ['dummy', 'ACCT', 'ADN', 'AET', 'AJ', 'ANIM', 'ANTH', 'ARCH', 'ART', 'ASL', 'ASTR', 
                 'AT', 'AUTO', 'BIOL', 'BIOT', 'BUS', 'CDEV', 'CHEM', 'CIT', 'CJLE', 'COMM', 'COUN', 
                 'CS', 'DANC', 'DH', 'DMBA', 'DRAM', 'DS', 'ECE', 'ECON', 'EDUC', 'EET', 'EMGT', 
                 'EMS', 'ENGL', 'ENGR', 'ENV', 'ESL', 'ETHN', 'FAID', 'FIN', 'FIRE', 'FN', 'FREN', 
                 'GEOG', 'GEOL', 'GERO', 'GRIT', 'HCD', 'HIST', 'HIT', 'HORT', 'HST', 'HUM', 'IDF', 
                 'ITAL', 'JAPN', 'JOUR', 'KIN', 'LAW', 'LIB', 'LING', 'LIT', 'MGMT', 'MKTG', 'MATH', 
                 'MET', 'MFT', 'MICRO', 'MUS', 'NURS', 'NUTR', 'OTA', 'PHIL', 'PHOT', 'PHYS', 'POLS', 
                 'PORT', 'PSY', 'PSYC', 'PTA', 'READ', 'RT', 'SOC', 'SPAN', 'SPCH', 'STAT', 'SW', 
                 'THTR', 'VET', 'WELD', 'WEXP', 'WFT', 'WS'],
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

print(f"Fetching schedule from: {schedule_url}")
print(f"Term: {params['TERM']} - {params['TERM_DESC']}")
print(f"Subjects: {len(params['sel_subj']) - 1} departments")

try:
    response = requests.post(schedule_url, data=params, timeout=60)
    print(f"\nStatus code: {response.status_code}")
    print(f"Content length: {len(response.text):,} bytes")
    
    # Save the response
    output_file = Path("data/test/rio_hondo_fall_2025_web.html")
    output_file.parent.mkdir(exist_ok=True, parents=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(response.text)
    
    print(f"\nHTML saved to: {output_file}")
    
    # Quick check for courses
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Count course rows
    course_rows = soup.find_all('tr', class_=['default1', 'default2'])
    print(f"Course rows found: {len(course_rows)}")
    
    # Check for any CRN links
    crn_links = soup.find_all('a', href=lambda x: x and 'p_course_popup' in x)
    print(f"CRN links found: {len(crn_links)}")
    
    # Look for subject headers
    subject_headers = soup.find_all('td', class_='subject_header')
    print(f"Subject headers found: {len(subject_headers)}")
    
    if subject_headers:
        print("\nFirst few subjects:")
        for i, header in enumerate(subject_headers[:5]):
            print(f"  - {header.get_text(strip=True)}")
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()