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

function togglePass(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
    } else {
        input.type = 'password';
        btn.textContent = '👁️';
    }
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

    const banner = document.getElementById('liveProgressBanner');
    const progText = document.getElementById('liveProgressText');
    if (banner && progText) {
        if (stats.active_progress && stats.active_progress.trim() !== '') {
            progText.textContent = stats.active_progress;
            banner.style.display = 'flex';
        } else {
            banner.style.display = 'none';
        }
    }

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

    // Populate Manual Post FB Target dropdown
    const manTargetSelect = document.getElementById('manTargetFb');
    if (manTargetSelect) {
        let optHtml = '<option value="all">🌐 All Connected Facebook Pages</option>';
        list.forEach(fb => {
            optHtml += `<option value="${esc(fb.page_id)}">📘 ${esc(fb.page_name)} (${esc(fb.page_id)})</option>`;
        });
        manTargetSelect.innerHTML = optHtml;
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

// ===== Manual Post Handler =====
async function handleManualPost(e) {
    e.preventDefault();
    const video_url = document.getElementById('manVideoUrl').value.trim();
    const target_fb_pages = document.getElementById('manTargetFb') ? document.getElementById('manTargetFb').value : 'all';
    const custom_title = document.getElementById('manCustomTitle').value.trim();
    const custom_desc = document.getElementById('manCustomDesc').value.trim();

    if (!video_url) return showToast('Video URL is required!', 'error');
    
    const btn = document.getElementById('btnManualPost');
    btn.disabled = true;
    btn.textContent = '⏳ Uploading in background...';
    
    const res = await api('/api/manual-post', 'POST', { video_url, target_fb_pages, custom_title, custom_desc });
    showToast(res.message, res.success ? 'success' : 'error');
    
    setTimeout(() => {
        btn.disabled = false;
        btn.textContent = '⚡ Upload Video Now';
        document.getElementById('manualPostForm').reset();
        loadDashboard();
        loadHistory();
        loadLogs();
    }, 2500);
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

function triggerDirectFBLogin() {
    const user_token = prompt("🔵 Paste your Facebook Access Token / User Token to connect Facebook Account & fetch all pages in 1-Click:");
    if (!user_token || !user_token.trim()) return;
    document.getElementById('userFBToken').value = user_token.trim();
    const fakeEvent = { preventDefault: () => {} };
    fetchUserFBPages(fakeEvent);
}

let fetchedPagesData = [];

async function fetchUserFBPages(e) {
    e.preventDefault();
    const user_token = document.getElementById('userFBToken').value.trim();
    const container = document.getElementById('fetchedPagesContainer');
    if (!user_token) return showToast('Please enter Facebook User Token!', 'error');
    
    container.innerHTML = '<p style="color:var(--accent-glow); font-size:0.9rem;">🔍 Fetching all managed Facebook Pages from Graph API...</p>';
    const res = await api('/api/facebook/fetch-user-pages', 'POST', { user_token });
    
    if (res.success && res.pages && res.pages.length > 0) {
        fetchedPagesData = res.pages;
        let html = `<div style="padding:15px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); border-radius:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:10px;">
                <h4 style="margin:0; color:var(--green);">🎉 ${res.pages.length} Facebook Page(s) Found!</h4>
                <button type="button" class="btn btn-primary" onclick="connectSelectedFBPages()">⚡ Connect All Selected Pages</button>
            </div>
            <div style="display:flex; flex-direction:column; gap:10px;">`;
            
        res.pages.forEach((p, idx) => {
            html += `
                <label style="display:flex; align-items:center; gap:12px; padding:10px 14px; background:var(--bg-dark); border:1px solid rgba(255,255,255,0.08); border-radius:8px; cursor:pointer;">
                    <input type="checkbox" class="fetched-page-cb" data-idx="${idx}" checked style="width:18px; height:18px; accent-color:var(--accent);">
                    <div style="flex:1;">
                        <strong style="color:#fff; font-size:0.95rem;">${esc(p.name)}</strong>
                        <span style="font-size:0.75rem; color:var(--text-muted); display:block;">Page ID: ${esc(p.id)} | Category: ${esc(p.category || 'General')}</span>
                    </div>
                    <span class="badge badge-success">Page Token Attached</span>
                </label>`;
        });
        
        html += `</div></div>`;
        container.innerHTML = html;
        showToast(`Found ${res.pages.length} Pages!`);
    } else {
        container.innerHTML = `<div style="padding:10px 14px; background:rgba(248,113,113,0.1); border:1px solid var(--red); border-radius:8px; color:var(--red); font-size:0.85rem;">
            ❌ ${esc(res.message || 'No Facebook Pages found!')}
        </div>`;
        showToast(res.message || 'Failed to fetch pages', 'error');
    }
}

async function connectSelectedFBPages() {
    const cbs = document.querySelectorAll('.fetched-page-cb:checked');
    if (cbs.length === 0) return showToast('Please select at least 1 Facebook Page!', 'error');
    
    const selected = [];
    cbs.forEach(cb => {
        const idx = parseInt(cb.getAttribute('data-idx'));
        if (fetchedPagesData[idx]) {
            selected.push(fetchedPagesData[idx]);
        }
    });
    
    const res = await api('/api/facebook/connect-multiple-pages', 'POST', { pages: selected });
    if (res.success) {
        showToast(res.message);
        document.getElementById('fetchedPagesContainer').innerHTML = '';
        loadFacebookPages();
    } else {
        showToast(res.message, 'error');
    }
}

async function verifyFBTokenInput() {
    const access_token = document.getElementById('fbToken').value.trim();
    const resultDiv = document.getElementById('tokenVerifyResult');
    if (!access_token) return showToast('Please paste a Facebook Access Token to test!', 'error');
    
    resultDiv.innerHTML = '<p style="color:var(--orange); font-size:0.85rem;">🔍 Testing token permissions with Facebook Graph API...</p>';
    const res = await api('/api/facebook/verify-token', 'POST', { access_token });
    
    if (res.success) {
        resultDiv.innerHTML = `<div style="padding:10px 14px; background:rgba(52,211,153,0.1); border:1px solid var(--green); border-radius:8px; font-size:0.85rem; color:var(--green);">
            ${esc(res.message)}
        </div>`;
        if (res.page_id && !document.getElementById('fbPageId').value) {
            document.getElementById('fbPageId').value = res.page_id;
        }
        if (res.page_name && !document.getElementById('fbName').value) {
            document.getElementById('fbName').value = res.page_name;
        }
        showToast('Token Verified Successfully!');
    } else {
        resultDiv.innerHTML = `<div style="padding:10px 14px; background:rgba(248,113,113,0.1); border:1px solid var(--red); border-radius:8px; font-size:0.85rem; color:var(--red);">
            ❌ ${esc(res.message)}
        </div>`;
        showToast('Token Verification Warning', 'error');
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
            <td class="log-msg-cell">${esc(r.message || '')}</td>
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

// ===== Settings & Admin Panel =====
async function loadSettings() {
    const s = await api('/api/settings');
    document.getElementById('settInterval').value = s.check_interval_hours;
    document.getElementById('settMaxVid').value = s.max_videos_per_sync;
    if (document.getElementById('settGeminiKey')) {
        document.getElementById('settGeminiKey').value = s.gemini_api_key || '';
    }
    if (document.getElementById('settPrivateMode')) {
        document.getElementById('settPrivateMode').value = s.allow_public_registration || '0';
    }
    loadCookiesStatus();
}

async function loadCookiesStatus() {
    try {
        const badge = document.getElementById('cookiesStatusBadge');
        if (!badge) return;
        const res = await api('/api/settings/cookies');
        if (res && res.exists) {
            badge.style.background = 'rgba(16,185,129,0.2)';
            badge.style.color = '#34d399';
            badge.textContent = `🟢 cookies.txt Loaded (${res.size} Bytes)`;
        } else {
            badge.style.background = 'rgba(107,114,128,0.2)';
            badge.style.color = '#9ca3af';
            badge.textContent = '⚪ No Cookies File';
        }
    } catch(e) { console.error(e); }
}

async function saveCookies() {
    const textEl = document.getElementById('cookiesContentText');
    if (!textEl) return;
    const content = textEl.value.trim();
    if (!content) return showToast('Please paste Netscape cookies.txt content!', 'error');
    const res = await api('/api/settings/cookies', 'POST', { content });
    showToast(res.message, res.success ? 'success' : 'error');
    if (res.success) {
        textEl.value = '';
        loadCookiesStatus();
    }
}

async function deleteCookies() {
    if (!confirm('Delete saved cookies.txt file?')) return;
    const res = await api('/api/settings/cookies', 'DELETE');
    showToast(res.message, res.success ? 'success' : 'error');
    loadCookiesStatus();
}

async function saveSettings(e) {
    e.preventDefault();
    const check_interval_hours = document.getElementById('settInterval').value;
    const max_videos_per_sync = document.getElementById('settMaxVid').value;
    const gemini_api_key = document.getElementById('settGeminiKey') ? document.getElementById('settGeminiKey').value.trim() : '';
    const allow_public_registration = document.getElementById('settPrivateMode') ? document.getElementById('settPrivateMode').value : '0';
    const res = await api('/api/settings', 'POST', { check_interval_hours, max_videos_per_sync, gemini_api_key, allow_public_registration });
    showToast(res.message, res.success ? 'success' : 'error');
    loadDashboard();
}

async function loadAdminUsers() {
    try {
        const users = await api('/api/admin/users');
        const card = document.getElementById('adminUsersCard');
        const el = document.getElementById('adminUsersList');
        if (!card || !el) return;
        
        card.style.display = 'block';
        if (!users || users.length === 0) {
            el.innerHTML = '<p class="text-muted text-center">No registered users found.</p>';
            return;
        }
        
        let html = `<table><thead><tr>
            <th>ID</th><th>User</th><th>Email</th><th>Created</th><th>Status</th><th>Admin Action</th>
        </tr></thead><tbody>`;
        
        users.forEach(u => {
            const isApproved = u.is_approved || u.is_admin;
            const statusBadge = u.is_admin
                ? '<span class="badge badge-success">SUPER ADMIN</span>'
                : isApproved
                ? '<span class="badge badge-success">APPROVED</span>'
                : '<span class="badge badge-warn">PENDING APPROVAL</span>';
                
            let actionBtn = '';
            if (!u.is_admin) {
                if (isApproved) {
                    actionBtn = `<button class="btn btn-danger-sm" onclick="rejectUser(${u.id})">Reject / Delete</button>`;
                } else {
                    actionBtn = `<button class="btn btn-primary" style="padding:6px 14px; font-size:0.82rem;" onclick="approveUser(${u.id})">✅ APPROVE ACCESS</button>`;
                }
            } else {
                actionBtn = `<span style="font-size:0.8rem; color:var(--text-muted); font-weight:700;">Owner (Imtiyaz)</span>`;
            }
            
            html += `<tr>
                <td>#${u.id}</td>
                <td><strong>${esc(u.display_name || u.username)}</strong><br><small class="text-muted">@${esc(u.username)}</small></td>
                <td>${esc(u.email || '-')}</td>
                <td>${formatTime(u.created_at)}</td>
                <td>${statusBadge}</td>
                <td>${actionBtn}</td>
            </tr>`;
        });
        
        html += '</tbody></table>';
        el.innerHTML = html;
    } catch(e) {
        console.log('Not admin or failed to load users:', e);
    }
}

async function approveUser(uid) {
    const res = await api('/api/admin/approve-user', 'POST', { user_id: uid });
    showToast(res.message, res.success ? 'success' : 'error');
    loadAdminUsers();
}

async function rejectUser(uid) {
    if (!confirm('Reject & Delete this user account?')) return;
    const res = await api('/api/admin/reject-user', 'POST', { user_id: uid });
    showToast(res.message, res.success ? 'success' : 'error');
    loadAdminUsers();
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

// ===== Cancel Process =====
async function cancelProcess() {
    if (!confirm('🛑 Stop and Cancel the active video download/upload process?')) return;
    const res = await api('/api/cancel-process', 'POST');
    showToast(res.message, 'error');
    const banner = document.getElementById('liveProgressBanner');
    if (banner) banner.style.display = 'none';
    loadLogs();
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

// ===== Auto-refresh Live Progress (%) every 3s (Ultra-fast & Zero Lag) =====
setInterval(async () => {
    try {
        const res = await api('/api/progress');
        const banner = document.getElementById('liveProgressBanner');
        const progText = document.getElementById('liveProgressText');
        if (banner && progText) {
            if (res.active_progress && res.active_progress.trim() !== '') {
                progText.textContent = res.active_progress;
                banner.style.display = 'flex';
            } else {
                banner.style.display = 'none';
            }
        }
    } catch(e) {}
}, 3000);

// ===== Auto-refresh Dashboard every 30s =====
setInterval(() => {
    const active = document.querySelector('.nav-item.active');
    if (active && active.dataset.tab === 'dashboard') loadDashboard();
}, 30000);

// ===== Initial Load =====
loadDashboard();
