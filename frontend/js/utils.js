/**
 * WikiKnowledge — Shared Utilities
 */

const Utils = {
    /**
     * Debounce a function call.
     */
    debounce(fn, delay = 300) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    },

    /**
     * Generate a URL-safe slug from text.
     */
    slugify(text) {
        return text
            .toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            .trim();
    },

    /**
     * Convert a slug back to a human-readable string.
     */
    unslugify(slug) {
        return slug
            .replace(/-/g, ' ')
            .replace(/\b\w/g, char => char.toUpperCase());
    },

    /**
     * Format an ISO date string for display.
     */
    formatDate(isoString) {
        if (!isoString) return '';
        const d = new Date(isoString);
        return d.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    },

    /**
     * Escape HTML special characters.
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Show a temporary toast notification.
     */
    toast(message, type = 'info') {
        const existing = document.querySelector('.toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 0.875rem;
            font-family: var(--font-sans);
            color: white;
            z-index: 1000;
            animation: fadeIn 0.3s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#6366f1'};
        `;
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.3s';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },

    /**
     * Determine source type, badge styling, label, and icon for an article or article ID.
     */
    getSourceInfo(articleOrId, sourcesList = []) {
        const article = typeof articleOrId === 'object' && articleOrId !== null ? articleOrId : { id: String(articleOrId || '') };
        const id = article.id || '';
        const tags = Array.isArray(article.tags) ? article.tags : [];

        if (id.startsWith('gdrive:')) {
            return {
                type: 'drive',
                badgeClass: 'drive',
                badgeText: 'Drive',
                icon: '☁️',
                label: 'Google Drive Document'
            };
        }

        if (id.startsWith('src:')) {
            const sourceId = id.slice(4).split('/')[0];
            const matchingSource = (sourcesList || []).find(s => s.id === sourceId);

            if (matchingSource) {
                if (matchingSource.type === 'MarkdownFilesPlugin') {
                    return {
                        type: 'markdown',
                        badgeClass: 'markdown',
                        badgeText: 'Markdown',
                        icon: '📄',
                        label: 'Markdown Document'
                    };
                }
                if (matchingSource.type === 'SourceCodePlugin') {
                    return {
                        type: 'code',
                        badgeClass: 'code',
                        badgeText: 'Code',
                        icon: '💻',
                        label: 'Source Code'
                    };
                }
            }

            // Fallback heuristics based on tags/id
            const tagsLower = tags.map(t => String(t).toLowerCase());
            if (tagsLower.includes('markdown') || tagsLower.includes('md') || id.includes('/guides') || id.includes('/docs')) {
                return {
                    type: 'markdown',
                    badgeClass: 'markdown',
                    badgeText: 'Markdown',
                    icon: '📄',
                    label: 'Markdown Document'
                };
            }
            if (tagsLower.includes('python') || tagsLower.includes('javascript') || tagsLower.includes('code') || tagsLower.includes('rst') || tagsLower.includes('jsdoc')) {
                return {
                    type: 'code',
                    badgeClass: 'code',
                    badgeText: 'Code',
                    icon: '💻',
                    label: 'Source Code'
                };
            }

            return {
                type: 'source',
                badgeClass: 'source',
                badgeText: 'Source',
                icon: '🔌',
                label: 'External Source'
            };
        }

        return {
            type: 'native',
            badgeClass: 'native',
            badgeText: 'Wiki',
            icon: article.type === 'category' ? '📁' : '📄',
            label: 'Wiki Article'
        };
    },
};