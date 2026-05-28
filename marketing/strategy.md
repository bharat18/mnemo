# Mnemo — Marketing Strategy
> "Give Claude Permanent Memory"

---

## 1. ONE-SENTENCE POSITIONING

**Mnemo compresses a 484,000-character Claude.ai chat into a 11,000-character YAML file that gives any new Claude session full project memory — including a Failure Memory that auto-warns before you repeat past mistakes.**

---

## 2. TARGET AUDIENCES

### Primary: Power Claude Users (Tier 1)
| Attribute | Detail |
|-----------|--------|
| Who | Developers, researchers, data scientists using Claude.ai daily |
| Pain | Hit context limit mid-project, must re-explain everything in new chats |
| Awareness | High — they already feel the pain every week |
| Where | GitHub, Twitter/X, Reddit r/ClaudeAI, r/LocalLLaMA, HackerNews |
| Hook | "97.6% token reduction" + "Never re-explain your project again" |

### Secondary: AI-augmented researchers (Tier 2)
| Attribute | Detail |
|-----------|--------|
| Who | Academic/bioinformatics/ML researchers using Claude for analysis |
| Pain | Long analysis sessions, complex domain context that gets lost |
| Awareness | Medium — they lose context but don't have a name for the problem |
| Where | Twitter/X, ResearchGate, domain-specific Discords |
| Hook | "Failure Memory — Claude warns you before you repeat 3-hour mistakes" |

### Tertiary: AI builders / hobbyists (Tier 3)
| Attribute | Detail |
|-----------|--------|
| Who | People building side projects with Claude.ai |
| Pain | Long project chats lose continuity; starting fresh each session |
| Awareness | Low — casual use, don't know this solution exists |
| Where | Product Hunt, Reddit r/SideProject, Dev.to, YouTube |
| Hook | "Three commands. Full context. Forever." |

---

## 3. CORE MESSAGING MATRIX

### Headline Bank (pick by channel)
| Tone | Headline |
|------|----------|
| Bold/punchy | **"Give Claude Permanent Memory"** |
| Problem-first | **"Tired of re-explaining your entire project every new chat?"** |
| Number-led | **"97.6% token reduction. 41× smaller. Zero setup."** |
| Fear (FOMO) | **"Every time you start a new Claude chat, you're throwing away 118,000 tokens of hard-earned context."** |
| Technical | **"5-layer YAML memory: decisions, nodes, diffs, failure patterns, dependency blast radius"** |

### Killer Differentiator (use everywhere)
> **"No other tool has Failure Memory. Claude checks trigger words before every response and warns you before you waste hours again."**

This is the moat. Lead with it in Tier 1 channels.

### Proof Points
- Real test: 484k char BioPrism project chat → 11k char YAML
- 9/9 failures captured (F001–F009), all with trigger words
- Works 100% offline — no MCP server, no API setup, just paste `system_prompt.md`
- Enrichment pass: `code_pattern_to_avoid` auto-generated for every failure

---

## 4. CHANNEL STRATEGY

### A. GitHub (Foundation — do this FIRST)
**Goal:** Credibility, discoverability, long-term organic

**Actions:**
1. Polish README with the hero screenshot + token comparison visual
2. Add `examples/my_chat_gtf.yaml` as a real-world demo (already done ✓)
3. Topics: `claude`, `llm-memory`, `context-window`, `yaml`, `claude-ai`, `ai-tools`
4. README sections: Quick Start (3 commands), What you get, Failure Memory demo, MCP setup
5. Add a `CONTRIBUTING.md` — community-built GTFs for popular project types

**Expected:** 50–200 stars organically from HN/Reddit traffic

---

### B. HackerNews Show HN (Highest leverage — do this 2nd)
**Goal:** 1 viral day, backlinks, GitHub stars spike

**Post title options:**
- `Show HN: Mnemo – compress Claude.ai chats 97% into structured YAML memory`
- `Show HN: I built a "Failure Memory" for Claude – it warns before you repeat past mistakes`

**Best time:** Tuesday–Thursday, 8–10am ET

**First comment (pre-write this):**
```
I've been using Claude.ai for a large bioinformatics desktop app project.
The problem: every time I start a new chat, I spend 10–15 minutes re-explaining
the codebase, past decisions, and mistakes I've already made.

Mnemo converts the full chat log into a 5-layer YAML:
- Exon: decisions + constants
- Nodes: components and their connections
- Diffs: what changed and why
- Failure Memory: past bugs with trigger words
- Dependency Web: blast radius if you change X

The Failure Memory layer is the interesting part. Claude checks your message
against trigger words before every response. Ask about QToolButton and it
warns you: "We spent 2 hours on this in F003 — use QPushButton instead."

Real test: 484k chars → 11k chars (97.6% reduction, 41× smaller).
Works with any Claude.ai chat. Export via bookmarklet → run indexer.py.

GitHub: [link] | Live demo: [marketing page link]
```

