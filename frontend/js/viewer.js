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
        // before marked.js processes the markdown
        let processed = this._processWikiLinks(markdown);

        // Pre-process: mark human/AI blocks
        processed = this._processContentBlocks(processed);

        // Render markdown
        const html = marked.parse(processed, {
            gfm: true,
            breaks: false,
        });

        return html;
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
        // Replace human blocks
        text = text.replace(
            /<!--\s*human:start\s*-->([\s\S]*?)<!--\s*human:end\s*-->/gi,
            '<div class="block-human"><span class="block-badge human">✍️ Human</span>\n$1</div>'
        );

        // Replace AI blocks
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
        // Render metadata chips
        const metaEl = document.getElementById('article-meta');
        metaEl.innerHTML = this._renderMeta(article);

        // Render breadcrumb
        const breadcrumb = document.getElementById('article-breadcrumb');
        breadcrumb.innerHTML = this._renderBreadcrumb(article);

        // Render body
        const bodyEl = document.getElementById('article-body');
        bodyEl.innerHTML = this.render(article.content);

        // Render backlinks
        await this._renderBacklinks(article.id);
    },

    _renderMeta(article) {
        const parts = [];

        // Type badge
        parts.push(`<div class="meta-group">
            <span class="meta-label">Type</span>
            <span class="chip chip-type">${article.type}</span>
        </div>`);

        // Tags
        if (article.tags.length) {
            const tagChips = article.tags
                .map(t => `<span class="chip chip-tag" onclick="App.filterByTag('${Utils.escapeHtml(t)}')">${Utils.escapeHtml(t)}</span>`)
                .join('');
            parts.push(`<div class="meta-divider"></div><div class="meta-group">
                <span class="meta-label">Tags</span>${tagChips}
            </div>`);
        }

        // Categories
        if (article.categories.length) {
            const catChips = article.categories
                .map(c => `<a class="chip chip-category" href="#/article/${encodeURIComponent(c)}">${Utils.escapeHtml(c)}</a>`)
                .join('');
            parts.push(`<div class="meta-divider"></div><div class="meta-group">
                <span class="meta-label">Categories</span>${catChips}
            </div>`);
        }

        // Modified date
        parts.push(`<div class="meta-divider"></div><div class="meta-group">
            <span class="meta-label">Modified</span>
            <span style="font-size: var(--text-xs); color: var(--text-muted);">${Utils.formatDate(article.modified)}</span>
        </div>`);

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

    async _renderBacklinks(articleId) {
        const container = document.getElementById('article-backlinks');
        try {
            const backlinks = await API.fetchBacklinks(articleId);
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
        }
    },
};
