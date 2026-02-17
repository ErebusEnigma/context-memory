/**
 * Toast notification component.
 */

const container = document.getElementById('toast-container');

export function showToast(message, type = 'info', duration = 3000) {
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = message;
    container.appendChild(el);

    setTimeout(() => {
        el.style.opacity = '0';
        el.style.transition = 'opacity 200ms';
        setTimeout(() => el.remove(), 200);
    }, duration);
}
