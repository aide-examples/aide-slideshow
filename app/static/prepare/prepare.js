/**
 * Image Preparation - JavaScript
 * Handles form submission, progress polling, and i18n
 */

let pollInterval = null;

// Apply i18n to elements
function applyI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        el.textContent = i18n.t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        el.placeholder = i18n.t(el.dataset.i18nPlaceholder);
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        el.title = i18n.t(el.dataset.i18nTitle);
    });
    document.title = i18n.t('prep_title');
}

// Load defaults on page load
async function loadDefaults() {
    try {
        const res = await fetch('/api/prepare/defaults');
        const data = await res.json();
        document.getElementById('input_dir').value = data.input_dir || '';
        document.getElementById('output_dir').value = data.output_dir || '';
        document.getElementById('mode').value = data.mode || 'hybrid-stretch';
        document.getElementById('pad_mode').value = data.pad_mode || 'average';
        document.getElementById('crop_min').value = data.crop_min || 0.8;
        document.getElementById('stretch_max').value = data.stretch_max || 0.2;
        document.getElementById('no_stretch_limit').value = data.no_stretch_limit || 0.4;
    } catch (e) {
        console.error('Failed to load defaults:', e);
    }

    // Check if job is already running
    checkStatus();
}

function showMessage(text, type = 'info') {
    const area = document.getElementById('message-area');
    area.innerHTML = `<div class="message ${type}">${text}</div>`;
    setTimeout(() => area.innerHTML = '', 5000);
}

function getConfig() {
    return {
        input_dir: document.getElementById('input_dir').value,
        output_dir: document.getElementById('output_dir').value,
        mode: document.getElementById('mode').value,
        target_size: document.getElementById('target_size').value,
        pad_mode: document.getElementById('pad_mode').value,
        crop_min: parseFloat(document.getElementById('crop_min').value),
        stretch_max: parseFloat(document.getElementById('stretch_max').value),
        no_stretch_limit: parseFloat(document.getElementById('no_stretch_limit').value),
        skip_existing: document.getElementById('skip_existing').checked,
        flatten: document.getElementById('flatten').checked,
        show_text: document.getElementById('show_text').checked,
        dry_run: document.getElementById('dry_run').checked,
    };
}

async function countImages() {
    const inputDir = document.getElementById('input_dir').value;
    if (!inputDir) {
        showMessage(i18n.t('prep_enter_input'), 'error');
        return;
    }
    try {
        const res = await fetch('/api/prepare/count?dir=' + encodeURIComponent(inputDir));
        const data = await res.json();
        if (data.error) {
            showMessage(data.error, 'error');
        } else {
            showMessage(i18n.t('prep_found_images', { count: data.count, directory: data.directory }), 'success');
        }
    } catch (e) {
        showMessage('Failed to count images: ' + e.message, 'error');
    }
}

async function startJob() {
    const config = getConfig();
    if (!config.input_dir || !config.output_dir) {
        showMessage(i18n.t('prep_enter_dirs'), 'error');
        return;
    }

    try {
        const res = await fetch('/api/prepare/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        const data = await res.json();

        if (data.success) {
            showMessage(i18n.t('prep_job_started'), 'success');
            document.getElementById('progress-card').classList.add('active');
            startPolling();
        } else {
            showMessage(data.error || 'Failed to start job', 'error');
        }
    } catch (e) {
        showMessage('Failed to start job: ' + e.message, 'error');
    }
}

async function cancelJob() {
    try {
        await fetch('/api/prepare/cancel');
        showMessage(i18n.t('prep_cancel_requested'), 'info');
    } catch (e) {
        showMessage('Failed to cancel: ' + e.message, 'error');
    }
}

async function checkStatus() {
    try {
        const res = await fetch('/api/prepare/status');
        const data = await res.json();
        updateProgressUI(data);

        if (data.running) {
            document.getElementById('progress-card').classList.add('active');
            if (!pollInterval) startPolling();
        } else if (pollInterval) {
            stopPolling();
        }
    } catch (e) {
        console.error('Status check failed:', e);
    }
}

function updateProgressUI(data) {
    const bar = document.getElementById('progress-bar');
    bar.style.width = data.percent + '%';
    bar.textContent = data.percent + '%';

    document.getElementById('stat-processed').textContent = data.counts.processed || 0;
    document.getElementById('stat-exists').textContent = data.counts.exists || 0;
    document.getElementById('stat-errors').textContent = data.counts.error || 0;

    const currentFile = document.getElementById('current-file');
    if (data.current_file) {
        currentFile.textContent = data.current_file.split('/').pop();
        currentFile.title = data.current_file;
    } else if (!data.running && data.current > 0) {
        currentFile.textContent = i18n.t('prep_complete');
    } else {
        currentFile.textContent = i18n.t('prep_waiting');
    }

    const cancelBtn = document.getElementById('cancel-btn');
    cancelBtn.disabled = !data.running;
    cancelBtn.textContent = data.running ? i18n.t('prep_cancel') : (data.cancelled ? i18n.t('prep_cancelled') : i18n.t('prep_done'));

    if (!data.running && data.current > 0) {
        if (data.cancelled) {
            showMessage(i18n.t('prep_job_cancelled'), 'info');
        } else if (data.error) {
            showMessage(i18n.t('prep_job_failed', { error: data.error }), 'error');
        } else {
            showMessage(i18n.t('prep_job_complete', {
                processed: data.counts.processed,
                skipped: data.counts.exists,
                errors: data.counts.error
            }), 'success');
        }
    }
}

function startPolling() {
    if (pollInterval) return;
    pollInterval = setInterval(checkStatus, 1000);
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// Set file manager link
document.getElementById('file-manager-link').href =
    window.location.protocol + '//' + window.location.hostname + ':8081';

// Initialize
(async () => {
    await i18n.init();
    applyI18n();
    loadDefaults();
})();
