from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import json
import os
from datetime import datetime

app = FastAPI(title="KRM — Kinetic Requirements Model")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.environ.get("KRM_DB_PATH", "/data/krm.db")

# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            state TEXT NOT NULL CHECK(state IN ('current','kinetic','desired')),
            role TEXT NOT NULL CHECK(role IN ('stakeholder','user','engineer')),
            story TEXT,
            scope_gate TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS queue_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cell_id INTEGER NOT NULL REFERENCES cells(id) ON DELETE CASCADE,
            order_num INTEGER NOT NULL DEFAULT 1,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active','closed','deferred','blocked')),
            notes TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ── Models ────────────────────────────────────────────────────────────────────

class ProjectIn(BaseModel):
    name: str
    description: Optional[str] = None

class CellIn(BaseModel):
    story: Optional[str] = None
    scope_gate: Optional[str] = None

class QueueItemIn(BaseModel):
    order_num: Optional[int] = 1
    description: Optional[str] = None
    status: Optional[str] = "pending"
    notes: Optional[str] = None

class ProjectImport(BaseModel):
    name: str
    description: Optional[str] = None
    cells: dict

# ── Helpers ───────────────────────────────────────────────────────────────────

STATES = ["current", "kinetic", "desired"]
ROLES  = ["stakeholder", "user", "engineer"]

def ensure_cells(conn, project_id):
    for state in STATES:
        for role in ROLES:
            existing = conn.execute(
                "SELECT id FROM cells WHERE project_id=? AND state=? AND role=?",
                (project_id, state, role)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO cells (project_id, state, role) VALUES (?,?,?)",
                    (project_id, state, role)
                )
    conn.commit()

def project_to_dict(conn, project_id):
    p = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not p:
        return None
    cells_raw = conn.execute("SELECT * FROM cells WHERE project_id=?", (project_id,)).fetchall()
    cells = {}
    for c in cells_raw:
        key = f"{c['state']}.{c['role']}"
        items = conn.execute(
            "SELECT * FROM queue_items WHERE cell_id=? ORDER BY order_num",
            (c['id'],)
        ).fetchall()
        cells[key] = {
            "id": c["id"],
            "state": c["state"],
            "role": c["role"],
            "story": c["story"],
            "scope_gate": c["scope_gate"],
            "queue": [dict(i) for i in items]
        }
    return {"id": p["id"], "name": p["name"], "description": p["description"],
            "created_at": p["created_at"], "updated_at": p["updated_at"], "cells": cells}

# ── Projects ──────────────────────────────────────────────────────────────────

@app.get("/api/projects")
def list_projects():
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/projects", status_code=201)
def create_project(body: ProjectIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO projects (name, description) VALUES (?,?)",
        (body.name, body.description)
    )
    conn.commit()
    pid = cur.lastrowid
    ensure_cells(conn, pid)
    result = project_to_dict(conn, pid)
    conn.close()
    return result

