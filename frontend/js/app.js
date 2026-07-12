/**
 * WikiKnowledge — Main Application Controller
 * 
 * @wk-id wk/frontend-app
 * @wk-tags javascript, spa, frontend, routing
 * @wk-categories system-architecture
 *
 * SPA controller: hash-based routing, sidebar management, view switching.
 * Links to: [[fastapi-backend]], [[src:wikiknowledge/wk/markdown-viewer]], [[src:wikiknowledge/wk/graph-visualization]]
 */

const App = {
    _articles: [],
    _resources: [],
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

        // Initialize AI floating chat
        Chat.init();
    },

    /**
     * Load article list and populate Viewer's known articles.
     */
    async _loadArticles() {
        try {
            const [articles, resources] = await Promise.all([
                API.fetchArticles(),
                API.fetchResources().catch(() => []),
            ]);
            this._articles = articles;
            this._resources = resources;
            Viewer.setKnownArticles(this._articles);
            Viewer.setKnownResources(this._resources);
        } catch (e) {
            console.error('Failed to load articles:', e);
            this._articles = [];
            this._resources = [];
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

        // Always hide the drive metadata editor panel when switching articles
        this._closeDriveMetadataEditor();

        const isDrive = articleId.startsWith('gdrive:');
        const isSrc = articleId.startsWith('src:');
        const isVirtual = isDrive || isSrc;

        // Standard Edit/Delete only for local articles
        document.getElementById('btn-edit').style.display = isVirtual ? 'none' : '';
        const btnDelete = document.getElementById('btn-delete');
        btnDelete.style.display = isVirtual ? 'none' : '';
        delete btnDelete.dataset.isResource;

        // "Edit Metadata" only for bidirectional Drive sources
        const editMetaBtn = document.getElementById('btn-edit-metadata');
        editMetaBtn.style.display = 'none'; // hidden by default
        if (isDrive) {
            // Check if any Drive source is bidirectional (determines if we can edit)
            try {
                const sources = await API.getSources();
                const driveSource = sources.find(s => s.type === 'GoogleDrivePlugin' && s.bidirectional);
                if (driveSource) {
                    editMetaBtn.style.display = '';
                    editMetaBtn.dataset.sourceId = driveSource.id;
                }
            } catch (e) {
                // Silently ignore — button stays hidden
            }
        }

        // Highlight in sidebar
        this._highlightSidebarItem(articleId);

        try {
            let data;
            try {
                data = await API.fetchArticle(articleId);
            } catch (e) {
                // If article not found, try fetching as a resource
                try {
                    data = await API.fetchResource(articleId);
                    data.type = 'resource';
                } catch (resErr) {
                    // Try fallback matching with extension if omitted
                    const resources = await API.fetchResources().catch(() => []);
                    const found = resources.find(r => r.id.split('.')[0] === articleId.split('.')[0]);
                    if (found) {
                        data = await API.fetchResource(found.id);
                        data.type = 'resource';
                    } else {
                        throw e; // Throw original article not found error
                    }
                }
            }
            
            if (data.type === 'resource') {
                document.getElementById('btn-edit').style.display = 'none';
                btnDelete.style.display = '';
                btnDelete.dataset.isResource = 'true';
                editMetaBtn.style.display = '';
                delete editMetaBtn.dataset.sourceId;
                editMetaBtn.dataset.isResource = 'true';
            }
            
            await Viewer.show(data);
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

        // Upload Media
        const uploadModal = document.getElementById('upload-modal');
        document.getElementById('btn-upload-media').addEventListener('click', () => {
            uploadModal.classList.remove('hidden');
        });
        
        document.getElementById('btn-close-upload').addEventListener('click', () => {
            uploadModal.classList.add('hidden');
        });
        
        document.getElementById('upload-file').addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                const file = e.target.files[0];
                const name = file.name;
                const baseName = name.replace(/\.[^/.]+$/, ""); // Strip extension
                
                // Auto-fill ID and Title if empty
                const idInput = document.getElementById('upload-id');
                const titleInput = document.getElementById('upload-title');
                
                if (!idInput.value) idInput.value = baseName.toLowerCase().replace(/[^a-z0-9_-]/g, '-');
                if (!titleInput.value) titleInput.value = baseName;
            }
        });
        
        document.getElementById('btn-submit-upload').addEventListener('click', async () => {
            const fileInput = document.getElementById('upload-file');
            const idInput = document.getElementById('upload-id');
            const titleInput = document.getElementById('upload-title');
            
            if (!fileInput.files.length) return Utils.toast('Please select a file', 'error');
            if (!idInput.value) return Utils.toast('Please provide a resource ID', 'error');
            if (!titleInput.value) return Utils.toast('Please provide a title', 'error');
            
            const btn = document.getElementById('btn-submit-upload');
            btn.disabled = true;
            btn.textContent = 'Uploading...';
            
            try {
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('resource_id', idInput.value);
                formData.append('title', titleInput.value);
                formData.append('description', document.getElementById('upload-description').value);
                formData.append('tags', document.getElementById('upload-tags').value);
                formData.append('categories', document.getElementById('upload-categories').value);
                formData.append('related', '');
                
                const result = await API.uploadResource(formData);
                Utils.toast(`Uploaded successfully! Embed with [[file:${result.id}]]`, 'success');
                
                uploadModal.classList.add('hidden');
                
                // Reset form
                fileInput.value = '';
                idInput.value = '';
                titleInput.value = '';
                document.getElementById('upload-description').value = '';
                document.getElementById('upload-tags').value = '';
                document.getElementById('upload-categories').value = '';
            } catch (e) {
                Utils.toast(`Upload failed: ${e.message}`, 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Upload';
            }
        });

        // Edit Metadata (Google Drive articles only — bidirectional sources OR local resources)
        document.getElementById('btn-edit-metadata').addEventListener('click', async () => {
            if (!this._currentArticleId) return;
            const editorEl = document.getElementById('drive-metadata-editor');
            if (!editorEl.classList.contains('hidden')) {
                // Toggle close if already open
                this._closeDriveMetadataEditor();
                return;
            }
            const sourceId = document.getElementById('btn-edit-metadata').dataset.sourceId;
            const isResource = document.getElementById('btn-edit-metadata').dataset.isResource === 'true';
            
            if (!sourceId && !isResource) return;
            try {
                let item;
                if (isResource) {
                    item = await API.fetchResource(this._currentArticleId);
                    item.type = 'resource';
                } else {
                    item = await API.fetchArticle(this._currentArticleId);
                }
                this._openDriveMetadataEditor(item, sourceId, isResource);
            } catch (e) {
                Utils.toast(`Failed to load item: ${e.message}`, 'error');
            }
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

            const isResource = document.getElementById('btn-delete').dataset.isResource === 'true';

            try {
                if (isResource) {
                    await API.deleteResource(this._currentArticleId);
                    Utils.toast('Resource deleted', 'success');
                } else {
                    await API.deleteArticle(this._currentArticleId);
                    Utils.toast('Article deleted', 'success');
                }
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
            
            const sortedArticles = [...this._articles].sort((a, b) => 
                (a.title || a.id).localeCompare(b.title || b.id)
            );
            
            container.innerHTML = sortedArticles.map(a => {
                const isSourceCode = a.id.startsWith('src:');
                const isDrive = a.id.startsWith('gdrive:');
                let externalIcon = '';
                if (isDrive) {
                    externalIcon = '<span class="source-badge drive" title="Google Drive">Drive</span>';
                } else if (isSourceCode) {
                    externalIcon = '<span class="source-badge code" title="Source Code">Code</span>';
                }
                return `<div class="sidebar-list-item${this._currentArticleId === a.id ? ' active' : ''}"
                     data-id="${Utils.escapeHtml(a.id)}">
                    <span class="item-icon ${a.type}"></span>
                    <span class="item-title">${externalIcon}${Utils.escapeHtml(a.title)}</span>
                </div>`;
            }).join('');

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
     * Open the inline metadata editor for a Google Drive article or local resource.
     * @param {Object} article - Full article or resource object
     * @param {string} sourceId - The source name (from btn-edit-metadata dataset, null if resource)
     * @param {boolean} isResource - True if editing a local resource
     */
    _openDriveMetadataEditor(article, sourceId, isResource = false) {
        const editorEl = document.getElementById('drive-metadata-editor');

        editorEl.innerHTML = `
            <div class="drive-meta-editor-inner">
                <div class="drive-meta-editor-title">🏷️ Edit Metadata</div>
                <div class="drive-meta-field">
                    <label>Tags</label>
                    <div id="drive-meta-tags" class="chip-input-container"></div>
                </div>
                <div class="drive-meta-field">
                    <label>Categories</label>
                    <div id="drive-meta-categories" class="chip-input-container"></div>
                </div>
                <div class="drive-meta-actions">
                    <button id="btn-drive-meta-save" class="btn btn-primary">💾 Save</button>
                    <button id="btn-drive-meta-cancel" class="btn btn-ghost">Cancel</button>
                </div>
            </div>
        `;

        editorEl.classList.remove('hidden');

        // Initialize ChipInputs
        const tagInput = new ChipInput(document.getElementById('drive-meta-tags'), {
            type: 'tag',
            placeholder: 'Add tag...',
            fetchSuggestions: async (query) => {
                try {
                    const tags = await API.fetchTags();
                    return tags.map(t => t.name).filter(n => n.toLowerCase().includes(query.toLowerCase()));
                } catch { return []; }
            },
        });
        tagInput.setChips(article.tags || []);

        const catInput = new ChipInput(document.getElementById('drive-meta-categories'), {
            type: 'category',
            placeholder: 'Add category...',
            fetchSuggestions: async (query) => {
                try {
                    const cats = await API.fetchCategories();
                    return cats.map(c => c.id).filter(id => id.toLowerCase().includes(query.toLowerCase()));
                } catch { return []; }
            },
        });
        catInput.setChips(article.categories || []);

        // Save handler
        document.getElementById('btn-drive-meta-save').addEventListener('click', async () => {
            const tags = tagInput.getChips();
            const categories = catInput.getChips();
            const articleId = this._currentArticleId;

            try {
                if (isResource) {
                    await API.updateResourceMetadata(articleId, { tags, categories });
                } else {
                    await API.updateDriveArticleMetadata(sourceId, articleId, tags, categories);
                }
                Utils.toast('Metadata saved!', 'success');
                this._closeDriveMetadataEditor();
                // Refresh the article view to show updated tags/categories
                let updated;
                if (isResource) {
                    updated = await API.fetchResource(articleId);
                    updated.type = 'resource';
                } else {
                    updated = await API.fetchArticle(articleId);
                }
                await Viewer.show(updated);
                // Reload article list to reflect category changes in sidebar
                await this._loadArticles();
                this._loadSidebarContent('articles');
            } catch (e) {
                Utils.toast(`Save failed: ${e.message}`, 'error');
            }
        });

        // Cancel handler
        document.getElementById('btn-drive-meta-cancel').addEventListener('click', () => {
            this._closeDriveMetadataEditor();
        });
    },

    /**
     * Close / hide the inline Drive metadata editor.
     */
    _closeDriveMetadataEditor() {
        const editorEl = document.getElementById('drive-metadata-editor');
        editorEl.classList.add('hidden');
        editorEl.innerHTML = '';
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
            const [articles, tags, categories, resources] = await Promise.all([
                API.fetchArticles(),
                API.fetchTags(),
                API.fetchCategories(),
                API.fetchResources().catch(() => []),
            ]);

            const externalCount = articles.filter(a => a.id.startsWith('src:') || a.id.startsWith('gdrive:')).length;

            document.getElementById('welcome-stats').innerHTML = `
                <div class="stat-card">
                    <div class="stat-value">${articles.length}</div>
                    <div class="stat-label">Articles</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: var(--accent-color);">${externalCount}</div>
                    <div class="stat-label">Ext Sources</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${categories.length}</div>
                    <div class="stat-label">Categories</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${tags.length}</div>
                    <div class="stat-label">Tags</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${resources.length}</div>
                    <div class="stat-label">Media</div>
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