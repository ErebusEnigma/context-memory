/**
 * Modal component — confirmation dialogs and edit forms.
 */

import { escapeHtml } from '../app.js';

const overlay = document.getElementById('modal-overlay');

export function showConfirm({ title, body, confirmText = 'Confirm', danger = false }) {
    return new Promise(resolve => {
        const btnClass = danger ? 'btn btn-danger' : 'btn btn-primary';
        overlay.innerHTML = `
            <div class="modal">
                <div class="modal-title">${escapeHtml(title)}</div>
                <div class="modal-body">${body}</div>
                <div class="modal-actions">
                    <button class="btn" id="modal-cancel">Cancel</button>
                    <button class="${btnClass}" id="modal-confirm">${escapeHtml(confirmText)}</button>
                </div>
            </div>
        `;
        overlay.classList.remove('hidden');

        const cancel = () => { overlay.classList.add('hidden'); resolve(false); };
        const confirm = () => { overlay.classList.add('hidden'); resolve(true); };

        document.getElementById('modal-cancel').addEventListener('click', cancel);
        document.getElementById('modal-confirm').addEventListener('click', confirm);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) cancel();
        }, { once: true });
    });
}

export function showEditModal({ title, fields }) {
    return new Promise(resolve => {
        const fieldHtml = fields.map(f => {
            const val = escapeHtml(f.value || '');
            if (f.type === 'textarea') {
                return `<div class="mb-sm">
                    <label class="text-sm text-muted">${escapeHtml(f.label)}</label>
                    <textarea class="textarea" id="edit-${f.key}" rows="3">${val}</textarea>
                </div>`;
            }
            return `<div class="mb-sm">
                <label class="text-sm text-muted">${escapeHtml(f.label)}</label>
                <input class="input" id="edit-${f.key}" value="${val}">
            </div>`;
        }).join('');

        overlay.innerHTML = `
            <div class="modal">
                <div class="modal-title">${escapeHtml(title)}</div>
                <div class="modal-body">${fieldHtml}</div>
                <div class="modal-actions">
                    <button class="btn" id="modal-cancel">Cancel</button>
                    <button class="btn btn-primary" id="modal-confirm">Save</button>
                </div>
            </div>
        `;
        overlay.classList.remove('hidden');

        const cancel = () => { overlay.classList.add('hidden'); resolve(null); };
        const save = () => {
            const result = {};
            fields.forEach(f => {
                result[f.key] = document.getElementById(`edit-${f.key}`).value;
            });
            overlay.classList.add('hidden');
            resolve(result);
        };

        document.getElementById('modal-cancel').addEventListener('click', cancel);
        document.getElementById('modal-confirm').addEventListener('click', save);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) cancel();
        }, { once: true });
    });
}

export function hideModal() {
    overlay.classList.add('hidden');
}