---

### C. Reddit — r/ClaudeAI, r/LocalLLaMA, r/MachineLearning
**Goal:** Community validation, niche traffic

**Post template for r/ClaudeAI:**
```
Title: I got tired of re-explaining my project every new Claude chat — 
       so I built something

[Screenshot of token comparison visual]

Every time I hit the context limit I'd spend 10 minutes re-explaining
everything to a new chat. Decisions made, bugs fixed, approaches rejected.

I built Mnemo — it compresses your full chat history into structured YAML
that fits in a system prompt. The wild part: it captures "Failure Memory" —
past mistakes with trigger words so Claude warns you before you repeat them.

484k char chat → 11k char YAML in one command.

[GitHub link]
```

**Post template for r/LocalLLaMA:**
Focus on: offline model support (phi4-mini via Ollama), no cloud dependency, YAML portability

---

### D. Twitter/X — Thread Strategy
**Goal:** Viral reach, developer audience

**Thread 1 — The Problem:**
```
Tweet 1:
Every time I start a new Claude.ai chat for my project, I spend 10 minutes 
re-explaining:
• What the project does
• What I've already tried
• What broke and why
• What decisions were made

This is insane. I fixed it. 🧵

Tweet 2:
I built Mnemo.
It compresses your entire Claude.ai chat history into a YAML file.

484,000 chars → 11,000 chars
97.6% token reduction
41× smaller

[Token comparison image]

Tweet 3:
But the real magic: FAILURE MEMORY.

Every past bug gets stored with:
• What failed
• The exact error  
• Time wasted
• TRIGGER WORDS

When you mention a trigger word, Claude warns you BEFORE you waste hours again.

[Failure memory screenshot]

Tweet 4:
The YAML has 5 layers:

🧬 Exon — decisions + constants
🔵 Nodes — components + connections  
📊 Diffs — what changed and why
⚠️ Failure Memory — past bugs + triggers
🕸️ Dependency Web — blast radius per component

[Architecture screenshot]

Tweet 5:
Three commands to never lose context again:

1. Export your chat (bookmarklet in browser)
2. python indexer.py my_chat.md --provider openai
3. Paste system_prompt.md into new Claude chat

That's it. Claude has full memory.

GitHub: [link]
```

**Thread 2 — The Failure Memory hook (more viral potential):**
```
Tweet 1:
I wasted 3 hours because Claude suggested the same broken approach twice.

So I built something that makes Claude remember its own mistakes. 
Here's how it works 🧵

[leads into Failure Memory explanation]
```

---

### E. Dev.to / Hashnode — Long-form article
**Goal:** SEO, long-tail discovery, credibility

**Article title:** *"How I Compressed 484,000 Characters of Claude.ai Chat into 11,000 Characters — and Made Claude Remember Its Own Mistakes"*

**Outline:**
1. The problem: context window resets
2. What other tools get wrong (code-only, no failure tracking)
3. The 5-layer GTF architecture
4. Failure Memory: the layer no one else has
5. Real benchmark: BioPrism project
6. How to use it in 3 steps
7. MCP integration for Claude Desktop

**Include:** All marketing page screenshots as inline images

---

### F. Product Hunt Launch
**Goal:** Early adopter spike, "product of the day" badge

**Tagline:** *"Compress Claude.ai chat history 97% — with Failure Memory"*

**Description:**
> Mnemo turns your Claude.ai conversation history into a structured 5-layer YAML file. 97.6% token reduction. Works with any project. The unique feature: Failure Memory — Claude checks trigger words before every response and warns you before you repeat past mistakes. Export via bookmarklet → one Python command → permanent memory.

**Hunter:** Self-hunt. Prep upvote network in advance.

**Timing:** Tuesday morning ET, coordinate with HN Show HN post (same week, different days)

---

## 5. VISUAL ASSETS (Generated from Landing Page)

All screenshots taken from `marketing/index.html` at localhost:7842.

### Asset 1 — Hero Section
> **"Give Claude Permanent Memory"**
> Context window bars: 121,054 tokens (red, large) vs 2,931 tokens (purple, tiny)
> Use for: Twitter header, GitHub README hero, HN post thumbnail

### Asset 2 — Stats Strip + Problem Panel
> Numbers: 97.6% · 41× · 9/9 · 0 MCP setup
> Two-chat comparison: "Starting fresh, please re-explain..." vs instant context
> Use for: Reddit posts, Dev.to article

### Asset 3 — 5-Layer Architecture Cards
> Visual cards: Exon (green) · Nodes (blue) · Diffs (yellow) · Failure Memory (orange) · Dependency Web (purple)
> Use for: Twitter thread image 4, Product Hunt media

