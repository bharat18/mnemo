# Mnemo

> **Give Claude Permanent Memory**

Mnemo compresses your entire Claude.ai conversation history into a structured YAML memory file.
Upload it once to a new chat — Claude instantly has full project context, past decisions, and a
**Failure Memory** that auto-warns before repeating past mistakes.

![token reduction](https://img.shields.io/badge/token%20reduction-97.6%25-7c3aed?style=flat-square)
![file size](https://img.shields.io/badge/file%20size-41%C3%97%20smaller-10b981?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-blue?style=flat-square)
![python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square)

---

## The Problem

Every time you hit Claude's context limit, you lose everything:
- Decisions already made
- Bugs already fixed
- Approaches already rejected
- Hours of hard-earned context

**Mnemo solves this in 3 commands.**

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/YOUR_USERNAME/chat-gtf
cd chat-gtf
pip install -r requirements.txt

# 2. Export your Claude.ai chat
# Open F12 > Console on any Claude.ai chat page
# Paste export_chat.js and press Enter → downloads my_chat.md

# 3. Index it
export OPENAI_API_KEY=sk-...          # or ANTHROPIC_API_KEY + --provider anthropic
python indexer.py my_chat.md --provider openai
# → creates my_chat_gtf.yaml

# 4. Start a new Claude.ai chat
# Attach chat_gtf.yaml + paste system_prompt.md → Claude has full context
```

**Real benchmark:** 484,000-char BioPrism project chat → 11,000-char YAML
- 97.6% token reduction · 41× smaller · 9 failure patterns captured

---

## The 5 Layers

| Layer | What it stores |
|-------|----------------|
| **Exon** | Committed decisions, pinned constants, rejected approaches, current state |
| **Nodes** | Every component/entity with type, connections, file locations |
| **Diffs** | What changed, from what version, and why |
| **Failure Memory** | Past bugs with trigger words — Claude warns before you repeat |
| **Dependency Web** | Blast radius per component (HIGH / MEDIUM / LOW) |

---

## Failure Memory — The Killer Feature

No other tool has this. Every captured failure includes **trigger words**.
When you mention one in a new chat, Claude intercepts automatically:

```
You: "should I use QToolButton for the dropdown?"

Claude: ⚠️ FAILURE MEMORY TRIGGERED — F003
  What failed  : QToolButton for dropdown menus
  Error        : Menu disappears when mouse leaves button area
  Time lost    : 2 hours
  Safe pattern : QPushButton + menu.exec() instead

Shall I proceed with the safe pattern?
```

---

## Usage

```bash
# Fully automated (default)
python indexer.py my_chat.md --provider openai

# Enrich: auto-fill missing code patterns for each failure
python indexer.py my_chat.md --provider openai --enrich

# Hybrid: manually enter known failures, Claude fills the rest
python indexer.py my_chat.md --provider openai --hybrid

# Anthropic provider
python indexer.py my_chat.md --provider anthropic
```

---

## Claude Desktop MCP Integration

Add to your `claude_desktop_config.json`
(`%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "chat-gtf": {
      "command": "python",
      "args": [
        "C:/path/to/chat-gtf/mcp_server.py",
        "C:/path/to/my_chat_gtf.yaml"
      ]
    }
  }
}
```

Claude can now call all 10 GTF tools directly — including `gtf_index` to
create a new YAML without leaving Claude Desktop.

Full setup guide: [docs/mcp-setup.md](docs/mcp-setup.md)

---

## MCP Tools (10 total)

| Tool | What it does |
|------|-------------|
| `gtf_check_failures` | Checks trigger words — called before every response |
| `gtf_index` | Index a new chat export without leaving Claude Desktop |
| `gtf_status` | Health check — is YAML loaded and valid? |
| `gtf_get_node` | Full context for any named component or entity |
| `gtf_get_decisions` | All committed decisions + rejected approaches |
| `gtf_get_blast_radius` | What breaks if component X changes |
| `gtf_get_open_problems` | Unresolved problems + current project state |
| `gtf_search` | Keyword search across all 5 layers |
| `gtf_add_failure` | Save a new failure to memory mid-session |
| `gtf_get_summary` | Full project overview for session start |

---

## Real-World Example

See [`examples/my_chat_gtf.yaml`](examples/my_chat_gtf.yaml) — a real GTF from a 484k-char
BioPrism bioinformatics desktop app project:
- 16 committed decisions, 16 nodes with file locations
- 9 failure memories (F001–F009) with trigger words and safe patterns
- 8 component diffs with evolution history

---

## Comparison

| Feature | Mnemo | Graphify | Graphiti/Zep | MemoryOS |
|---------|:-------:|:--------:|:------------:|:--------:|
| Works in Claude.ai UI | ✅ | ✅ | ❌ | ❌ |
| No server/API setup needed | ✅ | ✅ | ❌ | ❌ |
| Works on chat history | ✅ | ❌ code only | ⚠️ partial | ✅ |
| Failure Memory + trigger words | ✅ | ❌ | ❌ | ❌ |
| Offline / no cloud dependency | ✅ | ✅ | ❌ | ❌ |
| Portable YAML (attach anywhere) | ✅ | ❌ | ❌ | ❌ |
| Blast radius tracking | ✅ | ❌ | ❌ | ❌ |

---

## Project Structure

```
chat-gtf/
├── indexer.py           ← Main script: chat export → YAML
├── mcp_server.py        ← Claude Desktop MCP server (10 tools)
├── export_chat.js       ← Browser script to export Claude.ai chats
├── system_prompt.md     ← Paste into new Claude chat to activate memory
├── schema.yaml          ← Annotated YAML schema reference
├── requirements.txt
├── examples/
│   └── my_chat_gtf.yaml ← Real BioPrism project GTF (484k → 11k chars)
├── docs/
│   ├── quickstart.md
│   ├── mcp-setup.md
│   └── architecture.md
└── marketing/
    └── index.html       ← Landing page (open locally)
```

---

## Requirements

- Python 3.10+
- `pyyaml`, `colorama`
- `openai` or `anthropic` (one API key, one-time indexing only)
- `mcp` (only for Claude Desktop integration)

```bash
pip install -r requirements.txt
```

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

Ideas especially wanted:
- GTF templates for popular stacks (Next.js, FastAPI, ML experiments)
- Auto-export hook for Claude Desktop
- VS Code extension for inline GTF queries

---

## License

MIT — see [LICENSE](LICENSE)

---

*Inspired by GTF (Gene Transfer Format) annotation files in bioinformatics —
structured semantic layers on top of raw sequence data.*
