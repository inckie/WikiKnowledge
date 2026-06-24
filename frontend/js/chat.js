/**
 * WikiKnowledge — AI Agent Floating Chat Controller
 */

const Chat = {
    _initialized: false,

    init() {
        if (this._initialized) return;
        this._bindEvents();
        this._initialized = true;
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
                            <div class="message-content">Hello! I am your AI assistant, wired with WikiKnowledge MCP tools. How can I help you today?</div>
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

            try {
                const resp = await API.sendAIChat(prompt);
                this.updateMessage(thinkingId, resp.reply || 'No response generated.');
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

    updateMessage(id, text) {
        const msgDiv = document.getElementById(id);
        if (!msgDiv) return;
        const contentDiv = msgDiv.querySelector('.message-content');
        if (contentDiv) {
            contentDiv.innerText = text;
        }
        const messagesContainer = document.getElementById('chat-messages');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }
};
