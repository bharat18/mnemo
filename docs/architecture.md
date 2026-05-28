# Mnemo Architecture

## Why "GTF"?

GTF (Gene Transfer Format) is a bioinformatics file format that adds structured semantic
annotations on top of raw DNA sequence data. Mnemo does the same for conversation data —
it adds structured semantic layers on top of raw chat history.

---

## The 5-Layer Architecture

```
RAW CHAT (484,000 chars / 121,054 tokens)
         │
         ▼  indexer.py
┌────────────────────────────────────┐
│  L1  EXON LAYER                    │  ← What was decided
│      decisions, constants,         │
│      rejected_approaches,          │
│      current_state                 │
├────────────────────────────────────┤
│  L2  ASSOCIATIVE NODES             │  ← What exists
│      components, concepts,         │
│      connections, file locations   │
├────────────────────────────────────┤
│  L3  DIFF LAYER                    │  ← What changed and why
│      v1 → current, why_changed     │
├────────────────────────────────────┤
│  L4  FAILURE MEMORY                │  ← What went wrong
│      what_tried, exact_error,      │
│      trigger_words, safe_pattern,  │
│      time_wasted, never_again      │
├────────────────────────────────────┤
│  L5  DEPENDENCY WEB                │  ← What breaks what
│      if_changed, blast_radius,     │
│      safe_to_change                │
└────────────────────────────────────┘
         │
         ▼
CHAT GTF YAML (11,000 chars / 2,931 tokens)
97.6% token reduction · 41× smaller
```

---

## Indexing Pipeline

```
chat_export.md
    │
    ▼  chunk_on_turns()
Chunks (≤80k chars each)
    │
    ▼  extract_with_retry() × N chunks
Raw JSON extractions
    │
    ▼  merge_chunks()
Merged YAML (deduped)
    │
    ▼  enrich_failures()  [if --enrich]
Final YAML with code patterns filled
    │
    ▼  write to disk
chat_gtf.yaml
```

### Two-Pass Chunker

Large chats are split intelligently to preserve turn boundaries:

**Pass 1:** Split at Human/Claude turn markers, merge adjacent small turns into
one chunk (up to 80k chars).

**Pass 2:** Any chunk still over 80k chars is sub-split at paragraph boundaries.

Result: chunks never split mid-thought, and no single chunk exceeds the rate limit.

---

## Failure Memory — Detailed Design

Each failure entry:
```yaml
- id: F003
  what_tried: Using QToolButton for dropdown menus
  exact_error: Menu disappears when mouse leaves button area
  time_wasted: 2 hours
  trigger_words:
    - QToolButton
    - mouse hover
  never_again: true
  unless: QToolButton behavior changes
  code_pattern_to_avoid: |
    tool_button = QToolButton()
    tool_button.setPopupMode(QToolButton.InstantPopup)
  safe_pattern: |
    push_button = QPushButton("Menu")
    menu = QMenu(push_button)
    push_button.clicked.connect(lambda: menu.exec(...))
```

**How trigger words work:**
1. `mcp_server.py` implements `gtf_check_failures`
2. Claude Desktop calls it before every response
3. If any trigger word matches, Claude surfaces the full failure card
4. User sees warning before the broken approach is suggested

**Enrichment pass (`--enrich`):**
For failures where `code_pattern_to_avoid` is null, a focused mini-call
asks the LLM to generate both the bad and good code pattern based on
`what_tried` and `exact_error`. Duplicate patterns are discarded.

---

## MCP vs. File Upload — Two Operating Modes

### Mode A — File Upload (Claude.ai web)
```
chat_gtf.yaml  ──attach──▶  New Claude.ai chat
system_prompt.md ─paste──▶  First message

Claude reads full YAML once at session start.
Token cost: ~2,931 tokens upfront.
Works in Claude.ai browser UI. No setup required.
```

### Mode B — MCP (Claude Desktop)
```
chat_gtf.yaml  ──loaded by──▶  mcp_server.py
                                    │
New Claude Desktop session ◀──────  │ (MCP auto-registered)
     │
     ├─ gtf_check_failures()  ← every message
     ├─ gtf_get_node("X")     ← on demand
     └─ gtf_get_summary()     ← session start

Token cost: ~0 upfront. Claude fetches only what it needs.
Best for ongoing projects. Requires Claude Desktop.
```

Mode B is architecturally superior for active projects because context is
fetched on demand rather than loaded in full upfront.

---

## Schema Version

Current schema version: **v1**

See [`schema.yaml`](../schema.yaml) for the annotated reference.
Breaking changes to the schema will be versioned under `meta.schema_version`.
