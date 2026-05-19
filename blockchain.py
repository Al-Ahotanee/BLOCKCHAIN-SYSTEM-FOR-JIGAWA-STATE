import os
# ... (all your existing imports and class definitions stay the same)

# ─────────────────────────────────────────────────────────
#  SINGLETON INSTANCE (Updated for Render/Cloud)
# ─────────────────────────────────────────────────────────

_blockchain_instance: Optional[SarautaBlockchain] = None

def get_blockchain(db_path: str = None) -> SarautaBlockchain:
    global _blockchain_instance
    if _blockchain_instance is None:
        # Priority:
        # 1. Provided argument
        # 2. Environment variable 'DATABASE_PATH' (Set this in Render Dashboard)
        # 3. Default to /tmp/sarauta.db (The only writable area on Render)
        path = db_path or os.environ.get("DATABASE_PATH", "/tmp/sarauta.db")
        
        # Ensure the directory exists (for /tmp/sarauta.db)
        db_dir = os.path.dirname(path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        _blockchain_instance = SarautaBlockchain(path)
    return _blockchain_instance
