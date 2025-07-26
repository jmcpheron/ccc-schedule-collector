#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "requests",
#   "beautifulsoup4",
#   "rich"
# ]
# ///

"""Test script to fetch schedule using the search page approach."""

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from pathlib import Path
import time

console = Console()

def test_search_page():
    """Test fetching schedule via the search page."""
    
    # Step 1: Load search page
    search_url = "https://ssb.riohondo.edu:8443/prodssb/pw_pub_sched.p_search"
    console.print(f"[cyan]Loading search page: {search_url}[/cyan]")
    
    session = requests.Session()
    
    try:
        # Get the search form
        response = session.get(search_url, timeout=30)
        response.raise_for_status()
        console.print(f"[green]✓ Search page loaded successfully[/green]")
        
        # Parse to check if Fall 2025 is default
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for term selector
        term_select = soup.find('select', {'name': 'TERM'})
        if term_select:
            selected_option = term_select.find('option', selected=True)
            if selected_option:
                console.print(f"[yellow]Default term: {selected_option.text}[/yellow]")
        
        # Step 2: Submit term selection (simulate clicking "Select Term")
        console.print("\n[cyan]Submitting term selection...[/cyan]")
        
        # First, we need to select the term
        term_data = {
            'TERM': '202570',  # Fall 2025
            'TERM_DESC': 'Fall 2025'
        }
        
        # The form action for term selection
        term_response = session.post(search_url, data=term_data, timeout=30)
        term_response.raise_for_status()
        console.print(f"[green]✓ Term selected[/green]")
        
        # Step 3: Submit search with default parameters
        console.print("\n[cyan]Submitting search for all courses...[/cyan]")
        
        # Build search parameters (mimicking the form submission)
        search_params = {
            'TERM': '202570',
            'TERM_DESC': 'Fall 2025',
            'sel_subj': 'dummy',  # This selects all subjects
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
            'end_ap': 'p',
            'aa': 'Y',  # Submit search
            'bb': '1'   # Page number
        }
        
        # The search results endpoint
        results_url = "https://ssb.riohondo.edu:8443/prodssb/pw_pub_sched.p_listthislist"
        
        # Submit search
        search_response = session.post(results_url, data=search_params, timeout=60)
        search_response.raise_for_status()
        
        console.print(f"[green]✓ Search completed[/green]")
        console.print(f"Response size: {len(search_response.text):,} bytes")
        
        # Save the response
        output_file = Path("data/test/search_results_fall_2025.html")
        output_file.parent.mkdir(exist_ok=True, parents=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(search_response.text)
        
        console.print(f"\n[green]HTML saved to: {output_file}[/green]")
        
        # Quick analysis
        soup = BeautifulSoup(search_response.text, 'html.parser')
        
        # Count course rows (they have CRN links)
        crn_links = soup.find_all('a', href=lambda x: x and 'p_course_popup' in x)
        console.print(f"\n[yellow]Analysis:[/yellow]")
        console.print(f"CRN links found: {len(crn_links)}")
        
        # Count unique subjects
        subject_headers = soup.find_all('td', class_='subject_header')
        console.print(f"Subject headers found: {len(subject_headers)}")
        
        # Show first few subjects
        if subject_headers:
            console.print("\nFirst 5 subjects:")
            for header in subject_headers[:5]:
                console.print(f"  - {header.get_text(strip=True)}")
        
        # Look for the results header
        results_header = soup.find(text=lambda x: x and 'Class Schedule Search Results' in x)
        if results_header:
            console.print(f"\n[green]✓ Found search results header[/green]")
        
        # Check for course structure info
        if "Online ASYNC" in search_response.text:
            console.print("[green]✓ Found course structure definitions[/green]")
            
        # Look for the course rename notice
        if "Course Prefixes and Numbers Are Changing" in search_response.text:
            console.print("[green]✓ Found course renaming notice[/green]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_search_page()