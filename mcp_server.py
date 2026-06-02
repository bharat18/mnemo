#!/usr/bin/env python3
"""
mcp_server.py — Mnemo MCP Server
Exposes chat_gtf.yaml as live tools for Claude Desktop / Claude Code.

Usage:
  python mcp_server.py [path/to/chat_gtf.yaml]

Default GTF file: chat_gtf.yaml in current directory.
"""

import asyncio
import json
import subprocess
import sys
import threading
import time as _time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ---------------------------------------------------------------------------
# GTF file helpers
# ---------------------------------------------------------------------------

# Runtime-switchable active GTF path.
# Starts from CLI arg (or default), can be changed live via gtf_switch tool.
_active_gtf_path: Path = (
    Path(sys.argv[1]) if len(sys.argv) > 1 else Path("chat_gtf.yaml")
)


def get_gtf_path() -> Path:
    return _active_gtf_path


def load_gtf() -> dict:
    p = get_gtf_path()
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_gtf(data: dict) -> None:
    with open(get_gtf_path(), "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# GTF Registry  (~/.mnemo_registry.json)
# Tracks every GTF file ever saved — depth-independent discovery
# ---------------------------------------------------------------------------

_REGISTRY_PATH = Path.home() / ".mnemo_registry.json"


def _registry_load() -> list[str]:
    """Return list of absolute path strings from registry."""
    try:
        if _REGISTRY_PATH.exists():
            return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _registry_add(path: Path) -> None:
    """Add a GTF path to the registry (dedup, persist)."""
    try:
        entries = _registry_load()
        key = str(path.resolve())
        if key not in entries:
            entries.append(key)
            _REGISTRY_PATH.write_text(
                json.dumps(entries, indent=2), encoding="utf-8"
            )
    except Exception:
        pass


def _registry_clean() -> None:
    """Remove entries whose files no longer exist."""
    try:
        entries = _registry_load()
        valid   = [p for p in entries if Path(p).exists()]
        if len(valid) != len(entries):
            _REGISTRY_PATH.write_text(
                json.dumps(valid, indent=2), encoding="utf-8"
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Project scanner  (flat glob + registry — depth-independent)
# ---------------------------------------------------------------------------

def _scan_gtf_files(extra_dirs: list[Path] | None = None) -> list[tuple[float, Path, dict]]:
    """Return list of (mtime, resolved_path, yaml_data) sorted newest-first."""
    seen: set[str] = set()
    results = []

    def _add(f: Path) -> None:
        key = str(f.resolve())
        if key in seen:
            return
        seen.add(key)
        try:
            mtime = f.stat().st_mtime
            with open(f, encoding="utf-8") as fh:
                meta = yaml.safe_load(fh) or {}
            results.append((mtime, f.resolve(), meta))
        except Exception:
            pass

    # ── 1. Registry — catches files saved to any depth ────────────────────────
    for path_str in _registry_load():
        p = Path(path_str)
        if p.exists():
            _add(p)

    # ── 2. Flat scan — common locations + 1 level subdirs ────────────────────
    base_dirs: list[Path] = [
        _active_gtf_path.parent,
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Downloads",
    ]
    if extra_dirs:
        base_dirs += extra_dirs

    for d in base_dirs:
        if not d.exists():
            continue
        patterns = [d.glob("*_gtf.yaml")]
        patterns += [
            sub.glob("*_gtf.yaml")
            for sub in d.iterdir()
            if sub.is_dir() and not sub.name.startswith(".")
        ]
        for gen in patterns:
            try:
                for f in gen:
                    _add(f)
            except PermissionError:
                pass

    results.sort(key=lambda x: x[0], reverse=True)
    return results


# ---------------------------------------------------------------------------
# GUI project picker  (runs in a thread so it doesn't block the async loop)
# ---------------------------------------------------------------------------

def _show_picker_gui(projects: list[tuple[float, Path, dict]]) -> Optional[Path]:
    """
    Open a native tkinter window.
    User clicks a row → double-click or 'Load' button → returns chosen Path.
    Returns None if cancelled or timed out.
    Tkinter is imported lazily so MCP server doesn't crash if display is unavailable.
    On macOS, tkinter can be unstable in background threads — falls back to text menu
    if the display check fails.
    """
    try:
        import tkinter as tk
        # macOS: tkinter requires the main thread and a proper app bundle.
        # Running in a daemon thread (as we do) is unstable on macOS 11+.
        # Gracefully skip GUI on macOS to use the text menu instead.
        if sys.platform == "darwin":
            return None
        tk.Tk().destroy()          # quick display check — raises if no display
    except Exception:
        return None                # GUI unavailable; caller falls back to text menu

    result: dict[str, Optional[Path]] = {"chosen": None}
    done = threading.Event()

    def _run():
        import tkinter as tk
        from tkinter import ttk
        root = tk.Tk()
        root.title("Mnemo — Select Project")
        root.geometry("780x400")
        root.resizable(True, True)
        root.configure(bg="#0f0f1a")
        root.lift()
        root.attributes("-topmost", True)

        # ── Style ────────────────────────────────────────────────────────────
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Treeview",
                        background="#1a1a2e",
                        foreground="#e2e8f0",
                        fieldbackground="#1a1a2e",
                        rowheight=38,
                        font=("Segoe UI", 10))
        style.configure("Treeview.Heading",
                        background="#2d1b69",
                        foreground="#a78bfa",
                        font=("Segoe UI", 10, "bold"),
                        padding=6)
        style.map("Treeview",
                  background=[("selected", "#7c3aed")],
                  foreground=[("selected", "#ffffff")])
        style.configure("TScrollbar", background="#2d1b69", troughcolor="#1a1a2e")

        # ── Header ───────────────────────────────────────────────────────────
        tk.Label(root, text="  Select a project to load",
                 bg="#0f0f1a", fg="#a78bfa",
                 font=("Segoe UI", 13, "bold"),
                 anchor="w").pack(fill="x", pady=(10, 4), padx=10)
        tk.Label(root, text="  Sorted newest first  •  Double-click or select + Load",
                 bg="#0f0f1a", fg="#4b5563",
                 font=("Segoe UI", 9),
                 anchor="w").pack(fill="x", padx=10)

        # ── Table ────────────────────────────────────────────────────────────
        frame = tk.Frame(root, bg="#0f0f1a")
        frame.pack(fill="both", expand=True, padx=10, pady=(8, 4))

        cols = ("project", "stack", "modified", "nodes", "failures")
        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")

        tree.heading("project",  text="Project Name")
        tree.heading("stack",    text="Stack")
        tree.heading("modified", text="Last Modified")
        tree.heading("nodes",    text="Nodes")
        tree.heading("failures", text="Failures")

        tree.column("project",  width=220, anchor="w", stretch=True)
        tree.column("stack",    width=175, anchor="w", stretch=True)
        tree.column("modified", width=130, anchor="center", stretch=False)
        tree.column("nodes",    width=55,  anchor="center", stretch=False)
        tree.column("failures", width=60,  anchor="center", stretch=False)

        active_resolved = str(_active_gtf_path.resolve())
        for i, (mtime, path, meta) in enumerate(projects):
            proj_name = meta.get("meta", {}).get("project", path.stem)
            stack     = ", ".join(meta.get("meta", {}).get("stack", []))
            if len(stack) > 26:
                stack = stack[:23] + "..."
            modified  = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d  %H:%M")
            nodes     = len(meta.get("nodes", {}))
            failures  = len(meta.get("failure_memory", []))
            is_active = str(path) == active_resolved
            tag          = "active" if is_active else ("even" if i % 2 == 0 else "odd")
            display_name = ("● " + proj_name) if is_active else ("○ " + proj_name)
            tree.insert("", "end", iid=str(path),
                        values=(display_name, stack, modified, nodes, failures),
                        tags=(tag,))

        tree.tag_configure("active", background="#1e1b4b", foreground="#a78bfa")
        tree.tag_configure("even",   background="#1a1a2e", foreground="#e2e8f0")
        tree.tag_configure("odd",    background="#16213e", foreground="#e2e8f0")

        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # ── Info bar — shows project root + YAML path on selection ───────────
        info_var = tk.StringVar(value="")
        info_bar = tk.Label(root, textvariable=info_var,
                            bg="#111827", fg="#6b7280",
                            font=("Segoe UI", 8),
                            anchor="w", padx=12, pady=4)
        info_bar.pack(fill="x")

        def on_select_row(event=None):
            sel = tree.selection()
            if not sel:
                return
            path = Path(sel[0])
            # Read meta for this entry
            entry_meta = next(
                (m for _, p, m in projects if str(p) == sel[0]), {}
            )
            proj_root = entry_meta.get("meta", {}).get("project_root", "")
            yaml_loc  = str(path)
            if proj_root:
                info_var.set(f"  Folder: {proj_root}     YAML: {path.name}")
            else:
                info_var.set(f"  YAML: {yaml_loc}     (folder not recorded — index from within the project)")

        tree.bind("<<TreeviewSelect>>", on_select_row)

        # Select first row by default
        children = tree.get_children()
        if children:
            tree.selection_set(children[0])
            tree.focus(children[0])
            on_select_row()

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_frame = tk.Frame(root, bg="#0f0f1a")
        btn_frame.pack(fill="x", padx=10, pady=(4, 10))

        def on_load(*_):
            sel = tree.selection()
            if sel:
                result["chosen"] = Path(sel[0])
                root.destroy()

        def on_cancel():
            root.destroy()

        tree.bind("<Double-1>", on_load)
        root.bind("<Return>",   on_load)
        root.bind("<Escape>",   lambda _: on_cancel())

        def on_browse():
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="Select a GTF YAML file",
                filetypes=[("GTF YAML", "*_gtf.yaml"), ("YAML files", "*.yaml"), ("All files", "*.*")],
                initialdir=str(_active_gtf_path.parent),
            )
            if path:
                result["chosen"] = Path(path)
                root.destroy()

        tk.Button(btn_frame, text="Cancel",
                  command=on_cancel,
                  bg="#1f2937", fg="#9ca3af",
                  font=("Segoe UI", 10),
                  relief="flat", padx=16, pady=6,
                  activebackground="#374151",
                  cursor="hand2").pack(side="right", padx=(6, 0))

        tk.Button(btn_frame, text="Load Project  →",
                  command=on_load,
                  bg="#7c3aed", fg="#ffffff",
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=16, pady=6,
                  activebackground="#6d28d9",
                  cursor="hand2").pack(side="right", padx=(6, 0))

        tk.Button(btn_frame, text="Browse...",
                  command=on_browse,
                  bg="#1f2937", fg="#d1d5db",
                  font=("Segoe UI", 10),
                  relief="flat", padx=14, pady=6,
                  activebackground="#374151",
                  cursor="hand2").pack(side="left")

        root.mainloop()
        done.set()

    threading.Thread(target=_run, daemon=True).start()
    done.wait(timeout=120)          # 2-minute timeout
    return result["chosen"]


