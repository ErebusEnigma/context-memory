/**
 * Sessions browser view — paginated list with filters and bulk actions.
 */

import { listSessions, listProjects, deleteSession } from '../api.js';
import { renderSessionCard } from '../components/session-card.js';
import { showConfirm } from '../components/modal.js';
import { showToast } from '../components/toast.js';
import { escapeHtml } from '../app.js';

export async function renderSessionsView(container) {
    let page = 1;
    const perPage = 20;
    let currentProject = '';
    let currentSort = 'created_at';
    let currentOrder = 'desc';
    let selectedIds = new Set();

    // Load projects for filter
    let projects = [];
    try {
        const resp = await listProjects();
        projects = resp.projects || [];
    } catch {
        // Non-critical
    }

    const projectOptions = projects.map(p => {
        const path = p.project_path || p;
        const name = path.replace(/\\/g, '/').split('/').filter(Boolean).pop();
        return `<option value="${escapeHtml(path)}">${escapeHtml(name)}</option>`;
    }).join('');

    container.innerHTML = `
        <div class="flex items-center justify-between mb-md">
            <h1 style="font-size: 1.25rem; font-weight: 600;">Sessions</h1>
            <div class="flex gap-sm">
                <button class="btn btn-danger btn-sm hidden" id="bulk-delete">Delete selected</button>
            </div>
        </div>

        <div class="filters">
            <select class="select" id="sessions-project" style="max-width: 200px;">
                <option value="">All projects</option>
                ${projectOptions}
            </select>
            <select class="select" id="sessions-sort" style="max-width: 160px;">
                <option value="created_at">Date created</option>
                <option value="updated_at">Date updated</option>
                <option value="message_count">Message count</option>
            </select>
            <select class="select" id="sessions-order" style="max-width: 120px;">
                <option value="desc">Newest</option>
                <option value="asc">Oldest</option>
            </select>
        </div>

        <div id="sessions-list"></div>
        <div id="sessions-pagination" class="pagination"></div>
    `;

    const listEl = document.getElementById('sessions-list');
    const paginationEl = document.getElementById('sessions-pagination');
    const projectSelect = document.getElementById('sessions-project');
    const sortSelect = document.getElementById('sessions-sort');
    const orderSelect = document.getElementById('sessions-order');
    const bulkDeleteBtn = document.getElementById('bulk-delete');

    async function loadSessions() {
        listEl.innerHTML = '<div class="loading"><div class="spinner"></div> Loading...</div>';

        try {
            const data = await listSessions({
                page, perPage, project: currentProject || undefined,
                sort: currentSort, order: currentOrder,
            });

            if (!data.sessions || data.sessions.length === 0) {
                listEl.innerHTML = `<div class="empty-state">
                    <div class="empty-state-icon">&#128196;</div>
                    <div class="empty-state-title">No sessions</div>
                    <div class="empty-state-text">Save sessions with /remember or auto-save</div>
                </div>`;
                paginationEl.innerHTML = '';
                return;
            }

            listEl.innerHTML = `<div class="session-list">
                ${data.sessions.map(s => `
                    <div class="flex items-center gap-sm">
                        <input type="checkbox" class="session-checkbox" data-id="${s.id}">
                        ${renderSessionCard(s)}
                    </div>
                `).join('')}
            </div>`;

            // Pagination
            const totalPages = Math.ceil(data.total / perPage);
            if (totalPages > 1) {
                let pagHtml = '';
                if (page > 1) pagHtml += `<button class="btn btn-sm" data-page="${page - 1}">&laquo; Prev</button>`;
                pagHtml += `<span class="pagination-info">Page ${page} of ${totalPages} (${data.total} sessions)</span>`;
                if (page < totalPages) pagHtml += `<button class="btn btn-sm" data-page="${page + 1}">Next &raquo;</button>`;
                paginationEl.innerHTML = pagHtml;
            } else {
                paginationEl.innerHTML = `<span class="pagination-info">${data.total} session(s)</span>`;
            }

            // Wire pagination
            paginationEl.querySelectorAll('[data-page]').forEach(btn => {
                btn.addEventListener('click', () => {
                    page = parseInt(btn.dataset.page);
                    loadSessions();
                });
            });

            // Wire card clicks
            listEl.querySelectorAll('.session-card').forEach(card => {
                card.addEventListener('click', () => {
                    window.location.hash = `#/session/${card.dataset.id}`;
                });
            });

            // Wire checkboxes
            listEl.querySelectorAll('.session-checkbox').forEach(cb => {
                cb.addEventListener('click', (e) => e.stopPropagation());
                cb.addEventListener('change', () => {
                    const id = parseInt(cb.dataset.id);
                    if (cb.checked) selectedIds.add(id);
                    else selectedIds.delete(id);
                    bulkDeleteBtn.classList.toggle('hidden', selectedIds.size === 0);
                    bulkDeleteBtn.textContent = `Delete selected (${selectedIds.size})`;
                });
            });
        } catch (err) {
            listEl.innerHTML = `<div class="empty-state">
                <div class="empty-state-icon">&#9888;</div>
                <div class="empty-state-title">Error loading sessions</div>
                <div class="empty-state-text">${escapeHtml(err.message)}</div>
            </div>`;
        }
    }

    projectSelect.addEventListener('change', () => { currentProject = projectSelect.value; page = 1; loadSessions(); });
    sortSelect.addEventListener('change', () => { currentSort = sortSelect.value; page = 1; loadSessions(); });
    orderSelect.addEventListener('change', () => { currentOrder = orderSelect.value; page = 1; loadSessions(); });

    bulkDeleteBtn.addEventListener('click', async () => {
        const confirmed = await showConfirm({
            title: 'Delete sessions',
            body: `<p>Delete ${selectedIds.size} selected session(s)? This cannot be undone.</p>`,
            confirmText: 'Delete',
            danger: true,
        });
        if (!confirmed) return;

        let deleted = 0;
        for (const id of selectedIds) {
            try {
                await deleteSession(id);
                deleted++;
            } catch (err) {
                showToast(`Failed to delete session ${id}: ${err.message}`, 'error');
            }
        }
        showToast(`Deleted ${deleted} session(s)`, 'success');
        selectedIds.clear();
        bulkDeleteBtn.classList.add('hidden');
        loadSessions();
    });

    await loadSessions();
}
