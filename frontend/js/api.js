/**
 * WikiKnowledge — API Client
 */

const API = {
    BASE: '/api',

    async _fetch(path, options = {}) {
        const url = `${this.BASE}${path}`;
        const resp = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        if (resp.status === 204) return null;
        return resp.json();
    },

    // --- Articles ---

    async fetchArticles(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this._fetch(`/articles${query ? '?' + query : ''}`);
    },

    async fetchArticle(id) {
        return this._fetch(`/articles/${encodeURIComponent(id)}`);
    },

    async createArticle(data) {
        return this._fetch('/articles', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    async updateArticle(id, data) {
        return this._fetch(`/articles/${encodeURIComponent(id)}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    },

    async deleteArticle(id) {
        return this._fetch(`/articles/${encodeURIComponent(id)}`, {
            method: 'DELETE',
        });
    },

    async fetchBacklinks(id) {
        return this._fetch(`/articles/${encodeURIComponent(id)}/backlinks`);
    },

    // --- Search & Discovery ---

    async fetchTags() {
        return this._fetch('/tags');
    },

    async fetchCategories() {
        return this._fetch('/categories');
    },

    async search(query) {
        return this._fetch(`/search?q=${encodeURIComponent(query)}`);
    },

    // --- Graph ---

    async fetchGraph() {
        return this._fetch('/graph');
    },

    async fetchSubgraph(id, depth = 2) {
        return this._fetch(`/graph/${encodeURIComponent(id)}?depth=${depth}`);
    },

    async fetchCategoryTree() {
        return this._fetch('/graph/categories');
    },

    // --- Resources ---

    async fetchResources() {
        return this._fetch('/resources');
    },

    async fetchResource(id) {
        return this._fetch(`/resources/${encodeURIComponent(id)}`);
    },

    // --- AI Integration ---

    async getAISettings() {
        return this._fetch('/ai/settings');
    },

    async saveAISettings(data) {
        return this._fetch('/ai/settings', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    async fetchAIModels(url, apiKey) {
        return this._fetch('/ai/models', {
            method: 'POST',
            body: JSON.stringify({ url, api_key: apiKey }),
        });
    },

    async sendAIChat(prompt) {
        return this._fetch('/ai/chat', {
            method: 'POST',
            body: JSON.stringify({ prompt }),
        });
    },

    // --- Knowledge Sources ---

    async getSources() {
        return this._fetch('/sources');
    },

    async updateSourcePath(id, path) {
        return this._fetch(`/sources/${encodeURIComponent(id)}/path`, {
            method: 'PUT',
            body: JSON.stringify({ path }),
        });
    },

    async rescanSources() {
        return this._fetch('/sources/rescan', {
            method: 'POST',
        });
    }
};