# ---------------------------------------------------------------------------
# Shared capture helper  (used by gtf_capture_session, gtf_checkpoint, watcher)
# ---------------------------------------------------------------------------

def _ensure_sr_imported():
    """Lazily import session_reader from same folder as this script."""
    _sr_dir = str(Path(__file__).parent)
    if _sr_dir not in sys.path:
        sys.path.insert(0, _sr_dir)
    import importlib
    import session_reader as _sr
    importlib.reload(_sr)
    return _sr


def _find_project_session_dir(project_root: str) -> "str | None":
    """
    Given a project_root path, find the matching Claude Code session folder
    under ~/.claude/projects/ using fuzzy path-component matching.

    Claude Code encodes paths like:
      C:\\Users\\foo\\Desktop\\MyProject  →  C--Users-foo-Desktop-MyProject

    We match by checking how many path components appear in the folder name.
    Returns the encoded folder name (str) or None if no strong match found.
    """
    projects_root = Path.home() / ".claude" / "projects"
    if not projects_root.exists() or not project_root:
        return None

    # Normalise: lower-case, forward slashes, strip trailing slash
    norm = project_root.replace("\\", "/").rstrip("/").lower()
    # Split into path components, strip drive colon ("c:" → "c")
    parts = [p.rstrip(":") for p in norm.split("/") if p and p != "/"]

    best_dir: "str | None" = None
    best_score = 0

    for d in projects_root.iterdir():
        if not d.is_dir():
            continue
        folder_lower = d.name.lower()
        score = sum(1 for part in parts if part in folder_lower)
        if score > best_score:
            best_score = score
            best_dir = d.name

    # Require at least 2 matching path components to avoid false positives
    return best_dir if best_score >= 2 else None


def _run_capture(
    *,
    provider:     str  = "openai",
    session_path: str  = "",
    output_dir:   str  = "",
    incremental:  bool = True,
    force_full:   bool = False,
) -> dict:
    """
    Core capture logic shared by gtf_capture_session, gtf_checkpoint,
    and the background watcher.

    Parameters
    ----------
    force_full : if True, ignore last_captured_lines and re-read the full session.

    Returns a result dict:
      { ok, yaml_out, project_root, chat_chars, total_lines,
        nodes, failures, stdout_tail, error }
    """
    sr = _ensure_sr_imported()

    # ── 1. Locate session JSONL ───────────────────────────────────────────────
    if session_path:
        jsonl_path = Path(session_path)
        if not jsonl_path.exists():
            return {"ok": False, "error": f"Session file not found: {session_path}"}
    else:
        # Try to locate the session for the active project first (Fix 1)
        project_dir_encoded: "str | None" = None
        try:
            proj_root_hint = load_gtf().get("meta", {}).get("project_root", "")
            if proj_root_hint:
                project_dir_encoded = _find_project_session_dir(proj_root_hint)
        except Exception:
            pass

        jsonl_path, _ = sr.find_latest_session(project_dir_encoded)
        if jsonl_path is None:
            # Fallback: global latest
            jsonl_path, _ = sr.find_latest_session()
        if jsonl_path is None:
            return {"ok": False, "error": "No Claude Code session files found under ~/.claude/projects/"}

    # ── 2. Determine start_line for incremental mode ──────────────────────────
    start_line = 0
    current_gtf_data = load_gtf()
    if incremental and not force_full:
        start_line = current_gtf_data.get("meta", {}).get("last_captured_lines", 0)

    # ── 3. Convert JSONL → chat text (with smart filtering) ───────────────────
    try:
        chat_text, project_root, total_lines = sr.jsonl_to_chat(
            jsonl_path, smart_filter=True, start_line=start_line
        )
    except Exception as exc:
        return {"ok": False, "error": f"Failed to read session: {exc}"}

    if not chat_text.strip():
        return {"ok": False, "error": "No new content since last checkpoint."}

    # ── 4. Decide save directory ──────────────────────────────────────────────
    if output_dir:
        save_dir = Path(output_dir)
    elif project_root:
        save_dir = Path(project_root)
    else:
        save_dir = Path.home() / "Desktop"
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        save_dir = Path.home() / "Desktop"

    proj_name = Path(project_root).name if project_root else jsonl_path.stem[:24]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in proj_name)

    # ── 5. Write temp chat .md ────────────────────────────────────────────────
    tmp_chat = save_dir / f"{safe_name}_session_export.md"
    try:
        tmp_chat.write_text(chat_text, encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": f"Could not write temp file: {exc}"}

    # ── 6. Build indexer command ──────────────────────────────────────────────
    indexer_path = Path(__file__).parent / "indexer.py"
    if not indexer_path.exists():
        tmp_chat.unlink(missing_ok=True)
        return {"ok": False, "error": f"indexer.py not found at {indexer_path}"}

    yaml_out  = save_dir / f"{safe_name}_gtf.yaml"
    fast_model = "gpt-4o-mini" if provider == "openai" else "claude-haiku-4-5"

    cmd = [
        sys.executable, str(indexer_path),
        str(tmp_chat),
        "--provider", provider,
        "--model",    fast_model,
        "--output",   str(yaml_out),
        "--last-captured-lines", str(total_lines),
    ]
    if project_root:
        cmd += ["--project-root", project_root]
    if incremental and yaml_out.exists():
        cmd += ["--merge", str(yaml_out)]

    # ── 7. Run indexer ────────────────────────────────────────────────────────
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=600, encoding="utf-8", errors="replace",
        )
        stdout_tail = proc.stdout[-3000:] if len(proc.stdout) > 3000 else proc.stdout
        stderr_tail = proc.stderr[-800:]  if len(proc.stderr) > 800  else proc.stderr

        if proc.returncode != 0:
            tmp_chat.unlink(missing_ok=True)
            return {
                "ok": False,
                "error": f"Indexer exit {proc.returncode}.\n{stderr_tail}\n{stdout_tail}",
            }
    except subprocess.TimeoutExpired:
        tmp_chat.unlink(missing_ok=True)
        return {"ok": False, "error": "Indexing timed out after 10 minutes."}
    except Exception as exc:
        tmp_chat.unlink(missing_ok=True)
        return {"ok": False, "error": str(exc)}

    tmp_chat.unlink(missing_ok=True)

    # ── 8. Read back stats ────────────────────────────────────────────────────
    nodes_count = failures_count = 0
    if yaml_out.exists():
        try:
            import yaml as _yaml
            with open(yaml_out, encoding="utf-8") as fh:
                created = _yaml.safe_load(fh) or {}
            nodes_count    = len(created.get("nodes", {}))
            failures_count = len(created.get("failure_memory", []))
        except Exception:
            pass

    _registry_add(yaml_out)   # register so picker finds it at any depth

    return {
        "ok":           True,
        "yaml_out":     yaml_out,
        "project_root": project_root,
        "chat_chars":   len(chat_text),
        "total_lines":  total_lines,
        "start_line":   start_line,
        "nodes":        nodes_count,
        "failures":     failures_count,
        "stdout_tail":  stdout_tail,
    }


