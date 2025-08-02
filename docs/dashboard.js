// Dashboard functionality for CCC Schedule Collector Status

const STATUS_URL = 'status.json';
const REFRESH_INTERVAL = 60000; // Refresh every minute

// Status definitions
const STATUS_TYPES = {
    SUCCESS: { class: 'status-success', icon: '✓', label: 'Success' },
    WARNING: { class: 'status-warning', icon: '⚠', label: 'Warning' },
    ERROR: { class: 'status-error', icon: '✗', label: 'Error' },
    UNKNOWN: { class: 'status-unknown', icon: '?', label: 'Unknown' }
};

async function loadStatus() {
    try {
        const response = await fetch(STATUS_URL);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        displayStatus(data);
    } catch (error) {
        console.error('Error loading status:', error);
        displayError();
    }
}

function displayStatus(data) {
    const grid = document.getElementById('status-grid');
    grid.innerHTML = '';

    // Update last updated time
    const lastUpdatedEl = document.getElementById('last-updated-time');
    lastUpdatedEl.textContent = formatDate(data.last_updated || new Date().toISOString());

    // Display each college status
    data.colleges.forEach(college => {
        const card = createCollegeCard(college);
        grid.appendChild(card);
    });
}

function createCollegeCard(college) {
    const card = document.createElement('div');
    card.className = 'status-card';
    
    const status = getStatusType(college);
    
    card.innerHTML = `
        <div class="status-header">
            <h2>${college.name}</h2>
            <div class="status-indicator ${status.class}">
                <span class="status-icon">${status.icon}</span>
                <span class="status-label">${status.label}</span>
            </div>
        </div>
        <div class="status-details">
            <p><strong>Last Run:</strong> ${formatDate(college.last_run)}</p>
            ${college.error ? `<p class="error-message"><strong>Error:</strong> ${college.error}</p>` : ''}
            ${college.courses_collected !== undefined ? `<p><strong>Courses Collected:</strong> ${college.courses_collected}</p>` : ''}
            ${college.duration ? `<p><strong>Duration:</strong> ${formatDuration(college.duration)}</p>` : ''}
            ${college.workflow_run_url ? `<p><a href="${college.workflow_run_url}" target="_blank">View Workflow Run →</a></p>` : ''}
        </div>
    `;
    
    return card;
}

function getStatusType(college) {
    if (college.status === 'success') {
        return STATUS_TYPES.SUCCESS;
    } else if (college.status === 'warning') {
        return STATUS_TYPES.WARNING;
    } else if (college.status === 'error') {
        return STATUS_TYPES.ERROR;
    }
    return STATUS_TYPES.UNKNOWN;
}

function formatDate(dateString) {
    if (!dateString) return 'Never';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    // Show relative time for recent updates
    if (diffMins < 60) {
        return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    } else if (diffHours < 24) {
        return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
        return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    }
    
    // Show full date for older updates
    return date.toLocaleString();
}

function formatDuration(seconds) {
    if (!seconds) return 'N/A';
    
    if (seconds < 60) {
        return `${seconds}s`;
    }
    
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
}

function displayError() {
    const grid = document.getElementById('status-grid');
    grid.innerHTML = `
        <div class="error-container">
            <h2>Unable to load status data</h2>
            <p>Please check back later or view the <a href="https://github.com/jmcpheron/ccc-schedule-collector/actions" target="_blank">GitHub Actions page</a> directly.</p>
        </div>
    `;
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadStatus();
    
    // Set up auto-refresh
    setInterval(loadStatus, REFRESH_INTERVAL);
});