/**
 * Context Memory Dashboard — Main App
 * Hash-based SPA router and view lifecycle management.
 */

import { renderSearchView } from './views/search.js';
import { renderSessionsView } from './views/sessions.js';
import { renderDetailView } from './views/detail.js';
import { renderAnalyticsView } from './views/analytics.js';
import { renderSettingsView } from './views/settings.js';

const appEl = document.getElementById('app');
const navLinks = document.querySelectorAll('.nav-link');

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

const routes = [
    { pattern: /^\/$/, view: renderSearchView },
    { pattern: /^\/sessions$/, view: renderSessionsView },
    { pattern: /^\/session\/(\d+)$/, view: renderDetailView },
    { pattern: /^\/analytics$/, view: renderAnalyticsView },
    { pattern: /^\/settings$/, view: renderSettingsView },
];

let currentCleanup = null;

function getPath() {
    const hash = window.location.hash.slice(1) || '/';
    return hash;
}

async function navigate() {
    const path = getPath();

    // Cleanup previous view
    if (typeof currentCleanup === 'function') {
        currentCleanup();
        currentCleanup = null;
    }

    // Update active nav link
    navLinks.forEach(link => {
        const route = link.dataset.route;
        if (route === path || (route === '/sessions' && path.startsWith('/session/'))) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // Match route
    for (const route of routes) {
        const match = path.match(route.pattern);
        if (match) {
            appEl.innerHTML = '<div class="loading"><div class="spinner"></div> Loading...</div>';
            try {
                const cleanup = await route.view(appEl, ...match.slice(1));
                currentCleanup = cleanup || null;
            } catch (err) {
                appEl.innerHTML = `<div class="empty-state">
                    <div class="empty-state-icon">&#9888;</div>
                    <div class="empty-state-title">Error</div>
                    <div class="empty-state-text">${escapeHtml(err.message)}</div>
                </div>`;
            }
            return;
        }
    }

    // 404
    appEl.innerHTML = `<div class="empty-state">
        <div class="empty-state-icon">&#9898;</div>
        <div class="empty-state-title">Page not found</div>
        <div class="empty-state-text">Try <a href="#/">Search</a> or <a href="#/sessions">Sessions</a></div>
    </div>`;
}

window.addEventListener('hashchange', navigate);

// ---------------------------------------------------------------------------
// Theme toggle
// ---------------------------------------------------------------------------

const themeToggle = document.getElementById('theme-toggle');
const savedTheme = localStorage.getItem('cm-theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);

themeToggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('cm-theme', next);
});

// ---------------------------------------------------------------------------
// Helpers (exported for views)
// ---------------------------------------------------------------------------

export function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

export function formatDate(dateStr) {
    if (!dateStr) return 'Unknown';
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
        return dateStr.split('T')[0] || dateStr;
    }
}

export function projectName(path) {
    if (!path) return 'Unknown';
    return path.replace(/\\/g, '/').split('/').filter(Boolean).pop() || path;
}

export function outcomeBadge(outcome) {
    const map = {
        success: 'badge-success',
        partial: 'badge-warning',
        abandoned: 'badge-danger',
    };
    const cls = map[outcome] || 'badge-muted';
    return `<span class="badge ${cls}">${escapeHtml(outcome || 'unknown')}</span>`;
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

navigate();
