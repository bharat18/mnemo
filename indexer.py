#!/usr/bin/env python3
"""
indexer.py — Convert exported Claude.ai chat history into chat_gtf.yaml

Usage:
  python indexer.py chat_export.md
  python indexer.py chat_export.md --mode hybrid
  python indexer.py chat_export.md --provider openai --enrich
  python indexer.py chat_export.md --output myproject.yaml
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# Force UTF-8 on Windows so Unicode in chat content doesn't crash stdout
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import yaml

# ── Colorama (optional — graceful fallback if not installed) ─────────────────
try:
    from colorama import init as _colorama_init, Fore, Style
    _colorama_init(autoreset=True)
    C_GREEN  = Fore.GREEN
    C_YELLOW = Fore.YELLOW
    C_RED    = Fore.RED
    C_CYAN   = Fore.CYAN
    C_BLUE   = Fore.BLUE
    C_RESET  = Style.RESET_ALL
    C_BOLD   = Style.BRIGHT
except ImportError:
    C_GREEN = C_YELLOW = C_RED = C_CYAN = C_BLUE = C_RESET = C_BOLD = ""

# ── Rate-limit settings ───────────────────────────────────────────────────────
MAX_CHUNK_CHARS = 80_000   # ~20k tokens — safe under 30k TPM free tier
# Delay between chunks: gpt-4o-mini / claude-haiku have high rate limits → 5s is enough.
# gpt-4o / claude-sonnet on free tier may need longer — override with --chunk-delay if needed.
CHUNK_DELAY_SEC = 5

# =============================================================================
# PROMPTS
# =============================================================================

EXTRACTION_PROMPT = """\
You are extracting structured project memory from a Claude.ai chat export.
Return ONLY valid JSON. No markdown fences, no comments, no trailing commas.

=== OUTPUT STRUCTURE ===
{{
  "meta": {{
    "project": "<inferred project name>",
    "stack": ["<tech>"],
    "created": "YYYY-MM",
    "last_updated": "YYYY-MM",
    "source_chats": ["<filename>"]
  }},
  "exons": {{
    "decisions": ["<final committed decision — specific and actionable>"],
    "constants": {{"KEY": "value"}},
    "open_problems": ["<unresolved issue or pending task>"],
    "rejected_approaches": ["<approach explicitly dropped>"],
    "current_state": "<one sentence — where the project is right now>"
  }},
  "nodes": {{
    "EntityName": {{
      "type": "component|decision|constant|person|concept",
      "connects_to": ["<OtherEntityName>"],
      "decision": "<what was decided about this entity>",
      "state": "active|deprecated|planned",
      "file": "path/to/file or null"
    }}
  }},
  "diffs": {{
    "EntityName": {{
      "v1": "<what was tried or believed first>",
      "current": "v2",
      "why_changed": "<exact reason the approach changed>"
    }}
  }},
  "failure_memory": [
    {{
      "id": "F001",
      "what_tried": "<specific approach attempted>",
      "exact_error": "<exact error message, traceback, or symptom>",
      "time_wasted": "<estimate — '2 hours', 'unknown', etc.>",
      "trigger_words": ["<specific-term>", "<another-specific-term>"],
      "never_again": true,
      "unless": "<condition under which this is OK, or null>",
      "code_pattern_to_avoid": "<verbatim bad code from chat, or null>",
      "safe_pattern": "<verbatim fixed code from chat, or null>"
    }}
  ],
  "dependencies": {{
    "EntityName": {{
      "if_changed": ["<what else breaks>"],
      "safe_to_change": false,
      "blast_radius": "HIGH|MEDIUM|LOW"
    }}
  }}
}}

=== LAYER-BY-LAYER RULES ===

NODES — be EXHAUSTIVE:
- Extract EVERY named entity: components, files, modules, classes, APIs, tools, libraries, config values, concepts
- Include anything mentioned 2+ times OR that has a file path, decision, or connection attached
- WHEN IN DOUBT — INCLUDE IT. Missing nodes = lost context in the next chat.
- connects_to: list everything this entity talks to or depends on

