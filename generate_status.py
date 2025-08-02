#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "requests",
#   "pyyaml"
# ]
# ///
"""Generate status.json for the dashboard from collected data."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import requests
import yaml

# GitHub API configuration
GITHUB_API_URL = "https://api.github.com"
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "jmcpheron/ccc-schedule-collector")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# College configurations
COLLEGES = [
    {
        "id": "rio-hondo",
        "name": "Rio Hondo College",
        "data_dir": "data/rio-hondo",
        "workflow_name": "Collect Rio Hondo Schedule"
    },
    {
        "id": "citrus",
        "name": "Citrus College",
        "data_dir": "data/citrus",
        "workflow_name": "Collect Citrus Schedule"
    }
]

def get_latest_data_file(data_dir: str) -> Optional[Dict]:
    """Get the most recent data file from a college's data directory."""
    data_path = Path(data_dir)
    if not data_path.exists():
        return None
    
    # Find all schedule JSON files
    json_files = list(data_path.glob("schedule_*.json"))
    if not json_files:
        return None
    
    # Sort by modification time and get the latest
    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    
    try:
        with open(latest_file, 'r') as f:
            data = json.load(f)
            
        # Add file metadata
        file_stat = latest_file.stat()
        return {
            "file_path": str(latest_file),
            "file_name": latest_file.name,
            "modified_time": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
            "size_bytes": file_stat.st_size,
            "data": data
        }
    except Exception as e:
        print(f"Error reading {latest_file}: {e}")
        return None

def get_workflow_status(workflow_name: str) -> Optional[Dict]:
    """Get the latest workflow run status from GitHub API."""
    if not GITHUB_TOKEN:
        print(f"Warning: No GitHub token available, skipping workflow status for {workflow_name}")
        return None
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Get workflow runs
    url = f"{GITHUB_API_URL}/repos/{GITHUB_REPO}/actions/workflows"
    
    try:
        # First, get the workflow ID
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        workflows = response.json()
        
        workflow_id = None
        for workflow in workflows.get("workflows", []):
            if workflow["name"] == workflow_name:
                workflow_id = workflow["id"]
                break
        
        if not workflow_id:
            print(f"Workflow '{workflow_name}' not found")
            return None
        
        # Get the latest run for this workflow
        runs_url = f"{GITHUB_API_URL}/repos/{GITHUB_REPO}/actions/workflows/{workflow_id}/runs?per_page=1"
        response = requests.get(runs_url, headers=headers)
        response.raise_for_status()
        runs_data = response.json()
        
        if not runs_data.get("workflow_runs"):
            return None
        
        latest_run = runs_data["workflow_runs"][0]
        
        # Calculate duration if completed
        duration = None
        if latest_run["status"] == "completed" and latest_run.get("run_started_at"):
            start_time = datetime.fromisoformat(latest_run["run_started_at"].replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(latest_run["updated_at"].replace("Z", "+00:00"))
            duration = int((end_time - start_time).total_seconds())
        
        return {
            "run_id": latest_run["id"],
            "status": latest_run["status"],
            "conclusion": latest_run.get("conclusion"),
            "created_at": latest_run["created_at"],
            "updated_at": latest_run["updated_at"],
            "html_url": latest_run["html_url"],
            "duration_seconds": duration
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching workflow status for {workflow_name}: {e}")
        return None

def generate_college_status(college: Dict) -> Dict:
    """Generate status for a single college."""
    status = {
        "id": college["id"],
        "name": college["name"],
        "status": "unknown",
        "last_run": None,
        "courses_collected": None,
        "error": None,
        "workflow_run_url": None,
        "duration": None
    }
    
    # Get latest data file
    data_info = get_latest_data_file(college["data_dir"])
    if data_info:
        status["last_run"] = data_info["modified_time"]
        
        # Extract course count if available
        if "data" in data_info and "courses" in data_info["data"]:
            status["courses_collected"] = len(data_info["data"]["courses"])
        
        # Check collection metadata for errors
        metadata = data_info["data"].get("metadata", {})
        if metadata.get("collection_errors"):
            status["error"] = "Collection completed with errors"
            status["status"] = "warning"
        else:
            status["status"] = "success"
    
    # Get workflow status
    workflow_info = get_workflow_status(college["workflow_name"])
    if workflow_info:
        status["workflow_run_url"] = workflow_info["html_url"]
        
        # Update status based on workflow conclusion
        if workflow_info["conclusion"] == "failure":
            status["status"] = "error"
            if not status["error"]:
                status["error"] = "Workflow failed"
        elif workflow_info["conclusion"] == "cancelled":
            status["status"] = "warning"
            status["error"] = "Workflow cancelled"
        
        # Add duration if available
        if workflow_info["duration_seconds"]:
            status["duration"] = workflow_info["duration_seconds"]
        
        # Use workflow time if more recent than file time
        if workflow_info["updated_at"] and (not status["last_run"] or 
            workflow_info["updated_at"] > status["last_run"]):
            status["last_run"] = workflow_info["updated_at"]
    
    return status

def main():
    """Generate the status.json file."""
    print("Generating status dashboard data...")
    
    # Generate status for each college
    colleges_status = []
    for college in COLLEGES:
        print(f"Processing {college['name']}...")
        college_status = generate_college_status(college)
        colleges_status.append(college_status)
    
    # Create the final status object
    status_data = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "colleges": colleges_status,
        "metadata": {
            "generator": "generate_status.py",
            "version": "1.0.0"
        }
    }
    
    # Ensure docs directory exists
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    
    # Write status.json
    status_file = docs_dir / "status.json"
    with open(status_file, 'w') as f:
        json.dump(status_data, f, indent=2)
    
    print(f"Status data written to {status_file}")
    
    # Also create a pretty-printed version for debugging
    print("\nGenerated status:")
    print(json.dumps(status_data, indent=2))

if __name__ == "__main__":
    main()