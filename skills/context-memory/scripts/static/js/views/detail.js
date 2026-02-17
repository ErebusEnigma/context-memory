/**
 * Session Detail view — full session with messages, snippets, edit, delete.
 */

import { getSession, updateSession, deleteSession } from '../api.js';
import { renderCodeBlock, highlightAll } from '../components/code-block.js';
import { showConfirm, showEditModal } from '../components/modal.js';
import { showToast } from '../components/toast.js';
import { escapeHtml, formatDate, projectName, outcomeBadge } from '../app.js';

export async function renderDetailView(container, idStr) {
    const sessionId = parseInt(idStr);
    let session;

    try {
        session = await getSession(sessionId);
    } catch (err) {
        container.innerHTML = `<div class="empty-state">
            <div class="empty-state-icon">&#9888;</div>
            <div class="empty-state-title">Session not found</div>
            <div class="empty-state-text">${escapeHtml(err.message)}</div>
        </div>`;
        return;
    }

    function render() {
        const date = formatDate(session.created_at);
        const project = projectName(session.project_path);
        const outcome = outcomeBadge(session.outcome);
        const topics = (session.topics || []).map(t =>
            `<span class="tag">${escapeHtml(t)} <span class="tag-remove" data-topic="${escapeHtml(t)}">&times;</span></span>`
        ).join('');

        const decisions = session.key_decisions || [];
        const problems = session.problems_solved || [];
        const messages = session.messages || [];
        const snippets = session.code_snippets || [];
        const techs = session.technologies || [];

        const techsArr = typeof techs === 'string' ? (() => { try { return JSON.parse(techs); } catch { return [techs]; } })() : techs;
        const decisionsArr = typeof decisions === 'string' ? (() => { try { return JSON.parse(decisions); } catch { return [decisions]; } })() : decisions;
        const problemsArr = typeof problems === 'string' ? (() => { try { return JSON.parse(problems); } catch { return [problems]; } })() : problems;

        container.innerHTML = `
            <div class="flex items-center gap-sm mb-md">
                <a href="#/sessions" class="btn btn-sm">&larr; Back</a>
            </div>

            <div class="detail-header">
                <div class="detail-title">${escapeHtml(session.brief || 'Untitled session')}</div>
                <div class="detail-meta">
                    <span>${date}</span>
                    <span>${escapeHtml(project)}</span>
                    ${outcome}
                    <span>${session.message_count || 0} messages</span>
                    <span class="font-mono text-xs">${escapeHtml(session.session_id || '')}</span>
                </div>
            </div>

            <div class="flex gap-sm mb-md">
                <button class="btn btn-sm" id="edit-summary-btn">Edit Summary</button>
                <button class="btn btn-sm" id="edit-note-btn">Edit Note</button>
                <button class="btn btn-danger btn-sm" id="delete-btn">Delete</button>
            </div>

            ${session.user_note ? `
                <div class="detail-section">
                    <div class="detail-section-title">User Note</div>
                    <p class="text-sm">${escapeHtml(session.user_note)}</p>
                </div>
            ` : ''}

            ${session.detailed ? `
                <div class="detail-section">
                    <div class="detail-section-title">Detailed Summary</div>
                    <p class="text-sm" style="white-space: pre-wrap;">${escapeHtml(session.detailed)}</p>
                </div>
            ` : ''}

            <div class="detail-section">
                <div class="detail-section-title">Topics</div>
                <div class="flex gap-sm" style="flex-wrap:wrap;" id="topics-container">
                    ${topics}
                    <button class="btn btn-sm" id="add-topic-btn">+ Add</button>
                </div>
            </div>

            ${techsArr.length ? `
                <div class="detail-section">
                    <div class="detail-section-title">Technologies</div>
                    <div class="flex gap-sm" style="flex-wrap:wrap;">
                        ${techsArr.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}
                    </div>
                </div>
            ` : ''}

            ${decisionsArr.length ? `
                <div class="detail-section">
                    <div class="detail-section-title">Key Decisions</div>
                    <ul style="margin-left: 1.25rem;">
                        ${decisionsArr.map(d => `<li class="list-item">${escapeHtml(d)}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}

            ${problemsArr.length ? `
                <div class="detail-section">
                    <div class="detail-section-title">Problems Solved</div>
                    <ul style="margin-left: 1.25rem;">
                        ${problemsArr.map(p => `<li class="list-item">${escapeHtml(p)}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}

            ${messages.length ? `
                <div class="detail-section">
                    <div class="detail-section-title">Messages (${messages.length})</div>
                    ${messages.map(m => `
                        <div class="message message-${m.role || 'user'}">
                            <div class="message-role">${escapeHtml(m.role || 'user')}</div>
                            <div style="white-space: pre-wrap;">${escapeHtml(m.content || '')}</div>
                        </div>
                    `).join('')}
                </div>
            ` : ''}

            ${snippets.length ? `
                <div class="detail-section">
                    <div class="detail-section-title">Code Snippets (${snippets.length})</div>
                    ${snippets.map(s => renderCodeBlock(s)).join('')}
                </div>
            ` : ''}
        `;

        highlightAll(container);
        wireEvents();
    }

    function wireEvents() {
        // Delete
        document.getElementById('delete-btn')?.addEventListener('click', async () => {
            const confirmed = await showConfirm({
                title: 'Delete session',
                body: '<p>This will permanently delete this session and all its data.</p>',
                confirmText: 'Delete',
                danger: true,
            });
            if (!confirmed) return;
            try {
                await deleteSession(sessionId);
                showToast('Session deleted', 'success');
                window.location.hash = '#/sessions';
            } catch (err) {
                showToast(`Delete failed: ${err.message}`, 'error');
            }
        });

        // Edit summary
        document.getElementById('edit-summary-btn')?.addEventListener('click', async () => {
            const result = await showEditModal({
                title: 'Edit Summary',
                fields: [
                    { key: 'brief', label: 'Brief', value: session.brief || '' },
                    { key: 'detailed', label: 'Detailed', type: 'textarea', value: session.detailed || '' },
                    { key: 'user_note', label: 'User Note', value: session.user_note || '' },
                ],
            });
            if (!result) return;
            try {
                await updateSession(sessionId, result);
                Object.assign(session, result);
                render();
                showToast('Summary updated', 'success');
            } catch (err) {
                showToast(`Update failed: ${err.message}`, 'error');
            }
        });

        // Edit note shortcut
        document.getElementById('edit-note-btn')?.addEventListener('click', async () => {
            const result = await showEditModal({
                title: 'Edit Note',
                fields: [
                    { key: 'user_note', label: 'User Note', type: 'textarea', value: session.user_note || '' },
                ],
            });
            if (!result) return;
            try {
                await updateSession(sessionId, result);
                session.user_note = result.user_note;
                render();
                showToast('Note updated', 'success');
            } catch (err) {
                showToast(`Update failed: ${err.message}`, 'error');
            }
        });

        // Remove topic
        container.querySelectorAll('.tag-remove').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const topic = btn.dataset.topic;
                const newTopics = (session.topics || []).filter(t => t !== topic);
                try {
                    await updateSession(sessionId, { topics: newTopics });
                    session.topics = newTopics;
                    render();
                    showToast(`Removed topic: ${topic}`, 'info');
                } catch (err) {
                    showToast(`Failed: ${err.message}`, 'error');
                }
            });
        });

        // Add topic
        document.getElementById('add-topic-btn')?.addEventListener('click', async () => {
            const result = await showEditModal({
                title: 'Add Topic',
                fields: [{ key: 'topic', label: 'Topic name' }],
            });
            if (!result || !result.topic.trim()) return;
            const newTopic = result.topic.trim().toLowerCase();
            const newTopics = [...(session.topics || []), newTopic];
            try {
                await updateSession(sessionId, { topics: newTopics });
                session.topics = newTopics;
                render();
                showToast(`Added topic: ${newTopic}`, 'success');
            } catch (err) {
                showToast(`Failed: ${err.message}`, 'error');
            }
        });
    }

    render();
}