DIFFS — scan for change signals:
- Look for phrases: "switched to", "originally", "instead we", "previously", "changed from",
  "replaced", "now using", "updated to", "we moved to", "decided against"
- Each such phrase = a diff entry
- v1 = what was believed/tried first; why_changed = the ACTUAL reason (not just "better")

FAILURE MEMORY — miss nothing:
- Capture every: bug, wrong library choice, architecture mistake, environment issue,
  wasted effort, error message, frozen UI, failed approach
- trigger_words must be SPECIFIC (e.g. "uuid.getnode" not "machine id")
- time_wasted: estimate from context ("spent hours" → "~3 hours"; "wasted a day" → "~8 hours")
- code_pattern_to_avoid: if actual broken code appears in the chat, copy it VERBATIM here
- safe_pattern: if the fix code appears in the chat, copy it VERBATIM here
- unless: when would this EVER be OK? null if truly never

DECISIONS — only final committed choices:
- Not exploratory ideas, not "maybe we should", only "we decided to"

CONSTANTS — pinned values never to change without explicit instruction:
- API endpoints, model names, version pins, file paths, thresholds

If a field has nothing, use [] or {{}} or null. Never omit keys.

=== CHAT EXPORT ===
{chat}
"""

RETRY_PROMPT = """\
Your previous response was not valid JSON. Try again.
Return ONLY valid JSON — no markdown fences, no comments, no trailing commas.
Same structure as before.

=== CHAT EXPORT ===
{chat}
"""

ENRICHMENT_PROMPT = """\
A failure was extracted from a chat but is missing code examples.
Find the relevant code in the chat below and return ONLY a JSON object.

Failure to enrich:
  what_tried : {what_tried}
  exact_error: {exact_error}

Task: Find in the chat below:
  1. The EXACT broken code that caused this failure → "code_pattern_to_avoid"
  2. The EXACT fixed/correct code that replaced it → "safe_pattern"

Copy code VERBATIM from the chat. If no code exists, use null.
Return ONLY:
{{"code_pattern_to_avoid": "...", "safe_pattern": "..."}}

