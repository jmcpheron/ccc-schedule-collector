#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "requests",
#   "beautifulsoup4",
#   "rich"
# ]
# ///

"""Test fetching schedule with specific subject selection."""

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from pathlib import Path

console = Console()

def test_search_with_subjects():
    """Test search with actual subject selection."""
    
    session = requests.Session()
    
    # Use the direct listing endpoint with all subjects
    results_url = "https://ssb.riohondo.edu:8443/prodssb/pw_pub_sched.p_listthislist"
    
    # All subjects from fetch_raw_html.py
    all_subjects = ['ACCT', 'ADN', 'AET', 'AJ', 'ANIM', 'ANTH', 'ARCH', 'ART', 'ASL', 'ASTR', 
                    'AT', 'AUTO', 'BIOL', 'BIOT', 'BUS', 'CDEV', 'CHEM', 'CIT', 'CJLE', 'COMM', 
                    'COUN', 'CS', 'DANC', 'DH', 'DMBA', 'DRAM', 'DS', 'ECE', 'ECON', 'EDUC', 
                    'EET', 'EMGT', 'EMS', 'ENGL', 'ENGR', 'ENV', 'ESL', 'ETHN', 'FAID', 'FIN', 
                    'FIRE', 'FN', 'FREN', 'GEOG', 'GEOL', 'GERO', 'GRIT', 'HCD', 'HIST', 'HIT', 
                    'HORT', 'HST', 'HUM', 'IDF', 'ITAL', 'JAPN', 'JOUR', 'KIN', 'LAW', 'LIB', 
                    'LING', 'LIT', 'MGMT', 'MKTG', 'MATH', 'MET', 'MFT', 'MICRO', 'MUS', 'NURS', 
                    'NUTR', 'OTA', 'PHIL', 'PHOT', 'PHYS', 'POLS', 'PORT', 'PSY', 'PSYC', 'PTA', 
                    'READ', 'RT', 'SOC', 'SPAN', 'SPCH', 'STAT', 'SW', 'THTR', 'VET', 'WELD', 
                    'WEXP', 'WFT', 'WS']
    
    # Build parameters with all subjects
    search_params = {
        'TERM': '202570',
        'TERM_DESC': 'Fall 2025',
        'sel_subj': ['dummy'] + all_subjects,  # Include dummy + all subjects
        'sel_day': 'dummy',
        'sel_schd': 'dummy',
        'sel_camp': '%',
        'sel_ism': '%',
        'sel_sess': '%',
        'sel_instr': '%',
        'sel_ptrm': '%',
        'sel_attrib': '%',
        'sel_zero': 'N',
        'begin_hh': '5',
        'begin_mi': '0',
        'begin_ap': 'a',
        'end_hh': '11',
        'end_mi': '0',
        'end_ap': 'p'
    }
    
    console.print(f"[cyan]Fetching schedule with {len(all_subjects)} subjects...[/cyan]")
    console.print(f"URL: {results_url}")
    
    try:
        # Submit search
        response = session.post(results_url, data=search_params, timeout=60)
        response.raise_for_status()
        
        console.print(f"[green]✓ Search completed[/green]")
        console.print(f"Response size: {len(response.text):,} bytes")
        
        # Save the response
        output_file = Path("data/test/search_all_subjects_fall_2025.html")
        output_file.parent.mkdir(exist_ok=True, parents=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        console.print(f"\n[green]HTML saved to: {output_file}[/green]")
        
        # Parse and analyze
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Count CRN links
        crn_links = soup.find_all('a', href=lambda x: x and 'p_course_popup' in x)
        console.print(f"\n[yellow]CRN links found: {len(crn_links)}[/yellow]")
        
        # Count subject headers  
        subject_headers = soup.find_all('td', class_='subject_header')
        console.print(f"Subject headers found: {len(subject_headers)}")
        
        # Show first few subjects
        if subject_headers:
            console.print("\nFirst 10 subjects:")
            for i, header in enumerate(subject_headers[:10]):
                text = header.get_text(strip=True)
                console.print(f"  {i+1}. {text}")
        
        # Look for course rows
        course_rows = soup.find_all('tr', class_=['default1', 'default2'])
        console.print(f"\nCourse rows found: {len(course_rows)}")
        
        # Sample first CRN link
        if crn_links:
            first_link = crn_links[0]
            console.print(f"\nSample CRN link: {first_link.get('href')}")
            console.print(f"CRN text: {first_link.get_text(strip=True)}")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_search_with_subjects()