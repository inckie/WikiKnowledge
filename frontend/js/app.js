/**
 * WikiKnowledge — Main Application Controller
 * Hash-based routing, sidebar management, view switching.
 */

const App = {
    _articles: [],
    _currentView: 'welcome',
    _currentArticleId: null,

    /**
     * Initialize the application.
     */
    async init() {
        console.log('WikiKnowledge initializing...');

        // Initialize Theme & Mobile Navigation
        this._initTheme();
        this._initMobileSidebar();

        // Load initial data
        await this._loadArticles();

        // Bind navigation
        this._bindNav();
        this._bindActions();

        // Handle hash routing
        window.addEventListener('hashchange', () => this._route());
        this._route();

        // Load welcome stats
        this._loadWelcomeStats();
    },

    /**
     * Load article list and populate Viewer's known articles.
     */
    async _loadArticles() {
        try {
            this._articles = await API.fetchArticles();
            Viewer.setKnownArticles(this._articles);
        } catch (e) {
            console.error('Failed to load articles:', e);
            this._articles = [];
        }
    },

    /**
     * Hash-based router.
     */
    _route() {
        const hashContent = (window.location.hash || '#/').substring(2); // Remove '#/'
        const [path, queryString] = hashContent.split('?');
        
        const pathSegments = path.split('/');
        const route = pathSegments[0] || '';
        const param = pathSegments.slice(1).join('/');

        if (route === 'article' && param) {
            this._showArticle(decodeURIComponent(param));
        } else if (route === 'edit' && param) {
            this._showEditor(decodeURIComponent(param));
        } else if (route === 'new') {
            const urlParams = new URLSearchParams(queryString);
            const prefillId = urlParams.get('id');
            this._showNewEditor(prefillId);
        } else if (route === 'graph') {
            this._showGraph();
        } else if (route === 'settings') {
            this._showSettings();
        } else {
            this._showView('welcome');
        }
    },

    /**
     * Switch active view.
     */
    _showView(viewName) {
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        const el = document.getElementById(`view-${viewName}`);
        if (el) el.classList.add('active');
        this._currentView = viewName;

        if (viewName !== 'settings') {
            document.querySelectorAll('.theme-toggle-btn[title="AI Settings"]').forEach(b => b.classList.remove('active'));
        }

        // Close sidebar on mobile when navigating
        this.closeSidebar();
    },

    /**
     * Display an article.
     */
    async _showArticle(articleId) {
        this._showView('article');
        this._currentArticleId = articleId;

        // Highlight in sidebar
        this._highlightSidebarItem(articleId);

        try {
            const article = await API.fetchArticle(articleId);
            await Viewer.show(article);
            // Reset scroll position of the main content to top AFTER content is loaded
            // and the browser has had a chance to render it.
            requestAnimationFrame(() => {
                const mainContent = document.getElementById('main-content');
                if (mainContent) {
                    mainContent.scrollTo(0, 0);
                }
            });
        } catch (e) {
            document.getElementById('article-body').innerHTML =
                `<div style="color: var(--color-danger); padding: 2rem;">
                    <h2>Article Not Found</h2>
                    <p>${Utils.escapeHtml(e.message)}</p>
                    <button class="btn btn-primary" onclick="window.location.hash = '#/new?id=${encodeURIComponent(articleId)}'">
                        + Create Article "${Utils.escapeHtml(articleId)}"
                    </button>
                </div>`;
        }
    },

    /**
     * Open editor for existing article.
     */
    async _showEditor(articleId) {
        this._showView('editor');
        this._currentArticleId = articleId;
        await Editor.openEdit(articleId);
    },

    /**
     * Open editor for new article.
     */
    _showNewEditor(prefillId = null) {
        this._showView('editor');
        this._currentArticleId = null;
        Editor.openNew(prefillId);
    },

    /**
     * Show graph visualization.
     */
    async _showGraph() {
        this._showView('graph');
        // Update nav highlight
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.getElementById('nav-graph').classList.add('active');
        // Give DOM time to paint, then init graph
        requestAnimationFrame(() => Graph.init());
    },

    /**
     * Show AI settings view.
     */
    _showSettings() {
        this._showView('settings');
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.theme-toggle-btn[title="AI Settings"]').forEach(b => b.classList.add('active'));
        Settings.load();
    },

    /**
     * Bind sidebar navigation buttons.
     */
    _bindNav() {
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const view = btn.dataset.view;
                document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                if (view === 'graph') {
                    window.location.hash = '#/graph';
                    this._showGraph();
                } else {
                    this._loadSidebarContent(view);
                }
            });
        });

        const handleSettingsClick = () => {
            window.location.hash = '#/settings';
            this._showSettings();
        };
        const btnSettings = document.getElementById('btn-settings-toggle');
        const btnSettingsMobile = document.getElementById('btn-settings-toggle-mobile');
        if (btnSettings) btnSettings.addEventListener('click', handleSettingsClick);
        if (btnSettingsMobile) btnSettingsMobile.addEventListener('click', handleSettingsClick);

        // Initial sidebar load
        this._loadSidebarContent('articles');

        // Search
        const searchInput = document.getElementById('search-input');
        searchInput.addEventListener('input', Utils.debounce(async () => {
            const q = searchInput.value.trim();
            const resultsEl = document.getElementById('search-results');

            if (!q) {
                resultsEl.classList.add('hidden');
                return;
            }

            try {
                const results = await API.search(q);
                if (!results.length) {
                    resultsEl.innerHTML = '<div class="search-result-item" style="color:var(--text-muted)">No results</div>';
                } else {
                    resultsEl.innerHTML = results.map(r =>
                        `<div class="search-result-item" data-id="${Utils.escapeHtml(r.id)}">
                            <span class="type-badge ${r.type}">${r.type}</span>
                            ${Utils.escapeHtml(r.title)}
                        </div>`
                    ).join('');

                    resultsEl.querySelectorAll('.search-result-item[data-id]').forEach(el => {
                        el.addEventListener('click', () => {
                            window.location.hash = `#/article/${el.dataset.id}`;
                            searchInput.value = '';
                            resultsEl.classList.add('hidden');
                        });
                    });
                }
                resultsEl.classList.remove('hidden');
            } catch (e) {
                resultsEl.classList.add('hidden');
            }
        }, 250));

        // Hide search results on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.sidebar-search')) {
                document.getElementById('search-results').classList.add('hidden');
            }
        });
    },

    /**
     * Bind toolbar action buttons.
     */
    _bindActions() {
        // New article
        document.getElementById('btn-new-article').addEventListener('click', () => {
            window.location.hash = '#/new';
        });

        // Edit
        document.getElementById('btn-edit').addEventListener('click', () => {
            if (this._currentArticleId) {
                window.location.hash = `#/edit/${this._currentArticleId}`;
            }
        });

        // Delete
        document.getElementById('btn-delete').addEventListener('click', async () => {
            if (!this._currentArticleId) return;
            if (!confirm(`Delete "${this._currentArticleId}"? This cannot be undone.`)) return;

            try {
                await API.deleteArticle(this._currentArticleId);
                Utils.toast('Article deleted', 'success');
                await this._loadArticles();
                this._loadSidebarContent('articles');
                window.location.hash = '#/';
            } catch (e) {
                Utils.toast(`Delete failed: ${e.message}`, 'error');
            }
        });

        // Save
        document.getElementById('btn-save').addEventListener('click', async () => {
            const success = await Editor.save();
            if (success) {
                await this._loadArticles();
                this._loadSidebarContent('articles');
                const id = document.getElementById('meta-id').value.trim();
                window.location.hash = `#/article/${id}`;
            }
        });

        // Cancel
        document.getElementById('btn-cancel').addEventListener('click', () => {
            if (this._currentArticleId) {
                window.location.hash = `#/article/${this._currentArticleId}`;
            } else {
                window.location.hash = '#/';
            }
        });
    },

    /**
     * Load sidebar content based on selected nav.
     */
    async _loadSidebarContent(view) {
        const container = document.getElementById('sidebar-content');

        if (view === 'articles') {
            await this._loadArticles();
            container.innerHTML = this._articles.map(a =>
                `<div class="sidebar-list-item${this._currentArticleId === a.id ? ' active' : ''}"
                     data-id="${Utils.escapeHtml(a.id)}">
                    <span class="item-icon ${a.type}"></span>
                    <span class="item-title">${Utils.escapeHtml(a.title)}</span>
                </div>`
            ).join('');

            container.querySelectorAll('.sidebar-list-item').forEach(el => {
                el.addEventListener('click', () => {
                    window.location.hash = `#/article/${el.dataset.id}`;
                });
            });

        } else if (view === 'categories') {
            try {
                const tree = await API.fetchCategoryTree();
                container.innerHTML = this._renderCategoryTree(tree);
                this._bindCategoryTreeClicks(container);
            } catch (e) {
                container.innerHTML = '<div style="padding:1rem;color:var(--text-muted)">Failed to load categories</div>';
            }

        } else if (view === 'tags') {
            try {
                const tags = await API.fetchTags();
                container.innerHTML = `<div class="tag-cloud">${
                    tags.map(t =>
                        `<span class="tag-cloud-item" data-tag="${Utils.escapeHtml(t.name)}">
                            ${Utils.escapeHtml(t.name)}<span class="tag-count">${t.count}</span>
                        </span>`
                    ).join('')
                }</div>`;

                container.querySelectorAll('.tag-cloud-item').forEach(el => {
                    el.addEventListener('click', () => this.filterByTag(el.dataset.tag));
                });
            } catch (e) {
                container.innerHTML = '<div style="padding:1rem;color:var(--text-muted)">Failed to load tags</div>';
            }
        }
    },

    /**
     * Render category tree recursively.
     */
    _renderCategoryTree(tree) {
        if (!tree.length) return '<div style="padding:1rem;color:var(--text-muted)">No categories yet</div>';

        return tree.map(cat => {
            const articleCount = (cat.articles || []).length;
            const childCount = (cat.children || []).length;

            let html = `<div class="category-tree-item" data-id="${Utils.escapeHtml(cat.id)}">
                <span class="cat-icon">📂</span>${Utils.escapeHtml(cat.title)}
                <span class="member-count">${articleCount + childCount}</span>
            </div>`;

            const children = [];
            if (cat.children && cat.children.length) {
                children.push(this._renderCategoryTree(cat.children));
            }
            if (cat.articles && cat.articles.length) {
                children.push(cat.articles.map(a =>
                    `<div class="sidebar-list-item" data-id="${Utils.escapeHtml(a.id)}">
                        <span class="item-icon leaf"></span>
                        <span class="item-title">${Utils.escapeHtml(a.title)}</span>
                    </div>`
                ).join(''));
            }

            if (children.length) {
                html += `<div class="category-tree-children">${children.join('')}</div>`;
            }

            return html;
        }).join('');
    },

    _bindCategoryTreeClicks(container) {
        container.querySelectorAll('.category-tree-item, .sidebar-list-item').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                window.location.hash = `#/article/${el.dataset.id}`;
            });
        });
    },

    /**
     * Filter articles by tag.
     */
    async filterByTag(tag) {
        // Switch to articles view in sidebar with filter
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.getElementById('nav-articles').classList.add('active');

        try {
            const articles = await API.fetchArticles({ tag });
            const container = document.getElementById('sidebar-content');
            container.innerHTML = `
                <div style="padding: var(--space-2) var(--space-3); font-size: var(--text-xs); color: var(--text-muted);">
                    Filtered by tag: <span class="chip chip-tag">${Utils.escapeHtml(tag)}</span>
                    <span style="cursor:pointer;margin-left:8px;" onclick="App._loadSidebarContent('articles')">✕ Clear</span>
                </div>
            ` + articles.map(a =>
                `<div class="sidebar-list-item" data-id="${Utils.escapeHtml(a.id)}">
                    <span class="item-icon ${a.type}"></span>
                    <span class="item-title">${Utils.escapeHtml(a.title)}</span>
                </div>`
            ).join('');

            container.querySelectorAll('.sidebar-list-item').forEach(el => {
                el.addEventListener('click', () => {
                    window.location.hash = `#/article/${el.dataset.id}`;
                });
            });
        } catch (e) {
            Utils.toast('Failed to filter by tag', 'error');
        }
    },

    /**
     * Highlight a sidebar item.
     */
    _highlightSidebarItem(articleId) {
        document.querySelectorAll('.sidebar-list-item').forEach(el => {
            el.classList.toggle('active', el.dataset.id === articleId);
        });
    },

    /**
     * Load welcome screen stats.
     */
    async _loadWelcomeStats() {
        try {
            const [articles, tags, categories] = await Promise.all([
                API.fetchArticles(),
                API.fetchTags(),
                API.fetchCategories(),
            ]);

            document.getElementById('welcome-stats').innerHTML = `
                <div class="stat-card">
                    <div class="stat-value">${articles.length}</div>
                    <div class="stat-label">Articles</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${categories.length}</div>
                    <div class="stat-label">Categories</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${tags.length}</div>
                    <div class="stat-label">Tags</div>
                </div>
            `;
        } catch {
            // Silently ignore on welcome screen
        }
    },

    /**
     * Set up theme toggles and read preferences.
     */
    _initTheme() {
        this._updateThemeButtons();

        const toggleTheme = () => {
            const isLight = document.documentElement.classList.toggle('light-theme');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            this._updateThemeButtons();
            
            // Re-draw graph if active
            if (this._currentView === 'graph') {
                Graph.init();
            }
        };

        const btnDesktop = document.getElementById('btn-theme-toggle');
        if (btnDesktop) btnDesktop.addEventListener('click', toggleTheme);

        const btnMobile = document.getElementById('btn-theme-toggle-mobile');
        if (btnMobile) btnMobile.addEventListener('click', toggleTheme);
    },

    /**
     * Update labels and titles on theme buttons.
     */
    _updateThemeButtons() {
        const isLight = document.documentElement.classList.contains('light-theme');
        const icon = isLight ? '🌙' : '☀️';
        const text = isLight ? 'Dark Mode' : 'Light Mode';

        const btnDesktop = document.getElementById('btn-theme-toggle');
        if (btnDesktop) {
            btnDesktop.innerHTML = icon;
            btnDesktop.title = `Switch to ${text}`;
        }

        const btnMobile = document.getElementById('btn-theme-toggle-mobile');
        if (btnMobile) {
            btnMobile.innerHTML = icon;
            btnMobile.title = `Switch to ${text}`;
        }
    },

    /**
     * Initialize mobile hamburger menu and overlay.
     */
    _initMobileSidebar() {
        const toggleBtn = document.getElementById('btn-sidebar-toggle');
        const overlay = document.getElementById('sidebar-overlay');

        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                const sidebar = document.getElementById('sidebar');
                if (sidebar) sidebar.classList.toggle('open');
                if (overlay) overlay.classList.toggle('active');
            });
        }

        if (overlay) {
            overlay.addEventListener('click', () => {
                this.closeSidebar();
            });
        }
    },

    /**
     * Close the sidebar on mobile.
     */
    closeSidebar() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        if (sidebar) sidebar.classList.remove('open');
        if (overlay) overlay.classList.remove('active');
    },
};

// --- Bootstrap ---
document.addEventListener('DOMContentLoaded', () => App.init());