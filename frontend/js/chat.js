/**
 * WikiKnowledge — AI Agent Floating Chat Controller
 */

const Chat = {
    _initialized: false,
    _welcomeText: 'Hello! I am your AI assistant, wired with WikiKnowledge MCP tools. How can I help you today?',

    async init() {
        if (this._initialized) return;
        this._bindEvents();
        this._initialized = true;
        await this.updateWelcomeMessage();
    },

    async updateWelcomeMessage() {
        try {
            const settings = await API.getAISettings();
            const provider = settings.provider || 'openai';
            const providerName = provider === 'antigravity' ? 'Antigravity SDK' : 'OpenAI / Ollama';
            const modelName = settings.model || (provider === 'antigravity' ? 'gemini-2.5-pro' : 'default model');
            
            this._welcomeText = `Hello! I am your AI assistant powered by ${providerName} (${modelName}), wired with WikiKnowledge MCP tools. How can I help you today?`;
        } catch (e) {
            console.error("Failed to load AI settings for welcome message", e);
        }
        
        const messagesContainer = document.getElementById('chat-messages');
        if (messagesContainer && messagesContainer.children.length <= 1) {
             messagesContainer.innerHTML = `
                 <div class="chat-message assistant">
                     <div class="message-content">${Utils.escapeHtml(this._welcomeText)}</div>
                 </div>
             `;
        }
    },

    _bindEvents() {
        const fab = document.getElementById('btn-ai-chat-toggle');
        const win = document.getElementById('ai-chat-window');
        const closeBtn = document.getElementById('btn-ai-chat-close');
        const clearBtn = document.getElementById('btn-ai-chat-clear');
        const sendBtn = document.getElementById('btn-chat-send');
        const textarea = document.getElementById('chat-input-textarea');

        if (fab && win) {
            fab.addEventListener('click', () => {
                win.classList.toggle('hidden');
                if (!win.classList.contains('hidden')) {
                    textarea?.focus();
                }
            });
        }

        if (closeBtn && win) {
            closeBtn.addEventListener('click', () => {
                win.classList.add('hidden');
            });
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                const messagesContainer = document.getElementById('chat-messages');
                if (messagesContainer) {
                    messagesContainer.innerHTML = `
                        <div class="chat-message assistant">
                            <div class="message-content">${Utils.escapeHtml(this._welcomeText)}</div>
                        </div>
                    `;
                }
                Utils.toast('Chat history cleared', 'success');
                textarea?.focus();
            });
        }

        const sendMessage = async () => {
            if (!textarea || !sendBtn) return;
            const prompt = textarea.value.trim();
            if (!prompt) return;

            // Append user message
            this.appendMessage('user', prompt);
            textarea.value = '';
            textarea.style.height = '42px';

            sendBtn.disabled = true;
            textarea.disabled = true;

            // Append thinking placeholder
            const thinkingId = this.appendMessage('assistant', '⏳ Thinking... (Checking tools & generating response)');

            const context = {
                current_view: App._currentView,
                current_article_id: App._currentArticleId
            };

            try {
                const resp = await API.sendAIChat(prompt, context);
                this.updateMessage(thinkingId, resp.reply || 'No response generated.', resp.stats);
            } catch (e) {
                this.updateMessage(thinkingId, `❌ Error: ${e.message}`);
                Utils.toast('Failed to get AI response', 'error');
            } finally {
                sendBtn.disabled = false;
                textarea.disabled = false;
                textarea.focus();
            }
        };

        if (sendBtn) {
            sendBtn.addEventListener('click', sendMessage);
        }

        if (textarea) {
            textarea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });

            textarea.addEventListener('input', () => {
                textarea.style.height = 'auto';
                textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
            });
        }
    },

    appendMessage(role, text) {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return null;

        const id = 'msg-' + Date.now() + '-' + Math.floor(Math.random() * 1000);
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${role}`;
        msgDiv.id = id;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerText = text;

        msgDiv.appendChild(contentDiv);
        messagesContainer.appendChild(msgDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        return id;
    },

    updateMessage(id, text, stats = null) {
        const msgDiv = document.getElementById(id);
        if (!msgDiv) return;
        const contentDiv = msgDiv.querySelector('.message-content');
        if (contentDiv) {
            contentDiv.innerText = text;
        }

        if (stats) {
            let statsDiv = msgDiv.querySelector('.message-stats');
            if (!statsDiv) {
                statsDiv = document.createElement('div');
                statsDiv.className = 'message-stats';
                statsDiv.style.fontSize = '0.7em';
                statsDiv.style.color = 'var(--text-muted, #888)';
                statsDiv.style.marginTop = '4px';
                statsDiv.style.textAlign = 'right';
                msgDiv.appendChild(statsDiv);
            }
            statsDiv.innerText = `⏱ ${stats.time_s}s | ⚡ ${stats.tps} t/s | 📝 In: ${stats.prompt_tokens}, Out: ${stats.completion_tokens}`;
        }

        const messagesContainer = document.getElementById('chat-messages');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }
};
