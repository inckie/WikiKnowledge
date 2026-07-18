---
categories:
- user-manual
created: '2026-06-24T04:15:00+00:00'
id: ai-settings-and-mcp-binding
modified: '2026-07-18T06:38:38.691764+00:00'
tags:
- ai
- settings
- configuration
- ui
title: AI Settings and Web UI Configuration
type: leaf
---

# AI Settings and Web UI Configuration

WikiKnowledge features an optional AI integration architecture built upon the OpenAI API protocol. This allows remote AI models (such as those hosted via Ollama, OpenAI, or compatible endpoints) to seamlessly interact with the knowledge graph and assist in generating hierarchical category overviews.

## Web UI Settings Page

The WikiKnowledge web interface includes a dedicated **Settings** page accessible via the sidebar navigation (`#/settings`).

```
┌────────────────────────────────────────────────────────┐
│ ⚙️ AI Integration Settings                             │
├────────────────────────────────────────────────────────┤
│  OpenAI API Base URL: [ https://ollama.com/v1       ]  │
│  API Key:           [ ***************************** ]  │
│                                                        │
│  [ 🔄 Fetch Available Models ]                         │
│                                                        │
│  Select Model:      [ Default Model ▾               ]  │
│                                                        │
│  ☑ Enable AI Integration & MCP Tool Binding            │
│                                                        │
│                                   [ 💾 Save Settings ] │
└────────────────────────────────────────────────────────┘
```

### Dynamic Model Discovery
When you enter an OpenAI API Base URL (e.g., `https://ollama.com/v1`) and an API Key, the **Fetch Available Models** button becomes active. Clicking this button triggers a backend request which establishes a secure connection to the remote endpoint, parses the available models, and populates the selection dropdown in real-time.

### Storage Location
To maintain portability, these AI settings are automatically saved to a dedicated configuration file within your knowledge base directory:
```
knowledge/
├── .settings/
│   └── ai_config.json
```

## Floating AI Chat Window

Once the settings are configured and enabled, the WikiKnowledge web interface provides a persistent, floating AI chat assistant accessible via a Floating Action Button (FAB) in the bottom-right corner of the screen.

```
┌──────────────────────────────────────────┐
│ 🤖 AI Assistant (MCP Enabled)         [X]│
├──────────────────────────────────────────┤
│ [Assistant] Hello! I am your AI          │
│ assistant, wired with WikiKnowledge MCP  │
│ tools. How can I help you today?         │
│                                          │
│ [User] Check what articles are available │
│                                          │
│ [Assistant] I checked the knowledge base │
│ and found the following articles...      │
├──────────────────────────────────────────┤
│ Ask AI something...                 [🚀] │
└──────────────────────────────────────────┘
```

This interface enables users to verify model connectivity and interactively command the AI to inspect dirty category trees, trace backlinks, search for tags, and explore the knowledge graph in real-time.