/**
 * WikiKnowledge — AI Settings Controller
 * Manages UI logic for configuring OpenAI API models and MCP binding.
 */

const Settings = {
    _initialized: false,

    init() {
        if (this._initialized) return;
        this._bindEvents();
        this._initialized = true;
    },

    async load() {
        this.init();
        const statusEl = document.getElementById('settings-status');
        if (statusEl) statusEl.classList.add('hidden');

        try {
            const settings = await API.getAISettings();
            const urlEl = document.getElementById('ai-url');
            const keyEl = document.getElementById('ai-api-key');
            const selectEl = document.getElementById('ai-model-select');
            const enabledEl = document.getElementById('ai-enabled');

            if (settings.url) urlEl.value = settings.url;
            if (settings.api_key) keyEl.value = settings.api_key;
            if (enabledEl) enabledEl.checked = settings.enabled !== false;

            if (settings.model) {
                // Ensure model option exists in dropdown
                if (!selectEl.querySelector(`option[value="${Utils.escapeHtml(settings.model)}"]`)) {
                    const opt = document.createElement('option');
                    opt.value = settings.model;
                    opt.textContent = settings.model;
                    selectEl.appendChild(opt);
                }
                selectEl.value = settings.model;
                selectEl.disabled = false;
            }

            this._checkInputState();
        } catch (e) {
            console.error('Failed to load AI settings:', e);
            Utils.toast('Failed to load AI settings', 'error');
        }
    },

    _bindEvents() {
        const urlEl = document.getElementById('ai-url');
        const keyEl = document.getElementById('ai-api-key');
        const fetchBtn = document.getElementById('btn-fetch-models');
        const saveBtn = document.getElementById('btn-save-settings');

        if (urlEl) urlEl.addEventListener('input', () => this._checkInputState());
        if (keyEl) keyEl.addEventListener('input', () => this._checkInputState());

        if (fetchBtn) {
            fetchBtn.addEventListener('click', () => this.fetchModels());
        }

        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveSettings());
        }
    },

    _checkInputState() {
        const url = (document.getElementById('ai-url')?.value || '').trim();
        const key = (document.getElementById('ai-api-key')?.value || '').trim();
        const fetchBtn = document.getElementById('btn-fetch-models');

        if (fetchBtn) {
            fetchBtn.disabled = !(url && key);
        }
    },

    async fetchModels() {
        const url = (document.getElementById('ai-url')?.value || '').trim();
        const key = (document.getElementById('ai-api-key')?.value || '').trim();
        const fetchBtn = document.getElementById('btn-fetch-models');
        const selectEl = document.getElementById('ai-model-select');
        const statusEl = document.getElementById('settings-status');

        if (!url || !key) return;

        const currentSelection = selectEl.value;
        fetchBtn.disabled = true;
        const originalText = fetchBtn.innerHTML;
        fetchBtn.innerHTML = '⏳ Fetching Models...';
        statusEl.classList.add('hidden');

        try {
            const resp = await API.fetchAIModels(url, key);
            const models = resp.models || [];

            if (!models.length) {
                this._showStatus('No models found at the specified endpoint.', 'warning');
                selectEl.innerHTML = '<option value="">No models available</option>';
                selectEl.disabled = true;
            } else {
                selectEl.innerHTML = '<option value="">Select a model...</option>' + models.map(m =>
                    `<option value="${Utils.escapeHtml(m)}">${Utils.escapeHtml(m)}</option>`
                ).join('');
                selectEl.disabled = false;
                if (currentSelection && models.includes(currentSelection)) {
                    selectEl.value = currentSelection;
                }
                this._showStatus(`Successfully fetched ${models.length} available models.`, 'success');
                Utils.toast('Models fetched successfully', 'success');
            }
        } catch (e) {
            this._showStatus(`Failed to fetch models: ${e.message}`, 'error');
            Utils.toast('Failed to fetch models', 'error');
            selectEl.innerHTML = '<option value="">Select a model...</option>';
            selectEl.disabled = true;
        } finally {
            fetchBtn.innerHTML = originalText;
            this._checkInputState();
        }
    },

    async saveSettings() {
        const url = (document.getElementById('ai-url')?.value || '').trim();
        const key = (document.getElementById('ai-api-key')?.value || '').trim();
        const model = (document.getElementById('ai-model-select')?.value || '').trim();
        const enabled = document.getElementById('ai-enabled')?.checked ?? true;
        const saveBtn = document.getElementById('btn-save-settings');

        saveBtn.disabled = true;
        const originalText = saveBtn.innerHTML;
        saveBtn.innerHTML = '💾 Saving...';

        try {
            await API.saveAISettings({ url, api_key: key, model, enabled });
            this._showStatus('AI settings saved successfully! Environment configured for integration.', 'success');
            Utils.toast('AI settings saved', 'success');
        } catch (e) {
            this._showStatus(`Failed to save settings: ${e.message}`, 'error');
            Utils.toast('Failed to save settings', 'error');
        } finally {
            saveBtn.innerHTML = originalText;
            saveBtn.disabled = false;
        }
    },

    _showStatus(message, type) {
        const statusEl = document.getElementById('settings-status');
        if (!statusEl) return;
        statusEl.className = `settings-status ${type}`;
        statusEl.innerHTML = Utils.escapeHtml(message);
        statusEl.classList.remove('hidden');
    }
};
