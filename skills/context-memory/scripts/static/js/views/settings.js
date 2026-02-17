/**
 * Settings view — DB management, pruning, export, init.
 */

import { getStats, pruneSessions, initDatabase, exportAll } from '../api.js';
import { showConfirm } from '../components/modal.js';
import { showToast } from '../components/toast.js';
import { escapeHtml } from '../app.js';

export async function renderSettingsView(container) {
    let stats = null;
    try {
        stats = await getStats();
    } catch {
        // Will show empty state
    }

    const dbExists = stats && !stats.error;
    const dbSizeMB = dbExists && stats.db_size_bytes ? (stats.db_size_bytes / 1024 / 1024).toFixed(2) : '0';

    container.innerHTML = `
        <h1 style="font-size: 1.25rem; font-weight: 600; margin-bottom: 1.5rem;">Settings</h1>

        <!-- Database Info -->
        <div class="settings-section">
            <div class="settings-title">Database</div>
            ${dbExists ? `
                <div class="stat-grid" style="margin-bottom: 1rem;">
                    <div class="stat-card">
                        <div class="stat-value">${stats.sessions || 0}</div>
                        <div class="stat-label">Sessions</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.messages || 0}</div>
                        <div class="stat-label">Messages</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.summaries || 0}</div>
                        <div class="stat-label">Summaries</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.topics || 0}</div>
                        <div class="stat-label">Topics</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.code_snippets || 0}</div>
                        <div class="stat-label">Snippets</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${dbSizeMB} MB</div>
                        <div class="stat-label">File Size</div>
                    </div>
                </div>
                <p class="text-xs text-muted font-mono">~/.claude/context-memory/context.db</p>
            ` : `
                <p class="text-sm text-muted">Database does not exist yet.</p>
            `}
        </div>

        <!-- Prune -->
        <div class="settings-section">
            <div class="settings-title">Prune Sessions</div>
            <p class="text-sm text-muted mb-md">Remove old or excess sessions to manage database size.</p>

            <div class="settings-row">
                <label class="settings-label">Max age (days)</label>
                <input type="number" class="input" id="prune-age" style="max-width: 120px;" min="1" placeholder="e.g. 90">
            </div>
            <div class="settings-row">
                <label class="settings-label">Max sessions</label>
                <input type="number" class="input" id="prune-count" style="max-width: 120px;" min="1" placeholder="e.g. 100">
            </div>
            <div class="flex gap-sm mt-md">
                <button class="btn" id="prune-preview-btn">Preview</button>
                <button class="btn btn-danger" id="prune-btn">Prune</button>
            </div>
            <div id="prune-result" class="mt-md"></div>
        </div>

        <!-- Export -->
        <div class="settings-section">
            <div class="settings-title">Export</div>
            <p class="text-sm text-muted mb-md">Download all sessions as JSON.</p>
            <button class="btn" id="export-btn">Export JSON</button>
        </div>

        <!-- Initialize -->
        <div class="settings-section">
            <div class="settings-title">Initialize Database</div>
            <p class="text-sm text-muted mb-md">Create or reinitialize the database. Force-init will drop and recreate all tables.</p>
            <div class="flex gap-sm">
                <button class="btn" id="init-btn">Initialize</button>
                <button class="btn btn-danger" id="force-init-btn">Force Reinitialize</button>
            </div>
        </div>
    `;

    const pruneAge = document.getElementById('prune-age');
    const pruneCount = document.getElementById('prune-count');
    const pruneResult = document.getElementById('prune-result');

    // Prune preview
    document.getElementById('prune-preview-btn')?.addEventListener('click', async () => {
        const maxAge = pruneAge.value ? parseInt(pruneAge.value) : null;
        const maxSessions = pruneCount.value ? parseInt(pruneCount.value) : null;
        if (!maxAge && !maxSessions) {
            showToast('Set max age or max sessions', 'error');
            return;
        }
        try {
            const result = await pruneSessions({ maxAgeDays: maxAge, maxSessions, dryRun: true });
            if (result.pruned === 0) {
                pruneResult.innerHTML = '<p class="text-sm text-muted">No sessions would be pruned.</p>';
            } else {
                const sessions = result.sessions || [];
                pruneResult.innerHTML = `
                    <p class="text-sm"><strong>${result.pruned}</strong> session(s) would be removed:</p>
                    <ul style="margin-left: 1.25rem;">
                        ${sessions.slice(0, 10).map(s => `<li class="text-xs text-muted">${escapeHtml(s.session_id)} — ${escapeHtml(s.created_at)}</li>`).join('')}
                        ${sessions.length > 10 ? `<li class="text-xs text-muted">...and ${sessions.length - 10} more</li>` : ''}
                    </ul>
                `;
            }
        } catch (err) {
            showToast(`Preview failed: ${err.message}`, 'error');
        }
    });

    // Prune execute
    document.getElementById('prune-btn')?.addEventListener('click', async () => {
        const maxAge = pruneAge.value ? parseInt(pruneAge.value) : null;
        const maxSessions = pruneCount.value ? parseInt(pruneCount.value) : null;
        if (!maxAge && !maxSessions) {
            showToast('Set max age or max sessions', 'error');
            return;
        }
        const confirmed = await showConfirm({
            title: 'Prune sessions',
            body: '<p>This will permanently delete matching sessions. Run Preview first to see what will be removed.</p>',
            confirmText: 'Prune',
            danger: true,
        });
        if (!confirmed) return;
        try {
            const result = await pruneSessions({ maxAgeDays: maxAge, maxSessions, dryRun: false });
            showToast(`Pruned ${result.pruned} session(s)`, 'success');
            pruneResult.innerHTML = `<p class="text-sm">Pruned ${result.pruned} session(s).</p>`;
        } catch (err) {
            showToast(`Prune failed: ${err.message}`, 'error');
        }
    });

    // Export
    document.getElementById('export-btn')?.addEventListener('click', async () => {
        try {
            showToast('Exporting...', 'info');
            const data = await exportAll();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `context-memory-export-${new Date().toISOString().slice(0, 10)}.json`;
            a.click();
            URL.revokeObjectURL(url);
            showToast(`Exported ${data.count || 0} sessions`, 'success');
        } catch (err) {
            showToast(`Export failed: ${err.message}`, 'error');
        }
    });

    // Init
    document.getElementById('init-btn')?.addEventListener('click', async () => {
        try {
            const result = await initDatabase(false);
            showToast(result.message, result.created ? 'success' : 'info');
        } catch (err) {
            showToast(`Init failed: ${err.message}`, 'error');
        }
    });

    // Force init
    document.getElementById('force-init-btn')?.addEventListener('click', async () => {
        const confirmed = await showConfirm({
            title: 'Force reinitialize',
            body: '<p><strong>This will delete ALL data</strong> and recreate the database from scratch. This cannot be undone.</p>',
            confirmText: 'Reinitialize',
            danger: true,
        });
        if (!confirmed) return;

        // Double confirm
        const really = await showConfirm({
            title: 'Are you sure?',
            body: '<p>All sessions, messages, summaries, and code snippets will be permanently deleted.</p>',
            confirmText: 'Yes, delete everything',
            danger: true,
        });
        if (!really) return;

        try {
            const result = await initDatabase(true);
            showToast(result.message, 'success');
            // Reload stats
            renderSettingsView(container);
        } catch (err) {
            showToast(`Init failed: ${err.message}`, 'error');
        }
    });
}
