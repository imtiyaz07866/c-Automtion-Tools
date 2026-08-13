// ===== Tab Navigation =====
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', e => {
        e.preventDefault();
        const tab = item.dataset.tab;
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.getElementById('tab-' + tab).classList.add('active');
        // Close mobile sidebar
        document.getElementById('sidebar').classList.remove('open');
        // Refresh data on tab switch
        loadTabData(tab);
    });
});

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

// ===== Toast Notifications =====
function showToast(msg, type = 'success') {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast show ' + type;
    setTimeout(() => t.className = 'toast', 3500);
}

// ===== Logout =====
async function logout() {
    await fetch('/api/logout', { method: 'POST' });
    window.location.href = '/login';
}

// ===== API Helper =====
async function api(url, method = 'GET', body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (res.status === 401) { window.location.href = '/login'; return {}; }
    return res.json();
}

// ===== Load Data Per Tab =====
function loadTabData(tab) {
    switch (tab) {
        case 'dashboard': loadDashboard(); break;
        case 'channels': loadChannels(); break;
        case 'facebook': loadFB(); break;
        case 'history': loadHistory(); break;
        case 'logs': loadLogs(); break;
        case 'settings': loadSettings(); break;
    }
}

// ===== Dashboard =====
async function loadDashboard() {
    const stats = await api('/api/stats');
    document.getElementById('statChannels').textContent = stats.active_channels;
    document.getElementById('statFB').textContent = stats.fb_pages;
    document.getElementById('statUploads').textContent = stats.total_uploads;
    document.getElementById('statInterval').textContent = stats.interval + 'h';

    const history = await api('/api/history');
    const recent = history.filter(h => h.status === 'success').slice(0, 5);
    const el = document.getElementById('recentUploads');

    if (recent.length === 0) {
        el.innerHTML = `<div class="empty-state">
            <div class="empty-icon">📭</div>
            <p>No videos uploaded yet. Add channels & Facebook settings to get started.</p>
        </div>`;
        return;
    }

    let html = `<table><thead><tr>
        <th>Video Title</th><th>FB Page</th><th>FB Post ID</th><th>Time</th>
    </tr></thead><tbody>`;
    recent.forEach(r => {
        html += `<tr>
            <td title="${esc(r.yt_video_title)}">${esc(r.yt_video_title || '-')}</td>
            <td>${esc(r.fb_page_id || '-')}</td>
            <td>${esc(r.fb_post_id || '-')}</td>
            <td>${formatTime(r.processed_at)}</td>
        </tr>`;
    });
    html += '</tbody></table>';
    el.innerHTML = html;
}

// ===== Channels =====
async function loadChannels() {
    const channels = await api('/api/channels');
    const el = document.getElementById('channelsList');

    if (channels.length === 0) {
        el.innerHTML = `<div class="empty-state">
            <div class="empty-icon">📺</div>
            <p>No YouTube channels added yet. Paste a channel link above.</p>
        </div>`;
        return;
    }

    let html = '';
    channels.forEach(ch => {
        const isActive = ch.is_active;
        html += `<div class="list-item">
            <div class="list-item-info">
                <div class="list-item-title">${esc(ch.channel_name || 'Channel')}</div>
                <div class="list-item-sub">${esc(ch.channel_url)}</div>
            </div>
            <div class="list-item-actions">
                <button class="btn-toggle ${isActive ? 'active' : 'inactive'}"
                    onclick="toggleChannel(${ch.id}, ${isActive ? 0 : 1})">
                    ${isActive ? '● Active' : '○ Paused'}
                </button>
                <button class="btn-icon-del" onclick="deleteChannel(${ch.id})">🗑️ Delete</button>
            </div>
        </div>`;
    });
    el.innerHTML = html;
}

async function addChannel(e) {
    e.preventDefault();
    const url = document.getElementById('chUrl').value.trim();
    const name = document.getElementById('chName').value.trim();
    if (!url) return;
    const res = await api('/api/channels', 'POST', { url, name });
    showToast(res.message, res.success ? 'success' : 'error');
    if (res.success) {
        document.getElementById('addChannelForm').reset();
        loadChannels();
        loadDashboard();
    }
}

async function deleteChannel(id) {
    if (!confirm('Delete this channel?')) return;
    await api('/api/channels/' + id, 'DELETE');
    showToast('Channel deleted!');
    loadChannels();
    loadDashboard();
}

async function toggleChannel(id, active) {
    await api('/api/channels/' + id + '/toggle', 'POST', { active });
    loadChannels();
    loadDashboard();
}

// ===== Facebook =====
async function loadFB() {
    const list = await api('/api/facebook');
    const el = document.getElementById('fbList');

    if (list.length === 0) {
        el.innerHTML = `<div class="empty-state">
            <div class="empty-icon">📘</div>
            <p>No Facebook Page connected yet. Enter your Page ID & Token above.</p>
        </div>`;
        return;
    }

    let html = '';
    list.forEach(fb => {
        html += `<div class="list-item">
            <div class="list-item-info">
                <div class="list-item-title">${esc(fb.page_name || 'Page')}</div>
                <div class="list-item-sub">Page ID: ${esc(fb.page_id)} &nbsp;|&nbsp; Token: ${esc(fb.token_preview)}</div>
            </div>
            <div class="list-item-actions">
                <button class="btn-icon-del" onclick="deleteFB('${esc(fb.page_id)}')">🗑️ Remove</button>
            </div>
        </div>`;
    });
    el.innerHTML = html;
}

