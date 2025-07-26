#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "requests",
#   "beautifulsoup4",
#   "rich"
# ]
# ///

"""Test direct POST to listing with exact browser parameters."""

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from pathlib import Path

console = Console()

def test_direct_post():
    """Try exact parameters from working collector config."""
    
    session = requests.Session()
    
    # Browser headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://ssb.riohondo.edu:8443',
        'Referer': 'https://ssb.riohondo.edu:8443/prodssb/pw_pub_sched.p_search'
    }
    session.headers.update(headers)
    
    # Based on collector config - note the uppercase TERM
    results_url = "https://ssb.riohondo.edu:8443/prodssb/pw_pub_sched.p_listthislist"
    
    # Try with just a few subjects first
    test_subjects = ['ACCT', 'CS', 'MATH']
    
    # Build params - note term vs TERM
    search_params = {
        'term': '202570',  # lowercase as in collector
        'sel_subj': ['dummy'] + test_subjects,
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
    
    console.print(f"[cyan]Testing with subjects: {test_subjects}[/cyan]")
    console.print(f"URL: {results_url}")
    
    try:
        # Direct POST
        response = session.post(results_url, data=search_params, timeout=60)
        response.raise_for_status()
        
        console.print(f"\n[green]✓ Request completed[/green]")
        console.print(f"Status: {response.status_code}")
        console.print(f"Response size: {len(response.text):,} bytes")
        
        # Save response
        output_file = Path("data/test/direct_post_test.html")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        # Parse and check
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Different ways to find courses
        crn_links = soup.find_all('a', href=lambda x: x and 'p_course_popup' in x)
        console.print(f"\nCRN popup links: {len(crn_links)}")
        
        # Look for subject headers
        subject_headers = soup.find_all('td', class_='subject_header')
        console.print(f"Subject headers: {len(subject_headers)}")
        
        # Look for course rows
        default_rows = soup.find_all('tr', class_=['default1', 'default2'])
        console.print(f"Course rows: {len(default_rows)}")
        
        # Check display count
        display_text = soup.find(string=lambda x: x and 'class(es) displayed' in x if x else False)
        if display_text:
            console.print(f"\n[yellow]{display_text.strip()}[/yellow]")
            
        # Show response headers
        console.print(f"\n[dim]Response headers:[/dim]")
        for key, value in response.headers.items():
            if key.lower() in ['content-type', 'set-cookie', 'server']:
                console.print(f"  {key}: {value}")
                
        # Check cookies
        if session.cookies:
            console.print(f"\n[dim]Cookies:[/dim]")
            for cookie in session.cookies:
                console.print(f"  {cookie.name}: {cookie.value[:20]}...")
                
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_direct_post()