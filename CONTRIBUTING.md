# Contributing to Mnemo

Thank you for helping improve Mnemo! This document covers how to contribute effectively.

---

## Ways to Contribute

### 1. Share a real GTF file (highest value)
The best contribution is a real `chat_gtf.yaml` from your own project (with any sensitive info removed).
Place it in `examples/` with a short description at the top of the file.

Good GTFs to contribute:
- Web app projects (Next.js, FastAPI, Django)
- ML/data science projects
- Mobile app projects
- Any long Claude.ai session with good failures captured

### 2. Fix a bug
Check the [Issues](../../issues) tab. Issues tagged `bug` are ready to fix.

### 3. Add a feature
Comment on an existing feature request, or open a new issue before starting
so we can discuss the design first.

### 4. Improve extraction quality
The extraction prompts are in `indexer.py` (look for `EXTRACTION_PROMPT`, `RETRY_PROMPT`,
`ENRICHMENT_PROMPT`). Better prompts = better GTFs. Test against `examples/my_chat_gtf.yaml`.

### 5. Documentation
Improve or add to `docs/`. Especially needed: tutorials for non-Python users.

---

## Development Setup

```bash
git clone https://github.com/YOUR_USERNAME/chat-gtf
cd chat-gtf
pip install -r requirements.txt

# Run a quick test
python indexer.py examples/sample_chat.md --provider openai
```

---

## Pull Request Guidelines

1. **One thing per PR** — don't mix bug fixes and new features
2. **Test with a real chat** before submitting
3. **Update README.md** if you add new CLI flags or MCP tools
4. **No breaking changes** to the YAML schema without a version bump in `schema.yaml`

---

## Schema Stability Contract

The GTF YAML schema in `schema.yaml` is the contract between:
- `indexer.py` (writes the YAML)
- `mcp_server.py` (reads the YAML)
- Claude (interprets via `system_prompt.md`)

**If you change the schema**, you must update all three. Add a comment in `schema.yaml`
explaining the change.

---

## Reporting Issues

Please include:
- Python version
- Provider used (`openai` / `anthropic`)
- Approximate chat size (chars or turns)
- The exact error message
- Whether `--enrich` was used

---

## Questions?

Open a GitHub Discussion — not an Issue — for questions and ideas.