# ---------------------------------------------------------------------------
# Background auto-checkpoint watcher
# ---------------------------------------------------------------------------

_watcher_started = False

def _start_background_watcher() -> None:
    """
    Daemon thread started once when MCP server boots.
    Every 10 minutes: checks if current session JSONL has grown by 200 KB+.
    If yes: runs an incremental checkpoint silently in the background.
    User sees nothing — GTF is kept up to date automatically.
    """
    global _watcher_started
    if _watcher_started:
        return
    _watcher_started = True

    def _worker():
        CHECK_INTERVAL  = 600          # 10 minutes
        GROWTH_BYTES    = 200_000      # ~40k chars of new text
        last_size: dict[str, int] = {}

        while True:
            _time.sleep(CHECK_INTERVAL)
            try:
                sr          = _ensure_sr_imported()
                jsonl_path, _ = sr.find_latest_session()
                if jsonl_path is None:
                    continue

                cur  = jsonl_path.stat().st_size
                key  = str(jsonl_path)
                prev = last_size.get(key, 0)

                if cur - prev >= GROWTH_BYTES:
                    last_size[key] = cur
                    # Fire-and-forget background checkpoint
                    threading.Thread(
                        target=_silent_checkpoint,
                        daemon=True,
                    ).start()
            except Exception:
                pass   # never crash the watcher

    threading.Thread(target=_worker, daemon=True).start()


def _silent_checkpoint() -> None:
    """Run a full incremental capture silently — no return value needed."""
    try:
        result = _run_capture(incremental=True)
        if result["ok"]:
            # Auto-switch active GTF to the freshly updated file
            global _active_gtf_path
            _active_gtf_path = result["yaml_out"]
    except Exception:
        pass


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = Server("chat-gtf")

