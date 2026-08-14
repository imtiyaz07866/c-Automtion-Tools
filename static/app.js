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
    const [channels, fbList] = await Promise.all([
        api('/api/channels'),
        api('/api/facebook')
    ]);

    // Populate Add Form FB Target dropdown
    const targetSelect = document.getElementById('chTargetFb');
    if (targetSelect) {
        let optHtml = '<option value="all">🌐 All Connected FB Pages</option>';
        fbList.forEach(fb => {
            optHtml += `<option value="${esc(fb.page_id)}">📘 ${esc(fb.page_name)} (${esc(fb.page_id)})</option>`;
        });
        targetSelect.innerHTML = optHtml;
    }

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
        const currentTarget = ch.target_fb_pages || 'all';

        let fbOptions = `<option value="all" ${currentTarget === 'all' ? 'selected' : ''}>🌐 All FB Pages</option>`;
        fbList.forEach(fb => {
            const sel = currentTarget === fb.page_id ? 'selected' : '';
            fbOptions += `<option value="${esc(fb.page_id)}" ${sel}>📘 ${esc(fb.page_name)}</option>`;
        });

        html += `<div class="list-item">
            <div class="list-item-info">
                <div class="list-item-title">${esc(ch.channel_name || 'Channel')}</div>
                <div class="list-item-sub">${esc(ch.channel_url)}</div>
                <div style="margin-top:6px; font-size:0.8rem; color:var(--text-muted);">
                    Posting to: 
                    <select style="padding:2px 8px; font-size:0.78rem; border-radius:4px; background:var(--bg-input); color:var(--text); border:1px solid var(--border);"
                            onchange="updateChannelTarget(${ch.id}, this.value)">
                        ${fbOptions}
                    </select>
                </div>
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

async function updateChannelTarget(id, target_fb_pages) {
    const res = await api('/api/channels/' + id + '/target', 'PUT', { target_fb_pages });
    showToast(res.message || 'Mapping updated!');
}

async function addChannel(e) {
    e.preventDefault();
    const url = document.getElementById('chUrl').value.trim();
    const target_fb_pages = document.getElementById('chTargetFb') ? document.getElementById('chTargetFb').value : 'all';
    if (!url) return;
    const res = await api('/api/channels', 'POST', { url, name: url, target_fb_pages });
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

let currentFBList = [];

// ===== Facebook =====
async function loadFB() {
    const list = await api('/api/facebook');
    currentFBList = list;
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
        const hasBackup = fb.backup_token ? '<span class="badge badge-success">🛡️ Backup Token Active</span>' : '<span class="badge badge-warn">Primary Only</span>';
        html += `<div class="list-item">
            <div class="list-item-info">
                <div class="list-item-title">${esc(fb.page_name || 'Page')} &nbsp; ${hasBackup}</div>
                <div class="list-item-sub">Page ID: ${esc(fb.page_id)} &nbsp;|&nbsp; Token: ${esc(fb.token_preview)}</div>
            </div>
            <div class="list-item-actions">
                <button class="btn-toggle active" onclick="openEditFB('${esc(fb.page_id)}')">✏️ Edit</button>
                <button class="btn-icon-del" onclick="deleteFB('${esc(fb.page_id)}')">🗑️ Remove</button>
            </div>
        </div>`;
    });
    el.innerHTML = html;
}

function openEditFB(pageId) {
    const fb = currentFBList.find(item => item.page_id === pageId);
    if (!fb) return;
    document.getElementById('editFBPageId').value = fb.page_id;
    document.getElementById('editFBTitle').textContent = fb.page_name || fb.page_id;
    document.getElementById('editFBName').value = fb.page_name || '';
    document.getElementById('editFBToken').value = fb.access_token || '';
    document.getElementById('editFBBackupToken').value = fb.backup_token || '';
    
    const card = document.getElementById('editFBCard');
    card.style.display = 'block';
    card.scrollIntoView({ behavior: 'smooth' });
}

function cancelEditFB() {
    document.getElementById('editFBCard').style.display = 'none';
}

async function saveEditFB(e) {
    e.preventDefault();
    const page_id = document.getElementById('editFBPageId').value;
    const page_name = document.getElementById('editFBName').value.trim();
    const access_token = document.getElementById('editFBToken').value.trim();
    const backup_token = document.getElementById('editFBBackupToken').value.trim();

    const res = await api('/api/facebook/' + page_id, 'PUT', { access_token, backup_token, page_name });
    showToast(res.message, res.success ? 'success' : 'error');
    if (res.success) {
        cancelEditFB();
        loadFB();
        loadDashboard();
    }
}

async function addFB(e) {
    e.preventDefault();
    const page_id = document.getElementById('fbPageId').value.trim();
    const access_token = document.getElementById('fbToken').value.trim();
    const backup_token = document.getElementById('fbBackupToken') ? document.getElementById('fbBackupToken').value.trim() : '';
    const page_name = document.getElementById('fbName').value.trim();
    if (!page_id || !access_token) return showToast('Page ID and Primary Token are required!', 'error');
    const res = await api('/api/facebook', 'POST', { page_id, access_token, backup_token, page_name });
    showToast(res.message, res.success ? 'success' : 'error');
    if (res.success) {
        document.getElementById('addFBForm').reset();
        loadFB();
        loadDashboard();
    }
}

async function exchangeFBToken(e) {
    e.preventDefault();
    const short_lived_token = document.getElementById('exShortToken').value.trim();
    const app_id = document.getElementById('exAppId').value.trim();
    const app_secret = document.getElementById('exAppSecret').value.trim();
    const resultDiv = document.getElementById('exchangeResult');
    resultDiv.innerHTML = '<p style="color:var(--orange);">⏳ Converting token via Facebook Graph API...</p>';
    
    const res = await api('/api/facebook/exchange-token', 'POST', { short_lived_token, app_id, app_secret });
    if (res.success && res.long_lived_token) {
        resultDiv.innerHTML = `<div style="padding:12px; background:rgba(52,211,153,0.1); border:1px solid var(--green); border-radius:8px; word-break:break-all;">
            <p style="color:var(--green); font-weight:600;">✅ Long-Lived Permanent Token Generated!</p>
            <textarea readonly style="width:100%; margin-top:8px; font-size:0.8rem; background:var(--bg-input); color:var(--text); border:1px solid var(--border); border-radius:4px; padding:6px;" rows="3">${esc(res.long_lived_token)}</textarea>
            <p style="font-size:0.8rem; color:var(--text-muted); margin-top:4px;">Copy this token and paste it in the Primary/Backup Token field above.</p>
        </div>`;
        showToast('Long-lived token generated!');
    } else {
        resultDiv.innerHTML = `<p style="color:var(--red);">❌ ${esc(res.message)}</p>`;
        showToast(res.message || 'Token exchange failed', 'error');
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