@app.post("/api/projects/import", status_code=201)
def import_project(body: ProjectImport):
    """Import a project from a JSON snapshot (as produced by /export/json)."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO projects (name, description) VALUES (?,?)",
        (body.name, body.description)
    )
    conn.commit()
    pid = cur.lastrowid
    ensure_cells(conn, pid)

    # Build a map of new cell ids keyed by state.role
    cells_raw = conn.execute("SELECT * FROM cells WHERE project_id=?", (pid,)).fetchall()
    cell_map = {f"{c['state']}.{c['role']}": c['id'] for c in cells_raw}

    # old queue item id -> new queue item id (needed to remap notes references)
    id_remap = {}

    for key, cell_data in body.cells.items():
        cell_id = cell_map.get(key)
        if not cell_id:
            continue

        # Update story / scope_gate
        story = cell_data.get("story")
        scope_gate = cell_data.get("scope_gate")
        if story or scope_gate:
            conn.execute(
                "UPDATE cells SET story=?, scope_gate=? WHERE id=?",
                (story, scope_gate, cell_id)
            )

        # Insert queue items preserving order_num
        for item in cell_data.get("queue", []):
            cur2 = conn.execute(
                "INSERT INTO queue_items (cell_id, order_num, description, status, notes) VALUES (?,?,?,?,?)",
                (cell_id, item.get("order_num", 1), item.get("description"), item.get("status", "pending"), item.get("notes"))
            )
            conn.commit()
            id_remap[item["id"]] = cur2.lastrowid

    # Remap all old IDs in notes fields to new IDs
    # Affected tags: upstream_for:<id>, declared:<ids>, covers:<ids>, split_from:<id>
    all_items = conn.execute(
        "SELECT qi.id, qi.notes FROM queue_items qi "
        "JOIN cells c ON qi.cell_id = c.id WHERE c.project_id=?", (pid,)
    ).fetchall()

    for item in all_items:
        notes = item["notes"]
        if not notes:
            continue
        new_notes = remap_notes_ids(notes, id_remap)
        if new_notes != notes:
            conn.execute("UPDATE queue_items SET notes=? WHERE id=?", (new_notes, item["id"]))

    conn.commit()
    result = project_to_dict(conn, pid)
    conn.close()
    return result

def remap_notes_ids(notes: str, id_remap: dict) -> str:
    """Replace old queue item IDs in notes field tags with new IDs."""
    import re

    def remap_id(old_id_str):
        old_id = int(old_id_str)
        return str(id_remap.get(old_id, old_id))

    def remap_id_list(old_ids_str):
        return ",".join(remap_id(i) for i in old_ids_str.split(",") if i.strip())

    # upstream_for:<single_id>
    notes = re.sub(r'upstream_for:(\d+)', lambda m: f'upstream_for:{remap_id(m.group(1))}', notes)
    # split_from:<single_id>
    notes = re.sub(r'split_from:(\d+)', lambda m: f'split_from:{remap_id(m.group(1))}', notes)
    # declared:<id_list>
    notes = re.sub(r'declared:([\d,]+)', lambda m: f'declared:{remap_id_list(m.group(1))}', notes)
    # covers:<id_list>
    notes = re.sub(r'covers:([\d,]+)', lambda m: f'covers:{remap_id_list(m.group(1))}', notes)

    return notes

@app.get("/api/projects/{pid}")
def get_project(pid: int):
    conn = get_db()
    result = project_to_dict(conn, pid)
    conn.close()
    if not result:
        raise HTTPException(404, "Project not found")
    return result

@app.delete("/api/projects/{pid}", status_code=204)
def delete_project(pid: int):
    conn = get_db()
    conn.execute("DELETE FROM projects WHERE id=?", (pid,))
    conn.commit()
    conn.close()

# ── Cells ─────────────────────────────────────────────────────────────────────

@app.patch("/api/projects/{pid}/cells/{state}/{role}")
def update_cell(pid: int, state: str, role: str, body: CellIn):
    conn = get_db()
    cell = conn.execute(
        "SELECT id FROM cells WHERE project_id=? AND state=? AND role=?",
        (pid, state, role)
    ).fetchone()
    if not cell:
        raise HTTPException(404, "Cell not found")
    conn.execute(
        "UPDATE cells SET story=?, scope_gate=?, updated_at=datetime('now') WHERE id=?",
        (body.story, body.scope_gate, cell["id"])
    )
    conn.execute("UPDATE projects SET updated_at=datetime('now') WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return {"ok": True}

# ── Queue Items ───────────────────────────────────────────────────────────────

@app.post("/api/projects/{pid}/cells/{state}/{role}/queue", status_code=201)
def add_queue_item(pid: int, state: str, role: str, body: QueueItemIn):
    conn = get_db()
    cell = conn.execute(
        "SELECT id FROM cells WHERE project_id=? AND state=? AND role=?",
        (pid, state, role)
    ).fetchone()
    if not cell:
        raise HTTPException(404, "Cell not found")
    max_order = conn.execute(
        "SELECT COALESCE(MAX(order_num),0) FROM queue_items WHERE cell_id=?",
        (cell["id"],)
    ).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO queue_items (cell_id, order_num, description, status, notes) VALUES (?,?,?,?,?)",
        (cell["id"], max_order + 1, body.description, body.status or "pending", body.notes)
    )
    conn.commit()
    item_id = cur.lastrowid
    item = conn.execute("SELECT * FROM queue_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return dict(item)

@app.patch("/api/queue/{item_id}")
def update_queue_item(item_id: int, body: QueueItemIn):
    conn = get_db()
    item = conn.execute("SELECT * FROM queue_items WHERE id=?", (item_id,)).fetchone()
    if not item:
        raise HTTPException(404, "Item not found")
    conn.execute(
        """UPDATE queue_items SET
           description=COALESCE(?,description),
           status=COALESCE(?,status),
           notes=COALESCE(?,notes),
           updated_at=datetime('now')
           WHERE id=?""",
        (body.description, body.status, body.notes, item_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/queue/{item_id}", status_code=204)
def delete_queue_item(item_id: int):
    conn = get_db()
    conn.execute("DELETE FROM queue_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()

# ── Export ────────────────────────────────────────────────────────────────────

@app.get("/api/projects/{pid}/export/json")
def export_json(pid: int):
    conn = get_db()
    data = project_to_dict(conn, pid)
    conn.close()
    if not data:
        raise HTTPException(404)
    return data

@app.get("/api/projects/{pid}/export/markdown", response_class=PlainTextResponse)
def export_markdown(pid: int):
    conn = get_db()
    data = project_to_dict(conn, pid)
    conn.close()
    if not data:
        raise HTTPException(404)

    lines = [f"# KRM — {data['name']}", ""]
    if data.get("description"):
        lines += [data["description"], ""]

    STATE_LABELS = {"current": "Current", "kinetic": "Kinetic", "desired": "Desired"}
    ROLE_LABELS  = {"stakeholder": "Owner / Stakeholder", "user": "User", "engineer": "Engineer"}

    for state in STATES:
        lines += [f"## {STATE_LABELS[state]} State", ""]
        for role in ROLES:
            key = f"{state}.{role}"
            cell = data["cells"].get(key, {})
            lines += [f"### {ROLE_LABELS[role]}", ""]
            story = cell.get("story") or "_Not yet defined._"
            gate  = cell.get("scope_gate") or "_Not yet defined._"
            lines += [f"**Story:** {story}", "", f"**Scope Gate:** {gate}", ""]
            queue = cell.get("queue", [])
            if queue:
                lines.append("**Yield Queue:**")
                lines.append("")
                lines.append("| # | Item | Status | Notes |")
                lines.append("|---|---|---|---|")
                for item in queue:
                    desc   = item.get("description") or ""
                    status = item.get("status") or ""
                    notes  = item.get("notes") or ""
                    lines.append(f"| {item['order_num']} | {desc} | {status} | {notes} |")
                lines.append("")
            else:
                lines += ["**Yield Queue:** _Empty._", ""]

    return "\n".join(lines)

# ── Static frontend ───────────────────────────────────────────────────────────

FRONTEND_DIR = "/app/frontend"
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", response_class=FileResponse)
    def serve_frontend():
        return FileResponse(f"{FRONTEND_DIR}/index.html")

    @app.get("/{full_path:path}", response_class=FileResponse)
    def serve_spa(full_path: str):
        return FileResponse(f"{FRONTEND_DIR}/index.html")