# Start background auto-checkpoint watcher as soon as server loads
_start_background_watcher()


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="gtf_check_failures",
            description=(
                "CALL THIS BEFORE EVERY RESPONSE. "
                "Checks whether the user's message or your planned suggestion "
                "matches any failure memory trigger words. "
                "If triggered, warn the user BEFORE proceeding."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The user message or the approach you are about to suggest",
                    }
                },
                "required": ["text"],
            },
        ),
        types.Tool(
            name="gtf_get_node",
            description=(
                "Get full associative context for a specific entity, component, or concept. "
                "Use when the user mentions any name that might exist in the project."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Entity name to look up (partial match supported)",
                    }
                },
                "required": ["entity_name"],
            },
        ),
        types.Tool(
            name="gtf_get_decisions",
            description=(
                "Get all committed decisions, pinned constants, and rejected approaches. "
                "Use before suggesting any architectural or technical choice."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="gtf_get_open_problems",
            description=(
                "Get list of unresolved problems and current project state. "
                "Use when user asks 'what's next' or 'where are we'."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="gtf_get_blast_radius",
            description=(
                "Get blast radius for an entity — what else breaks if it changes. "
                "Always call this before suggesting changes to any component."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Entity to check blast radius for",
                    }
                },
                "required": ["entity_name"],
            },
        ),
        types.Tool(
            name="gtf_search",
            description=(
                "Search across all GTF layers (nodes, failures, decisions, diffs) "
                "for any relevant context matching a keyword or concept."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword or concept to search for",
                    }
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="gtf_add_failure",
            description=(
                "Add a NEW failure to memory during the current session. "
                "Call this immediately when something fails so future sessions are protected."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "what_tried": {
                        "type": "string",
                        "description": "What approach was attempted",
                    },
                    "exact_error": {
                        "type": "string",
                        "description": "Exact error message or symptom",
                    },
                    "trigger_words": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific words that should trigger this warning in future",
                    },
                    "time_wasted": {
                        "type": "string",
                        "description": "How much time was lost (e.g. '2 hours')",
                        "default": "unknown",
                    },
                    "unless": {
                        "type": "string",
                        "description": "Condition under which this might be OK, or null",
                    },
                    "safe_pattern": {
                        "type": "string",
                        "description": "The correct approach to use instead",
                    },
                },
                "required": ["what_tried", "exact_error", "trigger_words"],
            },
        ),
        types.Tool(
            name="gtf_get_summary",
            description=(
                "Get full project summary — meta info, current state, open problems, "
                "failure count, node count. Use at start of session to orient yourself."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="gtf_index",
            description=(
                "INDEX a chat export file to create or refresh the chat_gtf.yaml. "
                "Call this once after exporting your Claude.ai chat with the bookmarklet. "
                "Runs indexer.py in the background — may take 2-5 minutes for large chats. "
                "IMPORTANT: Always pass project_root as the current working directory "
                "of this Claude Code session (use the cwd you know from your environment). "
                "This links the YAML to the project folder so the picker can show it later."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_file": {
                        "type": "string",
                        "description": (
                            "Absolute path to the exported chat .md file. "
                            "Example: C:/Users/you/Downloads/my_project_chat.md"
                        ),
                    },
                    "project_root": {
                        "type": "string",
                        "description": (
                            "The project folder this chat belongs to. "
                            "AUTOMATICALLY SET THIS to the current working directory "
                            "of this Claude Code session. "
                            "Example: C:/Users/you/Desktop/MyProject"
                        ),
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["openai", "anthropic"],
                        "description": "LLM provider to use for indexing. Default: openai",
                    },
                    "output_path": {
                        "type": "string",
                        "description": (
                            "Optional: where to save the output YAML. "
                            "Defaults to same folder as the chat file."
                        ),
                    },
                },
                "required": ["chat_file"],
            },
        ),
        types.Tool(
            name="gtf_status",
            description=(
                "Check whether the GTF file exists, its size, when it was last modified, "
                "and a quick health summary. Call this to verify the GTF is loaded correctly."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="gtf_switch",
            description=(
                "Switch the active project at runtime — no restart needed. "
                "CALL WITH NO ARGUMENTS to show a numbered menu of all available "
                "projects sorted newest-first. User then picks a number or name. "
                "Pass a number (e.g. '1'), a project name, a full YAML path, "
                "or a GitHub Gist URL to load a shared GTF from a teammate."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": (
                            "Leave EMPTY to show the menu. "
                            "Or pass: a number from the menu, a project name to fuzzy-match, "
                            "a full path to a _gtf.yaml file, "
                            "or a GitHub Gist URL (https://gist.github.com/...) to load a shared GTF."
                        ),
                        "default": "",
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="gtf_list_projects",
            description=(
                "List all available GTF YAML files found in the same folder as the "
                "current active GTF, plus any extra directories you specify. "
                "Use this to discover projects before calling gtf_switch."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "search_dirs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional extra directories to scan for *_gtf.yaml files. "
                            "The folder of the current active GTF is always scanned."
                        ),
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="gtf_capture_session",
            description=(
                "CAPTURE THIS CLAUDE CODE SESSION into a GTF YAML memory file. "
                "NO API KEY NEEDED — you (Claude) extract the memory from your own context. "
                "Automatically detects project folder from the session's working directory. "
                "CALL THIS when the user says: 'shifting to new chat', 'index this session', "
                "'capture this chat', 'save this conversation', 'new chat', or similar phrases. "
                "Returns a YAML template. YOU fill it from memory, then call gtf_save()."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "force_full": {
                        "type": "boolean",
                        "description": (
                            "If true, extract the complete project state from scratch. "
                            "If false (default), focus on what's new or changed recently."
                        ),
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="gtf_mount",
            description=(
                "Mount the active project's folder into this session. "
                "Returns: project_root path, all key files from GTF nodes, "
                "and a directory listing of the project. "
                "Call this when user says 'mount this project', 'open this folder', "
                "'is folder ko mount kar', 'project files dikhao', or starts working "
                "on code from the loaded GTF. After this, use Read/Grep/Glob tools "
                "directly on the returned paths."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "show_tree": {
                        "type": "boolean",
                        "description": "Show directory tree of project root (default: true)",
                        "default": True,
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="gtf_prepare",
            description=(
                "STEP 1 of 2 for session capture. "
                "Returns the GTF YAML template + extraction instructions. "
                "CALL THIS when user says 'shifting to new chat', 'capture this chat', "
                "'index this session', or similar. "
                "After calling this, YOU (Claude) fill in the template from your own "
                "conversation memory, then call gtf_save() with the filled YAML. "
                "NO API KEYS NEEDED — you already know the full conversation."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="gtf_save",
            description=(
                "STEP 2 of 2 for session capture. "
                "Save the GTF YAML that YOU (Claude) extracted to disk. "
                "Pass the complete filled YAML as yaml_content. "
                "Automatically detects project_root and switches active GTF."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "yaml_content": {
                        "type": "string",
                        "description": "Complete GTF YAML string you extracted from the conversation.",
                    },
                    "output_path": {
                        "type": "string",
                        "description": (
                            "Optional: full path where YAML should be saved. "
                            "Leave empty to auto-detect from project root."
                        ),
                        "default": "",
                    },
                },
                "required": ["yaml_content"],
            },
        ),
        types.Tool(
            name="gtf_checkpoint",
            description=(
                "Save a lightweight checkpoint of the CURRENT session — NO API KEY NEEDED. "
                "YOU (Claude) extract only what's NEW since the last checkpoint from your context. "
                "CALL THIS: (1) when context is getting long, (2) before a risky change, "
                "(3) after a major decision or failure is discovered. "
                "Returns a YAML template pre-filled with existing GTF. Add only new items, then call gtf_save()."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "force_full": {
                        "type": "boolean",
                        "description": (
                            "If true, re-extract the full project state instead of delta only."
                        ),
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="gtf_set_root",
            description=(
                "Set or update the project_root folder for the active GTF file. "
                "Call this when the GTF was created without a project folder link, "
                "or when the project has moved to a new location. "
                "Stores the path in meta.project_root so the picker can show it "
                "and Claude knows exactly where the project lives on disk."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Absolute path to the project folder on disk. "
                            "Example: C:/Users/you/Desktop/MyProject"
                        ),
                    },
                    "gtf_path": {
                        "type": "string",
                        "description": (
                            "Optional: path to a specific GTF YAML to patch. "
                            "Leave empty to patch the currently active GTF."
                        ),
                        "default": "",
                    },
                },
                "required": ["path"],
            },
        ),
        types.Tool(
            name="gtf_share",
            description=(
                "Upload the active GTF YAML to a GitHub Gist and return a shareable URL. "
                "Anyone with the URL can load the full project context using gtf_switch(url=...). "
                "Requires the GitHub CLI (gh) to be installed and authenticated."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "public": {
                        "type": "boolean",
                        "description": (
                            "If true, the Gist is publicly searchable on GitHub. "
                            "If false (default), it is a secret Gist — only people with the URL can see it."
                        ),
                        "default": False,
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description for the Gist (shown on GitHub).",
                        "default": "",
                    },
                },
                "required": [],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    global _active_gtf_path          # declared once at top; used by gtf_switch and gtf_capture_session
    gtf = load_gtf()

    # ── gtf_check_failures ──────────────────────────────────────────────────
    if name == "gtf_check_failures":
        text = arguments.get("text", "").lower()
        failures = gtf.get("failure_memory", [])
        triggered = []
        for f in failures:
            for trigger in f.get("trigger_words", []):
                if trigger.lower() in text:
                    triggered.append(f)
                    break

        if not triggered:
            return [types.TextContent(type="text", text="✅ CLEAR — No failure memories triggered.")]

        warnings = []
        for f in triggered:
            block = (
                f"⚠️ FAILURE MEMORY TRIGGERED\n"
                f"ID: {f.get('id')}\n"
                f"What failed: {f.get('what_tried')}\n"
                f"Error: {f.get('exact_error')}\n"
                f"Time lost: {f.get('time_wasted', 'unknown')}\n"
                f"Unless: {f.get('unless') or 'never try this'}\n"
                f"Safe pattern: {f.get('safe_pattern') or 'see project history'}"
            )
            warnings.append(block)

        return [types.TextContent(type="text", text="\n\n---\n\n".join(warnings))]

    # ── gtf_get_node ────────────────────────────────────────────────────────
    elif name == "gtf_get_node":
        entity = arguments.get("entity_name", "")
        nodes = gtf.get("nodes", {})

        # Exact match first, then partial
        match_key = None
        for k in nodes:
            if k.lower() == entity.lower():
                match_key = k
                break
        if not match_key:
            for k in nodes:
                if entity.lower() in k.lower() or k.lower() in entity.lower():
                    match_key = k
                    break

        if not match_key:
            available = list(nodes.keys())
            return [types.TextContent(
                type="text",
                text=f"No node found for '{entity}'.\nAvailable nodes: {available}",
            )]

        node = nodes[match_key]
        lines = [
            f"**{match_key}**",
            f"Type       : {node.get('type')}",
            f"State      : {node.get('state')}",
            f"Decision   : {node.get('decision')}",
            f"Connects to: {', '.join(node.get('connects_to', []))}",
            f"File       : {node.get('file') or 'N/A'}",
        ]

        # Attach diff if exists
        diff = gtf.get("diffs", {}).get(match_key)
        if diff:
            lines.append(
                f"\nEvolution  : {diff.get('v1')} → (current: {diff.get('current')})"
                f"\nWhy changed: {diff.get('why_changed')}"
            )

        # Attach blast radius if exists
        dep = gtf.get("dependencies", {}).get(match_key)
        if dep:
            lines.append(f"\nBlast radius: {dep.get('blast_radius')} | Safe to change: {dep.get('safe_to_change')}")

        return [types.TextContent(type="text", text="\n".join(lines))]

    # ── gtf_get_decisions ───────────────────────────────────────────────────
    elif name == "gtf_get_decisions":
        exons = gtf.get("exons", {})
        decisions   = exons.get("decisions", [])
        constants   = exons.get("constants", {})
        rejected    = exons.get("rejected_approaches", [])

        parts = []
        parts.append("**Committed Decisions:**\n" + "\n".join(f"• {d}" for d in decisions))
        parts.append("**Pinned Constants (immutable unless explicitly changed):**\n" +
                     "\n".join(f"• {k}: {v}" for k, v in constants.items()))
        parts.append("**Rejected Approaches (never suggest these):**\n" +
                     "\n".join(f"• {r}" for r in rejected))

        return [types.TextContent(type="text", text="\n\n".join(parts))]

    # ── gtf_get_open_problems ───────────────────────────────────────────────
    elif name == "gtf_get_open_problems":
        exons    = gtf.get("exons", {})
        problems = exons.get("open_problems", [])
        state    = exons.get("current_state", "Unknown")

        result = f"**Current State:** {state}\n\n"
        result += f"**Open Problems ({len(problems)}):**\n"
        result += "\n".join(f"• {p}" for p in problems)

        return [types.TextContent(type="text", text=result)]

    # ── gtf_get_blast_radius ────────────────────────────────────────────────
    elif name == "gtf_get_blast_radius":
        entity = arguments.get("entity_name", "")
        deps   = gtf.get("dependencies", {})

        match_key = None
        for k in deps:
            if k.lower() == entity.lower() or entity.lower() in k.lower():
                match_key = k
                break

        if not match_key:
            return [types.TextContent(
                type="text",
                text=f"No dependency data for '{entity}'.\nTracked: {list(deps.keys())}",
            )]

        dep = deps[match_key]
        lines = [
            f"**{match_key}** — Blast Radius: {dep.get('blast_radius')}",
            f"Safe to change: {dep.get('safe_to_change')}",
            "If changed:",
            *[f"  • {item}" for item in dep.get("if_changed", [])],
        ]
        return [types.TextContent(type="text", text="\n".join(lines))]

    # ── gtf_search ──────────────────────────────────────────────────────────
    elif name == "gtf_search":
        query   = arguments.get("query", "").lower()
        results = []

        for k, node in gtf.get("nodes", {}).items():
            haystack = f"{k} {node.get('decision','')} {node.get('state','')}".lower()
            if query in haystack:
                results.append(f"[Node] {k}: {node.get('decision')}")

        for f in gtf.get("failure_memory", []):
            haystack = (
                f"{f.get('what_tried','')} "
                f"{f.get('exact_error','')} "
                f"{' '.join(f.get('trigger_words', []))}"
            ).lower()
            if query in haystack:
                results.append(f"[Failure] {f.get('id')}: {f.get('what_tried')}")

        for d in gtf.get("exons", {}).get("decisions", []):
            if query in d.lower():
                results.append(f"[Decision] {d}")

        for r in gtf.get("exons", {}).get("rejected_approaches", []):
            if query in r.lower():
                results.append(f"[Rejected] {r}")

        for k, diff in gtf.get("diffs", {}).items():
            haystack = f"{k} {diff.get('why_changed','')}".lower()
            if query in haystack:
                results.append(f"[Diff] {k}: {diff.get('why_changed')}")

        if not results:
            return [types.TextContent(type="text", text=f"No results found for '{query}'.")]

        output = f"Search results for '{query}' ({len(results)} found):\n\n"
        output += "\n".join(results)
        return [types.TextContent(type="text", text=output)]

    # ── gtf_add_failure ─────────────────────────────────────────────────────
    elif name == "gtf_add_failure":
        failures = gtf.get("failure_memory", [])
        new_id   = f"F{len(failures) + 1:03d}"

        new_failure = {
            "id":                    new_id,
            "what_tried":            arguments.get("what_tried"),
            "exact_error":           arguments.get("exact_error"),
            "time_wasted":           arguments.get("time_wasted", "unknown"),
            "trigger_words":         arguments.get("trigger_words", []),
            "never_again":           True,
            "unless":                arguments.get("unless"),
            "code_pattern_to_avoid": None,
            "safe_pattern":          arguments.get("safe_pattern"),
        }

        failures.append(new_failure)
        gtf["failure_memory"] = failures
        save_gtf(gtf)

        return [types.TextContent(
            type="text",
            text=(
                f"✅ Failure {new_id} saved to {get_gtf_path()}\n"
                f"What failed : {new_failure['what_tried']}\n"
                f"Triggers    : {new_failure['trigger_words']}"
            ),
        )]

    # ── gtf_get_summary ─────────────────────────────────────────────────────
    elif name == "gtf_get_summary":
        meta   = gtf.get("meta", {})
        exons  = gtf.get("exons", {})

        lines = [
            f"**Project:** {meta.get('project', 'Unknown')}",
            f"**Stack:** {', '.join(meta.get('stack', []))}",
            f"**Last updated:** {meta.get('last_updated', 'Unknown')}",
            f"**Current State:** {exons.get('current_state', 'Unknown')}",
            "",
            f"**Open Problems ({len(exons.get('open_problems', []))}):**",
            *[f"  • {p}" for p in exons.get("open_problems", [])],
            "",
            f"**Failure Memory:** {len(gtf.get('failure_memory', []))} failures tracked",
            f"**Nodes:** {len(gtf.get('nodes', {}))} entities",
            f"**Decisions:** {len(exons.get('decisions', []))} committed",
            f"**Constants:** {', '.join(exons.get('constants', {}).keys())}",
        ]

        return [types.TextContent(type="text", text="\n".join(lines))]

    # ── gtf_index ────────────────────────────────────────────────────────────
    elif name == "gtf_index":
        chat_file   = arguments.get("chat_file", "").strip()
        provider    = arguments.get("provider", "openai")
        output_path = arguments.get("output_path")

        chat_path = Path(chat_file)
        if not chat_path.exists():
            return [types.TextContent(
                type="text",
                text=(
                    f"❌ File not found: {chat_file}\n\n"
                    "Make sure you:\n"
                    "1. Exported your Claude.ai chat using export_chat.js\n"
                    "2. Provided the correct absolute path to the .md file"
                ),
            )]

        # Find indexer.py relative to this script
        indexer_path = Path(__file__).parent / "indexer.py"
        if not indexer_path.exists():
            return [types.TextContent(
                type="text",
                text=(
                    f"❌ indexer.py not found at {indexer_path}\n"
                    "Make sure mcp_server.py and indexer.py are in the same folder."
                ),
            )]

        project_root = arguments.get("project_root", "").strip()
        cmd = [sys.executable, str(indexer_path), str(chat_path), "--provider", provider]
        if output_path:
            cmd += ["--output", output_path]
        if project_root:
            cmd += ["--project-root", project_root]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,          # 10-minute ceiling for very large chats
                encoding="utf-8",
                errors="replace",
            )

            # Trim stdout to last 3000 chars to avoid flooding the context
            stdout_tail = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
            stderr_tail = result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr

            if result.returncode == 0:
                # Determine where the YAML was written
                if output_path:
                    yaml_out = Path(output_path)
                else:
                    yaml_out = chat_path.parent / (chat_path.stem + "_gtf.yaml")
                    # Fallback: indexer.py default is chat_gtf.yaml in cwd
                    if not yaml_out.exists():
                        yaml_out = Path("chat_gtf.yaml")

                return [types.TextContent(
                    type="text",
                    text=(
                        f"✅ Indexing complete!\n"
                        f"YAML saved to: {yaml_out}\n\n"
                        f"--- Indexer output (last 3000 chars) ---\n{stdout_tail}\n\n"
                        f"Next step: call gtf_get_summary to verify the extracted context."
                    ),
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=(
                        f"❌ Indexing failed (exit code {result.returncode}).\n\n"
                        f"Error output:\n{stderr_tail}\n\n"
                        f"Stdout:\n{stdout_tail}\n\n"
                        "Common fixes:\n"
                        "• Check that OPENAI_API_KEY or ANTHROPIC_API_KEY env var is set\n"
                        "• Try --provider anthropic if openai key is missing\n"
                        "• Make sure the chat .md file is not empty"
                    ),
                )]

        except subprocess.TimeoutExpired:
            return [types.TextContent(
                type="text",
                text=(
                    "❌ Indexing timed out after 10 minutes.\n"
                    "The chat file may be very large. Try splitting it into two halves "
                    "and running gtf_index on each half separately."
                ),
            )]
        except Exception as exc:
            return [types.TextContent(type="text", text=f"❌ Unexpected error: {exc}")]

    # ── gtf_status ────────────────────────────────────────────────────────────
    elif name == "gtf_status":
        gtf_path = get_gtf_path()

        if not gtf_path.exists():
            return [types.TextContent(
                type="text",
                text=(
                    f"❌ No GTF file found at: {gtf_path}\n\n"
                    "To create one:\n"
                    "1. Export your Claude.ai chat with export_chat.js (F12 → Console)\n"
                    "2. Call gtf_index with the path to the exported .md file\n"
                    "   Example: gtf_index(chat_file='C:/Downloads/my_chat.md')"
                ),
            )]

        stat      = gtf_path.stat()
        size_kb   = stat.st_size / 1024
        modified  = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        failures  = len(gtf.get("failure_memory", []))
        nodes     = len(gtf.get("nodes", {}))
        decisions = len(gtf.get("exons", {}).get("decisions", []))
        problems  = len(gtf.get("exons", {}).get("open_problems", []))
        project   = gtf.get("meta", {}).get("project", "Unknown")

        health = "✅ Healthy" if failures > 0 and nodes > 0 else "⚠️ Partial (re-run gtf_index?)"

        return [types.TextContent(
            type="text",
            text=(
                f"**GTF Status**\n"
                f"File         : {gtf_path}\n"
                f"Size         : {size_kb:.1f} KB\n"
                f"Last modified: {modified}\n"
                f"Health       : {health}\n\n"
                f"**Project    :** {project}\n"
                f"Nodes        : {nodes}\n"
                f"Failures     : {failures}\n"
                f"Decisions    : {decisions}\n"
                f"Open problems: {problems}"
            ),
        )]

    # ── gtf_switch ────────────────────────────────────────────────────────────
    elif name == "gtf_switch":
        project = arguments.get("project", "").strip()

        # ── Case 0: GitHub Gist URL → download and load ───────────────────────
        if project.startswith("https://gist.github.com/"):
            import tempfile, urllib.request
            try:
                # Convert Gist URL to raw content URL
                # https://gist.github.com/user/abc123  →  https://gist.githubusercontent.com/user/abc123/raw
                raw_url = project.replace(
                    "https://gist.github.com/",
                    "https://gist.githubusercontent.com/"
                ) + "/raw"

                with urllib.request.urlopen(raw_url, timeout=15) as resp:
                    content = resp.read().decode("utf-8")

                # Save to a temp file
                tmp_dir  = Path(tempfile.mkdtemp(prefix="mnemo_shared_"))
                tmp_file = tmp_dir / "shared_gtf.yaml"
                tmp_file.write_text(content, encoding="utf-8")

                # Try to extract project name from YAML
                try:
                    import yaml as _yaml
                    data = _yaml.safe_load(content)
                    pname = data.get("meta", {}).get("project_name", "Shared Project")
                except Exception:
                    pname = "Shared Project"

                _active_gtf_path = tmp_file
                return [types.TextContent(
                    type="text",
                    text=(
                        f"✅ Shared GTF loaded from Gist!\n\n"
                        f"Project : {pname}\n"
                        f"Source  : {project}\n"
                        f"Saved to: {tmp_file}\n\n"
                        "Full project context is now active. Use gtf_get_summary() to see everything."
                    ),
                )]
            except Exception as exc:
                return [types.TextContent(
                    type="text",
                    text=(
                        f"❌ Failed to load GTF from Gist: {exc}\n\n"
                        "Make sure the Gist URL is correct and publicly accessible."
                    ),
                )]

        # ── Case 1: No argument → open GUI picker (text fallback if no display) ─
        if not project:
            all_files = _scan_gtf_files()
            if not all_files:
                return [types.TextContent(
                    type="text",
                    text=(
                        "No GTF files found.\n\n"
                        "Create one first:\n"
                        "  1. Export your Claude.ai chat (F12 -> paste export_chat.js)\n"
                        "  2. Say: 'index my chat at C:/Downloads/my_chat.md'"
                    ),
                )]
            loop   = asyncio.get_event_loop()
            chosen = await loop.run_in_executor(None, _show_picker_gui, all_files)

            if chosen is None:
                # GUI unavailable or cancelled — return text menu as fallback
                lines = ["Choose a project (newest first):\n"]
                for i, (mtime, path, meta) in enumerate(all_files, 1):
                    name     = meta.get("meta", {}).get("project", path.stem)
                    stack    = ", ".join(meta.get("meta", {}).get("stack", []))
                    modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    nodes    = len(meta.get("nodes", {}))
                    failures = len(meta.get("failure_memory", []))
                    active   = " <- ACTIVE" if str(path) == str(_active_gtf_path.resolve()) else ""
                    lines.append(
                        f"  {i}. {name}{active}\n"
                        f"     {stack or 'unknown'} | {modified} | "
                        f"Nodes: {nodes}  Failures: {failures}\n"
                    )
                lines.append("\nReply with a number or name to switch.")
                return [types.TextContent(type="text", text="\n".join(lines))]

            _active_gtf_path = chosen

        # ── Case 2: Number → pick by index ───────────────────────────────────
        elif project.isdigit():
            all_files = _scan_gtf_files()
            idx = int(project) - 1
            if idx < 0 or idx >= len(all_files):
                return [types.TextContent(
                    type="text",
                    text="Invalid number. Call gtf_switch() (no args) to open the picker.",
                )]
            _active_gtf_path = all_files[idx][1]

        # ── Case 3: Exact path ────────────────────────────────────────────────
        elif Path(project).exists() and Path(project).suffix in (".yaml", ".yml"):
            _active_gtf_path = Path(project).resolve()

        # ── Case 4: Fuzzy name match on filename OR project name in YAML ─────
        else:
            all_files = _scan_gtf_files()
            matches = [
                (mtime, path, meta)
                for mtime, path, meta in all_files
                if project.lower() in path.stem.lower()
                or project.lower() in meta.get("meta", {}).get("project", "").lower()
            ]
            if not matches:
                return [types.TextContent(
                    type="text",
                    text=f"No GTF file matching '{project}'. Call gtf_switch() to open the picker.",
                )]
            if len(matches) > 1:
                options = "\n".join(
                    f"  * {m.get('meta', {}).get('project', p.stem)}  ({p.name})"
                    for _, p, m in matches
                )
                return [types.TextContent(
                    type="text",
                    text=f"Multiple matches for '{project}':\n\n{options}\n\nBe more specific.",
                )]
            _active_gtf_path = matches[0][1]

        # ── Load and confirm ──────────────────────────────────────────────────
        new_gtf = load_gtf()
        if not new_gtf:
            return [types.TextContent(
                type="text",
                text=f"Switched to {_active_gtf_path} but file is empty or invalid.",
            )]

        meta_s  = new_gtf.get("meta", {})
        exons_s = new_gtf.get("exons", {})
        return [types.TextContent(
            type="text",
            text=(
                f"Switched to: {_active_gtf_path.name}\n\n"
                f"Project   : {meta_s.get('project', 'Unknown')}\n"
                f"Stack     : {', '.join(meta_s.get('stack', []))}\n"
                f"State     : {exons_s.get('current_state', 'Unknown')}\n"
                f"Nodes     : {len(new_gtf.get('nodes', {}))}\n"
                f"Failures  : {len(new_gtf.get('failure_memory', []))}\n"
                f"Decisions : {len(exons_s.get('decisions', []))}\n\n"
                f"All gtf_ tools now use this project."
            ),
        )]

    # ── gtf_mount ─────────────────────────────────────────────────────────────
    elif name == "gtf_mount":
        show_tree   = arguments.get("show_tree", True)
        project_root = gtf.get("meta", {}).get("project_root", "").strip()

        if not project_root:
            return [types.TextContent(
                type="text",
                text=(
                    "❌ No project_root in active GTF.\n\n"
                    "Fix: call gtf_set_root(path='C:/your/project/folder') first."
                ),
            )]

        root = Path(project_root)
        if not root.exists():
            return [types.TextContent(
                type="text",
                text=(
                    f"❌ Project folder not found: {project_root}\n"
                    "The project may have moved. Call gtf_set_root() to update."
                ),
            )]

        # ── Key files from GTF nodes ──────────────────────────────────────────
        node_files = []
        for node_name, node_data in gtf.get("nodes", {}).items():
            f = node_data.get("file", "") if isinstance(node_data, dict) else ""
            if f:
                abs_path = root / f
                node_files.append((node_name, f, abs_path.exists()))

        # ── Directory tree (top-level + one level deep, skip hidden/venv) ─────
        SKIP = {".git", ".claude", "__pycache__", "node_modules",
                ".venv", "venv", ".mypy_cache", ".pytest_cache", "dist", "build"}

        tree_lines = [f"{root.name}/"]
        if show_tree:
            try:
                entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
                for entry in entries:
                    if entry.name in SKIP or entry.name.startswith("."):
                        continue
                    if entry.is_dir():
                        tree_lines.append(f"  {entry.name}/")
                        try:
                            sub_entries = sorted(entry.iterdir(),
                                                 key=lambda p: (p.is_file(), p.name.lower()))[:12]
                            for sub in sub_entries:
                                if sub.name in SKIP or sub.name.startswith("."):
                                    continue
                                tree_lines.append(f"    {sub.name}{'/' if sub.is_dir() else ''}")
                        except PermissionError:
                            pass
                    else:
                        tree_lines.append(f"  {entry.name}")
            except PermissionError:
                tree_lines.append("  (permission denied)")

        # ── Build response ────────────────────────────────────────────────────
        lines = [
            f"✅ Project mounted: {root.name}",
            f"Root: {project_root}",
            "",
        ]

        if node_files:
            lines.append(f"Key files from GTF ({len(node_files)} nodes with file paths):")
            for node_name, rel_path, exists in node_files:
                status = "✅" if exists else "❌ missing"
                lines.append(f"  {status}  {rel_path}  [{node_name}]")
                if exists:
                    lines.append(f"         → {root / rel_path}")
            lines.append("")

        if show_tree:
            lines.append("Directory structure:")
            lines.extend(f"  {ln}" for ln in tree_lines)
            lines.append("")

        lines.append("You can now use Read/Grep/Glob tools directly on these paths.")
        lines.append(f"Example: Read('{project_root}/main.py')")

        return [types.TextContent(type="text", text="\n".join(lines))]

    # ── gtf_prepare ──────────────────────────────────────────────────────────
    elif name == "gtf_prepare":
        # Detect likely output path using project-specific session detection
        try:
            sr = _ensure_sr_imported()
            # Try active GTF's project_root as hint first
            project_dir_encoded = None
            try:
                hint = load_gtf().get("meta", {}).get("project_root", "")
                if hint:
                    project_dir_encoded = _find_project_session_dir(hint)
            except Exception:
                pass
            jsonl_path, _ = sr.find_latest_session(project_dir_encoded)
            if jsonl_path is None:
                jsonl_path, _ = sr.find_latest_session()
            _, project_root, _ = sr.jsonl_to_chat(
                jsonl_path, max_chars=1, smart_filter=False
            ) if jsonl_path else ("", "", 0)
        except Exception:
            project_root = ""

        if project_root:
            save_dir  = Path(project_root)
            proj_name = save_dir.name
        else:
            proj_name = get_gtf_path().stem.replace("_gtf", "") or "project"
            save_dir  = get_gtf_path().parent

        safe_name    = "".join(c if c.isalnum() or c in "-_" else "_" for c in proj_name)
        suggested_path = str(save_dir / f"{safe_name}_gtf.yaml")

        template = f"""\
You are about to extract GTF memory from this conversation.
Fill in the YAML below from your own context — you already know everything.
Be concise: 1 sentence per field, bullet points for lists.
Then call gtf_save(yaml_content="<your filled YAML>").

Suggested output path: {suggested_path}

---
meta:
  project: "<inferred project name>"
  stack: ["<tech1>", "<tech2>"]
  created: "<YYYY-MM>"
  last_updated: "<YYYY-MM>"
  project_root: "{project_root or '<detected automatically>'}"

exons:
  current_state: "<what state is the project in right now>"
  decisions:
    - "<key architectural or technical decision made>"
  constants:
    KEY_NAME: "<value that must not change>"
  open_problems:
    - "<unresolved issue or next step>"
  rejected_approaches:
    - "<approach tried and discarded, and why>"

nodes:
  EntityName:
    type: "component|decision|concept|tool"
    connects_to: ["<OtherEntity>"]
    decision: "<what was decided about this entity>"
    state: "stable|in_progress|broken|deprecated"
    file: "<relative/path/optional>"

diffs:
  EntityName:
    v1: "<original approach>"
    current: "<current approach>"
    why_changed: "<reason for change>"

failure_memory:
  - id: "F001"
    what_tried: "<what was attempted>"
    exact_error: "<exact error or symptom>"
    time_wasted: "<e.g. 2 hours>"
    trigger_words: ["<word1>", "<word2>"]
    never_again: true
    unless: "<condition where it might be ok, or null>"
    safe_pattern: "<correct approach to use instead>"

dependencies:
  EntityName:
    if_changed: ["<what else breaks>"]
    safe_to_change: true|false
    blast_radius: "HIGH|MEDIUM|LOW"
"""
        return [types.TextContent(type="text", text=template)]

    # ── gtf_save ──────────────────────────────────────────────────────────────
    elif name == "gtf_save":
        yaml_content = arguments.get("yaml_content", "").strip()
        output_path  = arguments.get("output_path",  "").strip()

        if not yaml_content:
            return [types.TextContent(type="text",
                text="❌ yaml_content is required — pass the filled YAML string.")]

        # ── Validate YAML ──────────────────────────────────────────────────────
        try:
            data = yaml.safe_load(yaml_content)
            if not isinstance(data, dict):
                raise ValueError("Top-level must be a YAML mapping")
        except Exception as exc:
            return [types.TextContent(type="text",
                text=f"❌ Invalid YAML: {exc}\n\nCheck for unclosed quotes or bad indentation.")]

        # ── Detect project_root from latest session JSONL ─────────────────────
        # Priority: project_root already in YAML > JSONL cwd detection
        try:
            sr = _ensure_sr_imported()

            # If Claude already put project_root in the YAML, trust it — don't override
            existing_root = data.get("meta", {}).get("project_root", "")
            if not existing_root or not Path(existing_root).exists():
                # Use project-specific session detection (same Fix 1 logic)
                project_dir_encoded = None
                try:
                    if existing_root:
                        project_dir_encoded = _find_project_session_dir(existing_root)
                except Exception:
                    pass

                jsonl_path, _ = sr.find_latest_session(project_dir_encoded)
                if jsonl_path is None:
                    jsonl_path, _ = sr.find_latest_session()
                if jsonl_path:
                    _, proj_root, total_lines = sr.jsonl_to_chat(
                        jsonl_path, max_chars=1, smart_filter=False
                    )
                    if proj_root:
                        data.setdefault("meta", {}).setdefault("project_root", proj_root)
                    data.setdefault("meta", {})["last_captured_lines"] = total_lines
            else:
                # project_root already valid — just update last_captured_lines
                try:
                    project_dir_encoded = _find_project_session_dir(existing_root)
                    jsonl_path, _ = sr.find_latest_session(project_dir_encoded)
                    if jsonl_path:
                        _, _, total_lines = sr.jsonl_to_chat(
                            jsonl_path, max_chars=1, smart_filter=False
                        )
                        data["meta"]["last_captured_lines"] = total_lines
                except Exception:
                    pass
        except Exception:
            proj_root = ""

        # ── Determine save path ────────────────────────────────────────────────
        if output_path:
            yaml_out = Path(output_path)
        else:
            proj_root_meta = data.get("meta", {}).get("project_root", "")
            if proj_root_meta and Path(proj_root_meta).exists():
                save_dir = Path(proj_root_meta)
            else:
                save_dir = Path.home() / "Desktop"

            proj_name = data.get("meta", {}).get("project", "project")
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in proj_name)
            yaml_out  = save_dir / f"{safe_name}_gtf.yaml"

        try:
            yaml_out.parent.mkdir(parents=True, exist_ok=True)
            with open(yaml_out, "w", encoding="utf-8") as fh:
                yaml.dump(data, fh, default_flow_style=False,
                          allow_unicode=True, sort_keys=False)
        except Exception as exc:
            return [types.TextContent(type="text", text=f"❌ Could not save file: {exc}")]

        _registry_add(yaml_out)       # register so picker finds it at any depth
        _active_gtf_path = yaml_out   # auto-switch

        nodes    = len(data.get("nodes", {}))
        failures = len(data.get("failure_memory", []))

        return [types.TextContent(
            type="text",
            text=(
                f"✅ GTF saved!\n\n"
                f"File     : {yaml_out}\n"
                f"Project  : {data.get('meta', {}).get('project', 'Unknown')}\n"
                f"Nodes    : {nodes}\n"
                f"Failures : {failures}\n\n"
                f"Active GTF switched. You can now start a new chat — "
                f"load this file to restore full context instantly."
            ),
        )]

    # ── gtf_capture_session ───────────────────────────────────────────────────
    elif name == "gtf_capture_session":
        # Claude-native capture — no API key needed.
        # Detect project_root from the current project's session JSONL, then
        # return the YAML template for Claude to fill from its own memory.
        force_full = bool(arguments.get("force_full", False))

        project_root = ""
        try:
            sr = _ensure_sr_imported()
            project_dir_encoded: "str | None" = None
            try:
                proj_root_hint = load_gtf().get("meta", {}).get("project_root", "")
                if proj_root_hint:
                    project_dir_encoded = _find_project_session_dir(proj_root_hint)
            except Exception:
                pass
            jsonl_path, _ = sr.find_latest_session(project_dir_encoded)
            if jsonl_path is None:
                jsonl_path, _ = sr.find_latest_session()
            if jsonl_path:
                _, project_root, _ = sr.jsonl_to_chat(
                    jsonl_path, max_chars=1, smart_filter=False
                )
        except Exception:
            project_root = ""

        if project_root:
            save_dir  = Path(project_root)
            proj_name = save_dir.name
        else:
            proj_name = get_gtf_path().stem.replace("_gtf", "") or "project"
            save_dir  = get_gtf_path().parent

        safe_name      = "".join(c if c.isalnum() or c in "-_" else "_" for c in proj_name)
        suggested_path = str(save_dir / f"{safe_name}_gtf.yaml")

        scope_note = (
            "Extract the COMPLETE project state — all nodes, decisions, failures."
            if force_full else
            "Focus on what is NEW or CHANGED in this session. Merge with what you already know."
        )

        template = f"""\
One moment — capturing session...

{scope_note}
Fill in the YAML below from your own conversation memory — no API call needed.
Then call gtf_save(yaml_content="<your filled YAML>").

Suggested output path: {suggested_path}

---
meta:
  project: "<inferred project name>"
  stack: ["<tech1>", "<tech2>"]
  created: "<YYYY-MM>"
  last_updated: "<YYYY-MM>"
  project_root: "{project_root or '<detected automatically>'}"

exons:
  current_state: "<what state is the project in right now>"
  decisions:
    - "<key architectural or technical decision made>"
  constants:
    KEY_NAME: "<value that must not change>"
  open_problems:
    - "<unresolved issue or next step>"
  rejected_approaches:
    - "<approach tried and discarded, and why>"

nodes:
  EntityName:
    type: "component|decision|concept|tool"
    connects_to: ["<OtherEntity>"]
    decision: "<what was decided about this entity>"
    state: "stable|in_progress|broken|deprecated"
    file: "<relative/path/optional>"

diffs:
  EntityName:
    v1: "<original approach>"
    current: "<current approach>"
    why_changed: "<reason for change>"

failure_memory:
  - id: "F001"
    what_tried: "<what was attempted>"
    exact_error: "<exact error or symptom>"
    time_wasted: "<e.g. 2 hours>"
    trigger_words: ["<word1>", "<word2>"]
    never_again: true
    unless: "<condition where it might be ok, or null>"
    safe_pattern: "<correct approach to use instead>"

dependencies:
  EntityName:
    if_changed: ["<what else breaks>"]
    safe_to_change: true|false
    blast_radius: "HIGH|MEDIUM|LOW"
"""
        return [types.TextContent(type="text", text=template)]

    # ── gtf_checkpoint ────────────────────────────────────────────────────────
    elif name == "gtf_checkpoint":
        # Claude-native checkpoint — no API key needed.
        # Pre-fill the template with existing GTF content so Claude only needs
        # to ADD new nodes/failures/decisions discovered since last checkpoint.
        force_full = bool(arguments.get("force_full", False))

        existing = load_gtf()
        yaml_out = get_gtf_path()

        scope_note = (
            "Re-extract the COMPLETE project state — overwrite existing GTF."
            if force_full else
            "ADD only what is NEW since the last checkpoint. Keep existing entries intact."
        )

        # Serialise existing GTF as the base template Claude will amend
        try:
            existing_yaml = yaml.dump(
                existing, default_flow_style=False,
                allow_unicode=True, sort_keys=False
            )
        except Exception:
            existing_yaml = "# (could not read existing GTF — start fresh)"

        template = f"""\
Checkpoint time!

{scope_note}
The current GTF content is shown below. Update it with anything new from this session,
then call gtf_save(yaml_content="<updated YAML>") to persist.

Output path: {yaml_out}

--- CURRENT GTF (edit and extend this) ---
{existing_yaml}"""

        return [types.TextContent(type="text", text=template)]

    # ── gtf_set_root ──────────────────────────────────────────────────────────
    elif name == "gtf_set_root":
        project_path = arguments.get("path", "").strip()
        target_gtf   = arguments.get("gtf_path", "").strip()

        # ── Validate the project folder ───────────────────────────────────────
        if not project_path:
            return [types.TextContent(
                type="text",
                text="❌ path is required. Example: C:/Users/you/Desktop/MyProject",
            )]

        resolved_root = Path(project_path).resolve()
        if not resolved_root.exists():
            return [types.TextContent(
                type="text",
                text=(
                    f"⚠️ Path does not exist on disk: {resolved_root}\n\n"
                    "Saving anyway — update the path if the folder moves."
                ),
            )]

        # ── Decide which GTF to patch ─────────────────────────────────────────
        if target_gtf:
            gtf_file = Path(target_gtf).resolve()
            if not gtf_file.exists():
                return [types.TextContent(
                    type="text",
                    text=f"❌ GTF file not found: {target_gtf}",
                )]
        else:
            gtf_file = get_gtf_path().resolve()
            if not gtf_file.exists():
                return [types.TextContent(
                    type="text",
                    text=(
                        f"❌ No active GTF loaded at: {gtf_file}\n"
                        "Use gtf_switch() to load a project first, or pass gtf_path explicitly."
                    ),
                )]

        # ── Read → patch → write ──────────────────────────────────────────────
        try:
            with open(gtf_file, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except Exception as exc:
            return [types.TextContent(type="text", text=f"❌ Could not read GTF: {exc}")]

        old_root = data.get("meta", {}).get("project_root", "(not set)")
        data.setdefault("meta", {})["project_root"] = str(resolved_root)

        try:
            with open(gtf_file, "w", encoding="utf-8") as fh:
                yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
        except Exception as exc:
            return [types.TextContent(type="text", text=f"❌ Could not save GTF: {exc}")]

        return [types.TextContent(
            type="text",
            text=(
                f"✅ project_root updated!\n\n"
                f"GTF file  : {gtf_file.name}\n"
                f"Old root  : {old_root}\n"
                f"New root  : {resolved_root}\n\n"
                f"The picker will now show this folder, and Claude knows "
                f"exactly where to find the project files."
            ),
        )]

    # ── gtf_list_projects ─────────────────────────────────────────────────────
    elif name == "gtf_list_projects":
        extra_dirs  = arguments.get("search_dirs", [])
        search_dirs = [_active_gtf_path.parent] + [Path(d) for d in extra_dirs]

        found = {}
        for d in search_dirs:
            if not d.exists():
                continue
            for f in sorted(d.glob("*_gtf.yaml")):
                f = f.resolve()
                if str(f) in found:
                    continue
                try:
                    with open(f, encoding="utf-8") as fh:
                        data = yaml.safe_load(fh) or {}
                    project_name = data.get("meta", {}).get("project", f.stem)
                    failures     = len(data.get("failure_memory", []))
                    nodes        = len(data.get("nodes", {}))
                    active_mark  = " ◀ ACTIVE" if f == _active_gtf_path.resolve() else ""
                    found[str(f)] = (
                        f"{'●' if active_mark else '○'}  {project_name}{active_mark}\n"
                        f"   Path    : {f}\n"
                        f"   Nodes   : {nodes}  |  Failures: {failures}\n"
                    )
                except Exception:
                    found[str(f)] = f"○  {f.name} (could not read)\n"

        if not found:
            return [types.TextContent(
                type="text",
                text=(
                    f"No *_gtf.yaml files found in: {search_dirs[0]}\n\n"
                    "To add more search locations, call:\n"
                    "  gtf_list_projects(search_dirs=['C:/your/projects/folder'])"
                ),
            )]

        header = f"Found {len(found)} GTF project(s):\n\n"
        return [types.TextContent(
            type="text",
            text=header + "\n".join(found.values()) + "\nUse gtf_switch('project name') to switch.",
        )]

    # ── gtf_share ─────────────────────────────────────────────────────────────
    elif name == "gtf_share":
        if not _active_gtf_path or not _active_gtf_path.exists():
            return [types.TextContent(
                type="text",
                text="❌ No active GTF loaded. Use gtf_switch() first to load a project.",
            )]

        is_public   = arguments.get("public", False)
        description = arguments.get("description", "").strip()

        gtf_filename = _active_gtf_path.name
        project_name = gtf.get("meta", {}).get("project_name", gtf_filename)

        if not description:
            description = f"Mnemo GTF — {project_name}"

        visibility_flag = "--public" if is_public else "--secret"

        # ── Sanitize: replace absolute paths with relative before uploading ──
        import copy, tempfile, re as _re

        def _sanitize_paths(data: dict) -> dict:
            """Return a deep copy with absolute paths replaced by relative placeholders."""
            sanitized = copy.deepcopy(data)

            # Get project_root to make paths relative (if available)
            project_root = sanitized.get("meta", {}).get("project_root", "")

            def relativize(val: str) -> str:
                if not isinstance(val, str):
                    return val
                # Windows absolute path: C:\... or C:/...
                # Unix absolute path: /home/... or /Users/...
                if _re.match(r'^[A-Za-z]:[/\\]', val) or val.startswith('/'):
                    if project_root and val.startswith(project_root):
                        # Make relative to project root
                        rel = val[len(project_root):].lstrip('/\\')
                        return f"./{rel}" if rel else "."
                    else:
                        # Replace with placeholder — keep filename only
                        return f"<path>/{Path(val).name}"
                return val

            # Sanitize meta.project_root
            if "meta" in sanitized:
                sanitized["meta"]["project_root"] = "<project-root>"

            # Sanitize nodes (dict or list)
            nodes = sanitized.get("nodes", {})
            if isinstance(nodes, dict):
                for node in nodes.values():
                    if isinstance(node, dict):
                        for key in ("file", "file_path", "path", "location"):
                            if key in node:
                                node[key] = relativize(node[key])
            elif isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, dict):
                        for key in ("file", "file_path", "path", "location"):
                            if key in node:
                                node[key] = relativize(node[key])

            # Sanitize exons (decisions, constants, etc.)
            exons = sanitized.get("exons", {})
            if isinstance(exons, dict):
                for section in exons.values():
                    if isinstance(section, list):
                        for item in section:
                            if isinstance(item, dict):
                                for key in ("file", "file_path", "path", "location"):
                                    if key in item:
                                        item[key] = relativize(item[key])

            return sanitized

        sanitized_gtf = _sanitize_paths(gtf)

        # Write sanitized YAML to a temp file for upload
        tmp_share_dir  = Path(tempfile.mkdtemp(prefix="mnemo_share_"))
        tmp_share_file = tmp_share_dir / gtf_filename

        with open(tmp_share_file, "w", encoding="utf-8") as f:
            yaml.dump(sanitized_gtf, f, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)

        try:
            result = subprocess.run(
                [
                    "gh", "gist", "create",
                    str(tmp_share_file),
                    visibility_flag,
                    "--desc", description,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return [types.TextContent(
                    type="text",
                    text=(
                        "❌ GitHub Gist upload failed.\n\n"
                        f"Error: {result.stderr.strip()}\n\n"
                        "Make sure:\n"
                        "  1. GitHub CLI is installed: winget install GitHub.cli\n"
                        "  2. You are logged in: gh auth login"
                    ),
                )]

            gist_url = result.stdout.strip()

            return [types.TextContent(
                type="text",
                text=(
                    f"✅ GTF shared successfully!\n\n"
                    f"Project  : {project_name}\n"
                    f"Gist URL : {gist_url}\n"
                    f"Visible  : {'Public' if is_public else 'Secret (only people with the link)'}\n\n"
                    f"To load this context in any new session:\n"
                    f"  gtf_switch(url=\"{gist_url}\")\n\n"
                    f"Or share this link with a teammate — they can load your full project context instantly."
                ),
            )]

        except FileNotFoundError:
            return [types.TextContent(
                type="text",
                text=(
                    "❌ GitHub CLI (gh) not found.\n\n"
                    "Install it with:\n"
                    "  winget install GitHub.cli\n\n"
                    "Then authenticate:\n"
                    "  gh auth login"
                ),
            )]
        except subprocess.TimeoutExpired:
            return [types.TextContent(type="text", text="❌ Timed out uploading to GitHub Gist. Check your internet connection.")]
        except Exception as exc:
            return [types.TextContent(type="text", text=f"❌ Error: {exc}")]
        finally:
            import shutil as _shutil
            _shutil.rmtree(tmp_share_dir, ignore_errors=True)

    # ── Unknown ──────────────────────────────────────────────────────────────
    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import traceback
    _log = Path.home() / ".mnemo_startup.log"
    try:
        _log.write_text(
            f"[{datetime.now().isoformat()}] Mnemo MCP starting...\n"
            f"Python: {sys.executable}\n"
            f"Args: {sys.argv}\n",
            encoding="utf-8",
        )
        asyncio.run(main())
    except Exception as _exc:
        with open(_log, "a", encoding="utf-8") as _fh:
            _fh.write(f"\n[{datetime.now().isoformat()}] CRASH:\n")
            traceback.print_exc(file=_fh)
        raise
