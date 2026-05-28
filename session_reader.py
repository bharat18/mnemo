#!/usr/bin/env python3
"""
session_reader.py — Convert Claude Code JSONL session → plain chat text

Usage (standalone):
  python session_reader.py <session.jsonl> [output.md]

Called by mcp_server.py gtf_capture_session / gtf_checkpoint tools.
"""

import json
import sys
from pathlib import Path


# ── Smart filter ──────────────────────────────────────────────────────────────

def smart_filter_text(text: str, max_code_lines: int = 8) -> str:
    """
    Trim large code blocks from Claude responses.
    Blocks > max_code_lines → keep first 3 + last 3 lines, skip the middle.
    Preserves all conversational text, decisions, and explanations.
    Result: ~60-70% size reduction on code-heavy sessions.
    """
    lines   = text.split("\n")
    result  = []
    in_code = False
    code_buf: list[str] = []

    for line in lines:
        stripped = line.strip()

        if not in_code and stripped.startswith("```"):
            in_code = True
            result.append(line)   # opening fence
            code_buf = []

        elif in_code and stripped.startswith("```"):
            in_code = False
            if len(code_buf) > max_code_lines:
                kept   = 3
                middle = len(code_buf) - kept * 2
                result.extend(code_buf[:kept])
                result.append(f"    ... [{middle} lines omitted] ...")
                result.extend(code_buf[-kept:])
            else:
                result.extend(code_buf)
            result.append(line)   # closing fence
            code_buf = []

        elif in_code:
            code_buf.append(line)

        else:
            result.append(line)

    # Unclosed code block at end of message
    if code_buf:
        result.extend(code_buf)

    return "\n".join(result)


# ── Main reader ───────────────────────────────────────────────────────────────

def jsonl_to_chat(
    jsonl_path: "str | Path",
    max_chars:    int  = 400_000,
    smart_filter: bool = True,
    start_line:   int  = 0,
) -> "tuple[str, str, int]":
    """
    Read a Claude Code .jsonl session file.

    Parameters
    ----------
    jsonl_path   : path to the .jsonl session file
    max_chars    : hard cap on total output chars (keep last N)
    smart_filter : strip large code blocks to reduce size ~60-70%
    start_line   : skip the first N raw lines — used for incremental/delta capture

    Returns
    -------
    (chat_text, detected_project_root, total_lines_read)

    chat_text             — Human/Claude turn format, ready for indexer.py
    detected_project_root — cwd extracted from the first user message
    total_lines_read      — total raw JSONL lines in file (store in meta for next delta)
    """
    path         = Path(jsonl_path)
    turns        = []
    project_root = ""
    total_lines  = 0

    with open(path, encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            total_lines += 1

            # Skip already-processed lines (incremental mode)
            if total_lines <= start_line:
                continue

            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            t = obj.get("type", "")
            if t not in ("user", "assistant"):
                continue

            msg  = obj.get("message", {})
            role = msg.get("role", t)

            # Extract text — skip tool_use / tool_result blocks
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "text":
                        text_parts.append(c.get("text", ""))
                text = "\n".join(text_parts).strip()
            else:
                text = str(content).strip()

            if not text:
                continue

            # Smart filter on Claude responses (code-heavy)
            if smart_filter and role == "assistant":
                text = smart_filter_text(text)
                if not text:
                    continue

            # First user message's cwd = project root
            if role == "user" and not project_root:
                project_root = obj.get("cwd", "")

            label = "**Human**" if role == "user" else "**Claude**"
            turns.append(f"{label}:\n{text}\n\n---\n")

    chat_text = "\n".join(turns)

    # Truncate if over max_chars (keep LAST N chars — most recent context)
    if len(chat_text) > max_chars:
        chat_text = chat_text[-max_chars:]

    return chat_text, project_root, total_lines


# ── Session finder ────────────────────────────────────────────────────────────

def find_latest_session(
    project_dir_encoded: "str | None" = None,
) -> "tuple[Path | None, str]":
    """
    Find the most recently modified .jsonl session file.
    If project_dir_encoded is given, look in that project's folder.
    Otherwise scan all projects under ~/.claude/projects/.

    Returns (jsonl_path, project_root_guess).
    Note: project_root_guess is a rough decode of the folder name.
          The real root comes from the JSONL cwd field via jsonl_to_chat().
    """
    projects_root = Path.home() / ".claude" / "projects"
    if not projects_root.exists():
        return None, ""

    if project_dir_encoded:
        dirs = [projects_root / project_dir_encoded]
    else:
        dirs = [d for d in projects_root.iterdir() if d.is_dir()]

    best_file: "Path | None" = None
    best_mtime = 0.0

    for d in dirs:
        for f in d.glob("*.jsonl"):
            try:
                mt = f.stat().st_mtime
                if mt > best_mtime:
                    best_mtime = mt
                    best_file  = f
            except OSError:
                pass

    if best_file is None:
        return None, ""

    folder_name = best_file.parent.name

    # Decode Claude Code's encoded folder name back to a path.
    # Windows: "C--Users-foo-Desktop-Proj" → "C:\Users\foo\Desktop\Proj"
    # Mac/Linux: "-Users-foo-Desktop-Proj" → "/Users/foo/Desktop/Proj"
    # NOTE: this is a rough guess only — hyphens in folder names cause ambiguity.
    # The real project root always comes from the JSONL cwd field.
    if sys.platform == "win32":
        # Drive letter before "--", then path components separated by "-"
        project_root_guess = folder_name.replace("--", ":\\").replace("-", "\\")
    else:
        # Leading "-" represents the root "/"; remaining "-" are path separators
        project_root_guess = "/" + folder_name.lstrip("-").replace("-", "/")

    return best_file, project_root_guess


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python session_reader.py <session.jsonl> [output.md]")
        sys.exit(1)

    jsonl_path = sys.argv[1]
    out_path   = sys.argv[2] if len(sys.argv) > 2 else None

    chat_text, project_root, total_lines = jsonl_to_chat(jsonl_path)

    if out_path:
        Path(out_path).write_text(chat_text, encoding="utf-8")
        print(f"Written {len(chat_text):,} chars → {out_path}")
        print(f"Project root : {project_root}")
        print(f"Total lines  : {total_lines:,}")
    else:
        print(chat_text[:2000])
        print(f"\n[Project root  : {project_root}]")
        print(f"[Total chars   : {len(chat_text):,}]")
        print(f"[Total lines   : {total_lines:,}]")
