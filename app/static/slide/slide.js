/**
 * Slideshow control interface JavaScript.
 */

let currentDuration = 35;
let currentFilter = null;
let currentOrientation = 'auto';

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

        const pausedEl = document.getElementById('status-paused');
        pausedEl.textContent = data.paused ? i18n.t('paused') : i18n.t('playing');
        pausedEl.className = 'status-value notranslate ' + (data.paused ? 'off' : 'on');

        const monitorEl = document.getElementById('status-monitor');
        monitorEl.textContent = data.monitor_on ? i18n.t('on') : i18n.t('off');
        monitorEl.className = 'status-value notranslate ' + (data.monitor_on ? 'on' : 'off');

        const playlistEl = document.getElementById('status-playlist');
        playlistEl.textContent = i18n.t('remaining', { count: data.playlist_size });
        playlistEl.classList.add('notranslate');

        currentFilter = data.filter;
        const filterEl = document.getElementById('status-filter');
        filterEl.textContent = data.filter || i18n.t('none');
        filterEl.classList.add('notranslate');

        currentDuration = data.display_duration;
        document.getElementById('duration').textContent = currentDuration;

        currentOrientation = data.orientation || 'auto';
        updateOrientationButtons();

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
        list.innerHTML = `<button class="folder-btn notranslate" onclick="clearFilter()">${i18n.t('all')}</button>`;
        data.folders.forEach(folder => {
            const btn = document.createElement('button');
            btn.className = 'folder-btn notranslate';
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

async function setOrientation(mode) {
    await fetch('/orientation?mode=' + encodeURIComponent(mode));
    refreshStatus();
}

function updateOrientationButtons() {
    document.querySelectorAll('.orientation-btn').forEach(btn => {
        const isActive = btn.dataset.mode === currentOrientation;
        btn.classList.toggle('active', isActive);
    });
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

    // Initialize widgets
    HeaderWidget.init('#app-header', { appName: i18n.t('app_title'), showGoogleTranslate: true });
    StatusWidget.init('#status-widget', {
        showRestart: true,
        showLayoutToggle: false,
        layoutDefault: 'flow'
    });

    // Auto-refresh every 5 seconds
    setInterval(refreshStatus, 5000);
})();
