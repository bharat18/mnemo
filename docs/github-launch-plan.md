# GitHub Open-Source Launch Plan

## Step-by-Step: Zero to Published Repo

---

### PHASE 0 — Prepare Locally (Do this now)

**Files ready in this folder:**
```
chat-gtf/
├── README.md          ✅
├── LICENSE            ✅ (MIT)
├── CONTRIBUTING.md    ✅
├── .gitignore         ✅
├── requirements.txt   ✅
├── indexer.py         ✅
├── mcp_server.py      ✅ (10 tools including gtf_index)
├── export_chat.js     ✅
├── system_prompt.md   ✅
├── schema.yaml        ✅
├── examples/
│   └── my_chat_gtf.yaml  ✅ (real BioPrism GTF)
├── docs/
│   ├── mcp-setup.md       ✅
│   ├── architecture.md    ✅
│   └── quickstart.md      (copy from README Quick Start)
├── marketing/
│   └── index.html         ✅
└── .github/
    └── workflows/
        └── ci.yml         ✅ (GitHub Actions)
```

**Before pushing — VERIFY these are NOT in the repo:**
- [ ] No `.env` file with API keys
- [ ] No personal chat exports (`my_chat.md`, etc.)
- [ ] No personal GTF files outside `examples/`

---

### PHASE 1 — Create the GitHub Repo

1. Go to https://github.com/new

2. **Repo settings:**
   - Name: `chat-gtf`
   - Description: `Give Claude Permanent Memory — compress chat history into structured YAML with Failure Memory`
   - Visibility: **Public**
   - DO NOT initialize with README (you already have one)

3. **After creating, push your code:**
```bash
cd /path/to/Anthropic_App

# Initialize git
git init
git add .
git commit -m "Initial release: Mnemo v1.0

- indexer.py: 5-layer YAML extraction with chunking + enrichment
- mcp_server.py: 20 MCP tools for Claude Code / Claude Desktop
- session_reader.py: Claude Code JSONL session reader
- export_chat.js: browser bookmarklet for Claude.ai chat export
- Real-world example: BioPrism 484k-char project (97.6% reduction)"

# Connect to GitHub
git remote add origin https://github.com/YOUR_USERNAME/mnemo.git
git branch -M main
git push -u origin main
```

---

### PHASE 2 — Polish the Repo Page

**Add Topics** (GitHub sidebar, critical for discoverability):
Go to repo → About (gear icon) → Topics:
```
claude  claude-ai  llm-memory  context-window  yaml  ai-tools
mcp  anthropic  python  chatbot-memory
```

**Add Website URL:**
Link to the marketing page if you host it (GitHub Pages steps below).

**Pin the repo** to your GitHub profile.

---

### PHASE 3 — Host the Landing Page (GitHub Pages — FREE)

1. In your repo: Settings → Pages
2. Source: `Deploy from a branch`
3. Branch: `main` | Folder: `/marketing`
4. Save → your page goes live at:
   `https://YOUR_USERNAME.github.io/chat-gtf/`

5. Update README badges to point to this URL
6. Add to the repo's "Website" field in About

---

### PHASE 4 — Create v1.0 Release

1. Go to repo → Releases → "Create a new release"
2. Tag: `v1.0.0`
3. Title: `Mnemo v1.0 — Give Claude Permanent Memory`
4. Release notes:
```markdown
## Mnemo v1.0

### What's included
- `indexer.py` — Full 5-layer extraction pipeline with smart chunking
- `mcp_server.py` — 10 MCP tools for Claude Desktop  
- `export_chat.js` — Browser bookmarklet for Claude.ai chat export
- Real-world example: BioPrism project (484k chars → 11k chars, 97.6% reduction)
- 9 failure memories with trigger words and safe code patterns

### Highlights
- **Failure Memory**: Claude warns before repeating past mistakes
- **Two-pass chunker**: handles chats of any size without breaking turn context
- **MCP gtf_index tool**: index new chats without leaving Claude Desktop
- **Enrichment pass**: auto-generate `code_pattern_to_avoid` for every failure

### Quick Start
\`\`\`bash
pip install -r requirements.txt
python indexer.py my_chat.md --provider openai
\`\`\`
```

---

### PHASE 5 — Drive Traffic (Execute After Repo Is Live)

**Week 1 — Soft launch:**
```
Day 1: Post to r/ClaudeAI
       Title: "I compressed a 484k-char Claude project chat to 11k chars 
               — and made Claude remember its own past mistakes"

Day 3: Tweet thread (token comparison visual + failure memory screenshot)

Day 5: Dev.to article
       Title: "How I Compressed 484,000 Characters of Claude Chat into 11,000 
               — with a Failure Memory that Auto-Warns Before Repeating Mistakes"
```

**Week 2 — Main launch:**
```
Day 8:  Show HN — Tuesday 9am ET
        Title: "Show HN: Mnemo – compress Claude.ai chats 97% into YAML 
                with trigger-word Failure Memory"

Day 10: Product Hunt launch
        Coordinate upvotes from HN + Reddit audience
```

---

### PHASE 6 — Community Flywheel

Once you have ~50 stars, these create compounding growth:

1. **GTF templates** — invite community to share GTFs for popular stacks
   - "Share your Next.js project GTF"
   - "Share your ML experiment GTF"

2. **GitHub Discussions** — enable it, pin a "Share your GTF" thread

3. **Issues** — label good first issues for contributors

4. **CHANGELOG.md** — update after every meaningful change

---

## Checklist Before Going Public

- [ ] `git log` — no API keys in commit history
- [ ] `grep -r "sk-" .` — no leaked keys
- [ ] README renders correctly on GitHub (check headings, tables, badges)
- [ ] CI passes on GitHub Actions
- [ ] `examples/my_chat_gtf.yaml` loads without errors
- [ ] GitHub Pages live (optional but recommended)
- [ ] Repo topics added
- [ ] Release v1.0.0 created

---

*Once this is live, share the GitHub URL in your Show HN, Reddit, and Twitter posts.
Stars are the social proof that drives more traffic.*
