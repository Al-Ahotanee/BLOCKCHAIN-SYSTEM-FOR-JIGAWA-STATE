"""
JIGAWA STATE API SERVER
=======================
Blockchain-Based Asset Registry for Public Sector Accountability
Jigawa State Government — Flask REST API (Production Ready)
"""

import os
import json
import uuid
import hashlib
import sqlite3
import secrets
import functools
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify, g, make_response, send_from_directory
from flask_cors import CORS

from blockchain import get_blockchain, JigawaBlockchain

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "jigawa_registry.db"))
SESSION_EXPIRY_HOURS = 8
HIGH_VALUE_THRESHOLD = 10_000_000

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
app.config["SECRET_KEY"] = secrets.token_hex(32)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# ─────────────────────────────────────────────────────────
#  PAGE ROUTES
# ─────────────────────────────────────────────────────────

@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "login.html")

@app.route("/login")
@app.route("/login.html")
def login_page():
    return send_from_directory(BASE_DIR, "login.html")

@app.route("/dashboard")
@app.route("/index.html")
def dashboard_page():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/verify")
@app.route("/verify.html")
def verify_page():
    return send_from_directory(BASE_DIR, "verify.html")

# ─────────────────────────────────────────────────────────
#  DATABASE INITIALIZATION
# ─────────────────────────────────────────────────────────

