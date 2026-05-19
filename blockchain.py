"""
JIGAWA STATE BLOCKCHAIN ENGINE
==========================
Blockchain-Based Asset Registry for Public Sector Accountability
Jigawa State Government — Enterprise Blockchain Layer

Local Python blockchain with:
- SHA-256 cryptographic hashing
- Proof-of-Work (PoW) consensus
- Smart Contract simulation (asset registration, transfer, audit)
- Chain integrity validation
- Merkle root for block transactions
- Tamper-proof immutable ledger
"""

import hashlib
import json
import time
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any


# ─────────────────────────────────────────────────────────
#  SMART CONTRACTS (Pure Python — stateless rule engines)
# ─────────────────────────────────────────────────────────

class SmartContract:
    """
    Base class for all smart contracts.
    Contracts are stateless validators; state lives on the chain.
    """

    @staticmethod
    def execute(action: str, payload: dict, chain_state: dict) -> dict:
        raise NotImplementedError


class AssetRegistrationContract(SmartContract):
    """
    SC-001: Asset Registration Contract
    Validates and registers a new government asset onto the blockchain.
    """

    REQUIRED_FIELDS = [
        "asset_id", "asset_name", "category", "department",
        "asset_value", "owner", "status"
    ]

    VALID_CATEGORIES = [
        "Building", "Vehicle", "Equipment", "Infrastructure",
        "Land", "Technology", "Furniture", "Other"
    ]

    VALID_STATUSES = ["Active", "Inactive", "Under Maintenance", "Disposed", "Transferred"]

    @classmethod
    def execute(cls, action: str, payload: dict, chain_state: dict) -> dict:
        if action != "REGISTER_ASSET":
            return {"success": False, "error": "Invalid action for AssetRegistrationContract"}

        for field in cls.REQUIRED_FIELDS:
            if field not in payload or not str(payload[field]).strip():
                return {"success": False, "error": f"Missing required field: {field}"}

        if payload["category"] not in cls.VALID_CATEGORIES:
            return {"success": False, "error": f"Invalid category. Must be one of: {', '.join(cls.VALID_CATEGORIES)}"}

        if payload["status"] not in cls.VALID_STATUSES:
            return {"success": False, "error": f"Invalid status. Must be one of: {', '.join(cls.VALID_STATUSES)}"}

        try:
            val = float(payload["asset_value"])
            if val <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return {"success": False, "error": "Asset value must be a positive number"}

        if payload["asset_id"] in chain_state.get("registered_assets", {}):
            return {"success": False, "error": f"Asset ID {payload['asset_id']} already registered on blockchain"}

        return {
            "success": True,
            "contract": "SC-001-AssetRegistration",
            "gas_used": 21000,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class AssetTransferContract(SmartContract):
    """
    SC-002: Asset Transfer Contract
    Validates and processes the transfer of an asset between departments or owners.
    """

    @classmethod
    def execute(cls, action: str, payload: dict, chain_state: dict) -> dict:
        if action != "TRANSFER_ASSET":
            return {"success": False, "error": "Invalid action for AssetTransferContract"}

        required = ["asset_id", "from_owner", "to_owner", "reason", "authorized_by"]
        for field in required:
            if field not in payload or not str(payload[field]).strip():
                return {"success": False, "error": f"Missing required field: {field}"}

        registered = chain_state.get("registered_assets", {})
        if payload["asset_id"] not in registered:
            return {"success": False, "error": f"Asset {payload['asset_id']} not found on blockchain"}

        current_asset = registered[payload["asset_id"]]
        if current_asset.get("owner") != payload["from_owner"]:
            return {"success": False, "error": f"Ownership mismatch. Current owner is '{current_asset.get('owner')}'"}

        if payload["from_owner"] == payload["to_owner"]:
            return {"success": False, "error": "Sender and receiver cannot be the same"}

        return {
            "success": True,
            "contract": "SC-002-AssetTransfer",
            "gas_used": 45000,
            "previous_owner": payload["from_owner"],
            "new_owner": payload["to_owner"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class AuditContract(SmartContract):
    """
    SC-003: Audit Contract
    Records official audits, physical verification, and valuation updates.
    """

    @classmethod
    def execute(cls, action: str, payload: dict, chain_state: dict) -> dict:
        if action != "AUDIT_ASSET":
            return {"success": False, "error": "Invalid action for AuditContract"}

        required = ["asset_id", "auditor", "audit_type", "findings"]
        for field in required:
            if field not in payload or not str(payload[field]).strip():
                return {"success": False, "error": f"Missing required field: {field}"}

        valid_audit_types = ["Routine", "Special", "Compliance", "Disposal", "Valuation"]
        if payload["audit_type"] not in valid_audit_types:
            return {"success": False, "error": f"Audit type must be one of: {', '.join(valid_audit_types)}"}

        registered = chain_state.get("registered_assets", {})
        if payload["asset_id"] not in registered:
            return {"success": False, "error": f"Asset {payload['asset_id']} not found on blockchain"}

        return {
            "success": True,
            "contract": "SC-003-Audit",
            "gas_used": 15000,
            "audit_id": f"AUD-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ─────────────────────────────────────────────────────────
#  BLOCK
# ─────────────────────────────────────────────────────────

class Block:
    DIFFICULTY = 3

    def __init__(self, index: int, transactions: List[dict], previous_hash: str, mined_by: str = "system"):
        self.index = index
        self.timestamp = time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.mined_by = mined_by
        self.merkle_root = self._compute_merkle_root()
        self.nonce = 0
        self.hash = self._mine()

    def _compute_merkle_root(self) -> str:
        if not self.transactions:
            return hashlib.sha256(b"empty").hexdigest()
        
        tx_hashes = [hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest() for tx in self.transactions]
        
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
            new_level = []
            for i in range(0, len(tx_hashes), 2):
                combined = tx_hashes[i] + tx_hashes[i + 1]
                new_level.append(hashlib.sha256(combined.encode()).hexdigest())
            tx_hashes = new_level
            
        return tx_hashes[0]

    def _compute_hash(self) -> str:
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
            "mined_by": self.mined_by
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def _mine(self) -> str:
        target = "0" * self.DIFFICULTY
        while True:
            h = self._compute_hash()
            if h.startswith(target):
                return h
            self.nonce += 1

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "timestamp_human": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
            "mined_by": self.mined_by,
            "hash": self.hash,
            "tx_count": len(self.transactions)
        }


# ─────────────────────────────────────────────────────────
#  BLOCKCHAIN
# ─────────────────────────────────────────────────────────

class JigawaBlockchain:
    CONTRACTS = {
        "REGISTER_ASSET": AssetRegistrationContract,
        "TRANSFER_ASSET": AssetTransferContract,
        "AUDIT_ASSET": AuditContract
    }

    def __init__(self, db_path: str = "jigawa.db"):
        self.db_path = db_path
        self.chain: List[Block] = []
        self.pending_transactions: List[dict] = []
        self.chain_state: Dict[str, Any] = {"registered_assets": {}}
        
        self._init_db()
        self._load_chain()
        
        if not self.chain:
            self._create_genesis_block()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                block_index INTEGER PRIMARY KEY,
                block_hash TEXT UNIQUE NOT NULL,
                block_data TEXT NOT NULL
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                asset_name TEXT NOT NULL,
                category TEXT,
                department TEXT,
                asset_value REAL,
                owner TEXT,
                status TEXT,
                registration_date TEXT,
                block_index INTEGER,
                block_hash TEXT
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                tx_id TEXT PRIMARY KEY,
                action TEXT,
                asset_id TEXT,
                actor TEXT,
                block_index INTEGER,
                block_hash TEXT,
                payload TEXT,
                created_at TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    def _persist_block(self, block: Block):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute(
            "INSERT OR REPLACE INTO blocks (block_index, block_hash, block_data) VALUES (?, ?, ?)",
            (block.index, block.hash, json.dumps(block.to_dict()))
        )
        
        for tx in block.transactions:
            tx_id = tx.get("tx_id", str(uuid.uuid4()))
            action = tx.get("action")
            payload = tx.get("payload", {})
            asset_id = payload.get("asset_id", "")
            actor = tx.get("actor", "system")
            created_at = tx.get("timestamp", datetime.now(timezone.utc).isoformat())

            c.execute("""
                INSERT OR REPLACE INTO transactions (tx_id, action, asset_id, actor, block_index, block_hash, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (tx_id, action, asset_id, actor, block.index, block.hash, json.dumps(payload), created_at))

            if action == "REGISTER_ASSET":
                c.execute("""
                    INSERT OR REPLACE INTO assets 
                    (asset_id, asset_name, category, department, asset_value, owner, status, registration_date, block_index, block_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    payload.get("asset_id"), payload.get("asset_name"), payload.get("category"),
                    payload.get("department"), payload.get("asset_value"), payload.get("owner"),
                    payload.get("status"), block.to_dict()["timestamp_human"], block.index, block.hash
                ))
            elif action == "TRANSFER_ASSET":
                c.execute("""
                    UPDATE assets SET owner = ?, status = 'Transferred', block_hash = ?
                    WHERE asset_id = ?
                """, (payload.get("to_owner"), block.hash, payload.get("asset_id")))

        conn.commit()
        conn.close()

    def _load_chain(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT block_data FROM blocks ORDER BY block_index ASC")
        rows = c.fetchall()
        conn.close()

        for (data_str,) in rows:
            data = json.loads(data_str)
            b = Block.__new__(Block)
            b.index = data["index"]
            b.timestamp = data["timestamp"]
            b.transactions = data["transactions"]
            b.previous_hash = data["previous_hash"]
            b.merkle_root = data["merkle_root"]
            b.nonce = data["nonce"]
            b.mined_by = data.get("mined_by", "system")
            b.hash = data["hash"]
            self.chain.append(b)
            self._update_chain_state(b)

    def _update_chain_state(self, block: Block):
        for tx in block.transactions:
            action = tx.get("action")
            payload = tx.get("payload", {})
            
            if action == "REGISTER_ASSET":
                self.chain_state["registered_assets"][payload["asset_id"]] = dict(payload)
            elif action == "TRANSFER_ASSET":
                aid = payload.get("asset_id")
                if aid in self.chain_state["registered_assets"]:
                    self.chain_state["registered_assets"][aid]["owner"] = payload.get("to_owner")
                    self.chain_state["registered_assets"][aid]["status"] = "Transferred"

    def _create_genesis_block(self):
        genesis_tx = {
            "tx_id": "GENESIS-TX-001",
            "action": "GENESIS",
            "actor": "SYSTEM-CORE",
            "payload": {
                "message": "Blockchain Initialized — Jigawa State Asset Registry",
                "version": "1.0.0",
                "network": "JIGAWA-MAINNET",
                "jurisdiction": "Jigawa State, Federal Republic of Nigeria"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        genesis = Block(index=0, transactions=[genesis_tx], previous_hash="0" * 64, mined_by="GENESIS")
        self.chain.append(genesis)
        self._persist_block(genesis)

    def execute_transaction(self, action: str, payload: dict, actor: str) -> dict:
        contract_cls = self.CONTRACTS.get(action)
        if not contract_cls:
            return {"success": False, "error": f"Unknown contract action: {action}"}
            
        result = contract_cls.execute(action, payload, self.chain_state)
        if not result["success"]:
            return result

        tx = {
            "tx_id": f"TX-{uuid.uuid4().hex[:12].upper()}",
            "action": action,
            "actor": actor,
            "payload": payload,
            "contract_result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "pending"
        }
        
        self.pending_transactions.append(tx)
        return {"success": True, "tx_id": tx["tx_id"], "message": "Transaction added to mempool", "contract": result}

    def mine_block(self, miner: str = "admin") -> Optional[Block]:
        if not self.pending_transactions:
            return None
            
        txs = list(self.pending_transactions)
        self.pending_transactions = []
        
        new_block = Block(
            index=len(self.chain),
            transactions=txs,
            previous_hash=self.chain[-1].hash,
            mined_by=miner
        )
        
        self.chain.append(new_block)
        self._update_chain_state(new_block)
        self._persist_block(new_block)
        return new_block

    def is_chain_valid(self) -> dict:
        issues = []
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            
            if current.previous_hash != previous.hash:
                issues.append(f"Block {i}: previous_hash mismatch")
                
            recomputed_full = hashlib.sha256(json.dumps({
                "index": current.index,
                "timestamp": current.timestamp,
                "transactions": current.transactions,
                "previous_hash": current.previous_hash,
                "merkle_root": current.merkle_root,
                "nonce": current.nonce,
                "mined_by": current.mined_by
            }, sort_keys=True).encode()).hexdigest()
            
            if recomputed_full != current.hash:
                issues.append(f"Block {i}: hash tampered")
                
        return {
            "valid": len(issues) == 0,
            "chain_length": len(self.chain),
            "issues": issues,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }

    def get_asset_history(self, asset_id: str) -> List[dict]:
        history = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("payload", {}).get("asset_id") == asset_id:
                    history.append({
                        **tx,
                        "block_index": block.index,
                        "block_hash": block.hash,
                        "block_timestamp": block.to_dict()["timestamp_human"]
                    })
        return history

    def get_chain_stats(self) -> dict:
        total_tx = sum(len(b.transactions) for b in self.chain)
        asset_count = len(self.chain_state.get("registered_assets", {}))
        
        return {
            "total_blocks": len(self.chain),
            "total_transactions": total_tx,
            "pending_transactions": len(self.pending_transactions),
            "registered_assets": asset_count,
            "latest_block_hash": self.chain[-1].hash if self.chain else None,
            "network": "JIGAWA-MAINNET",
            "consensus": f"Proof-of-Work (Difficulty={Block.DIFFICULTY})"
        }

    def get_full_chain(self) -> List[dict]:
        return [b.to_dict() for b in self.chain]

    def get_all_assets_from_db(self, filters: dict = None) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        query = "SELECT * FROM assets WHERE 1=1"
        params = []
        
        if filters:
            if filters.get("category"):
                query += " AND category = ?"
                params.append(filters["category"])
            if filters.get("department"):
                query += " AND department LIKE ?"
                params.append(f"%{filters['department']}%")
            if filters.get("status"):
                query += " AND status = ?"
                params.append(filters["status"])
            if filters.get("search"):
                query += " AND (asset_name LIKE ? OR asset_id LIKE ?)"
                params += [f"%{filters['search']}%", f"%{filters['search']}%"]
                
        query += " ORDER BY registration_date DESC"
        
        c.execute(query, params)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def get_dashboard_stats(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM assets")
        total_assets = c.fetchone()[0]
        
        c.execute("SELECT SUM(asset_value) FROM assets")
        total_value = c.fetchone()[0] or 0
        
        c.execute("SELECT category, COUNT(*) as cnt FROM assets GROUP BY category")
        by_category = [{"category": r[0], "count": r[1]} for r in c.fetchall()]
        
        c.execute("SELECT department, COUNT(*) as cnt FROM assets GROUP BY department ORDER BY cnt DESC LIMIT 10")
        by_dept = [{"department": r[0], "count": r[1]} for r in c.fetchall()]
        
        c.execute("SELECT status, COUNT(*) as cnt FROM assets GROUP BY status")
        by_status = [{"status": r[0], "count": r[1]} for r in c.fetchall()]
        
        c.execute("SELECT COUNT(*) FROM transactions")
        total_tx = c.fetchone()[0]
        
        conn.close()
        return {
            "total_assets": total_assets,
            "total_value": total_value,
            "total_transactions": total_tx,
            "total_blocks": len(self.chain),
            "by_category": by_category,
            "by_department": by_dept,
            "by_status": by_status,
            "chain_valid": self.is_chain_valid()["valid"]
        }


# ─────────────────────────────────────────────────────────
#  SINGLETON INSTANCE
# ─────────────────────────────────────────────────────────

_blockchain_instance: Optional[JigawaBlockchain] = None

def get_blockchain(db_path: str = "jigawa.db") -> JigawaBlockchain:
    global _blockchain_instance
    if _blockchain_instance is None:
        _blockchain_instance = JigawaBlockchain(db_path)
    return _blockchain_instance