=== RELEVANT CHAT SECTION ===
{chunk}
"""


# =============================================================================
# PROVIDER ABSTRACTION
# =============================================================================

def get_client(provider: str):
    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError:
            _die("openai package not installed. Run: pip install openai")
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            _die("OPENAI_API_KEY not set.\nSet it with: export OPENAI_API_KEY=sk-...")
        return OpenAI(api_key=key)
    else:
        try:
            import anthropic as _ant
        except ImportError:
            _die("anthropic package not installed. Run: pip install anthropic")
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            _die("ANTHROPIC_API_KEY not set.\nSet it with: export ANTHROPIC_API_KEY=sk-ant-...")
        return _ant.Anthropic(api_key=key)


def call_llm(client, prompt: str, model: str, provider: str, max_tokens: int = 2048) -> str:
    if provider == "openai":
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    else:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()


# =============================================================================
# IMPROVEMENT 1 — SMART TURN-BASED CHUNKING
# =============================================================================

# Patterns that signal the start of a new conversation turn
_TURN_PATTERNS = re.compile(
    r"\n(?="
    r"\*\*Human\*\*[:\s]"
    r"|\*\*User\*\*[:\s]"
    r"|\*\*Claude\*\*[:\s]"
    r"|\*\*Assistant\*\*[:\s]"
    r"|Human[:\s]"
    r"|User[:\s]"
    r"|---\n"
    r")",
    re.MULTILINE,
)


def chunk_on_turns(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """
    Two-pass chunker:
      Pass 1 — Split at conversation turn boundaries (clean message splits).
      Pass 2 — Any chunk still over max_chars gets sub-split at paragraph
               boundaries. Guarantees every chunk stays within the token limit.
    """
    if len(text) <= max_chars:
        return [text]

    # ── Pass 1: split at turn boundaries ────────────────────────────────────
    boundaries = [m.start() for m in _TURN_PATTERNS.finditer(text)]

    if not boundaries:
        return _group_into_chunks(re.split(r"\n\n+", text), max_chars)

    # Collect raw per-turn segments
    raw: list[str] = []
    prev = 0
    for b in boundaries:
        seg = text[prev:b].strip()
        if seg:
            raw.append(seg)
        prev = b
    tail = text[prev:].strip()
    if tail:
        raw.append(tail)

    # Merge adjacent small turns into chunks under max_chars
    pass1: list[str] = []
    current = ""
    for seg in raw:
        if len(current) + len(seg) + 2 <= max_chars:
            current = (current + "\n\n" + seg).strip() if current else seg
        else:
            if current:
                pass1.append(current)
            current = seg
    if current:
        pass1.append(current)

    # ── Pass 2: sub-split any chunk still over limit ─────────────────────────
    result: list[str] = []
    for chunk in pass1:
        if len(chunk) <= max_chars:
            result.append(chunk)
        else:
            # Oversized chunk (e.g. one very long Claude reply) — split by paragraph
            sub = _group_into_chunks(re.split(r"\n\n+", chunk), max_chars)
            result.extend(sub)

    return [c for c in result if c] or [text]


def _group_into_chunks(pieces: list[str], max_chars: int) -> list[str]:
    chunks, current = [], ""
    for piece in pieces:
        if len(current) + len(piece) + 2 > max_chars and current:
            chunks.append(current.strip())
            current = piece
        else:
            current += ("\n\n" if current else "") + piece
    if current.strip():
        chunks.append(current.strip())
    return chunks


# =============================================================================
# CORE EXTRACTION
# =============================================================================

def read_chat(path: str) -> str:
    p = Path(path)
    if not p.exists():
        _die(f"Chat file '{path}' not found.\nUsage: python indexer.py <chat_export.md>")
    return p.read_text(encoding="utf-8")


def parse_json_response(raw: str) -> dict:
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)


def extract_with_retry(client, chunk: str, model: str, provider: str) -> dict:
    prompt = EXTRACTION_PROMPT.format(chat=chunk)
    raw = call_llm(client, prompt, model, provider)
    try:
        return parse_json_response(raw)
    except (json.JSONDecodeError, ValueError):
        _warn("Extraction malformed — retrying with stricter prompt...")
        raw2 = call_llm(client, RETRY_PROMPT.format(chat=chunk), model, provider)
        return parse_json_response(raw2)


def merge_chunks(chunks_data: list[dict]) -> dict:
    if len(chunks_data) == 1:
        return chunks_data[0]

    merged = chunks_data[0]
    for c in chunks_data[1:]:
        ex = c.get("exons", {})
        for key in ("decisions", "open_problems", "rejected_approaches"):
            merged["exons"][key] = _dedup(
                merged["exons"].get(key, []) + ex.get(key, [])
            )
        merged["exons"]["constants"].update(ex.get("constants", {}))
        if ex.get("current_state"):
            merged["exons"]["current_state"] = ex["current_state"]
        merged["nodes"].update(c.get("nodes", {}))
        merged["diffs"].update(c.get("diffs", {}))
        merged["failure_memory"].extend(c.get("failure_memory", []))
        merged["dependencies"].update(c.get("dependencies", {}))

    _renumber_failures(merged)
    return merged


def merge_with_existing(new_data: dict, existing_path: str) -> dict:
    """
    Merge a freshly-extracted GTF dict into an already-saved GTF YAML.
    Used by incremental / checkpoint capture so old context is preserved.

    Strategy:
    - exons.decisions / open_problems / rejected_approaches : append + dedup
    - exons.constants      : update (new values override)
    - exons.current_state  : overwrite with latest
    - nodes                : update (new node data overrides old for same key)
    - diffs                : update
    - failure_memory       : append new failures, dedup by trigger_words set
    - dependencies         : update
    - meta                 : preserve existing project_root; update last_updated
    """
    try:
        with open(existing_path, encoding="utf-8") as fh:
            existing = yaml.safe_load(fh) or {}
    except Exception:
        return new_data   # can't read existing — just use new

    merged = {k: v for k, v in existing.items()}   # shallow copy

    # ── Exons ────────────────────────────────────────────────────────────────
    ex_new = new_data.get("exons", {})
    ex_old = merged.setdefault("exons", {})
    for key in ("decisions", "open_problems", "rejected_approaches"):
        ex_old[key] = _dedup(ex_old.get(key, []) + ex_new.get(key, []))
    ex_old.setdefault("constants", {}).update(ex_new.get("constants", {}))
    if ex_new.get("current_state"):
        ex_old["current_state"] = ex_new["current_state"]

    # ── Nodes / Diffs / Dependencies ─────────────────────────────────────────
    merged.setdefault("nodes", {}).update(new_data.get("nodes", {}))
    merged.setdefault("diffs", {}).update(new_data.get("diffs", {}))
    merged.setdefault("dependencies", {}).update(new_data.get("dependencies", {}))

    # ── Failure memory — append only truly new failures (dedup by triggers) ──
    existing_trigger_sets = {
        frozenset(str(w).lower() for w in f.get("trigger_words", []))
        for f in merged.get("failure_memory", [])
    }
    new_failures = [
        f for f in new_data.get("failure_memory", [])
        if frozenset(str(w).lower() for w in f.get("trigger_words", []))
           not in existing_trigger_sets
    ]
    merged.setdefault("failure_memory", []).extend(new_failures)
    _renumber_failures(merged)

    # ── Meta — preserve project_root; update last_updated ────────────────────
    meta_new = new_data.get("meta", {})
    meta_old = merged.setdefault("meta", {})
    if meta_new.get("last_updated"):
        meta_old["last_updated"] = meta_new["last_updated"]
    if "project_root" not in meta_old and meta_new.get("project_root"):
        meta_old["project_root"] = meta_new["project_root"]

    return merged


# =============================================================================
# IMPROVEMENT 4 — FAILURE ENRICHMENT PASS (--enrich)
# =============================================================================

def enrich_failures(
    client, data: dict, chunks: list[str], model: str, provider: str
) -> dict:
    """
    For each failure where code_pattern_to_avoid is null,
    run a focused mini-call to find the actual verbatim code.

    Quality guards:
    - max_tokens raised to 1024 (was 512) so code isn't truncated mid-line
    - If avoid == fix after enrichment, discard the result (LLM found no diff)
    - Only update a field if the new value is strictly longer than the old one
    """
    failures = data.get("failure_memory", [])
    candidates = [f for f in failures if not f.get("code_pattern_to_avoid")]

    if not candidates:
        _ok("All failures already have code patterns — skipping enrichment.")
        return data

    _info(f"Enriching {len(candidates)} failure(s) with code patterns...")

    for f in candidates:
        best_chunk = _find_best_chunk(f, chunks)
        if not best_chunk:
            continue

        prompt = ENRICHMENT_PROMPT.format(
            what_tried=f.get("what_tried", ""),
            exact_error=f.get("exact_error", ""),
            chunk=best_chunk[:40_000],
        )
        try:
            # 1024 tokens — enough for a 20-line code block without truncation
            raw = call_llm(client, prompt, model, provider, max_tokens=1024)
            enriched = parse_json_response(raw)

            new_bad = (enriched.get("code_pattern_to_avoid") or "").strip()
            new_fix = (enriched.get("safe_pattern") or "").strip()

            # Quality guard: if LLM returned identical avoid/fix, it found nothing real
            if new_bad and new_fix and new_bad == new_fix:
                _warn(f"  {f['id']} avoid==fix after enrichment — discarding")
                new_bad = new_fix = ""

            old_bad = f.get("code_pattern_to_avoid") or ""
            old_fix = f.get("safe_pattern") or ""

            if new_bad and len(new_bad) > len(old_bad):
                f["code_pattern_to_avoid"] = new_bad
                _ok(f"  {f['id']} code_pattern: {len(old_bad)} -> {len(new_bad)} chars")
            else:
                _info(f"  {f['id']} code_pattern: no improvement — kept original")

            if new_fix and len(new_fix) > len(old_fix):
                f["safe_pattern"] = new_fix

        except Exception as e:
            _warn(f"  {f['id']} enrichment failed — {e}")

        time.sleep(15)

    return data


def _find_best_chunk(failure: dict, chunks: list[str]) -> str | None:
    triggers = failure.get("trigger_words", [])
    what_tried = failure.get("what_tried", "").lower()
    for chunk in chunks:
        cl = chunk.lower()
        if any(t.lower() in cl for t in triggers) or what_tried[:30] in cl:
            return chunk
    return chunks[0] if chunks else None


# =============================================================================
# IMPROVEMENT 3 — RUN AUTO
# =============================================================================

def run_auto(
    client, chat: str, model: str, provider: str, enrich: bool = False
) -> dict:
    chunks = chunk_on_turns(chat)
    n = len(chunks)

    if n > 1:
        _info(f"Chat split into {n} chunks (turn-based, ~{MAX_CHUNK_CHARS//4:,} tokens each)")
    else:
        _info("Chat fits in a single chunk")

    results = []
    for i, chunk in enumerate(chunks, 1):
        _info(f"  Extracting chunk {i}/{n}  ({len(chunk):,} chars)...")
        results.append(extract_with_retry(client, chunk, model, provider))
        if i < n:
            _info(f"  Waiting {CHUNK_DELAY_SEC}s for rate-limit reset...")
            time.sleep(CHUNK_DELAY_SEC)

    data = merge_chunks(results)

    if enrich:
        _info("Running failure enrichment pass...")
        time.sleep(CHUNK_DELAY_SEC)   # fresh TPM window
        data = enrich_failures(client, data, chunks, model, provider)

    return data


# =============================================================================
# IMPROVEMENT 5 — HYBRID MODE UI OVERHAUL
# =============================================================================

def run_hybrid(
    client, chat: str, model: str, provider: str, enrich: bool = False
) -> dict:
    _header("HYBRID MODE")
    _info("Step 1/3 — Auto-extracting all layers from your chat...")
    data = run_auto(client, chat, model, provider, enrich=False)

    # Show auto-extracted failures so user doesn't re-enter what's already caught
    failures = data.get("failure_memory", [])
    print()
    _header(f"Auto-extracted {len(failures)} failure(s)")
    for f in failures:
        print(f"  {C_GREEN}{f['id']}{C_RESET}  {f['what_tried']}")
        print(f"       error   : {C_YELLOW}{f['exact_error']}{C_RESET}")
        print(f"       triggers: {', '.join(f.get('trigger_words', []))}")
        has_code = bool(f.get("code_pattern_to_avoid"))
        code_status = f"{C_GREEN}✓ code captured{C_RESET}" if has_code else f"{C_YELLOW}✗ no code snippet{C_RESET}"
        print(f"       code    : {code_status}")
        print()

    # Manual additions
    print()
    _header("Step 2/3 — Add any failures NOT in the list above")
    print(f"  {C_CYAN}Press Enter on empty 'what_tried' to finish.{C_RESET}\n")
    manual = _collect_manual_failures(start_idx=len(failures) + 1)

    # Merge manual into data
    existing = {f.get("what_tried") for f in failures}
    for mf in manual:
        if mf["what_tried"] not in existing:
            data["failure_memory"].append(mf)

    _renumber_failures(data)

    if enrich:
        _info("Step 3/3 — Running failure enrichment pass...")
        time.sleep(CHUNK_DELAY_SEC)
        chunks = chunk_on_turns(chat)
        data = enrich_failures(client, data, chunks, model, provider)
    else:
        _info("Step 3/3 — Skipping enrichment (use --enrich to fill code patterns)")

    return data


def _collect_manual_failures(start_idx: int = 1) -> list[dict]:
    failures, idx = [], start_idx
    while True:
        what = _prompt(f"[F{idx:03d}] What was tried? (blank = done)").strip()
        if not what:
            break
        error    = _prompt("  Exact error / symptom").strip()
        time_w   = _prompt("  Time wasted (e.g. '2 hours')").strip()
        triggers = _prompt("  Trigger words (comma-separated)").strip()
        unless   = _prompt("  Unless condition (blank = never)").strip() or None
        code_bad = _prompt("  Bad code snippet (blank = skip)").strip() or None
        code_fix = _prompt("  Safe code snippet (blank = skip)").strip() or None
        failures.append({
            "id":                    f"F{idx:03d}",
            "what_tried":            what,
            "exact_error":           error,
            "time_wasted":           time_w,
            "trigger_words":         [t.strip() for t in triggers.split(",") if t.strip()],
            "never_again":           True,
            "unless":                unless,
            "code_pattern_to_avoid": code_bad,
            "safe_pattern":          code_fix,
        })
        idx += 1
    return failures


# =============================================================================
# OUTPUT
# =============================================================================

def write_yaml(data: dict, output: str) -> None:
    with open(output, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)


def print_summary(data: dict, output: str, input_chars: int) -> None:
    exons    = data.get("exons", {})
    failures = data.get("failure_memory", [])
    nodes    = data.get("nodes", {})
    diffs    = data.get("diffs", {})

    out_chars   = Path(output).stat().st_size if Path(output).exists() else 0
    in_tokens   = input_chars // 4
    out_tokens  = out_chars // 4
    reduction   = (1 - out_tokens / in_tokens) * 100 if in_tokens else 0

    null_codes  = sum(1 for f in failures if not f.get("code_pattern_to_avoid"))
    has_code    = len(failures) - null_codes

    print()
    _header("DONE")
    print(f"  Output file : {C_BOLD}{output}{C_RESET}")
    print(f"  Decisions   : {len(exons.get('decisions', []))}")
    print(f"  Nodes       : {len(nodes)}")
    print(f"  Diffs       : {len(diffs)}")
    print(f"  Failures    : {len(failures)}  "
          f"({C_GREEN}{has_code} with code snippets{C_RESET}, "
          f"{C_YELLOW}{null_codes} without{C_RESET})")
    print(f"  Open probs  : {len(exons.get('open_problems', []))}")
    print(f"  Tokens in   : ~{in_tokens:,}")
    print(f"  Tokens out  : ~{out_tokens:,}")
    print(f"  Reduction   : {C_GREEN}{reduction:.1f}%{C_RESET}  "
          f"({C_BOLD}{in_tokens // out_tokens if out_tokens else '∞'}x{C_RESET} smaller)")

    if null_codes:
        print()
        _warn(f"{null_codes} failure(s) have no code snippet. Run with --enrich to auto-fill.")


# =============================================================================
# HELPERS
# =============================================================================

def _die(msg: str) -> None:
    print(f"{C_RED}[ERROR]{C_RESET} {msg}", file=sys.stderr)
    sys.exit(1)

def _warn(msg: str) -> None:
    print(f"{C_YELLOW}[WARN]{C_RESET}  {msg}", file=sys.stderr)

def _ok(msg: str) -> None:
    print(f"{C_GREEN}[OK]{C_RESET}    {msg}")

def _info(msg: str) -> None:
    print(f"{C_CYAN}[>>]{C_RESET}    {msg}")

def _header(msg: str) -> None:
    print(f"\n{C_BOLD}{C_BLUE}{'='*52}{C_RESET}")
    print(f"{C_BOLD}{C_BLUE}  {msg}{C_RESET}")
    print(f"{C_BOLD}{C_BLUE}{'='*52}{C_RESET}")

def _prompt(label: str) -> str:
    return input(f"  {C_CYAN}{label}:{C_RESET} ")

def _dedup(lst: list) -> list:
    seen, out = set(), []
    for item in lst:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out

def _renumber_failures(data: dict) -> None:
    for i, f in enumerate(data.get("failure_memory", []), 1):
        f["id"] = f"F{i:03d}"


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Claude.ai chat export → chat_gtf.yaml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python indexer.py chat.md
  python indexer.py chat.md --provider openai --enrich
  python indexer.py chat.md --mode hybrid
  python indexer.py chat.md --output myproject.yaml
        """,
    )
    parser.add_argument("chat_file", help="Exported chat file (.md or .txt)")
    parser.add_argument(
        "--mode", choices=["auto", "hybrid"], default="auto",
        help="auto: fully automated | hybrid: review + add failures interactively (default: auto)",
    )
    parser.add_argument(
        "--output", default="chat_gtf.yaml",
        help="Output filename (default: chat_gtf.yaml)",
    )
    parser.add_argument(
        "--provider", choices=["anthropic", "openai"], default="anthropic",
        help="LLM provider: anthropic or openai (default: anthropic)",
    )
    parser.add_argument(
        "--model", default=None,
        help="Model override. Defaults: anthropic=claude-sonnet-4-6, openai=gpt-4o",
    )
    parser.add_argument(
        "--enrich", action="store_true",
        help="Run a focused pass to fill null code_pattern_to_avoid fields in failures",
    )
    parser.add_argument(
        "--project-root", default=None,
        help=(
            "Absolute path to the project folder on disk. "
            "Stored in meta.project_root so the GTF picker can show where each project lives. "
            "Example: --project-root C:/Users/you/Projects/MyApp"
        ),
    )
    parser.add_argument(
        "--merge", default=None,
        metavar="EXISTING_GTF",
        help=(
            "Path to an existing GTF YAML to merge into instead of overwriting. "
            "Used by incremental / checkpoint capture. "
            "New nodes/failures are appended; current_state is overwritten."
        ),
    )
    parser.add_argument(
        "--last-captured-lines", type=int, default=None,
        metavar="N",
        help=(
            "Total JSONL lines read in this capture. "
            "Stored in meta.last_captured_lines so the next delta capture "
            "knows where to start."
        ),
    )
    args = parser.parse_args()

    if args.model is None:
        args.model = "claude-sonnet-4-6" if args.provider == "anthropic" else "gpt-4o"

    chat = read_chat(args.chat_file)
    _header("CHAT GTF INDEXER")
    _info(f"File     : {args.chat_file}  ({len(chat):,} chars)")
    _info(f"Provider : {args.provider} / {args.model}")
    _info(f"Mode     : {args.mode}" + (" + enrich" if args.enrich else ""))
    _info(f"Output   : {args.output}")
    if args.project_root:
        _info(f"Root     : {args.project_root}")

    client = get_client(args.provider)

    if args.mode == "auto":
        data = run_auto(client, chat, args.model, args.provider, enrich=args.enrich)
    else:
        data = run_hybrid(client, chat, args.model, args.provider, enrich=args.enrich)

    # Store project root in meta if provided
    if args.project_root:
        data.setdefault("meta", {})["project_root"] = str(Path(args.project_root).resolve())

    # Store last-captured-lines for incremental / checkpoint delta tracking
    if args.last_captured_lines is not None:
        data.setdefault("meta", {})["last_captured_lines"] = args.last_captured_lines

    # Merge into existing GTF instead of overwriting (incremental mode)
    if args.merge and Path(args.merge).exists():
        _info(f"Merging into existing GTF: {args.merge}")
        data = merge_with_existing(data, args.merge)

    with open(args.output, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print_summary(data, args.output, len(chat))


if __name__ == "__main__":
    main()
