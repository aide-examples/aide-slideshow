/**
 * Slideshow control interface JavaScript.
 */

let currentDuration = 35;
let currentFilter = null;

async function api(endpoint) {
    try {
        const res = await fetch('/' + endpoint);
        const data = await res.json();
        refreshStatus();
        return data;
    } catch (e) {
        console.error('API error:', e);
    }
}

async function refreshStatus() {
    try {
        const res = await fetch('/status');
        const data = await res.json();

        document.getElementById('status-paused').textContent =
            data.paused ? i18n.t('paused') : i18n.t('playing');
        document.getElementById('status-paused').className =
            'status-value ' + (data.paused ? 'off' : 'on');

        document.getElementById('status-monitor').textContent =
            data.monitor_on ? i18n.t('on') : i18n.t('off');
        document.getElementById('status-monitor').className =
            'status-value ' + (data.monitor_on ? 'on' : 'off');

        document.getElementById('status-playlist').textContent =
            i18n.t('remaining', { count: data.playlist_size });

        currentFilter = data.filter;
        document.getElementById('status-filter').textContent =
            data.filter || i18n.t('none');

        currentDuration = data.display_duration;
        document.getElementById('duration').textContent = currentDuration;

        // Update memory display
        if (data.memory) {
            const mem = data.memory;
            document.getElementById('memory-display').textContent =
                `${mem.used_mb}/${mem.total_mb} MB (${mem.percent_used}%)`;
        }

        updateFolderButtons();
    } catch (e) {
        console.error('Status error:', e);
    }
}

async function loadFolders() {
    try {
        const res = await fetch('/folders');
        const data = await res.json();
        const list = document.getElementById('folder-list');
        list.innerHTML = `<button class="folder-btn" onclick="clearFilter()">${i18n.t('all')}</button>`;
        data.folders.forEach(folder => {
            const btn = document.createElement('button');
            btn.className = 'folder-btn';
            btn.textContent = folder.split('/').pop();
            btn.title = folder;
            btn.onclick = () => setFilter(folder);
            list.appendChild(btn);
        });
    } catch (e) {
        console.error('Folders error:', e);
    }
}

function updateFolderButtons() {
    const allText = i18n.t('all');
    document.querySelectorAll('.folder-btn').forEach(btn => {
        const isAll = btn.textContent === allText;
        const isActive = isAll ? !currentFilter : btn.title === currentFilter;
        btn.classList.toggle('active', isActive);
    });
}

async function setFilter(folder) {
    await fetch('/filter?folder=' + encodeURIComponent(folder));
    refreshStatus();
}

async function clearFilter() {
    await fetch('/filter/clear');
    refreshStatus();
}

async function changeDuration(delta) {
    currentDuration = Math.max(5, Math.min(120, currentDuration + delta));
    await fetch('/duration?seconds=' + currentDuration);
    document.getElementById('duration').textContent = currentDuration;
}

async function loadVersion() {
    try {
        const res = await fetch('/api/update/status');
        const data = await res.json();
        document.getElementById('version-display').textContent = data.current_version || '--';
        const updateRow = document.getElementById('update-row');
        if (data.update_available) {
            updateRow.style.display = 'flex';
        } else {
            updateRow.style.display = 'none';
        }
    } catch (e) {
        console.error('Version error:', e);
    }
}

async function restartServer() {
    if (confirm(i18n.t('restart_confirm'))) {
        try {
            await fetch('/restart');
            alert(i18n.t('restarting'));
        } catch (e) {
            // Expected - server stops before responding
        }
    }
}

// Initialize on DOM ready
(async () => {
    await i18n.init();
    document.title = i18n.t('app_title');
    i18n.applyToDOM();

    // Set file manager link dynamically
    document.getElementById('file-manager-link').href =
        window.location.protocol + '//' + window.location.hostname + ':8081';

    // Initial load
    refreshStatus();
    loadFolders();
    loadVersion();

    // Initialize header widget
    HeaderWidget.init('#app-header', { appName: i18n.t('app_title') });

    // Auto-refresh every 5 seconds
    setInterval(refreshStatus, 5000);
    setInterval(loadVersion, 30000);  // Check version every 30s
})();
