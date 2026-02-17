/**
 * Code Block component — renders syntax-highlighted code snippets.
 */

import { escapeHtml } from '../app.js';

export function renderCodeBlock(snippet) {
    const lang = escapeHtml(snippet.language || '');
    const desc = escapeHtml(snippet.description || 'Code snippet');
    const filePath = escapeHtml(snippet.file_path || '');
    const code = escapeHtml(snippet.code || '');

    return `
        <div class="code-block">
            <div class="code-block-header">
                <span>${desc}</span>
                <span>${filePath ? filePath : lang}</span>
            </div>
            <pre><code class="language-${lang}">${code}</code></pre>
        </div>
    `;
}

export function highlightAll(container) {
    if (typeof hljs !== 'undefined') {
        container.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
        });
    }
}
