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
    /** Currently displayed article ID */
    _currentArticleId: null,
    /** Scrollspy cleanup callback */
    _scrollspyCleanup: null,

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
        html = html.replace(/<pre><code class="(?:[^"]*?\s+)?language-mermaid(?:\s+[^"]*?)?">([\s\S]*?)<\/code><\/pre>/gi, (match, code) => {
            let unescaped = code
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(/&quot;/g, '"')
                .replace(/&#39;/g, "'")
                .replace(/&amp;/g, '&');

            // Resolve file and wiki links within mermaid diagrams
            unescaped = this._processFileLinks(unescaped);
            unescaped = this._processWikiLinks(unescaped);

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
            
            let articlePart = targetId;
            let anchorPart = '';
            if (targetId.includes('#')) {
                const hashIndex = targetId.indexOf('#');
                articlePart = targetId.substring(0, hashIndex).trim();
                anchorPart = targetId.substring(hashIndex + 1).trim();
            }
            
            const isSameArticleAnchor = !articlePart && Boolean(anchorPart);
            const effectiveArticleId = articlePart || this._currentArticleId || '';
            const exists = isSameArticleAnchor ? true : this._knownArticles.has(effectiveArticleId);
            let cssClass = exists ? 'wiki-link' : 'wiki-link missing';
            let icon = '';
            
            const isSrc = effectiveArticleId.startsWith('src:');
            const isGDrive = effectiveArticleId.startsWith('gdrive:');
            
            if (isSrc || isGDrive) {
                cssClass += ' source-link';
                if (!exists) {
                    icon = '<span class="source-icon disconnected" title="Source Disconnected" style="font-size: 0.9em; margin-right: 2px; color: var(--text-muted);">⊘</span>';
                    cssClass = cssClass.replace('missing', 'disconnected');
                    return `<span class="${cssClass}" data-article-id="${Utils.escapeHtml(effectiveArticleId)}">${icon}${Utils.escapeHtml(display)}</span>`;
                } else {
                    const sourceIconStr = isSrc ? '🔌' : '☁️';
                    const sourceTitle = isSrc ? 'External Source Code' : 'Google Drive Document';
                    icon = `<span class="source-icon" title="${sourceTitle}" style="font-size: 0.9em; margin-right: 2px;">${sourceIconStr}</span>`;
                }
            }
            
            const href = anchorPart 
                ? `#/article/${encodeURIComponent(effectiveArticleId)}#${encodeURIComponent(anchorPart)}`
                : `#/article/${encodeURIComponent(effectiveArticleId)}`;
            
            return `<a class="${cssClass}" href="${href}" data-article-id="${Utils.escapeHtml(effectiveArticleId)}">${icon}${Utils.escapeHtml(display)}</a>`;
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
        this._currentArticleId = article.id;

        // Clean up previous scrollspy observer/listener
        if (this._scrollspyCleanup) {
            this._scrollspyCleanup();
            this._scrollspyCleanup = null;
        }

        // Render metadata, breadcrumb, and body
        document.getElementById('article-meta').innerHTML = this._renderMeta(article);
        document.getElementById('article-breadcrumb').innerHTML = this._renderBreadcrumb(article);

        if (article.type === 'resource') {
            document.getElementById('article-body').innerHTML = this._renderResourcePage(article);
        } else {
            document.getElementById('article-body').innerHTML = this.render(article.content);
        }

        // Process headers, anchors, and floating ToC
        this._setupHeadersAndToc(article.id);

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

        const sourcesList = (window.App && window.App._sources) ? window.App._sources : [];
        const sourceInfo = Utils.getSourceInfo(article, sourcesList);

        if (sourceInfo.type !== 'native') {
            parts.push(`<div class="meta-group"><span class="source-badge ${sourceInfo.badgeClass}" title="${sourceInfo.label}">${sourceInfo.badgeText}</span></div><div class="meta-divider"></div>`);
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

        const sourcesList = (window.App && window.App._sources) ? window.App._sources : [];
        const subArticles = (article.sub_articles || []).map(sub => {
            const unmentionedClass = sub.is_unmentioned ? 'unmentioned' : '';
            const iconClass = sub.type === 'category' ? 'item-icon category' : 'item-icon';
            const newerIcon = sub.is_newer ? `<span class="newer-indicator" title="Modified more recently than the category article" style="margin-left: 6px; font-size: 0.9em; cursor: help;">✨</span>` : '';
            
            const sourceInfo = Utils.getSourceInfo(sub, sourcesList);
            const sourceBadge = sourceInfo.type !== 'native' ?
                `<span class="source-badge ${sourceInfo.badgeClass}" title="${sourceInfo.label}">${sourceInfo.badgeText}</span>` : '';
            const tagChips = sub.tags && sub.tags.length ?
                `<span class="sub-article-tags">${sub.tags.slice(0, 3).map(t => `<span class="mini-tag">#${Utils.escapeHtml(t)}</span>`).join('')}</span>` : '';

            return `
                <div class="sub-article-item ${unmentionedClass}">
                    <span class="${iconClass}"></span>
                    ${sourceBadge}
                    <a href="#/article/${encodeURIComponent(sub.id)}">${Utils.escapeHtml(sub.title)}</a>
                    ${tagChips}
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

    /**
     * Process headers in article-body: add IDs, anchor links with copy function, and generate ToC.
     */
    _setupHeadersAndToc(articleId) {
        const bodyEl = document.getElementById('article-body');
        const tocEl = document.getElementById('article-toc');
        if (!bodyEl) return;

        const headings = bodyEl.querySelectorAll('h1, h2, h3, h4, h5, h6');
        if (!headings.length) {
            if (tocEl) {
                tocEl.innerHTML = '';
                tocEl.classList.add('hidden');
            }
            return;
        }

        const seenSlugs = new Map();
        const headingList = [];

        headings.forEach((heading, idx) => {
            heading.classList.add('heading-with-anchor');

            // Extract text without existing anchor icons or tools
            let text = '';
            for (const node of heading.childNodes) {
                if (node.nodeType === Node.TEXT_NODE) {
                    text += node.textContent;
                } else if (node.nodeType === Node.ELEMENT_NODE && !node.classList.contains('heading-anchor')) {
                    text += node.textContent;
                }
            }
            text = text.trim();
            if (!text) text = heading.textContent.trim();

            let baseSlug = Utils.slugify(text) || `section-${idx + 1}`;
            let count = seenSlugs.get(baseSlug) || 0;
            let slug = count === 0 ? baseSlug : `${baseSlug}-${count + 1}`;
            seenSlugs.set(baseSlug, count + 1);

            heading.id = slug;

            // Remove existing anchor if any
            const existingAnchor = heading.querySelector('.heading-anchor');
            if (existingAnchor) existingAnchor.remove();

            // Create anchor element
            const anchor = document.createElement('a');
            anchor.className = 'heading-anchor';
            anchor.href = `#/article/${encodeURIComponent(articleId)}#${encodeURIComponent(slug)}`;
            anchor.setAttribute('aria-label', `Copy link to "${text}"`);
            anchor.setAttribute('title', 'Copy link to this section');
            anchor.innerHTML = `
                <svg class="anchor-icon" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                </svg>
                <span class="anchor-tooltip">Copied!</span>
            `;

            anchor.addEventListener('click', (e) => {
                e.preventDefault();
                const hash = `#/article/${encodeURIComponent(articleId)}#${encodeURIComponent(slug)}`;
                const fullUrl = `${window.location.origin}${window.location.pathname}${window.location.search}${hash}`;

                if (window.location.hash !== hash) {
                    history.pushState(null, '', hash);
                }

                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(fullUrl).then(() => {
                        this._showAnchorCopied(anchor);
                        Utils.toast('Link copied to clipboard!', 'success');
                    }).catch(() => {
                        this._fallbackCopyText(fullUrl);
                        this._showAnchorCopied(anchor);
                    });
                } else {
                    this._fallbackCopyText(fullUrl);
                    this._showAnchorCopied(anchor);
                }

                this.scrollToAnchor(slug);
            });

            heading.appendChild(anchor);

            const level = parseInt(heading.tagName.substring(1), 10);
            headingList.push({
                id: slug,
                text: text,
                level: level,
                element: heading
            });
        });

        // Render Floating ToC
        this._renderFloatingToc(articleId, headingList);
    },

    _showAnchorCopied(anchor) {
        anchor.classList.add('copied');
        setTimeout(() => {
            anchor.classList.remove('copied');
        }, 1600);
    },

    _fallbackCopyText(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            Utils.toast('Link copied to clipboard!', 'success');
        } catch (err) {
            console.error('Copy fallback failed', err);
        }
        textarea.remove();
    },

    /**
     * Scroll smoothly to a specific anchor ID and trigger highlight pulse.
     */
    scrollToAnchor(anchorId) {
        if (!anchorId) return;
        const decoded = decodeURIComponent(anchorId);
        const target = document.getElementById(decoded) || document.getElementById(anchorId);
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            target.classList.remove('heading-highlight');
            void target.offsetWidth; // force reflow
            target.classList.add('heading-highlight');
            setTimeout(() => {
                target.classList.remove('heading-highlight');
            }, 2000);

            this._updateActiveTocLink(decoded);
        }
    },

    /**
     * Render floating collapsible Table of Contents widget.
     */
    _renderFloatingToc(articleId, headingList) {
        const tocEl = document.getElementById('article-toc');
        if (!tocEl) return;

        // Hide if fewer than 2 headings
        if (headingList.length < 2) {
            tocEl.innerHTML = '';
            tocEl.classList.add('hidden');
            return;
        }

        tocEl.classList.remove('hidden');

        // Check stored collapsed preference (default to collapsed on small screens, expanded or saved on desktop)
        const storedState = localStorage.getItem('wk_toc_collapsed');
        const defaultCollapsed = window.innerWidth <= 1024;
        const isCollapsed = storedState !== null ? storedState === 'true' : defaultCollapsed;

        tocEl.innerHTML = `
            <div id="toc-pill" class="toc-pill-btn ${isCollapsed ? '' : 'hidden'}" title="Expand Table of Contents">
                <span class="toc-pill-icon">📑</span>
                <span>Contents</span>
                <span class="toc-pill-count">${headingList.length}</span>
            </div>
            <div id="toc-panel" class="toc-panel ${isCollapsed ? 'hidden' : ''}">
                <div class="toc-header">
                    <div class="toc-header-title">
                        <span>📑</span>
                        <span>Contents</span>
                    </div>
                    <div class="toc-header-actions">
                        <button id="btn-toc-collapse" class="toc-btn-close" title="Collapse Table of Contents" aria-label="Collapse">✕</button>
                    </div>
                </div>
                <div class="toc-body">
                    <ul class="toc-list">
                        ${headingList.map(h => `
                            <li class="toc-item" data-level="${h.level}">
                                <a class="toc-link" href="#/article/${encodeURIComponent(articleId)}#${encodeURIComponent(h.id)}" data-target-id="${Utils.escapeHtml(h.id)}" title="${Utils.escapeHtml(h.text)}">
                                    ${Utils.escapeHtml(h.text)}
                                </a>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            </div>
        `;

        const pill = tocEl.querySelector('#toc-pill');
        const panel = tocEl.querySelector('#toc-panel');
        const collapseBtn = tocEl.querySelector('#btn-toc-collapse');

        const setCollapsed = (collapsed) => {
            localStorage.setItem('wk_toc_collapsed', collapsed ? 'true' : 'false');
            if (collapsed) {
                panel.classList.add('hidden');
                pill.classList.remove('hidden');
            } else {
                pill.classList.add('hidden');
                panel.classList.remove('hidden');
            }
        };

        if (pill) {
            pill.addEventListener('click', () => setCollapsed(false));
        }
        if (collapseBtn) {
            collapseBtn.addEventListener('click', () => setCollapsed(true));
        }

        // Bind click on ToC links
        const links = tocEl.querySelectorAll('.toc-link');
        links.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = link.getAttribute('data-target-id');
                const hash = `#/article/${encodeURIComponent(articleId)}#${encodeURIComponent(targetId)}`;
                if (window.location.hash !== hash) {
                    history.pushState(null, '', hash);
                }
                this.scrollToAnchor(targetId);

                if (window.innerWidth <= 768) {
                    setCollapsed(true);
                }
            });
        });

        // Initialize scrollspy
        this._initScrollspy(headingList);
    },

    /**
     * Scrollspy to highlight active ToC item on scroll.
     */
    _initScrollspy(headingList) {
        const mainContent = document.getElementById('main-content');
        if (!mainContent || !headingList.length) return;

        const onScroll = Utils.debounce(() => {
            const threshold = 140;
            let activeId = headingList[0].id;

            for (const h of headingList) {
                const rect = h.element.getBoundingClientRect();
                if (rect.top <= threshold) {
                    activeId = h.id;
                } else {
                    break;
                }
            }

            this._updateActiveTocLink(activeId);
        }, 40);

        mainContent.addEventListener('scroll', onScroll, { passive: true });
        this._scrollspyCleanup = () => {
            mainContent.removeEventListener('scroll', onScroll);
        };

        // Run once on init
        setTimeout(onScroll, 100);
    },

    _updateActiveTocLink(targetId) {
        const tocEl = document.getElementById('article-toc');
        if (!tocEl) return;

        const links = tocEl.querySelectorAll('.toc-link');
        links.forEach(link => {
            if (link.getAttribute('data-target-id') === targetId) {
                link.classList.add('active');
                const body = tocEl.querySelector('.toc-body');
                if (body) {
                    const top = link.offsetTop;
                    if (top < body.scrollTop || top > body.scrollTop + body.clientHeight) {
                        body.scrollTo({ top: Math.max(0, top - 30), behavior: 'smooth' });
                    }
                }
            } else {
                link.classList.remove('active');
            }
        });
    },
};