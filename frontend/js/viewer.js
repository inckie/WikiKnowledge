/**
 * WikiKnowledge — Markdown Viewer
 * Renders markdown with wiki-link resolution and human/AI block indicators.
 */

const Viewer = {
    /** All known article IDs (populated on init) */
    _knownArticles: new Set(),

    /**
     * Update the set of known article IDs for link resolution.
     */
    setKnownArticles(articles) {
        this._knownArticles = new Set(articles.map(a => a.id));
    },

    /**
     * Render markdown content to HTML with wiki-link support.
     * @param {string} markdown - Raw markdown content
     * @returns {string} HTML string
     */
    render(markdown) {
        if (!markdown) return '';

        // Pre-process: convert [[wiki-links]] to temporary placeholders
        let processed = this._processWikiLinks(markdown);

        // Pre-process: mark human/AI blocks
        processed = this._processContentBlocks(processed);

        // Render markdown
        return marked.parse(processed, {
            gfm: true,
            breaks: false,
        });
    },

    /**
     * Replace [[target]] and [[target|display]] with clickable HTML links.
     */
    _processWikiLinks(text) {
        return text.replace(/\[\[([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]/g, (match, targetId, displayText) => {
            targetId = targetId.trim();
            const display = displayText ? displayText.trim() : targetId;
            const exists = this._knownArticles.has(targetId);
            const cssClass = exists ? 'wiki-link' : 'wiki-link missing';
            return `<a class="${cssClass}" href="#/article/${encodeURIComponent(targetId)}" data-article-id="${Utils.escapeHtml(targetId)}">${Utils.escapeHtml(display)}</a>`;
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
        document.getElementById('article-body').innerHTML = this.render(article.content);

        // Render category-specific section or clear it
        const categorySectionEl = document.getElementById('category-section');
        if (article.type === 'category') {
            categorySectionEl.innerHTML = this._renderCategorySection(article);
        } else {
            categorySectionEl.innerHTML = '';
        }

        // Render backlinks for all article types
        await this._renderBacklinks(article);
    },

    _renderMeta(article) {
        const parts = [];
        parts.push(`<div class="meta-group"><span class="meta-label">Type</span><span class="chip chip-type">${article.type}</span></div>`);
        if (article.tags.length) {
            const tagChips = article.tags.map(t => `<span class="chip chip-tag" onclick="App.filterByTag('${Utils.escapeHtml(t)}')">${Utils.escapeHtml(t)}</span>`).join('');
            parts.push(`<div class="meta-divider"></div><div class="meta-group"><span class="meta-label">Tags</span>${tagChips}</div>`);
        }
        if (article.categories.length) {
            const catChips = article.categories.map(c => `<a class="chip chip-category" href="#/article/${encodeURIComponent(c)}">${Utils.escapeHtml(c)}</a>`).join('');
            parts.push(`<div class="meta-divider"></div><div class="meta-group"><span class="meta-label">Categories</span>${catChips}</div>`);
        }
        parts.push(`<div class="meta-divider"></div><div class="meta-group"><span class="meta-label">Modified</span><span style="font-size: var(--text-xs); color: var(--text-muted);">${Utils.formatDate(article.modified)}</span></div>`);
        return parts.join('');
    },

    _renderBreadcrumb(article) {
        const parts = [`<a href="#/">Home</a>`, `<span class="separator">›</span>`];
        if (article.categories.length) {
            const cat = article.categories[0];
            parts.push(`<a href="#/article/${encodeURIComponent(cat)}">${Utils.escapeHtml(cat)}</a>`);
            parts.push(`<span class="separator">›</span>`);
        }
        parts.push(`<span>${Utils.escapeHtml(article.title)}</span>`);
        return parts.join(' ');
    },

    _renderCategorySection(article) {
        const dirtyIndicator = article.is_dirty ?
            `<span class="dirty-indicator" title="This category might be outdated. One or more of its articles have been modified more recently than this overview.">⚠️</span>` :
            '';

        const subArticles = (article.sub_articles || []).map(sub => {
            const unmentionedClass = sub.is_unmentioned ? 'unmentioned' : '';
            const iconClass = sub.type === 'category' ? 'item-icon category' : 'item-icon';
            const newerIcon = sub.is_newer ? `<span class="newer-indicator" title="Modified more recently than the category article" style="margin-left: 6px; font-size: 0.9em; cursor: help;">✨</span>` : '';
            return `
                <div class="sub-article-item ${unmentionedClass}">
                    <span class="${iconClass}"></span>
                    <a href="#/article/${encodeURIComponent(sub.id)}">${Utils.escapeHtml(sub.title)}</a>
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

            if (!backlinks.length) {
                container.innerHTML = '';
                return;
            }

            const items = backlinks.map(bl => {
                const title = bl.source_title || bl.source_id;
                return `<a class="backlink-item" href="#/article/${encodeURIComponent(bl.source_id)}">
                    ← ${Utils.escapeHtml(title)}
                </a>`;
            }).join('');

            container.innerHTML = `
                <div class="backlinks-title">🔗 What Links Here (${backlinks.length})</div>
                <div>${items}</div>
            `;
        } catch (e) {
            container.innerHTML = '';
            console.error('Failed to render backlinks:', e);
        }
    },
};