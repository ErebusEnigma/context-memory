/**
 * Search view — sidebar project list + search with hint chips.
 */

import { search, listProjects, getHints } from '../api.js';
import { renderSessionCard } from '../components/session-card.js';
import { escapeHtml, projectName } from '../app.js';

export async function renderSearchView(container) {
    let debounceTimer = null;
    let abortController = null;
    let selectedProject = '';
    let hints = { topics: [], technologies: [] };

    // Load projects for sidebar
    let projects = [];
    try {
        const resp = await listProjects();
        projects = resp.projects || [];
    } catch {
        // Non-critical
    }

    // Build sidebar project list
    function renderProjectList() {
        const items = projects.map(p => {
            const name = projectName(p.project_path);
            const count = p.session_count || 0;
            const active = selectedProject === p.project_path ? 'active' : '';
            return `<li class="sidebar-item ${active}" data-project="${escapeHtml(p.project_path)}">
                <span class="truncate">${escapeHtml(name)}</span>
                <span class="sidebar-item-count">${count}</span>
            </li>`;
        }).join('');

        const allActive = selectedProject === '' ? 'active' : '';
        return `<li class="sidebar-item ${allActive}" data-project="">
            <span>All projects</span>
            <span class="sidebar-item-count">${projects.reduce((s, p) => s + (p.session_count || 0), 0)}</span>
        </li>${items}`;
    }

    // Build hint chips
    function renderHints() {
        if (!hints.topics.length && !hints.technologies.length) {
            return '<span class="text-xs text-muted">No hints available</span>';
        }
        const topicChips = hints.topics.map(t =>
            `<span class="hint-chip" data-hint="${escapeHtml(t.topic)}">${escapeHtml(t.topic)}</span>`
        ).join('');
        const techChips = hints.technologies.map(t =>
            `<span class="hint-chip hint-chip-tech" data-hint="${escapeHtml(t.technology)}">${escapeHtml(t.technology)}</span>`
        ).join('');
        return topicChips + techChips;
    }

    container.innerHTML = `
        <div class="search-layout">
            <aside class="search-sidebar">
                <div class="sidebar-section">
                    <div class="sidebar-section-title">Projects</div>
                    <ul class="sidebar-list" id="project-list">
                        ${renderProjectList()}
                    </ul>
                </div>
            </aside>

            <div class="search-content">
                <div class="search-box">
                    <span class="search-icon">&#128269;</span>
                    <input type="text" class="input input-lg" id="search-input"
                           placeholder="Search sessions..." autofocus>
                </div>

                <div class="search-hints" id="search-hints">
                    ${renderHints()}
                </div>

                <div class="filters">
                    <label class="flex items-center gap-sm text-sm text-muted" style="cursor:pointer">
                        <input type="checkbox" id="search-detailed"> Include full messages
                    </label>
                </div>

                <div id="search-results"></div>
            </div>
        </div>
    `;

    const input = document.getElementById('search-input');
    const detailedCheck = document.getElementById('search-detailed');
    const resultsEl = document.getElementById('search-results');
    const hintsEl = document.getElementById('search-hints');
    const projectListEl = document.getElementById('project-list');

    // Load hints for current project
    async function loadHints() {
        try {
            hints = await getHints(selectedProject || undefined);
        } catch {
            hints = { topics: [], technologies: [] };
        }
        hintsEl.innerHTML = renderHints();
        wireHintClicks();
    }

    // Wire hint chip clicks — fill search input with the hint text
    function wireHintClicks() {
        hintsEl.querySelectorAll('.hint-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                input.value = chip.dataset.hint;
                input.focus();
                doSearch();
            });
        });
    }

    async function doSearch() {
        const query = input.value.trim();
        if (!query) {
            resultsEl.innerHTML = `<div class="empty-state">
                <div class="empty-state-icon">&#128270;</div>
                <div class="empty-state-title">Start typing to search</div>
                <div class="empty-state-text">Or click a hint above to explore a topic</div>
            </div>`;
            return;
        }

        if (abortController) abortController.abort();
        abortController = new AbortController();

        resultsEl.innerHTML = '<div class="loading"><div class="spinner"></div> Searching...</div>';

        try {
            const results = await search(query, {
                project: selectedProject || undefined,
                detailed: detailedCheck.checked,
            });

            if (!results.sessions || results.sessions.length === 0) {
                resultsEl.innerHTML = `<div class="empty-state">
                    <div class="empty-state-icon">&#128196;</div>
                    <div class="empty-state-title">No results</div>
                    <div class="empty-state-text">Try broader terms${selectedProject ? ' or select "All projects"' : ''}</div>
                </div>`;
                return;
            }

            resultsEl.innerHTML = `
                <p class="text-sm text-muted mb-md">${results.result_count} session(s) found</p>
                <div class="session-list">
                    ${results.sessions.map(s => renderSessionCard(s)).join('')}
                </div>
            `;

            resultsEl.querySelectorAll('.session-card').forEach(card => {
                card.addEventListener('click', () => {
                    window.location.hash = `#/session/${card.dataset.id}`;
                });
            });
        } catch (err) {
            if (err.name === 'AbortError') return;
            resultsEl.innerHTML = `<div class="empty-state">
                <div class="empty-state-icon">&#9888;</div>
                <div class="empty-state-title">Search error</div>
                <div class="empty-state-text">${escapeHtml(err.message)}</div>
            </div>`;
        }
    }

    function debouncedSearch() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(doSearch, 300);
    }

    // Wire sidebar project clicks
    function wireProjectClicks() {
        projectListEl.querySelectorAll('.sidebar-item').forEach(item => {
            item.addEventListener('click', () => {
                selectedProject = item.dataset.project;
                projectListEl.innerHTML = renderProjectList();
                wireProjectClicks();
                loadHints();
                if (input.value.trim()) doSearch();
            });
        });
    }

    input.addEventListener('input', debouncedSearch);
    detailedCheck.addEventListener('change', () => { if (input.value.trim()) doSearch(); });

    wireProjectClicks();
    wireHintClicks();

    // Load initial hints
    await loadHints();

    // Show initial empty state
    doSearch();

    return () => {
        clearTimeout(debounceTimer);
        if (abortController) abortController.abort();
    };
}