def init_user_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'viewer',
            department TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            token TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            ip_address TEXT,
            created_at TEXT,
            last_activity TEXT,
            expires_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS token_blocklist (
            token TEXT PRIMARY KEY,
            blocked_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id TEXT PRIMARY KEY,
            user_id TEXT,
            action TEXT,
            detail TEXT,
            ip_address TEXT,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_approvals (
            approval_id TEXT PRIMARY KEY,
            approval_type TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            review_note TEXT,
            created_at TEXT,
            reviewed_at TEXT
        )
    """)

    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        default_users = [
            ("USR-001", "admin",     _hash_pw("Admin@2025!"),  "System Administrator",      "admin",   "ICT Department"),
            ("USR-002", "auditor1",  _hash_pw("Audit@2025!"),  "Bello Musa (State Auditor)", "auditor", "Audit Department"),
            ("USR-003", "assetmgr1", _hash_pw("Asset@2025!"),  "Fatima Abdullahi",           "manager", "Finance & Assets"),
            ("USR-004", "viewer1",   _hash_pw("View@2025!"),   "Ibrahim Sule",               "viewer",  "Ministry of Works"),
        ]
        now = datetime.now(timezone.utc).isoformat()
        for ud in default_users:
            c.execute(
                "INSERT INTO users (user_id, username, password, full_name, role, department, created_at) VALUES (?,?,?,?,?,?,?)",
                (*ud, now)
            )

    conn.commit()
    conn.close()


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ─────────────────────────────────────────────────────────
#  AUTH HELPERS
# ─────────────────────────────────────────────────────────

def create_session(user_id: str) -> str:
    token = secrets.token_hex(32)
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(hours=SESSION_EXPIRY_HOURS)).isoformat()
    ip = request.remote_addr

    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (session_id, token, user_id, ip_address, created_at, last_activity, expires_at) VALUES (?,?,?,?,?,?,?)",
        (session_id, token, user_id, ip, now.isoformat(), now.isoformat(), expires)
    )
    conn.commit()
    conn.close()
    return token


def get_current_user(token: str):
    conn = get_db()

    # Check blocklist
    blocked = conn.execute("SELECT token FROM token_blocklist WHERE token=?", (token,)).fetchone()
    if blocked:
        conn.close()
        return None

    row = conn.execute("""
        SELECT u.*, s.expires_at, s.session_id
        FROM users u
        JOIN sessions s ON u.user_id = s.user_id
        WHERE s.token = ? AND u.active = 1
    """, (token,)).fetchone()

    if not row:
        conn.close()
        return None

    user = dict(row)
    try:
        exp = datetime.fromisoformat(user["expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp:
            conn.close()
            return None
    except Exception:
        conn.close()
        return None

    # Update last_activity
    conn.execute("UPDATE sessions SET last_activity=? WHERE token=?",
                 (datetime.now(timezone.utc).isoformat(), token))
    conn.commit()
    conn.close()
    return user


def require_auth(*roles):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Authentication required."}), 401
            token = auth_header.split(" ", 1)[1]
            user = get_current_user(token)
            if not user:
                return jsonify({"error": "Invalid or expired session."}), 401
            if roles and user["role"] not in roles:
                return jsonify({"error": f"Access denied. Required roles: {list(roles)}"}), 403
            g.current_user = user
            g.token = token
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def log_action(action: str, detail: str = ""):
    try:
        user_id = getattr(g, "current_user", {}).get("user_id", "anonymous")
        conn = get_db()
        conn.execute(
            "INSERT INTO audit_logs (log_id, user_id, action, detail, ip_address, created_at) VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), user_id, action, detail, request.remote_addr, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to log action: {e}")

# ─────────────────────────────────────────────────────────
#  AUTH ROUTES
# ─────────────────────────────────────────────────────────

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=? AND active=1",
        (username, _hash_pw(password))
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "Invalid credentials."}), 401

    user = dict(user)
    token = create_session(user["user_id"])
    log_action("LOGIN", f"User '{username}' logged in.")

    return jsonify({
        "token": token,
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "department": user["department"]
        }
    })


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        conn = get_db()
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.execute(
            "INSERT OR IGNORE INTO token_blocklist (token, blocked_at) VALUES (?,?)",
            (token, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
    return jsonify({"message": "Session terminated."})

# ─────────────────────────────────────────────────────────
#  FEATURE 1 — USER MANAGEMENT (CRUD)
# ─────────────────────────────────────────────────────────

@app.route("/api/users", methods=["GET"])
@require_auth("admin")
def list_users():
    conn = get_db()
    users = conn.execute(
        "SELECT user_id, username, full_name, role, department, active, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify({"users": [dict(u) for u in users]})


@app.route("/api/users", methods=["POST"])
@require_auth("admin")
def create_user():
    data = request.get_json(silent=True) or {}
    required = ["username", "password", "full_name", "role", "department"]
    for f in required:
        if not data.get(f):
            return jsonify({"error": f"Missing field: {f}"}), 400

    valid_roles = ["admin", "manager", "auditor", "viewer"]
    if data["role"] not in valid_roles:
        return jsonify({"error": f"Invalid role. Must be one of: {valid_roles}"}), 400

    user_id = f"USR-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO users (user_id, username, password, full_name, role, department, active, created_at) VALUES (?,?,?,?,?,?,1,?)",
            (user_id, data["username"].strip().lower(), _hash_pw(data["password"]),
             data["full_name"], data["role"], data["department"], now)
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already exists."}), 409

    log_action("CREATE_USER", f"User '{data['username']}' created by {g.current_user['username']}")
    return jsonify({"success": True, "user_id": user_id}), 201


@app.route("/api/users/<user_id>", methods=["PUT"])
@require_auth("admin")
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    fields = []
    params = []
    allowed = ["full_name", "role", "department", "active"]
    for f in allowed:
        if f in data:
            fields.append(f"{f}=?")
            params.append(data[f])

    if data.get("password"):
        fields.append("password=?")
        params.append(_hash_pw(data["password"]))

    if not fields:
        conn.close()
        return jsonify({"error": "No fields to update"}), 400

    params.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id=?", params)
    conn.commit()
    conn.close()
    log_action("UPDATE_USER", f"User {user_id} updated by {g.current_user['username']}")
    return jsonify({"success": True})


@app.route("/api/users/<user_id>", methods=["DELETE"])
@require_auth("admin")
def delete_user(user_id):
    if user_id == g.current_user["user_id"]:
        return jsonify({"error": "Cannot delete your own account"}), 400
    conn = get_db()
    conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    log_action("DELETE_USER", f"User {user_id} deleted by {g.current_user['username']}")
    return jsonify({"success": True})

# ─────────────────────────────────────────────────────────
#  FEATURE 3 — BULK ASSET IMPORT
# ─────────────────────────────────────────────────────────

@app.route("/api/assets/bulk-register", methods=["POST"])
@require_auth("admin", "manager")
def bulk_register():
    data = request.get_json(silent=True) or {}
    assets = data.get("assets", [])
    if not assets:
        return jsonify({"error": "No assets provided"}), 400

    bc = get_blockchain(DB_PATH)
    success_count = 0
    fail_count = 0
    errors = []

    for i, asset in enumerate(assets):
        if not asset.get("asset_id"):
            asset["asset_id"] = f"JSG-{uuid.uuid4().hex[:8].upper()}"
        result = bc.execute_transaction(action="REGISTER_ASSET", payload=asset, actor=g.current_user["username"])
        if result["success"]:
            success_count += 1
        else:
            fail_count += 1
            errors.append({"row": i + 1, "asset_name": asset.get("asset_name", ""), "error": result["error"]})

    if success_count > 0:
        bc.mine_block(miner=g.current_user["username"])

    log_action("BULK_IMPORT", f"{success_count} assets imported by {g.current_user['username']}")
    return jsonify({"success": True, "imported": success_count, "failed": fail_count, "errors": errors})

# ─────────────────────────────────────────────────────────
#  FEATURE 4 — ASSET DISPOSAL WORKFLOW
# ─────────────────────────────────────────────────────────

@app.route("/api/assets/dispose/request", methods=["POST"])
@require_auth("admin", "manager")
def request_disposal():
    data = request.get_json(silent=True) or {}
    required = ["asset_id", "reason", "residual_value", "supporting_note"]
    for f in required:
        if not str(data.get(f, "")).strip():
            return jsonify({"error": f"Missing field: {f}"}), 400

    approval_id = f"DISP-{uuid.uuid4().hex[:8].upper()}"
    conn = get_db()
    conn.execute(
        "INSERT INTO pending_approvals (approval_id, approval_type, asset_id, requested_by, payload, status, created_at) VALUES (?,?,?,?,?,?,?)",
        (approval_id, "DISPOSAL", data["asset_id"], g.current_user["username"],
         json.dumps(data), "pending", datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    log_action("DISPOSAL_REQUEST", f"Disposal requested for {data['asset_id']} by {g.current_user['username']}")
    return jsonify({"success": True, "approval_id": approval_id})


@app.route("/api/assets/dispose/approve", methods=["POST"])
@require_auth("admin")
def approve_disposal():
    data = request.get_json(silent=True) or {}
    approval_id = data.get("approval_id")
    if not approval_id:
        return jsonify({"error": "approval_id required"}), 400

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM pending_approvals WHERE approval_id=? AND approval_type='DISPOSAL' AND status='pending'",
        (approval_id,)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Pending disposal not found"}), 404

    row = dict(row)
    payload = json.loads(row["payload"])
    payload["authorized_by"] = g.current_user["username"]
    payload["status"] = "Disposed"

    bc = get_blockchain(DB_PATH)
    # Record disposal as audit on chain
    audit_payload = {
        "asset_id": row["asset_id"],
        "auditor": g.current_user["username"],
        "audit_type": "Disposal",
        "findings": f"Asset disposed. Reason: {payload.get('reason')}. Residual value: {payload.get('residual_value')}"
    }
    result = bc.execute_transaction(action="AUDIT_ASSET", payload=audit_payload, actor=g.current_user["username"])
    if result["success"]:
        block = bc.mine_block(miner=g.current_user["username"])

        # Update asset status in DB
        db2 = sqlite3.connect(DB_PATH)
        db2.execute("UPDATE assets SET status='Disposed' WHERE asset_id=?", (row["asset_id"],))
        db2.commit()
        db2.close()

    conn.execute(
        "UPDATE pending_approvals SET status='approved', reviewed_by=?, reviewed_at=?, review_note=? WHERE approval_id=?",
        (g.current_user["username"], datetime.now(timezone.utc).isoformat(), data.get("note", ""), approval_id)
    )
    conn.commit()
    conn.close()
    log_action("DISPOSAL_APPROVED", f"Disposal of {row['asset_id']} approved by {g.current_user['username']}")
    return jsonify({"success": True})


@app.route("/api/assets/dispose/reject", methods=["POST"])
@require_auth("admin")
def reject_disposal():
    data = request.get_json(silent=True) or {}
    approval_id = data.get("approval_id")
    conn = get_db()
    conn.execute(
        "UPDATE pending_approvals SET status='rejected', reviewed_by=?, reviewed_at=?, review_note=? WHERE approval_id=? AND approval_type='DISPOSAL'",
        (g.current_user["username"], datetime.now(timezone.utc).isoformat(), data.get("note", ""), approval_id)
    )
    conn.commit()
    conn.close()
    log_action("DISPOSAL_REJECTED", f"Disposal {approval_id} rejected by {g.current_user['username']}")
    return jsonify({"success": True})

# ─────────────────────────────────────────────────────────
#  FEATURE 6 — HIGH-VALUE TRANSFER APPROVAL WORKFLOW
# ─────────────────────────────────────────────────────────

@app.route("/api/assets/transfer/request", methods=["POST"])
@require_auth("admin", "manager")
def request_transfer():
    data = request.get_json(silent=True) or {}
    required = ["asset_id", "from_owner", "to_owner", "reason"]
    for f in required:
        if not str(data.get(f, "")).strip():
            return jsonify({"error": f"Missing field: {f}"}), 400

    approval_id = f"TRF-{uuid.uuid4().hex[:8].upper()}"
    conn = get_db()
    conn.execute(
        "INSERT INTO pending_approvals (approval_id, approval_type, asset_id, requested_by, payload, status, created_at) VALUES (?,?,?,?,?,?,?)",
        (approval_id, "TRANSFER", data["asset_id"], g.current_user["username"],
         json.dumps(data), "pending", datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    log_action("TRANSFER_REQUEST", f"Transfer requested for {data['asset_id']} by {g.current_user['username']}")
    return jsonify({"success": True, "approval_id": approval_id})


@app.route("/api/assets/transfer/approve", methods=["POST"])
@require_auth("admin")
def approve_transfer():
    data = request.get_json(silent=True) or {}
    approval_id = data.get("approval_id")

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM pending_approvals WHERE approval_id=? AND approval_type='TRANSFER' AND status='pending'",
        (approval_id,)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Pending transfer not found"}), 404

    row = dict(row)
    payload = json.loads(row["payload"])
    payload["authorized_by"] = g.current_user["username"]

    bc = get_blockchain(DB_PATH)
    result = bc.execute_transaction(action="TRANSFER_ASSET", payload=payload, actor=g.current_user["username"])
    if not result["success"]:
        conn.close()
        return jsonify(result), 400

    bc.mine_block(miner=g.current_user["username"])
    conn.execute(
        "UPDATE pending_approvals SET status='approved', reviewed_by=?, reviewed_at=?, review_note=? WHERE approval_id=?",
        (g.current_user["username"], datetime.now(timezone.utc).isoformat(), data.get("note", ""), approval_id)
    )
    conn.commit()
    conn.close()
    log_action("TRANSFER_APPROVED", f"Transfer of {row['asset_id']} approved by {g.current_user['username']}")
    return jsonify({"success": True})


@app.route("/api/assets/transfer/reject", methods=["POST"])
@require_auth("admin")
def reject_transfer():
    data = request.get_json(silent=True) or {}
    approval_id = data.get("approval_id")
    conn = get_db()
    conn.execute(
        "UPDATE pending_approvals SET status='rejected', reviewed_by=?, reviewed_at=?, review_note=? WHERE approval_id=? AND approval_type='TRANSFER'",
        (g.current_user["username"], datetime.now(timezone.utc).isoformat(), data.get("note", ""), approval_id)
    )
    conn.commit()
    conn.close()
    log_action("TRANSFER_REJECTED", f"Transfer {approval_id} rejected by {g.current_user['username']}")
    return jsonify({"success": True})


@app.route("/api/assets/pending-approvals", methods=["GET"])
@require_auth("admin", "manager")
def list_pending_approvals():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM pending_approvals WHERE status='pending' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        item = dict(r)
        item["payload"] = json.loads(item["payload"])
        result.append(item)
    return jsonify({"approvals": result})

# ─────────────────────────────────────────────────────────
#  EXISTING ASSET ROUTES (updated transfer to check high-value)
# ─────────────────────────────────────────────────────────

@app.route("/api/dashboard", methods=["GET"])
@require_auth()
def dashboard():
    bc = get_blockchain(DB_PATH)
    return jsonify(bc.get_dashboard_stats())


@app.route("/api/assets/register", methods=["POST"])
@require_auth("admin", "manager")
def register_asset():
    data = request.get_json(silent=True) or {}
    if not data.get("asset_id"):
        data["asset_id"] = f"JSG-{uuid.uuid4().hex[:8].upper()}"

    bc = get_blockchain(DB_PATH)
    result = bc.execute_transaction(action="REGISTER_ASSET", payload=data, actor=g.current_user["username"])

    if not result["success"]:
        return jsonify(result), 400

    block = bc.mine_block(miner=g.current_user["username"])
    log_action("REGISTER_ASSET", f"Asset {data.get('asset_id')} registered by {g.current_user['username']}")

    return jsonify({
        "success": True,
        "asset_id": data["asset_id"],
        "tx_id": result["tx_id"],
        "block_index": block.index if block else None,
        "block_hash": block.hash if block else None,
        "message": f"Asset registered in block #{block.index if block else '?'}"
    }), 201


@app.route("/api/assets", methods=["GET"])
@require_auth()
def list_assets():
    bc = get_blockchain(DB_PATH)
    filters = {}
    if request.args.get("category"): filters["category"] = request.args.get("category")
    if request.args.get("department"): filters["department"] = request.args.get("department")
    if request.args.get("status"): filters["status"] = request.args.get("status")
    if request.args.get("search"): filters["search"] = request.args.get("search")
    assets = bc.get_all_assets_from_db(filters)
    return jsonify({"assets": assets, "total": len(assets)})


@app.route("/api/assets/<asset_id>", methods=["GET"])
@require_auth()
def get_asset(asset_id):
    bc = get_blockchain(DB_PATH)
    assets = bc.get_all_assets_from_db({"search": asset_id})
    asset = next((a for a in assets if a["asset_id"] == asset_id), None)
    if not asset:
        return jsonify({"error": "Asset not found."}), 404
    history = bc.get_asset_history(asset_id)
    return jsonify({"asset": asset, "history": history})


@app.route("/api/assets/<asset_id>/history", methods=["GET"])
@require_auth()
def get_asset_history(asset_id):
    bc = get_blockchain(DB_PATH)
    history = bc.get_asset_history(asset_id)
    return jsonify({"asset_id": asset_id, "history": history})


@app.route("/api/assets/transfer", methods=["POST"])
@require_auth("admin", "manager")
def transfer_asset():
    data = request.get_json(silent=True) or {}
    data["authorized_by"] = g.current_user["username"]

    # Check if high-value — route to approval workflow
    bc = get_blockchain(DB_PATH)
    assets = bc.get_all_assets_from_db({"search": data.get("asset_id", "")})
    asset = next((a for a in assets if a["asset_id"] == data.get("asset_id")), None)

    if asset and float(asset.get("asset_value", 0)) >= HIGH_VALUE_THRESHOLD and g.current_user["role"] != "admin":
        # Non-admins must go through approval
        approval_id = f"TRF-{uuid.uuid4().hex[:8].upper()}"
        conn = get_db()
        conn.execute(
            "INSERT INTO pending_approvals (approval_id, approval_type, asset_id, requested_by, payload, status, created_at) VALUES (?,?,?,?,?,?,?)",
            (approval_id, "TRANSFER", data["asset_id"], g.current_user["username"],
             json.dumps(data), "pending", datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        log_action("TRANSFER_REQUEST", f"High-value transfer queued for {data['asset_id']}")
        return jsonify({
            "success": True,
            "pending": True,
            "approval_id": approval_id,
            "message": "High-value asset transfer submitted for admin approval."
        })

    result = bc.execute_transaction(action="TRANSFER_ASSET", payload=data, actor=g.current_user["username"])
    if not result["success"]:
        return jsonify(result), 400

    block = bc.mine_block(miner=g.current_user["username"])
    log_action("TRANSFER_ASSET", f"Asset {data.get('asset_id')} transferred to {data.get('to_owner')}")
    return jsonify({
        "success": True,
        "tx_id": result["tx_id"],
        "block_index": block.index if block else None,
        "block_hash": block.hash if block else None,
        "message": "Transfer recorded."
    })


@app.route("/api/assets/audit", methods=["POST"])
@require_auth("admin", "auditor", "manager")
def audit_asset():
    data = request.get_json(silent=True) or {}
    data["auditor"] = g.current_user["username"]

    bc = get_blockchain(DB_PATH)
    result = bc.execute_transaction(action="AUDIT_ASSET", payload=data, actor=g.current_user["username"])
    if not result["success"]:
        return jsonify(result), 400

    block = bc.mine_block(miner=g.current_user["username"])
    log_action("AUDIT_ASSET", f"Asset {data.get('asset_id')} audited by {g.current_user['username']}")
    return jsonify({
        "success": True,
        "tx_id": result["tx_id"],
        "audit_id": result["contract"].get("audit_id"),
        "block_index": block.index if block else None,
        "block_hash": block.hash if block else None,
        "message": "Audit recorded."
    })

# ─────────────────────────────────────────────────────────
#  FEATURE 8 — SESSION MANAGEMENT
# ─────────────────────────────────────────────────────────

@app.route("/api/sessions", methods=["GET"])
@require_auth("admin")
def list_sessions():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.session_id, s.token, s.ip_address, s.created_at, s.last_activity, s.expires_at,
               u.username, u.full_name, u.role
        FROM sessions s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.expires_at > ?
        ORDER BY s.last_activity DESC
    """, (datetime.now(timezone.utc).isoformat(),)).fetchall()
    conn.close()
    sessions = []
    for r in rows:
        s = dict(r)
        s["token"] = s["token"][:8] + "..."  # mask token
        sessions.append(s)
    return jsonify({"sessions": sessions})


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
@require_auth("admin")
def force_logout(session_id):
    conn = get_db()
    row = conn.execute("SELECT token FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Session not found"}), 404

    token = row["token"]
    conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
    conn.execute(
        "INSERT OR IGNORE INTO token_blocklist (token, blocked_at) VALUES (?,?)",
        (token, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    log_action("FORCE_LOGOUT", f"Session {session_id} force-terminated by {g.current_user['username']}")
    return jsonify({"success": True})

# ─────────────────────────────────────────────────────────
#  BLOCKCHAIN & REPORTS
# ─────────────────────────────────────────────────────────

@app.route("/api/blockchain/mine", methods=["POST"])
@require_auth("admin")
def mine():
    bc = get_blockchain(DB_PATH)
    block = bc.mine_block(miner=g.current_user["username"])
    if not block:
        return jsonify({"message": "No pending transactions."}), 200
    log_action("MINE_BLOCK", f"Block #{block.index} mined by {g.current_user['username']}")
    return jsonify({"success": True, "block": block.to_dict()})


@app.route("/api/blockchain/chain", methods=["GET"])
@require_auth()
def get_chain():
    bc = get_blockchain(DB_PATH)
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    full_chain = list(reversed(bc.get_full_chain()))
    total = len(full_chain)
    start = (page - 1) * per_page
    return jsonify({
        "chain": full_chain[start:start + per_page],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    })


@app.route("/api/blockchain/validate", methods=["GET"])
@require_auth()
def validate_chain():
    bc = get_blockchain(DB_PATH)
    return jsonify(bc.is_chain_valid())


@app.route("/api/blockchain/stats", methods=["GET"])
@require_auth()
def blockchain_stats():
    bc = get_blockchain(DB_PATH)
    return jsonify(bc.get_chain_stats())


@app.route("/api/reports/export", methods=["GET"])
@require_auth("admin", "auditor", "manager")
def export_report():
    bc = get_blockchain(DB_PATH)
    report = {
        "report_title": "Jigawa State Asset Registry — Official Cryptographic Report",
        "jurisdiction": "Jigawa State, Federal Republic of Nigeria",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": g.current_user["full_name"],
        "blockchain_status": "VALID" if bc.get_dashboard_stats()["chain_valid"] else "INVALID",
        "summary": bc.get_dashboard_stats(),
        "assets": bc.get_all_assets_from_db()
    }
    log_action("EXPORT_REPORT", f"Report exported by {g.current_user['username']}")
    response = make_response(json.dumps(report, indent=2))
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = f'attachment; filename="jigawa_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
    return response


@app.route("/api/reports/audit-log", methods=["GET"])
@require_auth("admin", "auditor")
def get_audit_log():
    conn = get_db()
    logs = conn.execute("""
        SELECT al.*, u.full_name
        FROM audit_logs al
        LEFT JOIN users u ON al.user_id = u.user_id
        ORDER BY al.created_at DESC
        LIMIT 200
    """).fetchall()
    conn.close()
    return jsonify({"logs": [dict(r) for r in logs]})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "system": "Jigawa State Blockchain Asset Registry",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

# ─────────────────────────────────────────────────────────
#  INITIALIZATION
# ─────────────────────────────────────────────────────────

with app.app_context():
    try:
        init_user_db()
        get_blockchain(DB_PATH)
        print(f"[*] App Initialized. DB: {DB_PATH}")
    except Exception as e:
        print(f"[!] Init Error: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    bc = get_blockchain(DB_PATH)
    stats = bc.get_chain_stats()
    print("=" * 60)
    print("  Jigawa State Blockchain Asset Registry v2.0")
    print(f"  Blocks: {stats['total_blocks']}  |  Assets: {stats['registered_assets']}")
    print(f"  Running at: http://localhost:{port}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False)
