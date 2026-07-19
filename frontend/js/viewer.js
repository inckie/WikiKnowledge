/**
 * WikiKnowledge — Markdown Viewer
 * 
 * Renders markdown with wiki-link resolution and human/AI block indicators.
 */

const Viewer = {
    /** All known article IDs (populated on init) */
    _knownArticles: new Set(),
    /** All known resource metadata keyed by ID */
    _knownResources: new Map(),

    /**
     * Update the set of known article IDs for link resolution.
     */
    setKnownArticles(articles) {
        this._knownArticles = new Set(articles.map(a => a.id));
    },

    /**
     * Update the map of known resources for file link resolution.
     * @param {Array} resources - Array of resource metadata objects
     */
    setKnownResources(resources) {
        this._knownResources = new Map(resources.map(r => [r.id, r]));
    },

    /**
     * Render markdown content to HTML with wiki-link support.
     * @param {string} markdown - Raw markdown content
     * @returns {string} HTML string
     */
    render(markdown) {
        if (!markdown) return '';

        // Protect code blocks from wiki-link processing
        const codeBlocks = [];
        let processed = markdown.replace(/(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`]+`)/g, (match) => {
            codeBlocks.push(match);
            return `__WK_CODE_${codeBlocks.length - 1}__`;
        });

        // Pre-process: convert [[file:...]] links first, then [[wiki-links]]
        processed = this._processFileLinks(processed);
        processed = this._processWikiLinks(processed);

        // Restore code blocks
        processed = processed.replace(/__WK_CODE_(\d+)__/g, (match, index) => {
            return codeBlocks[parseInt(index, 10)];
        });

        // Render markdown
        let html = marked.parse(processed, {
            gfm: true,
            breaks: false,
        });

        // Post-process: mark human/AI blocks on the generated HTML
        html = this._processContentBlocks(html);

        // Process mermaid code blocks
        html = html.replace(/<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/gi, (match, code) => {
            let unescaped = code
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(/&quot;/g, '"')
                .replace(/&#39;/g, "'")
                .replace(/&amp;/g, '&');
            return `<div class="mermaid">${unescaped}</div>`;
        });

        return html;
    },

    /**
     * Replace [[file:resource-id]] and [[file:resource-id|display]] with
     * inline images or download links.
     */
    _processFileLinks(text) {
        return text.replace(/\[\[file:([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]/gi, (match, resourceId, displayText) => {
            resourceId = resourceId.trim();
            let resource = this._knownResources.get(resourceId);
            if (!resource) {
                // Fallback: try matching with or without extension
                for (const [id, res] of this._knownResources.entries()) {
                    if (id.split('.')[0] === resourceId.split('.')[0]) {
                        resource = res;
                        break;
                    }
                }
            }
            const display = displayText ? displayText.trim() : (resource ? resource.title : resourceId);

            if (!resource) {
                return `<a class="wiki-link missing file-link" title="Resource not found: ${Utils.escapeHtml(resourceId)}">${Utils.escapeHtml(display)}</a>`;
            }

            const fileUrl = `/api/resources/${encodeURIComponent(resource.id)}/file`;

            if (resource.mime_type && resource.mime_type.startsWith('image/')) {
                // Render images inline
                const alt = resource.description || display;
                return `<figure class="wiki-resource-figure"><img class="wiki-resource-img" src="${fileUrl}" alt="${Utils.escapeHtml(alt)}" title="${Utils.escapeHtml(display)}" loading="lazy"><figcaption>${Utils.escapeHtml(display)}</figcaption></figure>`;
            } else {
                // Render non-image resources as download links
                const icon = this._getResourceIcon(resource.mime_type);
                return `<a class="wiki-link file-link" href="${fileUrl}" target="_blank" title="${Utils.escapeHtml(resource.description || display)}">${icon} ${Utils.escapeHtml(display)}</a>`;
            }
        });
    },

    /**
     * Get an appropriate icon emoji for a MIME type.
     */
    _getResourceIcon(mimeType) {
        if (!mimeType) return '📎';
        if (mimeType.startsWith('audio/')) return '🎵';
        if (mimeType.startsWith('video/')) return '🎬';
        if (mimeType.startsWith('text/')) return '📄';
        if (mimeType.includes('pdf')) return '📕';
        return '📎';
    },

    /**
     * Replace [[target]] and [[target|display]] with clickable HTML links.
     */
    _processWikiLinks(text) {
        return text.replace(/\[\[(?!file:)([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]/gi, (match, targetId, displayText) => {
            targetId = targetId.trim();
            const display = displayText ? displayText.trim() : targetId;
            const exists = this._knownArticles.has(targetId);
            let cssClass = exists ? 'wiki-link' : 'wiki-link missing';
            let icon = '';
            
            const isSrc = targetId.startsWith('src:');
            const isGDrive = targetId.startsWith('gdrive:');
            
            if (isSrc || isGDrive) {
                cssClass += ' source-link';
                if (!exists) {
                    icon = '<span class="source-icon disconnected" title="Source Disconnected" style="font-size: 0.9em; margin-right: 2px; color: var(--text-muted);">⊘</span>';
                    cssClass = cssClass.replace('missing', 'disconnected');
                    return `<span class="${cssClass}" data-article-id="${Utils.escapeHtml(targetId)}">${icon}${Utils.escapeHtml(display)}</span>`;
                } else {
                    const sourceIconStr = isSrc ? '🔌' : '☁️';
                    const sourceTitle = isSrc ? 'External Source Code' : 'Google Drive Document';
                    icon = `<span class="source-icon" title="${sourceTitle}" style="font-size: 0.9em; margin-right: 2px;">${sourceIconStr}</span>`;
                }
            }
            
            return `<a class="${cssClass}" href="#/article/${encodeURIComponent(targetId)}" data-article-id="${Utils.escapeHtml(targetId)}">${icon}${Utils.escapeHtml(display)}</a>`;
        });
    },

    /**
     * Wrap human:start/end and ai:start/end blocks with visual indicators.
     */
    _processContentBlocks(text) {
        text = text.replace(
            /<!--\s*human:start\s*-->([\s\S]*?)<!--\s*human:end\s*-->/gi,
            '<div class="block-human"><span class="block-badge human">✍️ Human</span>\n$1</div>'
        );
        text = text.replace(
            /<!--\s*ai:start\s*-->([\s\S]*?)<!--\s*ai:end\s*-->/gi,
            '<div class="block-ai"><span class="block-badge ai">🤖 AI</span>\n$1</div>'
        );
        return text;
    },

    /**
     * Display an article in the viewer.
     * @param {Object} article - Full article object from API
     */
    async show(article) {
        // Render metadata, breadcrumb, and body
        document.getElementById('article-meta').innerHTML = this._renderMeta(article);
        document.getElementById('article-breadcrumb').innerHTML = this._renderBreadcrumb(article);

        if (article.type === 'resource') {
            document.getElementById('article-body').innerHTML = this._renderResourcePage(article);
        } else {
            document.getElementById('article-body').innerHTML = this.render(article.content);
        }

        // Render category-specific section or clear it
        const categorySectionEl = document.getElementById('category-section');
        if (article.type === 'category') {
            categorySectionEl.innerHTML = this._renderCategorySection(article);
        } else {
            categorySectionEl.innerHTML = '';
        }

        // Render backlinks for all article types
        await this._renderBacklinks(article);

        // Render any mermaid diagrams
        this.renderMermaid();
    },

    /**
     * Render Mermaid diagrams in the DOM.
     */
    async renderMermaid() {
        if (window.mermaid) {
            try {
                await mermaid.run({
                    querySelector: '.mermaid',
                    suppressErrors: true
                });
            } catch (e) {
                console.warn('Mermaid render error:', e);
            }
        }
    },

    _renderMeta(article) {
        const parts = [];

        const isSourceCode = article.id && article.id.startsWith('src:');
        const isDrive = article.id && article.id.startsWith('gdrive:');
        
        if (isDrive) {
            parts.push(`<div class="meta-group"><span class="source-badge drive" title="Google Drive">Drive</span></div><div class="meta-divider"></div>`);
        } else if (isSourceCode) {
            parts.push(`<div class="meta-group"><span class="source-badge code" title="Source Code">Code</span></div><div class="meta-divider"></div>`);
        }

        parts.push(`<div class="meta-group"><span class="meta-label">Type</span><span class="chip chip-type">${article.type}</span></div>`);
        if (article.mime_type) {
            parts.push(`<div class="meta-divider"></div><div class="meta-group"><span class="meta-label">MIME Type</span><span class="chip" style="background:var(--bg-tertiary); border:1px solid var(--border-color); padding: 2px 8px; border-radius: 4px; font-size: var(--text-xs);">${Utils.escapeHtml(article.mime_type)}</span></div>`);
        }
        if (article.tags && article.tags.length) {
            const tagChips = article.tags.map(t => `<span class="chip chip-tag" onclick="App.filterByTag('${Utils.escapeHtml(t)}')">${Utils.escapeHtml(t)}</span>`).join('');
            parts.push(`<div class="meta-divider"></div><div class="meta-group"><span class="meta-label">Tags</span>${tagChips}</div>`);
        }
        if (article.categories && article.categories.length) {
            const catChips = article.categories.map(c => `<a class="chip chip-category" href="#/article/${encodeURIComponent(c)}">${Utils.escapeHtml(c)}</a>`).join('');
            parts.push(`<div class="meta-divider"></div><div class="meta-group"><span class="meta-label">Categories</span>${catChips}</div>`);
        }
        if (article.modified) {
            parts.push(`<div class="meta-divider"></div><div class="meta-group"><span class="meta-label">Modified</span><span style="font-size: var(--text-xs); color: var(--text-muted);">${Utils.formatDate(article.modified)}</span></div>`);
        }
        return parts.join('');
    },

    _renderBreadcrumb(article) {
        const parts = [`<a href="#/">Home</a>`, `<span class="separator">›</span>`];
        if (article.categories && article.categories.length) {
            const cat = article.categories[0];
            parts.push(`<a href="#/article/${encodeURIComponent(cat)}">${Utils.escapeHtml(cat)}</a>`);
            parts.push(`<span class="separator">›</span>`);
        }
        parts.push(`<span>${Utils.escapeHtml(article.title || article.id)}</span>`);
        return parts.join(' ');
    },

    _renderResourcePage(resource) {
        const fileUrl = `/api/resources/${encodeURIComponent(resource.id)}/file`;
        let previewHtml = '';

        if (resource.mime_type && resource.mime_type.startsWith('image/')) {
            previewHtml = `
                <div class="resource-media-preview" style="text-align: center; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: var(--space-6); margin-bottom: var(--space-6); box-shadow: var(--shadow-inner);">
                    <a href="${fileUrl}" target="_blank" title="Click to view full size">
                        <img src="${fileUrl}" alt="${Utils.escapeHtml(resource.title)}" style="max-width: 100%; max-height: 500px; object-fit: contain; border-radius: var(--radius-md); box-shadow: var(--shadow-sm); background: #ffffff;">
                    </a>
                    <div style="margin-top: var(--space-3); font-size: var(--text-sm); color: var(--text-muted);">
                        <a href="${fileUrl}" target="_blank" style="color: var(--accent-primary); text-decoration: none;">🔍 View original file (${Utils.escapeHtml(resource.filename)})</a>
                    </div>
                </div>
            `;
        } else {
            const icon = this._getResourceIcon(resource.mime_type);
            previewHtml = `
                <div class="resource-media-preview" style="text-align: center; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: var(--space-8); margin-bottom: var(--space-6);">
                    <div style="font-size: 4rem; margin-bottom: var(--space-3);">${icon}</div>
                    <h3 style="margin-bottom: var(--space-2); color: var(--text-normal);">${Utils.escapeHtml(resource.filename)}</h3>
                    <p style="color: var(--text-muted); font-size: var(--text-sm); margin-bottom: var(--space-4);">MIME Type: ${Utils.escapeHtml(resource.mime_type || 'unknown')}</p>
                    <a class="btn btn-primary" href="${fileUrl}" target="_blank" style="display: inline-flex; align-items: center; gap: 8px;">
                        📥 Download File
                    </a>
                </div>
            `;
        }

        const descriptionHtml = resource.description ? `
            <h2 style="margin-bottom: var(--space-3); border-bottom: 1px solid var(--border-color); padding-bottom: var(--space-2);">Summary</h2>
            <div style="font-size: var(--text-base); line-height: 1.6; color: var(--text-normal); margin-bottom: var(--space-6);">
                ${this.render(resource.description)}
            </div>
        ` : '';

        const relatedHtml = resource.related && resource.related.length ? `
            <h2 style="margin-bottom: var(--space-3); border-bottom: 1px solid var(--border-color); padding-bottom: var(--space-2);">Related Articles</h2>
            <div style="display: flex; flex-direction: column; gap: var(--space-2); margin-bottom: var(--space-6);">
                ${resource.related.map(rel => `
                    <div class="related-item">
                        <span class="item-icon leaf"></span>
                        <a class="wiki-link" href="#/article/${encodeURIComponent(rel)}">${Utils.escapeHtml(rel)}</a>
                    </div>
                `).join('')}
            </div>
        ` : '';

        const embedHtml = `
            <h2 style="margin-bottom: var(--space-3); border-bottom: 1px solid var(--border-color); padding-bottom: var(--space-2);">File Usage</h2>
            <p style="color: var(--text-muted); font-size: var(--text-sm); margin-bottom: var(--space-3);">To embed this resource in any wiki article, use the following syntax:</p>
            <pre style="background: var(--bg-tertiary); border: 1px solid var(--border-color); padding: var(--space-3); border-radius: var(--radius-md); font-family: monospace; color: var(--accent-primary);">[[file:${Utils.escapeHtml(resource.id)}|${Utils.escapeHtml(resource.title)}]]</pre>
        `;

        return `
            <div class="resource-info-page">
                <h1 style="margin-bottom: var(--space-6); color: var(--text-normal);">${Utils.escapeHtml(resource.title)}</h1>
                ${previewHtml}
                ${descriptionHtml}
                ${relatedHtml}
                ${embedHtml}
            </div>
        `;
    },

    _renderCategorySection(article) {
        const dirtyIndicator = article.is_dirty ?
            `<span class="dirty-indicator" title="This category might be outdated. One or more of its articles have been modified more recently than this overview.">⚠️</span>` :
            '';

        const subArticles = (article.sub_articles || []).map(sub => {
            const unmentionedClass = sub.is_unmentioned ? 'unmentioned' : '';
            const iconClass = sub.type === 'category' ? 'item-icon category' : 'item-icon';
            const newerIcon = sub.is_newer ? `<span class="newer-indicator" title="Modified more recently than the category article" style="margin-left: 6px; font-size: 0.9em; cursor: help;">✨</span>` : '';
            const isExternal = sub.id.startsWith('src:');
            const externalIcon = isExternal ? '<span title="External Source" style="margin-right: 4px; text-decoration: none; display: inline-block;">🔌</span>' : '';
            return `
                <div class="sub-article-item ${unmentionedClass}">
                    <span class="${iconClass}"></span>
                    <a href="#/article/${encodeURIComponent(sub.id)}">${externalIcon}${Utils.escapeHtml(sub.title)}</a>
                    ${newerIcon}
                </div>
            `;
        }).join('');

        return `
            <div class="category-section-title">
                <span>Sub-articles</span>
                ${dirtyIndicator}
            </div>
            <div>${subArticles}</div>
        `;
    },

    async _renderBacklinks(article) {
        const container = document.getElementById('article-backlinks');
        try {
            let backlinks = await API.fetchBacklinks(article.id);

            // For categories, filter out backlinks from their own sub-articles
            if (article.type === 'category' && article.sub_articles) {
                const subArticleIds = new Set(article.sub_articles.map(sa => sa.id));
                backlinks = backlinks.filter(bl => !subArticleIds.has(bl.source_id));
            }

            // Deduplicate by source_id
            const uniqueBacklinks = [];
            const seen = new Set();
            for (const bl of backlinks) {
                if (!seen.has(bl.source_id)) {
                    seen.add(bl.source_id);
                    uniqueBacklinks.push(bl);
                }
            }

            if (!uniqueBacklinks.length) {
                container.innerHTML = '';
                return;
            }

            const items = uniqueBacklinks.map(bl => {
                const title = bl.source_title || bl.source_id;
                return `<a class="backlink-item" href="#/article/${encodeURIComponent(bl.source_id)}">
                    ← ${Utils.escapeHtml(title)}
                </a>`;
            }).join('');

            container.innerHTML = `
                <div class="backlinks-title">🔗 What Links Here (${uniqueBacklinks.length})</div>
                <div>${items}</div>
            `;
        } catch (e) {
            container.innerHTML = '';
            console.error('Failed to render backlinks:', e);
        }
    },
};