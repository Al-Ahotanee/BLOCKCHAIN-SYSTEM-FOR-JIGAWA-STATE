"""
JIGAWA STATE API SERVER
=======================
Blockchain-Based Asset Registry for Public Sector Accountability
Jigawa State Government — Flask REST API (Production Ready)

Endpoints:
  POST /api/auth/login
  POST /api/auth/logout
  GET  /api/dashboard
  POST /api/assets/register
  GET  /api/assets
  GET  /api/assets/<asset_id>
  GET  /api/assets/<asset_id>/history
  POST /api/assets/transfer
  POST /api/assets/audit
  POST /api/blockchain/mine
  GET  /api/blockchain/chain
  GET  /api/blockchain/validate
  GET  /api/blockchain/stats
  GET  /api/reports/export
  GET  /api/reports/audit-log
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

# ─────────────────────────────────────────────────────────
#  APP SETUP & CONFIGURATION
# ─────────────────────────────────────────────────────────

# Define the base directory for serving static HTML files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Setup dynamic Database Path for Railway Persistent Volumes
# If DATABASE_PATH env variable exists (e.g. /data/jigawa_registry.db), use it. Otherwise, use local directory.
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "jigawa_registry.db"))
SESSION_EXPIRY_HOURS = 8

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
app.config["SECRET_KEY"] = secrets.token_hex(32)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# ─────────────────────────────────────────────────────────
#  PAGE ROUTES (Serve HTML files)
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
#  USER / SESSION DATABASE INITIALIZATION
# ─────────────────────────────────────────────────────────

def init_user_db():
    """Initializes the database tables for users, sessions, and audit logs."""
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
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT,
            expires_at TEXT
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

    # Seed default government users if the table is empty
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        default_users = [
            ("USR-001", "admin",     _hash_pw("Admin@2025!"),  "System Administrator",     "admin",    "ICT Department"),
            ("USR-002", "auditor1",  _hash_pw("Audit@2025!"),  "Bello Musa (State Auditor)","auditor",  "Audit Department"),
            ("USR-003", "assetmgr1", _hash_pw("Asset@2025!"),  "Fatima Abdullahi",          "manager",  "Finance & Assets"),
            ("USR-004", "viewer1",   _hash_pw("View@2025!"),   "Ibrahim Sule",              "viewer",   "Ministry of Works"),
        ]
        now = datetime.now(timezone.utc).isoformat()
        for user_data in default_users:
            c.execute(
                "INSERT INTO users (user_id, username, password, full_name, role, department, created_at) VALUES (?,?,?,?,?,?,?)", 
                (*user_data, now)
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
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(hours=SESSION_EXPIRY_HOURS)).isoformat()
    
    conn = get_db()
    conn.execute("INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                 (token, user_id, now.isoformat(), expires))
    conn.commit()
    conn.close()
    return token

def get_current_user(token: str) -> dict | None:
    conn = get_db()
    row = conn.execute("""
        SELECT u.*, s.expires_at 
        FROM users u 
        JOIN sessions s ON u.user_id = s.user_id 
        WHERE s.token = ? AND u.active = 1
    """, (token,)).fetchone()
    conn.close()
    
    if not row: 
        return None
    
    user = dict(row)
    try:
        exp = datetime.fromisoformat(user["expires_at"])
        if exp.tzinfo is None: 
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp: 
            return None
    except Exception:
        return None
        
    return user

def require_auth(*roles):
    """Decorator to enforce JWT-like Session authentication and RBAC."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Authentication required. Bearer token missing."}), 401
                
            token = auth_header.split(" ", 1)[1]
            user = get_current_user(token)
            
            if not user:
                return jsonify({"error": "Invalid or expired session. Please log in again."}), 401
                
            if roles and user["role"] not in roles:
                return jsonify({"error": f"Access denied. Required roles: {list(roles)}"}), 403
                
            g.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def log_action(action: str, detail: str = ""):
    """Records user actions in the immutable audit log table."""
    try:
        user_id = getattr(g, "current_user", {}).get("user_id", "anonymous")
        conn = get_db()
        conn.execute("INSERT INTO audit_logs (log_id, user_id, action, detail, ip_address, created_at) VALUES (?,?,?,?,?,?)",
                     (str(uuid.uuid4()), user_id, action, detail, request.remote_addr, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to log action: {e}")

# ─────────────────────────────────────────────────────────
#  API ROUTES — AUTHENTICATION
# ─────────────────────────────────────────────────────────

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=? AND password=? AND active=1",
                        (username, _hash_pw(password))).fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "Invalid credentials provided."}), 401

    user = dict(user)
    token = create_session(user["user_id"])
    log_action("LOGIN", f"User '{username}' established a secure session.")

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
        conn.commit()
        conn.close()
    return jsonify({"message": "Session terminated successfully."})

