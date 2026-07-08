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

        await this.loadSources();
    },

    _bindEvents() {
        const urlEl = document.getElementById('ai-url');
        const keyEl = document.getElementById('ai-api-key');
        const fetchBtn = document.getElementById('btn-fetch-models');
        const saveBtn = document.getElementById('btn-save-settings');
        const rescanBtn = document.getElementById('btn-rescan-sources');

        if (urlEl) urlEl.addEventListener('input', () => this._checkInputState());
        if (keyEl) keyEl.addEventListener('input', () => this._checkInputState());

        if (fetchBtn) {
            fetchBtn.addEventListener('click', () => this.fetchModels());
        }

        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveSettings());
        }

        if (rescanBtn) {
            rescanBtn.addEventListener('click', () => this.rescanSources());
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
    },

    // --- Knowledge Sources UI ---

    async loadSources() {
        const container = document.getElementById('sources-container');
        if (!container) return;
        
        try {
            const sources = await API.getSources();
            
            if (!sources || sources.length === 0) {
                container.innerHTML = '<div class="empty-state">No configured sources found.</div>';
                return;
            }

            container.innerHTML = sources.map(source => {
                const isDrive = source.type === 'GoogleDrivePlugin';
                const isAvailable = source.available;
                const statusPill = isAvailable
                    ? '<span class="source-status-pill connected">● Connected</span>'
                    : '<span class="source-status-pill disconnected">⊘ Disconnected</span>';

                if (isDrive) {
                    const lastSync = source.last_sync
                        ? new Date(source.last_sync).toLocaleString()
                        : 'Never synced';
                    const articleCount = source.article_count ?? 0;
                    const syncStatus = source.sync_status;
                    const syncStatusBadge = syncStatus === 'success'
                        ? '<span class="source-sync-badge ok">✓ Success</span>'
                        : syncStatus === 'partial'
                            ? '<span class="source-sync-badge warn">⚠ Partial</span>'
                            : '';
                    const biDir = source.bidirectional
                        ? '<span class="source-feature-tag">↔ Bidirectional</span>'
                        : '<span class="source-feature-tag readonly">→ Read-only</span>';

                    return `
                        <div class="source-card drive-source">
                            <div class="source-card-header">
                                <div class="source-card-icon">🗂️</div>
                                <div class="source-card-meta">
                                    <div class="source-card-title">
                                        <strong>${Utils.escapeHtml(source.id)}</strong>
                                        ${statusPill}
                                    </div>
                                    <div class="source-card-subtitle">Google Drive · Folder: <code>${Utils.escapeHtml(source.folder_id || '—')}</code></div>
                                </div>
                            </div>
                            <div class="source-card-stats">
                                <div class="source-stat">
                                    <span class="source-stat-value">${articleCount}</span>
                                    <span class="source-stat-label">Documents</span>
                                </div>
                                <div class="source-stat">
                                    <span class="source-stat-value" style="font-size:0.75rem;">${Utils.escapeHtml(lastSync)}</span>
                                    <span class="source-stat-label">Last Sync ${syncStatusBadge}</span>
                                </div>
                                <div class="source-stat">
                                    ${biDir}
                                </div>
                            </div>
                            <div class="source-card-actions">
                                <button class="btn btn-sm" 
                                    id="btn-sync-${Utils.escapeHtml(source.id)}"
                                    onclick="Settings.syncDriveSource('${Utils.escapeHtml(source.id)}')"
                                    ${isAvailable ? '' : 'disabled'}>
                                    🔄 Sync Now
                                </button>
                            </div>
                        </div>`;
                }

                // Source-code source card
                return `
                    <div class="source-card">
                        <div class="source-card-header">
                            <div class="source-card-icon">📂</div>
                            <div class="source-card-meta">
                                <div class="source-card-title">
                                    <strong>${Utils.escapeHtml(source.id)}</strong>
                                    ${statusPill}
                                </div>
                                <div class="source-card-subtitle">Source Code · ${Utils.escapeHtml(source.path || 'path not set')}</div>
                            </div>
                        </div>
                        <div class="source-card-path-row">
                            <input type="text" class="form-control" id="src-path-${Utils.escapeHtml(source.id)}"
                                value="${Utils.escapeHtml(source.path || '')}" placeholder="Local absolute path override">
                            <button class="btn btn-sm" onclick="Settings.updateSourcePath('${Utils.escapeHtml(source.id)}')">Update Path</button>
                        </div>
                    </div>`;
            }).join('');
        } catch (e) {
            container.innerHTML = '<div class="empty-state">Error loading sources.</div>';
            console.error('Failed to load sources:', e);
        }
    },

    async syncDriveSource(sourceId) {
        const btn = document.getElementById(`btn-sync-${sourceId}`);
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '⏳ Syncing...';
        }
        try {
            const resp = await API.rescanSources();
            const result = resp.sync_results?.[sourceId];
            if (result?.error) {
                Utils.toast(`Sync failed: ${result.error}`, 'error');
            } else if (result) {
                const { new: n = 0, updated: u = 0, deleted: d = 0, failed: f = 0 } = result;
                Utils.toast(`Synced "${sourceId}": +${n} new · ${u} updated · ${d} removed${f ? ` · ${f} failed` : ''}`, 'success');
            } else {
                Utils.toast(`Sync complete for "${sourceId}"`, 'success');
            }
            await this.loadSources();
        } catch (e) {
            Utils.toast(`Sync failed: ${e.message}`, 'error');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '🔄 Sync Now';
            }
        }
    },

    async updateSourcePath(id) {
        const pathInput = document.getElementById(`src-path-${id}`);
        if (!pathInput) return;

        const path = pathInput.value.trim();
        try {
            await API.updateSourcePath(id, path);
            Utils.toast(`Source path updated for ${id}`, 'success');
            await this.loadSources();
        } catch (e) {
            Utils.toast(`Failed to update path: ${e.message}`, 'error');
        }
    },

    async rescanSources() {
        const btn = document.getElementById('btn-rescan-sources');
        if (!btn) return;

        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '🔄 Scanning...';

        try {
            const resp = await API.rescanSources();
            const syncResults = resp.sync_results || {};
            const driveNames = Object.keys(syncResults);
            let msg = `Rescanned. Found ${resp.virtual_articles_discovered} virtual articles.`;
            if (driveNames.length) {
                const parts = driveNames.map(name => {
                    const r = syncResults[name];
                    if (r.error) return `${name}: error`;
                    return `${name}: +${r.new ?? 0} new, ${r.updated ?? 0} updated`;
                });
                msg += ` Drive: ${parts.join(' | ')}`;
            }
            Utils.toast(msg, 'success');
            await this.loadSources();
        } catch (e) {
            Utils.toast(`Failed to rescan sources: ${e.message}`, 'error');
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }
};
