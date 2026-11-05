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
        await this.loadEmbeddingSettings();
        await this.loadStats();
    },

    _bindEvents() {
        const urlEl = document.getElementById('ai-url');
        const keyEl = document.getElementById('ai-api-key');
        const fetchBtn = document.getElementById('btn-fetch-models');
        const saveBtn = document.getElementById('btn-save-settings');
        const rescanBtn = document.getElementById('btn-rescan-sources');
        const embeddingToggle = document.getElementById('embedding-enabled');
        const rebuildEmbeddingBtn = document.getElementById('btn-rebuild-embeddings');
        const refreshStatsBtn = document.getElementById('btn-refresh-stats');
        const toggleBrokenBtn = document.getElementById('btn-toggle-broken-links');
        const toggleOrphansBtn = document.getElementById('btn-toggle-orphans');

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

        if (embeddingToggle) {
            embeddingToggle.addEventListener('change', (e) => this.saveEmbeddingToggle(e.target.checked));
        }

        if (rebuildEmbeddingBtn) {
            rebuildEmbeddingBtn.addEventListener('click', () => this.rebuildEmbeddingIndex());
        }

        if (refreshStatsBtn) {
            refreshStatsBtn.addEventListener('click', () => this.loadStats());
        }

        if (toggleBrokenBtn) {
            toggleBrokenBtn.addEventListener('click', () => this.toggleAccordion('broken-links'));
        }

        if (toggleOrphansBtn) {
            toggleOrphansBtn.addEventListener('click', () => this.toggleAccordion('orphans'));
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

                // Source-code or markdown-files source card
                const isMarkdown = source.type === 'MarkdownFilesPlugin';
                const typeLabel = isMarkdown ? 'Markdown Files' : 'Source Code';
                const typeIcon = isMarkdown ? '📝' : '📂';

                return `
                    <div class="source-card">
                        <div class="source-card-header">
                            <div class="source-card-icon">${typeIcon}</div>
                            <div class="source-card-meta">
                                <div class="source-card-title">
                                    <strong>${Utils.escapeHtml(source.id)}</strong>
                                    ${statusPill}
                                </div>
                                <div class="source-card-subtitle">${typeLabel} · ${Utils.escapeHtml(source.path || 'path not set')}</div>
                            </div>
                        </div>
                        <div class="source-card-path-row">
                            <input type="text" class="form-control" id="src-path-${Utils.escapeHtml(source.id)}"
                                value="${Utils.escapeHtml(source.path || '')}" placeholder="Local absolute path override"
                                onkeydown="if (event.key === 'Enter') Settings.updateSourcePath('${Utils.escapeHtml(source.id)}')">
                            <button id="btn-update-path-${Utils.escapeHtml(source.id)}" class="btn btn-sm"
                                onclick="Settings.updateSourcePath('${Utils.escapeHtml(source.id)}')">Update Path</button>
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
                const dur = result.duration_seconds !== undefined ? ` (${result.duration_seconds}s)` : '';
                Utils.toast(`Sync failed${dur}: ${result.error}`, 'error');
            } else if (result) {
                const { new: n = 0, updated: u = 0, deleted: d = 0, failed: f = 0, duration_seconds: dur } = result;
                const durStr = dur !== undefined ? ` in ${dur}s` : '';
                Utils.toast(`Synced "${sourceId}"${durStr}: +${n} new · ${u} updated · ${d} removed${f ? ` · ${f} failed` : ''}`, 'success');
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

        const btn = document.getElementById(`btn-update-path-${id}`);
        const originalText = btn ? btn.innerHTML : 'Update Path';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '⏳ Updating...';
        }
        pathInput.disabled = true;

        const path = pathInput.value.trim();
        try {
            await API.updateSourcePath(id, path);
            Utils.toast(`Source path updated for ${id}`, 'success');
            await this.loadSources();
        } catch (e) {
            Utils.toast(`Failed to update path: ${e.message}`, 'error');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
            pathInput.disabled = false;
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
            const durStr = resp.duration_seconds !== undefined ? ` in ${resp.duration_seconds}s` : '';
            let msg = `Rescanned${durStr}. Found ${resp.virtual_articles_discovered} virtual articles.`;
            if (driveNames.length) {
                const parts = driveNames.map(name => {
                    const r = syncResults[name];
                    const rDur = r.duration_seconds !== undefined ? ` (${r.duration_seconds}s)` : '';
                    if (r.error) return `${name}: error${rDur}`;
                    return `${name}: +${r.new ?? 0} new, ${r.updated ?? 0} updated${rDur}`;
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
    },

    // --- Embedding Search UI ---

    _embeddingPollTimer: null,

    async loadEmbeddingSettings() {
        const toggleEl = document.getElementById('embedding-enabled');
        if (!toggleEl) return;

        try {
            const data = await API.getEmbeddingSettings();
            toggleEl.checked = !!data.enabled;
            this.updateEmbeddingStatusUI(data);

            if (data.status === 'indexing') {
                this._startEmbeddingPolling();
            }
        } catch (e) {
            console.error('Failed to load embedding settings:', e);
        }
    },

    updateEmbeddingStatusUI(data) {
        const badgeEl = document.getElementById('embedding-status-badge');
        const statsEl = document.getElementById('embedding-stats');
        const errorEl = document.getElementById('embedding-status-message');
        const rebuildBtn = document.getElementById('btn-rebuild-embeddings');

        if (!badgeEl) return;

        if (!data.enabled) {
            badgeEl.textContent = 'Disabled';
            badgeEl.className = 'source-badge';
            badgeEl.style.background = 'var(--bg-hover)';
            badgeEl.style.color = 'var(--text-muted)';
            badgeEl.style.borderColor = 'var(--border-color)';
        } else if (data.status === 'indexing') {
            badgeEl.textContent = '⏳ Indexing...';
            badgeEl.className = 'source-badge';
            badgeEl.style.background = 'rgba(245, 158, 11, 0.15)';
            badgeEl.style.color = '#f59e0b';
            badgeEl.style.borderColor = 'rgba(245, 158, 11, 0.3)';
        } else if (data.status === 'ready') {
            badgeEl.textContent = '● Ready';
            badgeEl.className = 'source-badge';
            badgeEl.style.background = 'rgba(16, 185, 129, 0.15)';
            badgeEl.style.color = '#10b981';
            badgeEl.style.borderColor = 'rgba(16, 185, 129, 0.3)';
        } else if (data.status === 'error') {
            badgeEl.textContent = '● Error';
            badgeEl.className = 'source-badge';
            badgeEl.style.background = 'rgba(239, 68, 68, 0.15)';
            badgeEl.style.color = '#ef4444';
            badgeEl.style.borderColor = 'rgba(239, 68, 68, 0.3)';
        } else {
            badgeEl.textContent = data.status || 'Idle';
            badgeEl.className = 'source-badge';
            badgeEl.style.background = 'var(--bg-hover)';
            badgeEl.style.color = 'var(--text-secondary)';
            badgeEl.style.borderColor = 'var(--border-color)';
        }

        if (statsEl) {
            if (data.status === 'ready' && data.article_count > 0) {
                statsEl.textContent = `(${data.article_count} articles, ${data.chunk_count} chunks indexed)`;
            } else if (data.status === 'indexing') {
                statsEl.textContent = '(indexing in background...)';
            } else {
                statsEl.textContent = '';
            }
        }

        if (rebuildBtn) {
            rebuildBtn.disabled = data.status === 'indexing';
        }

        if (errorEl) {
            if (data.last_error) {
                errorEl.className = 'settings-status error';
                errorEl.textContent = `Indexing error: ${data.last_error}`;
                errorEl.classList.remove('hidden');
            } else {
                errorEl.classList.add('hidden');
            }
        }
    },

    _startEmbeddingPolling() {
        if (this._embeddingPollTimer) return;
        this._embeddingPollTimer = setInterval(async () => {
            try {
                const data = await API.getEmbeddingSettings();
                this.updateEmbeddingStatusUI(data);
                if (data.status !== 'indexing') {
                    clearInterval(this._embeddingPollTimer);
                    this._embeddingPollTimer = null;
                    if (data.status === 'ready') {
                        Utils.toast('Embedding index build completed!', 'success');
                    } else if (data.status === 'error') {
                        Utils.toast('Embedding index build failed.', 'error');
                    }
                }
            } catch (e) {
                clearInterval(this._embeddingPollTimer);
                this._embeddingPollTimer = null;
            }
        }, 1500);
    },

    async saveEmbeddingToggle(enabled) {
        try {
            const data = await API.saveEmbeddingSettings(enabled);
            this.updateEmbeddingStatusUI(data);
            Utils.toast(enabled ? 'Embedding search enabled' : 'Embedding search disabled', 'info');
            if (enabled && data.status === 'indexing') {
                this._startEmbeddingPolling();
            }
        } catch (e) {
            Utils.toast(`Failed to update embedding settings: ${e.message}`, 'error');
        }
    },

    async rebuildEmbeddingIndex() {
        const btn = document.getElementById('btn-rebuild-embeddings');
        if (btn) btn.disabled = true;

        try {
            const data = await API.rebuildEmbeddingIndex();
            this.updateEmbeddingStatusUI(data);
            Utils.toast('Started background embedding indexing...', 'info');
            this._startEmbeddingPolling();
        } catch (e) {
            Utils.toast(`Failed to rebuild embeddings: ${e.message}`, 'error');
            if (btn) btn.disabled = false;
        }
    },

    // --- Knowledge Base Health & Statistics ---

    toggleAccordion(type) {
        const accordion = document.getElementById(`${type}-accordion`);
        if (!accordion) return;
        const list = accordion.querySelector('.health-accordion-content');
        const chevron = accordion.querySelector('.health-toggle-chevron');
        if (!list) return;

        const isHidden = list.classList.toggle('hidden');
        if (chevron) {
            chevron.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(180deg)';
        }
    },

    async loadStats() {
        const grid = document.getElementById('stats-overview-grid');
        const refreshBtn = document.getElementById('btn-refresh-stats');
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.textContent = '⏳ Loading...';
        }

        try {
            const stats = await API.getStats();
            this._renderStats(stats);
        } catch (e) {
            console.error('Failed to load KB stats:', e);
            if (grid) {
                grid.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1; color: var(--color-danger);">Failed to load statistics: ${Utils.escapeHtml(e.message)}</div>`;
            }
        } finally {
            if (refreshBtn) {
                refreshBtn.disabled = false;
                refreshBtn.textContent = '🔄 Refresh';
            }
        }
    },

    _renderStats(stats) {
        const grid = document.getElementById('stats-overview-grid');
        const brokenBadge = document.getElementById('broken-links-badge');
        const orphansBadge = document.getElementById('orphans-badge');
        const brokenList = document.getElementById('broken-links-list');
        const orphansList = document.getElementById('orphans-list');

        // Render overview mini cards
        if (grid) {
            const brokenCount = stats.broken_links_count || 0;
            const orphansCount = stats.orphaned_pages_count || 0;

            const brokenColorClass = brokenCount === 0 ? 'text-success' : 'text-warning';
            const brokenSubtitle = brokenCount === 0 ? '✓ All link targets exist' : `⚠ ${brokenCount} link${brokenCount === 1 ? '' : 's'} to missing pages`;

            const orphanColorClass = orphansCount === 0 ? 'text-success' : 'text-info';
            const orphanSubtitle = orphansCount === 0 ? '✓ Fully connected graph' : `${orphansCount} unreferenced page${orphansCount === 1 ? '' : 's'}`;

            grid.innerHTML = `
                <div class="stat-mini-card">
                    <div class="stat-mini-header">
                        <span class="stat-mini-icon">📄</span>
                        <span class="stat-mini-lbl">Articles</span>
                    </div>
                    <div class="stat-mini-val">${stats.total_articles}</div>
                    <div class="stat-mini-sub">${stats.native_articles} native · ${stats.external_articles} external</div>
                </div>
                <div class="stat-mini-card">
                    <div class="stat-mini-header">
                        <span class="stat-mini-icon">🌐</span>
                        <span class="stat-mini-lbl">Wiki Links</span>
                    </div>
                    <div class="stat-mini-val">${stats.total_links}</div>
                    <div class="stat-mini-sub">${stats.total_categories} categories · ${stats.total_tags} tags</div>
                </div>
                <div class="stat-mini-card">
                    <div class="stat-mini-header">
                        <span class="stat-mini-icon">🖼️</span>
                        <span class="stat-mini-lbl">Media Resources</span>
                    </div>
                    <div class="stat-mini-val">${stats.total_resources}</div>
                    <div class="stat-mini-sub">Images, diagrams & docs</div>
                </div>
                <div class="stat-mini-card">
                    <div class="stat-mini-header">
                        <span class="stat-mini-icon">🔗</span>
                        <span class="stat-mini-lbl">Broken Links</span>
                    </div>
                    <div class="stat-mini-val ${brokenColorClass}">${brokenCount}</div>
                    <div class="stat-mini-sub">${brokenSubtitle}</div>
                </div>
                <div class="stat-mini-card">
                    <div class="stat-mini-header">
                        <span class="stat-mini-icon">🏝️</span>
                        <span class="stat-mini-lbl">Orphaned Pages</span>
                    </div>
                    <div class="stat-mini-val ${orphanColorClass}">${orphansCount}</div>
                    <div class="stat-mini-sub">${orphanSubtitle}</div>
                </div>
            `;
        }

        // Badges on headers
        if (brokenBadge) {
            brokenBadge.textContent = stats.broken_links_count;
            if (stats.broken_links_count > 0) {
                brokenBadge.className = 'chip chip-warning';
            } else {
                brokenBadge.className = 'chip chip-success';
            }
        }
        if (orphansBadge) {
            orphansBadge.textContent = stats.orphaned_pages_count;
            if (stats.orphaned_pages_count > 0) {
                orphansBadge.className = 'chip chip-muted';
            } else {
                orphansBadge.className = 'chip chip-success';
            }
        }

        // Render Broken Links List
        if (brokenList) {
            if (!stats.broken_links || stats.broken_links.length === 0) {
                brokenList.innerHTML = `
                    <div class="health-empty-msg">
                        <span style="font-size: 1.1rem; color: var(--color-success);">✓</span>
                        <span>Awesome! No broken wiki links detected in any article.</span>
                    </div>
                `;
            } else {
                brokenList.innerHTML = `
                    <div class="health-items-table">
                        <div class="health-table-header">
                            <div>Source Article</div>
                            <div>Target Reference</div>
                            <div style="text-align: right;">Line</div>
                        </div>
                        ${stats.broken_links.map(item => `
                            <div class="health-table-row">
                                <div class="health-cell-main">
                                    <a href="#/article/${encodeURIComponent(item.source_id)}" class="health-link" onclick="App.navigateToArticle('${Utils.escapeHtml(item.source_id)}')">
                                        ${Utils.escapeHtml(item.source_id)}
                                    </a>
                                </div>
                                <div class="health-cell-target">
                                    <code class="health-broken-code">[[${Utils.escapeHtml(item.target_id)}]]</code>
                                    ${item.display_text ? `<span class="health-link-display">(${Utils.escapeHtml(item.display_text)})</span>` : ''}
                                </div>
                                <div class="health-cell-line">
                                    ${item.line_number ? `L${item.line_number}` : '—'}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                `;
            }
        }

        // Render Orphaned Pages List
        if (orphansList) {
            if (!stats.orphaned_pages || stats.orphaned_pages.length === 0) {
                orphansList.innerHTML = `
                    <div class="health-empty-msg">
                        <span style="font-size: 1.1rem; color: var(--color-success);">✓</span>
                        <span>All pages have at least one incoming reference from another article or category.</span>
                    </div>
                `;
            } else {
                orphansList.innerHTML = `
                    <div class="health-items-table">
                        <div class="health-table-header">
                            <div>Orphaned Page / Resource</div>
                            <div>Type</div>
                            <div style="text-align: right;">Outgoing</div>
                        </div>
                        ${stats.orphaned_pages.map(item => {
                            const isResource = item.type === 'resource';
                            const linkHref = isResource ? `#/resource/${encodeURIComponent(item.id)}` : `#/article/${encodeURIComponent(item.id)}`;
                            const clickHandler = isResource ? '' : `onclick="App.navigateToArticle('${Utils.escapeHtml(item.id)}')"` ;
                            return `
                                <div class="health-table-row">
                                    <div class="health-cell-main">
                                        <a href="${linkHref}" class="health-link" ${clickHandler}>
                                            ${Utils.escapeHtml(item.title || item.id)}
                                        </a>
                                        <code class="health-id-code">${Utils.escapeHtml(item.id)}</code>
                                    </div>
                                    <div>
                                        <span class="source-badge ${item.type === 'category' ? 'source' : (item.id.startsWith('src:') ? 'code' : (item.id.startsWith('gdrive:') ? 'drive' : 'markdown'))}">
                                            ${Utils.escapeHtml(item.type)}
                                        </span>
                                    </div>
                                    <div class="health-cell-line">
                                        ${item.outgoing_count} link${item.outgoing_count === 1 ? '' : 's'}
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                `;
            }
        }
    }
};