# ─────────────────────────────────────────────────────────
#  API ROUTES — DASHBOARD & ASSETS
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
        "message": f"Asset successfully registered in block #{block.index if block else '?'}"
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
        return jsonify({"error": "Asset could not be found in the registry."}), 404
        
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
    
    bc = get_blockchain(DB_PATH)
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
        "message": "Asset transfer contract successfully recorded."
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
        "message": "Audit findings officially recorded."
    })


# ─────────────────────────────────────────────────────────
#  API ROUTES — BLOCKCHAIN CORE & REPORTS
# ─────────────────────────────────────────────────────────

@app.route("/api/blockchain/mine", methods=["POST"])
@require_auth("admin")
def mine():
    bc = get_blockchain(DB_PATH)
    block = bc.mine_block(miner=g.current_user["username"])
    
    if not block:
        return jsonify({"message": "No pending transactions in the mempool."}), 200
        
    log_action("MINE_BLOCK", f"Block #{block.index} successfully mined by {g.current_user['username']}")
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
    end = start + per_page
    
    return jsonify({
        "chain": full_chain[start:end],
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
    
    log_action("EXPORT_REPORT", f"Official report exported by {g.current_user['username']}")
    
    response = make_response(json.dumps(report, indent=2))
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = f'attachment; filename="jigawa_registry_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
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


# ─────────────────────────────────────────────────────────
#  HEALTH CHECK
# ─────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "system": "Jigawa State Blockchain Asset Registry",
        "jurisdiction": "Jigawa State",
        "version": "1.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ─────────────────────────────────────────────────────────
#  INITIALIZATION (CRITICAL FOR GUNICORN / RAILWAY)
# ─────────────────────────────────────────────────────────

# When deploying to Railway using Gunicorn, the `if __name__ == "__main__":` block is skipped.
# We must initialize the database and blockchain globally so it runs upon worker startup.
with app.app_context():
    try:
        init_user_db()
        get_blockchain(DB_PATH)
        print(f"[*] App Initialized Successfully. Using Database at: {DB_PATH}")
    except Exception as e:
        print(f"[!] Critical Initialization Error: {e}")

# ─────────────────────────────────────────────────────────
#  LOCAL ENTRY POINT (FLASK DEVELOPMENT SERVER)
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Get port from environment variables, fallback to 5000 (Required for Railway)
    port = int(os.environ.get("PORT", 5000))
    
    bc = get_blockchain(DB_PATH)
    print("=" * 60)
    print("  Jigawa State Blockchain Asset Registry")
    print("  Jigawa State Government System")
    print("=" * 60)
    stats = bc.get_chain_stats()
    print(f"  Blocks:       {stats['total_blocks']}")
    print(f"  Assets:       {stats['registered_assets']}")
    print(f"  Transactions: {stats['total_transactions']}")
    print(f"  Network:      {stats['network']}")
    print(f"  Database:     {DB_PATH}")
    print("=" * 60)
    print(f"\n  System running locally at: http://localhost:{port}")
    print("  Default credentials: admin / Admin@2025!")
    print("=" * 60 + "\n")
    
    app.run(host="0.0.0.0", port=port, debug=False)