async function addFB(e) {
    e.preventDefault();
    const page_id = document.getElementById('fbPageId').value.trim();
    const access_token = document.getElementById('fbToken').value.trim();
    const page_name = document.getElementById('fbName').value.trim();
    if (!page_id || !access_token) return showToast('Page ID and Token are required!', 'error');
    const res = await api('/api/facebook', 'POST', { page_id, access_token, page_name });
    showToast(res.message, res.success ? 'success' : 'error');
    if (res.success) {
        document.getElementById('addFBForm').reset();
        loadFB();
        loadDashboard();
    }
}

async function deleteFB(pid) {
    if (!confirm('Remove this Facebook page?')) return;
    await api('/api/facebook/' + pid, 'DELETE');
    showToast('Facebook page removed!');
    loadFB();
    loadDashboard();
}

// ===== History =====
async function loadHistory() {
    const data = await api('/api/history');
    const el = document.getElementById('historyTable');

    if (data.length === 0) {
        el.innerHTML = `<div class="empty-state">
            <div class="empty-icon">📜</div>
            <p>Upload history is empty.</p>
        </div>`;
        return;
    }

    let html = `<table><thead><tr>
        <th>Video</th><th>Channel</th><th>FB Page</th><th>Status</th><th>Error</th><th>Time</th>
    </tr></thead><tbody>`;
    data.forEach(r => {
        const badge = r.status === 'success'
            ? '<span class="badge badge-success">Success</span>'
            : '<span class="badge badge-failed">Failed</span>';
        html += `<tr>
            <td title="${esc(r.yt_video_title)}">${esc((r.yt_video_title || '-').substring(0, 40))}</td>
            <td title="${esc(r.channel_url)}">${esc((r.channel_url || '-').substring(0, 30))}</td>
            <td>${esc(r.fb_page_id || '-')}</td>
            <td>${badge}</td>
            <td title="${esc(r.error_message)}">${esc((r.error_message || '-').substring(0, 30))}</td>
            <td>${formatTime(r.processed_at)}</td>
        </tr>`;
    });
    html += '</tbody></table>';
    el.innerHTML = html;
}

// ===== Logs =====
async function loadLogs() {
    const data = await api('/api/logs');
    const el = document.getElementById('logsTable');

    if (data.length === 0) {
        el.innerHTML = `<div class="empty-state">
            <div class="empty-icon">📟</div>
            <p>System logs are empty.</p>
        </div>`;
        return;
    }

    let html = `<table><thead><tr>
        <th>Time</th><th>Level</th><th>Message</th>
    </tr></thead><tbody>`;
    data.forEach(r => {
        const lvl = r.level || 'INFO';
        const cls = lvl === 'ERROR' ? 'badge-error' : lvl === 'WARNING' ? 'badge-warn' : 'badge-info';
        html += `<tr>
            <td>${formatTime(r.log_time)}</td>
            <td><span class="badge ${cls}">${esc(lvl)}</span></td>
            <td>${esc(r.message || '')}</td>
        </tr>`;
    });
    html += '</tbody></table>';
    el.innerHTML = html;
}

async function clearLogs() {
    if (!confirm('Clear all logs?')) return;
    await api('/api/logs', 'DELETE');
    showToast('Logs cleared!');
    loadLogs();
}

// ===== Settings =====
async function loadSettings() {
    const s = await api('/api/settings');
    document.getElementById('settInterval').value = s.check_interval_hours;
    document.getElementById('settMaxVid').value = s.max_videos_per_sync;
}

async function saveSettings(e) {
    e.preventDefault();
    const check_interval_hours = document.getElementById('settInterval').value;
    const max_videos_per_sync = document.getElementById('settMaxVid').value;
    const res = await api('/api/settings', 'POST', { check_interval_hours, max_videos_per_sync });
    showToast(res.message, res.success ? 'success' : 'error');
    loadDashboard();
}

// ===== Manual Sync =====
async function runSync() {
    const icon = document.getElementById('syncIcon');
    icon.className = 'sync-icon spinning';
    icon.textContent = '🔄';
    showToast('Sync started in background...', 'success');
    await api('/api/sync', 'POST');
    setTimeout(() => {
        icon.className = 'sync-icon';
        icon.textContent = '⚡';
        loadDashboard();
        loadHistory();
        loadLogs();
    }, 3000);
}

// ===== Helpers =====
function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function formatTime(t) {
    if (!t) return '-';
    try {
        const d = new Date(t + (t.includes('Z') || t.includes('+') ? '' : 'Z'));
        return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch {
        return t;
    }
}

// ===== Auto-refresh Dashboard every 30s =====
setInterval(() => {
    const active = document.querySelector('.nav-item.active');
    if (active && active.dataset.tab === 'dashboard') loadDashboard();
}, 30000);

// ===== Initial Load =====
loadDashboard();
