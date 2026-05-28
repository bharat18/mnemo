# MCP Setup — Claude Desktop Integration

This guide connects Mnemo to Claude Desktop so Claude can query your project memory
directly — no copy-pasting needed.

---

## Prerequisites

- [Claude Desktop](https://claude.ai/download) installed
- Python 3.10+ with `mcp` package: `pip install mcp pyyaml`
- A `chat_gtf.yaml` file (run `indexer.py` first, or use `examples/my_chat_gtf.yaml` to test)

---

## Step 1 — Find your Claude Desktop config file

| OS | Location |
|----|----------|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

If the file doesn't exist, create it.

---

## Step 2 — Add the Mnemo MCP server

Open `claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "chat-gtf": {
      "command": "python",
      "args": [
        "C:/Users/YOU/chat-gtf/mcp_server.py",
        "C:/Users/YOU/my_project/chat_gtf.yaml"
      ]
    }
  }
}
```

Replace the paths with your actual locations. Use forward slashes even on Windows.

---

## Step 3 — Restart Claude Desktop

Fully quit and reopen Claude Desktop. You should see "chat-gtf" listed in the tools panel.

---

## Step 4 — Verify it works

In a new Claude Desktop conversation, type:

```
call gtf_status
```

Expected response:
```
GTF Status
File         : C:/...chat_gtf.yaml
Size         : 11.2 KB
Last modified: 2026-04-27 14:32:00
Health       : ✅ Healthy

Project    : BioPrism Local AI Integration
Nodes        : 16
Failures     : 9
Decisions    : 16
Open problems: 8
```

---

## Step 5 — Index a new chat without leaving Claude Desktop

Instead of running `indexer.py` from the terminal, you can now ask Claude directly:

```
Index my chat export at C:/Downloads/my_new_project_chat.md using openai
```

Claude will call `gtf_index` and run the full indexing pipeline in the background.

---

## How Claude uses the tools automatically

With `gtf_check_failures` in the MCP, Claude checks every message you send against
failure trigger words. You don't need to ask — it happens automatically.

The full list of 10 tools and when Claude uses each:

| Tool | Triggered by |
|------|-------------|
| `gtf_check_failures` | Every message (auto) |
| `gtf_get_summary` | Start of session |
| `gtf_get_node` | Mentions of any component name |
| `gtf_get_decisions` | Architectural questions |
| `gtf_get_blast_radius` | "Can I change X?" |
| `gtf_get_open_problems` | "What's next?" |
| `gtf_search` | Any unfamiliar term |
| `gtf_add_failure` | When something breaks |
| `gtf_index` | "Index my chat file at..." |
| `gtf_status` | "Is my GTF loaded?" |

---

## Troubleshooting

**"Unknown tool: gtf_index"**
→ Restart Claude Desktop after editing the config file.

**"indexer.py not found"**
→ Make sure `mcp_server.py` and `indexer.py` are in the same folder.

**"No GTF file found"**
→ Check the path in `claude_desktop_config.json`. Use forward slashes `/`.

**Indexing fails with API error**
→ Make sure `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is set in your system environment
  (not just in a terminal). On Windows: System Properties → Environment Variables.
