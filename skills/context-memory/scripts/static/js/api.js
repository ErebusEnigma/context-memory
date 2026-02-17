/**
 * API client for Context Memory Dashboard.
 * Wraps all REST endpoints with fetch calls.
 */

const BASE = '';

async function fetchJSON(url, options = {}) {
    const resp = await fetch(`${BASE}${url}`, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: resp.statusText }));
        throw new Error(err.error || `HTTP ${resp.status}`);
    }
    return resp.json();
}

// Sessions
export function listSessions({ page = 1, perPage = 20, project, sort, order } = {}) {
    const params = new URLSearchParams({ page, per_page: perPage });
    if (project) params.set('project', project);
    if (sort) params.set('sort', sort);
    if (order) params.set('order', order);
    return fetchJSON(`/api/sessions?${params}`);
}

export function getSession(id) {
    return fetchJSON(`/api/sessions/${id}`);
}

export function updateSession(id, data) {
    return fetchJSON(`/api/sessions/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

export function deleteSession(id) {
    return fetchJSON(`/api/sessions/${id}`, { method: 'DELETE' });
}

// Search
export function search(query, { project, detailed = false, limit = 10 } = {}) {
    const params = new URLSearchParams({ q: query, limit });
    if (project) params.set('project', project);
    if (detailed) params.set('detailed', 'true');
    return fetchJSON(`/api/search?${params}`);
}

// Stats
export function getStats() {
    return fetchJSON('/api/stats');
}

// Analytics
export function getTimeline(granularity = 'week') {
    return fetchJSON(`/api/analytics/timeline?granularity=${granularity}`);
}

export function getTopTopics(limit = 20) {
    return fetchJSON(`/api/analytics/topics?limit=${limit}`);
}

export function getProjects() {
    return fetchJSON('/api/analytics/projects');
}

export function getOutcomes() {
    return fetchJSON('/api/analytics/outcomes');
}

export function getTechnologies(limit = 15) {
    return fetchJSON(`/api/analytics/technologies?limit=${limit}`);
}

// Management
export function pruneSessions({ maxAgeDays, maxSessions, dryRun = true }) {
    return fetchJSON('/api/prune', {
        method: 'POST',
        body: JSON.stringify({
            max_age_days: maxAgeDays || null,
            max_sessions: maxSessions || null,
            dry_run: dryRun,
        }),
    });
}

export function initDatabase(force = false) {
    return fetchJSON('/api/init', {
        method: 'POST',
        body: JSON.stringify({ force }),
    });
}

export function exportAll() {
    return fetchJSON('/api/export');
}

// Project list (for filters)
export function listProjects() {
    return fetchJSON('/api/projects');
}

// Search hints (topics + technologies, optionally scoped to project)
export function getHints(project) {
    const params = new URLSearchParams();
    if (project) params.set('project', project);
    return fetchJSON(`/api/hints?${params}`);
}
