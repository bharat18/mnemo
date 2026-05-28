# Mnemo — Project Brief for Claude Code

## What We Are Building

A Python tool that converts exported Claude.ai chat history into a
structured YAML file called `chat_gtf.yaml`. This file acts like a
GTF annotation file in bioinformatics — it stores only the
**functionally important** parts of a conversation, not the whole thing.

The output file is uploaded to a new Claude.ai chat session, giving
Claude full project context in ~400 tokens instead of ~10,000+.

---

## The Problem Being Solved

Claude.ai context window fills up over long projects. Users open a
new chat but lose all project context. Current solutions:

- `summary.md` — flat prose, lossy, not queryable
- Graphify — works on codebases only, not chat history
- Graphiti/Zep — API-only, not Claude.ai UI compatible

**Mnemo fills this gap.** It works with a simple file upload in
Claude.ai UI. No API key needed. No MCP setup needed.

---

## The 5-Layer Architecture

Every `chat_gtf.yaml` file has exactly these 5 layers:

### Layer 1 — Exon Layer
Key facts extracted from chat. Like GTF exons — only functional
regions, no filler (introns = greetings, repeated explanations, etc.)

Fields: `decisions`, `constants`, `open_problems`,
`rejected_approaches`, `current_state`

### Layer 2 — Associative Node Layer
Inspired by human brain associative memory. One word invokes full
context. User types "AuthService" in new chat — Claude knows
everything about it without re-explanation.

Fields per node: `type`, `connects_to[]`, `decision`, `state`, `file`

### Layer 3 — Diff Layer
Inspired by Git commits. Tracks how thinking evolved — not just
current state but why it changed.

Fields: `v1..vN`, `current`, `why_changed`

### Layer 4 — Failure Memory Layer ⭐ (Most Novel)
Inspired by immune system memory cells. Explicitly stores failed
approaches with trigger words. When trigger word appears in a new
chat, Claude automatically warns the user.

Fields: `id`, `what_tried`, `exact_error`, `time_wasted`,
`trigger_words[]`, `never_again`, `unless`, `code_pattern_to_avoid`,
`safe_pattern`

### Layer 5 — Dependency Web Layer
Inspired by protein interaction networks. Tracks blast radius —
if X changes, what breaks?

Fields: `if_changed[]`, `safe_to_change`, `blast_radius`

---

## Full YAML Schema

```yaml
meta:
  project: "string"
  stack: [list]
  created: "YYYY-MM"
  last_updated: "YYYY-MM"
  source_chats: [list of filenames]

exons:
  decisions: [list]
  constants: {key: value}
  open_problems: [list]
  rejected_approaches: [list]
  current_state: "string"

nodes:
  EntityName:
    type: "component|decision|constant|person|concept"
    connects_to: [list]
    decision: "string"
    state: "string"
    file: "path/optional"

diffs:
  EntityName:
    v1: "string"
    current: "vN"
    why_changed: "string"

failure_memory:
  - id: "F001"
    what_tried: "string"
    exact_error: "string"
    time_wasted: "string"
    trigger_words: [list]
    never_again: true
    unless: "string or null"
    code_pattern_to_avoid: "optional multiline string"
    safe_pattern: "optional multiline string"

dependencies:
  EntityName:
    if_changed: [list]
    safe_to_change: true|false
    blast_radius: "HIGH|MEDIUM|LOW"
```

---

## Files To Build

```
chat_gtf/
├── CLAUDE.md              ← this file (project brief)
├── README.md              ← user-facing documentation
├── schema.yaml            ← GTF schema definition
├── indexer.py             ← MAIN SCRIPT: chat export → GTF
├── system_prompt.md       ← paste this in new Claude.ai chat
└── examples/
    ├── sample_export.md   ← fake chat export for testing
    └── sample_gtf.yaml    ← expected GTF output
```

---

## indexer.py — Detailed Spec

### Inputs
- `chat_export.md` — exported chat file (required)
- `--mode auto|hybrid` — default: auto
- `--output` — output filename, default: `chat_gtf.yaml`
- `--model` — which LLM to use for extraction

### Mode A: Full Auto
1. Read `chat_export.md`
2. Split into chunks if very long
3. Send to Claude API with extraction prompt
4. Parse response into 5-layer YAML
5. Write `chat_gtf.yaml`

### Mode B: Hybrid
1. Read `chat_export.md`
2. Ask user to manually input any known failures (interactive CLI)
3. Send chat + manual failures to Claude API
4. Claude fills L1, L2, L3, L5 automatically
5. Merge manual L4 with auto-extracted L4
6. Write `chat_gtf.yaml`

### Extraction Prompt Strategy
Use a structured prompt that asks Claude to extract each layer
separately. Return JSON, parse, convert to YAML.

Do NOT ask Claude to return YAML directly — JSON is safer to parse.

### Error Handling
- Chat file not found → clear error message
- API key missing → instructions to set env var
- Malformed extraction → retry once with stricter prompt
- Very long chat (>50k tokens) → chunk and merge

---

## system_prompt.md — Detailed Spec

This file is what users paste at the start of a new Claude.ai chat,
along with their `chat_gtf.yaml` upload.

It must instruct Claude to:
1. Read the GTF file on first message
2. Before every response — check `failure_memory` trigger words
3. If trigger word found → warn user before proceeding
4. Use `nodes` for associative context
5. Respect `dependencies.blast_radius` when suggesting changes
6. Never ask user to re-explain things already in GTF

---

## What Makes This Novel

| Feature | Exists Anywhere? |
|---|---|
| Chat history → structured memory | Partially (Graphiti, API only) |
| Failure memory + trigger words | NO — unique to Mnemo |
| Works in Claude.ai UI (file upload) | NO — all others need API/MCP |
| Controlled loss (not random) | NO — summary.md is random loss |
| Evolution diffs | NO |
| Blast radius for chat decisions | NO |

---

## Token Reduction Target

- Typical chat export: 8,000–15,000 tokens
- Target GTF output: 300–600 tokens
- Target reduction: ~95%
- Acceptable information loss: zero for L4 (failures), minimal for L1-L3

---

## Non-Goals (Do Not Build)

- Do NOT build a UI — CLI only for now
- Do NOT require a vector database
- Do NOT require MCP setup
- Do NOT store data anywhere except local files
- Do NOT require any subscription — user provides their own API key

---

## Success Criteria

1. `python indexer.py sample_export.md` runs without error
2. Output `chat_gtf.yaml` contains all 5 layers
3. All failures from chat are captured in `failure_memory`
4. `trigger_words` are meaningful and not generic
5. Total output tokens < 600 for a typical 10k token chat
6. New Claude.ai chat with GTF uploaded can answer project questions
   without user re-explaining anything
