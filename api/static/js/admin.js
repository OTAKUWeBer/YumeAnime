/* ═══════════════════════════════════════════════════════════════
   Admin Panel JS — YumeZone
   ═══════════════════════════════════════════════════════════════ */
(function () {
    'use strict';
    const API = '/api/admin';
    let currentTab = 'dashboard';
    let usersPage = 1, reportsPage = 1, logsPage = 1;
    let userSearchTimer = null;

    // ── Helpers ──────────────────────────────────────────────────
    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return document.querySelectorAll(sel); }

    async function api(path, opts = {}) {
        const res = await fetch(API + path, {
            headers: { 'Content-Type': 'application/json', ...opts.headers },
            ...opts,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || 'Request failed');
        return data;
    }

    function toast(msg, type = 'success') {
        const c = $('#admin-toast-container');
        const t = document.createElement('div');
        t.className = `admin-toast toast-${type}`;
        t.textContent = msg;
        c.appendChild(t);
        setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3500);
    }

    function timeAgo(iso) {
        if (!iso) return '—';
        const d = new Date(iso), now = new Date(), s = Math.floor((now - d) / 1000);
        if (s < 60) return 'just now';
        if (s < 3600) return Math.floor(s / 60) + 'm ago';
        if (s < 86400) return Math.floor(s / 3600) + 'h ago';
        if (s < 604800) return Math.floor(s / 86400) + 'd ago';
        return d.toLocaleDateString();
    }

    function formatDate(iso) {
        if (!iso) return '—';
        return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    }

    function avatarUrl(avatar, name) {
        return avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(name || 'U')}&size=72&background=1a1a1a&color=fff&bold=true`;
    }

    function roleBadge(role) {
        return `<span class="admin-list-badge role-${role}">${role}</span>`;
    }

    function statusBadge(user) {
        if (user.is_banned) return '<span class="status-badge status-banned">Banned</span>';
        if (user.muted_until && new Date(user.muted_until) > new Date()) return '<span class="status-badge status-muted">Muted</span>';
        return '<span class="status-badge status-active">Active</span>';
    }

    function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

    function formatAction(action) {
        const mapping = {
            ban: 'Banned user',
            unban: 'Unbanned user',
            mute: 'Muted user',
            unmute: 'Unmuted user',
            post_comment: 'Posted comment',
            post_reply: 'Posted reply',
            delete_comment: 'Deleted comment',
            resolve_report: 'Resolved report',
            ignore_report: 'Ignored report',
            set_role: 'Updated role'
        };
        return mapping[action] || action;
    }

    function actionBadgeClass(action) {
        if (action?.includes('ban')) return 'status-banned';
        if (action?.includes('mute')) return 'status-muted';
        if (action === 'post_comment') return 'status-comment';
        if (action === 'post_reply') return 'status-reply';
        if (action?.includes('delete')) return 'status-banned';
        if (action?.includes('resolve')) return 'status-active';
        if (action?.includes('ignore')) return 'status-ignored';
        return 'status-active';
    }

    function pagination(container, page, pages, cb) {
        const el = document.getElementById(container);
        if (!el || pages <= 1) { if (el) el.innerHTML = ''; return; }
        let html = '';
        html += `<button ${page <= 1 ? 'disabled' : ''} onclick="window._adminPage('${container}',${page - 1})">‹</button>`;
        for (let i = 1; i <= pages; i++) {
            if (pages > 7 && i > 2 && i < pages - 1 && Math.abs(i - page) > 1) {
                if (i === 3 || i === pages - 2) html += '<button disabled>…</button>';
                continue;
            }
            html += `<button class="${i === page ? 'active' : ''}" onclick="window._adminPage('${container}',${i})">${i}</button>`;
        }
        html += `<button ${page >= pages ? 'disabled' : ''} onclick="window._adminPage('${container}',${page + 1})">›</button>`;
        el.innerHTML = html;
        window._adminPage = (c, p) => cb(p);
    }

    // ── Tab Navigation ──────────────────────────────────────────
    function switchTab(tab) {
        currentTab = tab;
        $$('.admin-nav-item').forEach(n => n.classList.toggle('active', n.dataset.tab === tab));
        $$('.admin-tab').forEach(t => t.classList.toggle('active', t.id === 'tab-' + tab));
        // Close mobile sidebar
        $('#admin-sidebar').classList.remove('open');
        // Load data
        if (tab === 'dashboard') loadDashboard();
        else if (tab === 'users') loadUsers();
        else if (tab === 'reports') loadReports();
        else if (tab === 'logs') loadLogs();
    }

    // ── Dashboard ───────────────────────────────────────────────
    async function loadDashboard() {
        try {
            const d = await api('/dashboard');
            $('#stat-total-users').textContent = d.total_users?.toLocaleString() || '0';
            $('#stat-new-today').textContent = d.new_users_today || '0';
            $('#stat-total-comments').textContent = d.total_comments?.toLocaleString() || '0';
            $('#stat-pending-reports').textContent = d.reports?.pending || '0';
            $('#stat-banned').textContent = d.banned_users || '0';
            $('#stat-new-week').textContent = d.new_users_week || '0';
            updatePendingBadge(d.reports?.pending || 0);
            renderChart(d.signup_chart || []);
            renderRoles(d.roles || {}, d.total_users || 0);
            renderRecentUsers(d.recent_users || []);
            renderRecentLogs(d.recent_logs || []);
        } catch (e) { toast(e.message, 'error'); }
    }

    function updatePendingBadge(count) {
        const b = $('#pending-reports-badge');
        if (count > 0) { b.textContent = count; b.style.display = 'flex'; }
        else b.style.display = 'none';
    }

    function renderChart(data) {
        const c = $('#signup-chart');
        if (!data.length) { c.innerHTML = '<div class="admin-empty">No signup data</div>'; return; }
        const max = Math.max(...data.map(d => d.count), 1);
        c.innerHTML = data.map(d => {
            const h = Math.max(4, (d.count / max) * 160);
            const label = d._id.split('-').slice(1).join('/');
            return `<div class="chart-bar-wrap"><span class="chart-bar-value">${d.count}</span><div class="chart-bar" style="height:${h}px"></div><span class="chart-bar-label">${label}</span></div>`;
        }).join('');
    }

    function renderRoles(roles, total) {
        const c = $('#role-distribution');
        const t = total || 1;
        c.innerHTML = ['admin', 'mod', 'user'].map(r => {
            const count = roles[r] || 0;
            const pct = Math.max(2, (count / t) * 100);
            return `<div class="role-bar-item"><span class="role-bar-label">${r}</span><div class="role-bar-track"><div class="role-bar-fill fill-${r}" style="width:${pct}%"><span>${count}</span></div></div></div>`;
        }).join('');
    }

    function renderRecentUsers(users) {
        const c = $('#recent-users-list');
        if (!users.length) { c.innerHTML = '<div class="admin-empty">No users yet</div>'; return; }
        c.innerHTML = users.map(u => `
            <div class="admin-list-item">
                <img class="admin-list-avatar" src="${avatarUrl(u.avatar, u.username)}" alt="${esc(u.username)}" onerror="this.src='${avatarUrl(null, u.username)}'">
                <div class="admin-list-info"><span class="admin-list-name">${esc(u.username)}</span><span class="admin-list-meta">${timeAgo(u.created_at)}</span></div>
                ${roleBadge(u.role || 'user')}
            </div>`).join('');
    }

    function renderRecentLogs(logs) {
        const c = $('#recent-logs-list');
        if (!logs.length) { c.innerHTML = '<div class="admin-empty">No recent actions</div>'; return; }
        c.innerHTML = logs.map(l => {
            const formatted = formatAction(l.action);
            const target = l.target_username ? ` → <strong>${esc(l.target_username)}</strong>` : '';
            const details = l.details ? ` (${esc(l.details)})` : '';
            return `
                <div class="admin-list-item">
                    <div class="admin-list-info">
                        <span class="admin-list-name"><strong>${esc(l.actor_username)}</strong></span>
                        <span class="admin-list-meta">${formatted}${target}${details}</span>
                    </div>
                    <span class="admin-list-meta" style="white-space:nowrap">${timeAgo(l.created_at)}</span>
                </div>`;
        }).join('');
    }

    // ── Users ───────────────────────────────────────────────────
    async function loadUsers(page) {
        if (page) usersPage = page;
        const q = $('#user-search-input').value.trim();
        const role = $('#user-role-filter').value;
        try {
            const d = await api(`/users?q=${encodeURIComponent(q)}&role=${role}&page=${usersPage}`);
            renderUsersTable(d.users || []);
            pagination('users-pagination', d.page, d.pages, loadUsers);
        } catch (e) { toast(e.message, 'error'); }
    }

    function renderUsersTable(users) {
        const tbody = $('#users-tbody');
        if (!users.length) { tbody.innerHTML = '<tr><td colspan="5" class="admin-empty">No users found</td></tr>'; return; }
        tbody.innerHTML = users.map(u => `
            <tr>
                <td><div class="user-cell"><img src="${avatarUrl(u.avatar, u.username)}" alt="" onerror="this.src='${avatarUrl(null, u.username)}'"><div class="user-cell-info"><span class="user-cell-name">${esc(u.username)}</span><span class="user-cell-email">${esc(u.email) || 'ID: ' + u._id}</span></div></div></td>
                <td>${roleBadge(u.role || 'user')}</td>
                <td>${statusBadge(u)}</td>
                <td>${formatDate(u.created_at)}</td>
                <td><div class="admin-btn-group"><button class="admin-btn admin-btn-ghost admin-btn-sm" onclick="window._viewUser('${u._id}')">View</button></div></td>
            </tr>`).join('');
    }

    window._viewUser = async function (id) {
        try {
            const d = await api(`/users/${id}`);
            showUserModal(d.user);
        } catch (e) { toast(e.message, 'error'); }
    };

    function showUserModal(u) {
        const body = $('#modal-user-body');
        $('#modal-username').textContent = u.username;
        let actionsHtml = '';
        if (ADMIN_ROLE === 'admin' && String(u._id) !== String(ADMIN_USER_ID)) {
            actionsHtml += `
                <select id="modal-role-select" class="admin-select" style="width:auto"><option value="user" ${u.role==='user'?'selected':''}>User</option><option value="mod" ${u.role==='mod'?'selected':''}>Moderator</option><option value="admin" ${u.role==='admin'?'selected':''}>Admin</option></select>
                <button class="admin-btn admin-btn-primary admin-btn-sm" onclick="window._setRole('${u._id}')">Update Role</button>`;
            if (!u.is_banned) actionsHtml += `<button class="admin-btn admin-btn-danger admin-btn-sm" onclick="window._confirmAction('ban','${u._id}','${esc(u.username)}')">Ban</button>`;
            else actionsHtml += `<button class="admin-btn admin-btn-success admin-btn-sm" onclick="window._confirmAction('unban','${u._id}','${esc(u.username)}')">Unban</button>`;
        }
        if (ADMIN_ROLE === 'admin' || ADMIN_ROLE === 'mod') {
            if (u.role === 'user') {
                actionsHtml += `<button class="admin-btn admin-btn-warning admin-btn-sm" onclick="window._confirmAction('mute','${u._id}','${esc(u.username)}')">Mute</button>`;
                actionsHtml += `<button class="admin-btn admin-btn-secondary admin-btn-sm" onclick="window._confirmAction('unmute','${u._id}','${esc(u.username)}')">Unmute</button>`;
            }
        }
        body.innerHTML = `
            <div class="modal-user-header"><img class="modal-user-avatar" src="${avatarUrl(u.avatar, u.username)}" alt="" onerror="this.src='${avatarUrl(null, u.username)}'"><div class="modal-user-info"><h3>${esc(u.username)}</h3><div style="display:flex;gap:6px;align-items:center">${roleBadge(u.role||'user')} ${statusBadge(u)}</div><span style="font-size:12px;color:var(--admin-text-muted)">ID: ${u._id} · ${u.auth_method || 'local'}</span></div></div>
            <div class="modal-user-stats"><div class="modal-stat"><span class="modal-stat-value">${u.comment_count||0}</span><span class="modal-stat-label">Comments</span></div><div class="modal-stat"><span class="modal-stat-value">${u.reports_against||0}</span><span class="modal-stat-label">Reports</span></div><div class="modal-stat"><span class="modal-stat-value">${formatDate(u.created_at)}</span><span class="modal-stat-label">Joined</span></div></div>
            ${u.email ? `<p style="font-size:13px;color:var(--admin-text-muted);margin-bottom:16px">Email: ${esc(u.email)}</p>` : ''}
            <div class="modal-actions">${actionsHtml}</div>`;
        document.getElementById('user-detail-modal').style.display = 'flex';
    }

    window._setRole = async function (id) {
        const role = document.getElementById('modal-role-select')?.value;
        if (!role) return;
        try {
            const d = await api(`/users/${id}/role`, { method: 'POST', body: JSON.stringify({ role }) });
            toast(d.message); closeModal('user-detail-modal'); loadUsers(); loadDashboard();
        } catch (e) { toast(e.message, 'error'); }
    };

    // ── Confirm Action Modal ────────────────────────────────────
    let pendingAction = null;

    window._confirmAction = function (action, id, username) {
        const titles = { ban: 'Ban User', unban: 'Unban User', mute: 'Mute User', unmute: 'Unmute User' };
        const msgs = { ban: `Ban "${username}"? They won't be able to access the platform.`, unban: `Unban "${username}"?`, mute: `Mute "${username}"? They won't be able to comment.`, unmute: `Unmute "${username}"?` };
        $('#confirm-title').textContent = titles[action] || 'Confirm';
        $('#confirm-message').textContent = msgs[action] || 'Are you sure?';
        $('#confirm-note-group').style.display = (action === 'ban' || action === 'mute') ? 'block' : 'none';
        $('#confirm-duration-group').style.display = action === 'mute' ? 'block' : 'none';
        $('#confirm-note').value = '';
        const btn = $('#confirm-action-btn');
        btn.className = 'admin-btn ' + (action === 'ban' ? 'admin-btn-danger' : action === 'unban' || action === 'unmute' ? 'admin-btn-success' : 'admin-btn-warning');
        btn.textContent = titles[action] || 'Confirm';
        pendingAction = { action, id };
        document.getElementById('confirm-modal').style.display = 'flex';
    };

    $('#confirm-action-btn')?.addEventListener('click', async () => {
        if (!pendingAction) return;
        const { action, id } = pendingAction;
        const note = $('#confirm-note')?.value || '';
        try {
            if (action === 'ban' || action === 'unban') {
                await api(`/users/${id}/ban`, { method: 'POST', body: JSON.stringify({ action, note }) });
            } else {
                const duration = parseInt($('#confirm-duration')?.value) || 24;
                await api(`/users/${id}/mute`, { method: 'POST', body: JSON.stringify({ action, duration, note }) });
            }
            toast(`Action "${action}" completed`);
            closeModal('confirm-modal'); closeModal('user-detail-modal'); loadUsers(); loadDashboard();
        } catch (e) { toast(e.message, 'error'); }
    });

    // ── Reports ─────────────────────────────────────────────────
    async function loadReports(page) {
        if (page) reportsPage = page;
        const status = $('#report-status-filter').value;
        const reason = $('#report-reason-filter').value;
        try {
            const d = await api(`/reports?status=${status}&reason=${reason}&page=${reportsPage}`);
            renderReports(d.reports || []);
            pagination('reports-pagination', d.page, d.pages, loadReports);
            const counts = await api('/report-counts');
            updatePendingBadge(counts.pending || 0);
            $('#report-count-badges').innerHTML = `
                <span class="report-count-badge status-pending">${counts.pending||0} Pending</span>
                <span class="report-count-badge status-resolved">${counts.resolved||0} Resolved</span>
                <span class="report-count-badge status-ignored">${counts.ignored||0} Ignored</span>`;
        } catch (e) { toast(e.message, 'error'); }
    }

    function renderReports(reports) {
        const c = $('#reports-list');
        if (!reports.length) { c.innerHTML = '<div class="admin-empty">No reports found</div>'; return; }
        c.innerHTML = reports.map(r => {
            let actions = '';
            if (r.status === 'pending') {
                actions = `<div class="report-card-actions">
                    <button class="admin-btn admin-btn-danger admin-btn-sm" onclick="window._reportAction('${r._id}','delete')">Delete Comment</button>
                    <button class="admin-btn admin-btn-success admin-btn-sm" onclick="window._reportAction('${r._id}','resolve')">Resolve</button>
                    <button class="admin-btn admin-btn-secondary admin-btn-sm" onclick="window._reportAction('${r._id}','ignore')">Ignore</button>
                </div>`;
            } else {
                actions = `<div class="report-card-resolved"><div class="resolved-label">Resolved by ${esc(r.moderator_username||'—')}</div><div class="resolved-info">Action: ${esc(r.action_taken||'—')} · ${timeAgo(r.resolved_at)}${r.moderator_note ? ' · Note: ' + esc(r.moderator_note) : ''}</div></div>`;
            }
            return `<div class="report-card">
                <div class="report-card-header"><div class="report-card-meta"><span class="report-reason-badge reason-${r.reason}">${r.reason.replace('_',' ')}</span><span class="status-badge status-${r.status}">${r.status}</span></div><span style="font-size:12px;color:var(--admin-text-muted)">${timeAgo(r.created_at)}</span></div>
                <div class="report-card-body">${esc(r.comment_body) || '<em>No content</em>'}</div>
                <div class="report-card-info"><span>Reported: <strong>${esc(r.reported_username)}</strong></span><span>By: <strong>${esc(r.reporter_username)}</strong></span>${r.anime_id ? `<span>Anime: ${esc(r.anime_id)} Ep ${r.episode_number}</span>` : ''}</div>
                ${actions}
            </div>`;
        }).join('');
    }

    window._reportAction = async function (id, action) {
        const note = prompt(`Enter moderation note for "${action}" action (optional):`, "") || "";
        try {
            if (action === 'delete') {
                await api(`/reports/${id}/delete-comment`, { method: 'POST', body: JSON.stringify({ note }) });
                toast('Comment deleted & report resolved');
            } else if (action === 'resolve') {
                await api(`/reports/${id}/resolve`, { method: 'POST', body: JSON.stringify({ action: 'resolved', note }) });
                toast('Report resolved');
            } else {
                await api(`/reports/${id}/ignore`, { method: 'POST', body: JSON.stringify({ note }) });
                toast('Report ignored');
            }
            loadReports();
        } catch (e) { toast(e.message, 'error'); }
    };

    // ── Logs ────────────────────────────────────────────────────
    async function loadLogs(page) {
        if (page) logsPage = page;
        try {
            const d = await api(`/logs?page=${logsPage}`);
            renderLogs(d.logs || []);
            pagination('logs-pagination', d.page, d.pages, loadLogs);
        } catch (e) { toast(e.message, 'error'); }
    }

    function renderLogs(logs) {
        const tbody = $('#logs-tbody');
        if (!logs.length) { tbody.innerHTML = '<tr><td colspan="5" class="admin-empty">No logs yet</td></tr>'; return; }
        tbody.innerHTML = logs.map(l => {
            const formatted = formatAction(l.action);
            const badgeClass = actionBadgeClass(l.action);
            return `
                <tr>
                    <td><strong>${esc(l.actor_username)}</strong></td>
                    <td><span class="status-badge ${badgeClass}">${esc(formatted)}</span></td>
                    <td>${l.target_username ? esc(l.target_username) : '—'}</td>
                    <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(l.details)}">${esc(l.details)}</td>
                    <td>${timeAgo(l.created_at)}</td>
                </tr>`;
        }).join('');
    }

    // ── Modal helpers ───────────────────────────────────────────
    window.closeModal = function (id) { document.getElementById(id).style.display = 'none'; };

    // Close modals on backdrop click
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('admin-modal-backdrop')) e.target.style.display = 'none';
    });

    // ── Init ────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        // Tab clicks
        $$('.admin-nav-item[data-tab]').forEach(btn => {
            btn.addEventListener('click', () => switchTab(btn.dataset.tab));
        });

        // Mobile toggle
        $('#admin-mobile-toggle')?.addEventListener('click', () => {
            $('#admin-sidebar').classList.toggle('open');
        });

        // User search
        $('#user-search-input')?.addEventListener('input', () => {
            clearTimeout(userSearchTimer);
            userSearchTimer = setTimeout(() => { usersPage = 1; loadUsers(); }, 400);
        });
        $('#user-role-filter')?.addEventListener('change', () => { usersPage = 1; loadUsers(); });

        // Report filters
        $('#report-status-filter')?.addEventListener('change', () => { reportsPage = 1; loadReports(); });
        $('#report-reason-filter')?.addEventListener('change', () => { reportsPage = 1; loadReports(); });

        // Initial load
        loadDashboard();
    });
})();
