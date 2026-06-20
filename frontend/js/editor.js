/**
 * WikiKnowledge — Markdown Editor
 * Split-pane editor with metadata panel, live preview, and wiki-link autocomplete.
 */

const Editor = {
    _tagInput: null,
    _categoryInput: null,
    _currentArticleId: null,
    _isNew: false,

    /**
     * Open the editor for a new article.
     */
    openNew(prefillId = null) {
        this._isNew = true;
        this._currentArticleId = null;

        document.getElementById('editor-title-label').textContent = 'New Article';

        const initialArticle = {
            id: prefillId || '',
            title: prefillId ? Utils.unslugify(prefillId) : '', // Convert slug back to title
            type: 'leaf',
            tags: [],
            categories: [],
        };

        this._renderMetaPanel(initialArticle);

        // If prefillId is provided, mark the ID input as manual to prevent auto-slugification
        if (prefillId) {
            const idInput = document.getElementById('meta-id');
            if (idInput) {
                idInput.dataset.manual = 'true';
            }
        }

        document.getElementById('editor-content').value = '';
        document.getElementById('editor-preview').innerHTML = '';

        this._bindPreview();
    },

    /**
     * Open the editor for an existing article.
     */
    async openEdit(articleId) {
        this._isNew = false;
        this._currentArticleId = articleId;

        try {
            const article = await API.fetchArticle(articleId);
            document.getElementById('editor-title-label').textContent = `Edit: ${article.title}`;

            this._renderMetaPanel(article);

            const textarea = document.getElementById('editor-content');
            textarea.value = article.content;

            // Trigger preview
            document.getElementById('editor-preview').innerHTML = Viewer.render(article.content);

            this._bindPreview();
        } catch (e) {
            Utils.toast(`Failed to load article: ${e.message}`, 'error');
        }
    },

    /**
     * Render the metadata editing panel.
     */
    _renderMetaPanel(article) {
        const metaEl = document.getElementById('editor-meta');
        metaEl.innerHTML = `
            <div class="meta-field">
                <label for="meta-id">ID (slug)</label>
                <input type="text" id="meta-id" value="${Utils.escapeHtml(article.id)}"
                    placeholder="my-article-slug" ${this._isNew ? '' : 'disabled'}>
            </div>
            <div class="meta-field">
                <label for="meta-title">Title</label>
                <input type="text" id="meta-title" value="${Utils.escapeHtml(article.title)}"
                    placeholder="Article Title">
            </div>
            <div class="meta-field">
                <label for="meta-type">Type</label>
                <select id="meta-type">
                    <option value="leaf" ${article.type === 'leaf' ? 'selected' : ''}>Leaf Article</option>
                    <option value="category" ${article.type === 'category' ? 'selected' : ''}>Category</option>
                </select>
            </div>
            <div class="meta-field">
                <label>Tags</label>
                <div id="meta-tags"></div>
            </div>
            <div class="meta-field">
                <label>Categories</label>
                <div id="meta-categories"></div>
            </div>
        `;

        // Auto-generate ID from title for new articles
        if (this._isNew) {
            const titleInput = document.getElementById('meta-title');
            const idInput = document.getElementById('meta-id');
            titleInput.addEventListener('input', () => {
                if (!idInput.dataset.manual) {
                    idInput.value = Utils.slugify(titleInput.value);
                }
            });
            idInput.addEventListener('input', () => {
                idInput.dataset.manual = 'true';
            });
        }

        // Initialize chip inputs
        this._tagInput = new ChipInput(document.getElementById('meta-tags'), {
            type: 'tag',
            placeholder: 'Add tag...',
            fetchSuggestions: async (query) => {
                try {
                    const tags = await API.fetchTags();
                    return tags
                        .map(t => t.name)
                        .filter(n => n.toLowerCase().includes(query.toLowerCase()));
                } catch {
                    return [];
                }
            },
        });
        this._tagInput.setChips(article.tags || []);

        this._categoryInput = new ChipInput(document.getElementById('meta-categories'), {
            type: 'category',
            placeholder: 'Add category...',
            fetchSuggestions: async (query) => {
                try {
                    const categories = await API.fetchCategories();
                    return categories
                        .map(c => c.id)
                        .filter(id => id.toLowerCase().includes(query.toLowerCase()));
                } catch {
                    return [];
                }
            },
        });
        this._categoryInput.setChips(article.categories || []);
    },

    /**
     * Bind live preview updates.
     */
    _bindPreview() {
        const textarea = document.getElementById('editor-content');
        const preview = document.getElementById('editor-preview');

        const updatePreview = Utils.debounce(() => {
            preview.innerHTML = Viewer.render(textarea.value);
        }, 300);

        textarea.removeEventListener('input', textarea._previewHandler);
        textarea._previewHandler = updatePreview;
        textarea.addEventListener('input', updatePreview);

        // Wiki-link autocomplete on [[
        textarea.removeEventListener('input', textarea._autocompleteHandler);
        textarea._autocompleteHandler = (e) => this._handleWikiAutocomplete(textarea);
        textarea.addEventListener('input', textarea._autocompleteHandler);
    },

    /**
     * Handle [[ autocomplete in the textarea.
     */
    _handleWikiAutocomplete(textarea) {
        const pos = textarea.selectionStart;
        const text = textarea.value.substring(0, pos);

        // Check if we're inside a [[ that hasn't been closed
        const lastOpen = text.lastIndexOf('[[');
        const lastClose = text.lastIndexOf(']]');

        if (lastOpen > lastClose && lastOpen >= 0) {
            const query = text.substring(lastOpen + 2);
            if (query.length >= 1 && !query.includes('\n')) {
                this._showWikiAutocomplete(textarea, query, lastOpen + 2);
                return;
            }
        }

        this._hideWikiAutocomplete();
    },

    async _showWikiAutocomplete(textarea, query, insertPos) {
        try {
            const articles = await API.fetchArticles();
            const matches = articles.filter(a =>
                a.id.toLowerCase().includes(query.toLowerCase()) ||
                a.title.toLowerCase().includes(query.toLowerCase())
            ).slice(0, 8);

            if (!matches.length) {
                this._hideWikiAutocomplete();
                return;
            }

            const dropdown = document.getElementById('autocomplete-dropdown');
            dropdown.innerHTML = matches
                .map(a => `<div class="autocomplete-item" data-id="${Utils.escapeHtml(a.id)}" data-title="${Utils.escapeHtml(a.title)}">
                    <span class="type-badge ${a.type}">${a.type}</span> ${Utils.escapeHtml(a.title)} <span style="opacity:0.5">(${Utils.escapeHtml(a.id)})</span>
                </div>`)
                .join('');

            // Position near caret (approximate)
            const rect = textarea.getBoundingClientRect();
            dropdown.style.top = `${rect.top + 60}px`;
            dropdown.style.left = `${rect.left + 20}px`;
            dropdown.style.width = '350px';
            dropdown.classList.remove('hidden');

            dropdown.querySelectorAll('.autocomplete-item').forEach(el => {
                el.addEventListener('click', () => {
                    const id = el.dataset.id;
                    const before = textarea.value.substring(0, insertPos);
                    const after = textarea.value.substring(textarea.selectionStart);
                    textarea.value = before + id + ']]' + after;
                    textarea.selectionStart = textarea.selectionEnd = insertPos + id.length + 2;
                    textarea.focus();
                    this._hideWikiAutocomplete();
                    // Trigger preview update
                    textarea.dispatchEvent(new Event('input'));
                });
            });
        } catch {
            this._hideWikiAutocomplete();
        }
    },

    _hideWikiAutocomplete() {
        document.getElementById('autocomplete-dropdown')?.classList.add('hidden');
    },

    /**
     * Save the current article.
     * @returns {boolean} Success
     */
    async save() {
        const id = document.getElementById('meta-id').value.trim();
        const title = document.getElementById('meta-title').value.trim();
        const type = document.getElementById('meta-type').value;
        const content = document.getElementById('editor-content').value;
        const tags = this._tagInput.getChips();
        const categories = this._categoryInput.getChips();

        if (!id) {
            Utils.toast('Article ID is required', 'error');
            return false;
        }
        if (!title) {
            Utils.toast('Title is required', 'error');
            return false;
        }

        try {
            if (this._isNew) {
                await API.createArticle({ id, title, type, tags, categories, content });
                Utils.toast(`Created "${title}"`, 'success');
            } else {
                await API.updateArticle(this._currentArticleId, { title, type, tags, categories, content });
                Utils.toast(`Saved "${title}"`, 'success');
            }
            return true;
        } catch (e) {
            Utils.toast(`Save failed: ${e.message}`, 'error');
            return false;
        }
    },
};