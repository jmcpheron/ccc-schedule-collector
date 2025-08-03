// Dashboard functionality for CCC Schedule Collector Status

const REFRESH_INTERVAL = 60000; // Refresh every minute

// College configurations - points directly to latest data files from GitHub raw content
const COLLEGES = [
    {
        id: 'rio-hondo',
        name: 'Rio Hondo College',
        dataUrl: 'https://raw.githubusercontent.com/jmcpheron/ccc-schedule-collector/main/data/rio-hondo/schedule_202570_latest.json'
    },
    {
        id: 'citrus', 
        name: 'Citrus College',
        dataUrl: 'https://raw.githubusercontent.com/jmcpheron/ccc-schedule-collector/main/data/citrus/schedule_202620_latest.json'
    },
    {
        id: 'mtsac',
        name: 'Mt. San Antonio College', 
        dataUrl: 'https://raw.githubusercontent.com/jmcpheron/ccc-schedule-collector/main/data/mtsac/schedule_202520_latest.json'
    }
];

// Status definitions
const STATUS_TYPES = {
    SUCCESS: { class: 'status-success', icon: '✓', label: 'Success' },
    WARNING: { class: 'status-warning', icon: '⚠', label: 'Warning' },
    ERROR: { class: 'status-error', icon: '✗', label: 'Error' },
    UNKNOWN: { class: 'status-unknown', icon: '?', label: 'Unknown' }
};

async function loadCollegeData(college) {
    try {
        const response = await fetch(college.dataUrl);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return {
            college: college,
            data: data,
            success: true,
            error: null
        };
    } catch (error) {
        console.error(`Error loading data for ${college.name}:`, error);
        return {
            college: college,
            data: null,
            success: false,
            error: error.message
        };
    }
}

async function loadAllData() {
    try {
        // Load all college data in parallel
        const promises = COLLEGES.map(college => loadCollegeData(college));
        const results = await Promise.all(promises);
        
        displayStatus(results);
    } catch (error) {
        console.error('Error loading status:', error);
        displayError();
    }
}

function getCollegeStatus(result) {
    const college = result.college;
    const data = result.data;
    
    const status = {
        id: college.id,
        name: college.name,
        status: 'unknown',
        last_run: null,
        courses_collected: null,
        error: null,
        collection_timestamp: null,
        term: null,
        staleness_hours: null
    };

    if (!result.success) {
        status.status = 'error';
        status.error = `Failed to load data: ${result.error}`;
        return status;
    }

    if (data) {
        // Extract information from the data file
        status.collection_timestamp = data.collection_timestamp;
        status.last_run = data.collection_timestamp;
        status.term = data.term || 'Unknown';
        
        if (data.courses && Array.isArray(data.courses)) {
            status.courses_collected = data.courses.length;
        }

        // Check for collection errors in metadata
        if (data.metadata && data.metadata.collection_errors) {
            status.error = 'Collection completed with errors';
            status.status = 'warning';
        } else {
            status.status = 'success';
        }

        // Calculate staleness
        if (data.collection_timestamp) {
            const collectionTime = new Date(data.collection_timestamp);
            const now = new Date();
            const diffHours = Math.floor((now - collectionTime) / (1000 * 60 * 60));
            status.staleness_hours = diffHours;

            // Mark as warning if data is more than 7 days old
            if (diffHours > 168) { // 7 days * 24 hours
                status.status = 'warning';
                if (!status.error) {
                    status.error = `Data is ${Math.floor(diffHours / 24)} days old`;
                }
            }
        }
    }
    
    return status;
}

function displayStatus(results) {
    const grid = document.getElementById('status-grid');
    grid.innerHTML = '';

    // Update last updated time to now since we just fetched the latest data
    const lastUpdatedEl = document.getElementById('last-updated-time');
    lastUpdatedEl.textContent = formatDate(new Date().toISOString());

    // Display each college status
    results.forEach(result => {
        const collegeStatus = getCollegeStatus(result);
        const card = createCollegeCard(collegeStatus);
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
            ${college.term ? `<p><strong>Term:</strong> ${college.term}</p>` : ''}
            <p><strong>Last Collection:</strong> ${formatDate(college.last_run)}</p>
            ${college.staleness_hours !== null ? `<p><strong>Data Age:</strong> ${formatStaleness(college.staleness_hours)}</p>` : ''}
            ${college.error ? `<p class="error-message"><strong>Issue:</strong> ${college.error}</p>` : ''}
            ${college.courses_collected !== null ? `<p><strong>Courses Collected:</strong> ${college.courses_collected.toLocaleString()}</p>` : ''}
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

function formatStaleness(hours) {
    if (hours < 24) {
        return `${hours} hour${hours !== 1 ? 's' : ''}`;
    } else {
        const days = Math.floor(hours / 24);
        return `${days} day${days !== 1 ? 's' : ''}`;
    }
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
    loadAllData();
    
    // Set up auto-refresh
    setInterval(loadAllData, REFRESH_INTERVAL);
});