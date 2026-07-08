---
categories:
- system-architecture
created: '2026-07-08T02:32:38.384770+00:00'
id: kb-manager
modified: '2026-07-08T02:32:38.384791+00:00'
tags:
- architecture
- manager
- instances
- configuration
title: Knowledge Base Manager (kb_manager.py)
type: leaf
---

`kb_manager.py` is a UI manager tool included with WikiKnowledge. It allows you to start and stop different instances of WikiKnowledge with their own specific paths and ports, and it provides an interface to view the logs for each instance.

## Configuration (config.json)

The manager relies on a `config.json` file which defines the available knowledge bases, their directory paths, and the ports they should run on.

### Example config.json

Here is an example configuration file outlining multiple instances running on different ports. (Note: Ensure paths match your actual system structure, the paths below are examples.)

```json
{
  "knowledge_bases": {
    "self": {
      "kb_dir": "",
      "port": 8001
    },
    "ProjectAlpha": {
      "kb_dir": "/path/to/project-alpha/knowledge/",
      "port": 8002
    },
    "ToolsDocumentation": {
      "kb_dir": "/path/to/tools/docs/",
      "port": 8003
    },
    "TestingEnv": {
      "kb_dir": "/path/to/tests/knowledge/",
      "port": 8004
    },
    "AgentKnowledge": {
      "kb_dir": "/path/to/agent/knowledge/",
      "port": 8005
    }
  }
}
```

*Note: In the `self` configuration, leaving `kb_dir` empty typically indicates running the current instance's knowledge base.*

## Managing Instances

Using `kb_manager.py`, you can easily launch or terminate instances defined in the `config.json`. The UI manager simplifies the orchestration of multiple WikiKnowledge environments, making it useful for developers working across various projects simultaneously.