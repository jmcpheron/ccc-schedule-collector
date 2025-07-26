#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "requests",
#   "beautifulsoup4",
#   "rich"
# ]
# ///

"""Test mimicking the exact browser flow."""

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from pathlib import Path

console = Console()

def test_browser_flow():
    """Mimic the exact browser workflow."""
    
    session = requests.Session()
    
    # Add browser-like headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    session.headers.update(headers)
    
    # Step 1: Load the search page first
    search_url = "https://ssb.riohondo.edu:8443/prodssb/pw_pub_sched.p_search"
    console.print(f"[cyan]Step 1: Loading search page...[/cyan]")
    
    try:
        response = session.get(search_url, timeout=30)
        response.raise_for_status()
        console.print("[green]✓ Search page loaded[/green]")
        
        # Step 2: Submit term selection
        console.print("\n[cyan]Step 2: Selecting term...[/cyan]")
        
        # Based on the form, we need to submit to p_search with term selection
        term_data = {
            'term': '202570',
            'p_menu2use': 'S'  # Might be needed
        }
        
        term_response = session.post(search_url, data=term_data, timeout=30)
        term_response.raise_for_status()
        console.print("[green]✓ Term selected[/green]")
        
        # Step 3: Submit the actual search
        console.print("\n[cyan]Step 3: Submitting search...[/cyan]")
        
        # Parameters that match what the browser sends
        search_params = {
            'term': '202570',
            'term_desc': 'Fall 2025',
            'sel_subj': 'dummy',  # First, just try with dummy (all subjects)
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
            'aa': 'N',  # This might be important
            'bb': '1'   # Page number
        }
        
        # Submit to the listing endpoint
        results_url = "https://ssb.riohondo.edu:8443/prodssb/pw_pub_sched.p_listthislist"
        
        final_response = session.post(results_url, data=search_params, timeout=60)
        final_response.raise_for_status()
        
        console.print(f"[green]✓ Search completed[/green]")
        console.print(f"Response size: {len(final_response.text):,} bytes")
        
        # Save and analyze
        output_file = Path("data/test/browser_flow_test.html")
        output_file.parent.mkdir(exist_ok=True, parents=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_response.text)
        
        console.print(f"\n[green]HTML saved to: {output_file}[/green]")
        
        # Check content
        soup = BeautifulSoup(final_response.text, 'html.parser')
        
        # Look for the key elements
        crn_links = soup.find_all('a', href=lambda x: x and 'p_course_popup' in x)
        console.print(f"\n[yellow]CRN links found: {len(crn_links)}[/yellow]")
        
        # Check for "You have X class(es) displayed"
        class_count_text = soup.find(string=lambda x: x and 'class(es) displayed' in x if x else False)
        if class_count_text:
            console.print(f"Display message: {class_count_text.strip()}")
            
        # Try to find any error messages
        error_msgs = soup.find_all(string=lambda x: x and ('error' in x.lower() or 'invalid' in x.lower()) if x else False)
        if error_msgs:
            console.print("\n[red]Possible errors found:[/red]")
            for msg in error_msgs[:3]:
                console.print(f"  - {msg.strip()}")
                
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_browser_flow()