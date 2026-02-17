/**
 * Session Card component — renders a clickable session summary card.
 */

import { escapeHtml, formatDate, projectName, outcomeBadge } from '../app.js';

export function renderSessionCard(session) {
    const date = formatDate(session.created_at);
    const project = projectName(session.project_path);
    const brief = escapeHtml(session.brief || 'No summary');
    const topics = (session.topics || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('');
    const outcome = outcomeBadge(session.outcome);
    const msgCount = session.message_count || 0;
    const isAuto = session.metadata && (session.metadata.auto_save === true || session.metadata === '{"auto_save": true}');
    const matchSources = (session.match_sources || []).map(s => `<span class="badge badge-muted">${escapeHtml(s)}</span>`).join('');

    return `
        <div class="card card-clickable session-card" data-id="${session.id}">
            <div class="session-card-header">
                <span class="session-card-date">${date}</span>
                <span class="session-card-project">${escapeHtml(project)}</span>
                ${outcome}
                ${isAuto ? '<span class="badge badge-muted">auto</span>' : ''}
                ${matchSources}
            </div>
            <div class="session-card-brief">${brief}</div>
            <div class="session-card-footer">
                <span class="session-card-meta">${msgCount} messages</span>
                <div class="flex gap-sm" style="flex-wrap:wrap">${topics}</div>
            </div>
        </div>
    `;
}