### Asset 4 — Token Comparison Visual
> 121,054 red pixel blocks → 2,931 purple pixel blocks
> "97.6% token reduction · 41× smaller · 118,123 tokens saved" pill
> Use for: Twitter thread image 2, strongest visual proof

### Asset 5 — Failure Memory Demo
> Terminal card: "FAILURE MEMORY TRIGGERED — F003 — QToolButton — 2 hours"
> Claude response: "I've flagged this before we proceed. Here's the safe implementation..."
> Use for: Twitter thread image 3, most viral-worthy visual

### Asset 6 — Comparison Table
> Mnemo ✓ vs Graphify ✗ vs Graphiti/Zep ✗ vs MemoryOS ✗
> Unique rows: "Works in Claude.ai UI", "Failure Memory", "Cross-session YAML portability"
> Use for: HN first comment, landing page social proof

### Asset 7 — CTA + How It Works
> "Three commands. Full context. Forever."
> "Start in 60 seconds" with code snippet
> Use for: Product Hunt tagline, email footer

---

## 6. CONTENT CALENDAR (4-Week Launch Plan)

### Week 1 — Foundation
- [ ] Polish GitHub README with screenshots
- [ ] Add live demo link to repo
- [ ] Record 60-second screen recording: export → run → paste → Claude knows everything
- [ ] Pre-write all social copy

### Week 2 — Soft Launch
- [ ] Post to r/ClaudeAI and r/LocalLLaMA
- [ ] Publish Dev.to article
- [ ] Post Twitter thread 1 (Problem thread)

### Week 3 — HN Show HN
- [ ] Tuesday 9am ET: Submit Show HN
- [ ] Be online for first 3 hours to respond to comments
- [ ] Cross-post to Twitter with HN link

### Week 4 — Product Hunt
- [ ] Tuesday launch
- [ ] Coordinate upvotes from Dev.to / HN audience
- [ ] Post Twitter thread 2 (Failure Memory hook — most viral)

---

## 7. ELEVATOR PITCHES

### 15-second version
> "Mnemo is a Python script that turns your entire Claude.ai project chat into a tiny YAML file. 97% smaller. Paste it into a new chat and Claude instantly has full project memory — including a failure log that warns you before you repeat past mistakes."

### 30-second version
> "Every time you hit Claude's context limit, you lose everything — decisions made, bugs fixed, approaches that failed. Mnemo compresses that entire history into a structured YAML. Five layers: decisions, components, what changed, failure patterns with trigger words, and blast-radius dependencies. The failure layer is unique — Claude actively intercepts your messages and warns you if you're about to repeat something that already cost you hours. 484k chars became 11k chars in my real test. It's open source, works offline, and takes 3 commands to set up."

### Tweet-length (280 chars)
> "Compressed 484k chars of Claude.ai project history → 11k chars YAML. 97.6% smaller. Includes Failure Memory: Claude now warns before you repeat past mistakes. Three commands. Full context. Forever. github.com/[user]/chat-gtf"

---

## 8. OBJECTION HANDLING

| Objection | Response |
|-----------|----------|
| "Just use Projects feature" | Claude Projects resets context per session. GTF persists across ALL sessions forever, is portable, and adds Failure Memory. |
| "I'll just paste my README" | README has no failure patterns, no trigger words, no blast radius, no diffs. GTF is structured memory, not documentation. |
| "Needs API key" | Yes, one-time indexing costs ~$0.05 on GPT-3.5. After that: zero cost. The YAML runs offline forever. |
| "Too much setup" | 3 commands. No server, no database, no cloud. Paste one file into Claude's system prompt. Done. |
| "What about privacy?" | Your chat goes to OpenAI/Anthropic once for indexing. The output YAML stays on your machine forever. Use `--provider anthropic` for same-company privacy. |

---

## 9. NAMING & BRAND NOTES

- **Name:** Mnemo (Gene Transfer Format — borrowed from bioinformatics, intentional nerd signal)
- **Tagline:** "Give Claude Permanent Memory"  
- **Secondary tagline:** "Three commands. Full context. Forever."
- **Color palette:** Purple (#7c3aed) primary, green (#10b981) for success/proof, orange/amber for failure warnings
- **Tone:** Direct, technical, slightly irreverent. No corporate speak. Speak like a dev who solved their own problem.

---

## 10. QUICK WINS (Do this week)

1. **Tweet the token comparison visual** — highest visual impact, easiest to make viral
2. **Post to r/ClaudeAI** — most targeted audience, lowest barrier
3. **Add `examples/my_chat_gtf.yaml` to GitHub README** — real proof > any claim
4. **Write the Dev.to article** — SEO + credibility foundation
5. **Record 60-second demo video** — embed in README, tweet it, add to Product Hunt

---

*Strategy version 1.0 — built for Mnemo open-source launch*
*Generated: 2026-04-27*
