"""
SARAUTA SEED DATA
=================
Blockchain-Based Asset Registry for Public Sector Accountability
Jigawa State Government — Demo Data Seeder

Run this ONCE after starting the server to populate the blockchain
with realistic Jigawa State government assets for demonstration.

Usage:
    python seed_data.py

Note: Requires the Flask server (app.py) to be running on port 5000.
"""

import requests
import json
import time

BASE = "http://localhost:5000/api"

# ─────────────────────────────────────────────────────────────────
#  REALISTIC JIGAWA STATE GOVERNMENT ASSETS
# ─────────────────────────────────────────────────────────────────

SEED_ASSETS = [
    # ── Buildings ──────────────────────────────────────────────
    {
        "asset_id": "JSG-BLDG-0001",
        "asset_name": "Jigawa State Secretariat Complex — Block A",
        "category": "Building",
        "department": "Ministry of Finance & Economic Planning",
        "asset_value": 450000000.00,
        "owner": "Ministry of Finance & Economic Planning",
        "status": "Active"
    },
    {
        "asset_id": "JSG-BLDG-0002",
        "asset_name": "Government House Annex — Dutse",
        "category": "Building",
        "department": "Office of the Governor",
        "asset_value": 850000000.00,
        "owner": "Office of the Governor",
        "status": "Active"
    },
    {
        "asset_id": "JSG-BLDG-0003",
        "asset_name": "Jigawa State House of Assembly Complex",
        "category": "Building",
        "department": "Jigawa State House of Assembly",
        "asset_value": 620000000.00,
        "owner": "Jigawa State House of Assembly",
        "status": "Active"
    },
    {
        "asset_id": "JSG-BLDG-0004",
        "asset_name": "Ministry of Education Headquarters — Dutse",
        "category": "Building",
        "department": "Ministry of Education",
        "asset_value": 280000000.00,
        "owner": "Ministry of Education",
        "status": "Active"
    },
    {
        "asset_id": "JSG-BLDG-0005",
        "asset_name": "Jigawa State Teaching Hospital — Main Block",
        "category": "Building",
        "department": "Ministry of Health",
        "asset_value": 1200000000.00,
        "owner": "Ministry of Health",
        "status": "Active"
    },
    {
        "asset_id": "JSG-BLDG-0006",
        "asset_name": "Dutse International Market Complex",
        "category": "Building",
        "department": "Ministry of Commerce & Industry",
        "asset_value": 390000000.00,
        "owner": "Ministry of Commerce & Industry",
        "status": "Active"
    },
    {
        "asset_id": "JSG-BLDG-0007",
        "asset_name": "Jigawa State Polytechnic Admin Block — Dutse",
        "category": "Building",
        "department": "Ministry of Education",
        "asset_value": 175000000.00,
        "owner": "Jigawa State Polytechnic",
        "status": "Active"
    },

    # ── Vehicles ─────────────────────────────────────────────────
    {
        "asset_id": "JSG-VEH-0001",
        "asset_name": "Toyota Land Cruiser Prado V8 — JGA-003-GH",
        "category": "Vehicle",
        "department": "Office of the Governor",
        "asset_value": 58000000.00,
        "owner": "Office of the Governor",
        "status": "Active"
    },
    {
        "asset_id": "JSG-VEH-0002",
        "asset_name": "Toyota Hilux Double Cab (x4) — Ministry Fleet",
        "category": "Vehicle",
        "department": "Ministry of Works & Transport",
        "asset_value": 92000000.00,
        "owner": "Ministry of Works & Transport",
        "status": "Active"
    },
    {
        "asset_id": "JSG-VEH-0003",
        "asset_name": "Mitsubishi Pajero 4WD — JGA-119-MH",
        "category": "Vehicle",
        "department": "Ministry of Health",
        "asset_value": 35000000.00,
        "owner": "Ministry of Health",
        "status": "Under Maintenance"
    },
    {
        "asset_id": "JSG-VEH-0004",
        "asset_name": "Ambulance Unit — Dutse General Hospital",
        "category": "Vehicle",
        "department": "Ministry of Health",
        "asset_value": 28000000.00,
        "owner": "Dutse General Hospital",
        "status": "Active"
    },
    {
        "asset_id": "JSG-VEH-0005",
        "asset_name": "Mercedes-Benz Sprinter Bus — Education Transport",
        "category": "Vehicle",
        "department": "Ministry of Education",
        "asset_value": 45000000.00,
        "owner": "Ministry of Education",
        "status": "Active"
    },
    {
        "asset_id": "JSG-VEH-0006",
        "asset_name": "Caterpillar D6 Bulldozer — Road Construction Unit",
        "category": "Vehicle",
        "department": "Ministry of Works & Transport",
        "asset_value": 320000000.00,
        "owner": "Ministry of Works & Transport",
        "status": "Active"
    },

    # ── Equipment ────────────────────────────────────────────────
    {
        "asset_id": "JSG-EQP-0001",
        "asset_name": "500KVA Perkins Generator — State Secretariat",
        "category": "Equipment",
        "department": "Ministry of Finance & Economic Planning",
        "asset_value": 22000000.00,
        "owner": "Ministry of Finance & Economic Planning",
        "status": "Active"
    },
    {
        "asset_id": "JSG-EQP-0002",
        "asset_name": "Medical CT Scan Machine — Teaching Hospital",
        "category": "Equipment",
        "department": "Ministry of Health",
        "asset_value": 185000000.00,
        "owner": "Jigawa State Teaching Hospital",
        "status": "Active"
    },
    {
        "asset_id": "JSG-EQP-0003",
        "asset_name": "Irrigation Water Pump System (20 Units) — Kano River",
        "category": "Equipment",
        "department": "Ministry of Agriculture",
        "asset_value": 48000000.00,
        "owner": "Ministry of Agriculture",
        "status": "Active"
    },
    {
        "asset_id": "JSG-EQP-0004",
        "asset_name": "Solar Power System — Rural Electrification Project",
        "category": "Equipment",
        "department": "Ministry of Energy & Environment",
        "asset_value": 67000000.00,
        "owner": "Ministry of Energy & Environment",
        "status": "Active"
    },
    {
        "asset_id": "JSG-EQP-0005",
        "asset_name": "Dialysis Machine (x3) — Teaching Hospital",
        "category": "Equipment",
        "department": "Ministry of Health",
        "asset_value": 54000000.00,
        "owner": "Jigawa State Teaching Hospital",
        "status": "Active"
    },

    # ── Infrastructure ────────────────────────────────────────────
    {
        "asset_id": "JSG-INF-0001",
        "asset_name": "Dutse–Ringim Dual Carriageway — Phase 1",
        "category": "Infrastructure",
        "department": "Ministry of Works & Transport",
        "asset_value": 3800000000.00,
        "owner": "Ministry of Works & Transport",
        "status": "Active"
    },
    {
        "asset_id": "JSG-INF-0002",
        "asset_name": "Hadejia Urban Water Supply Project",
        "category": "Infrastructure",
        "department": "Ministry of Water Resources",
        "asset_value": 2200000000.00,
        "owner": "Ministry of Water Resources",
        "status": "Active"
    },
    {
        "asset_id": "JSG-INF-0003",
        "asset_name": "Dutse Stadium & Sports Complex",
        "category": "Infrastructure",
        "department": "Ministry of Youth & Sports",
        "asset_value": 980000000.00,
        "owner": "Ministry of Youth & Sports",
        "status": "Active"
    },

    # ── Land ─────────────────────────────────────────────────────
    {
        "asset_id": "JSG-LAND-0001",
        "asset_name": "Government Reserved Area — Dutse (Block 47, 12 Plots)",
        "category": "Land",
        "department": "Ministry of Lands & Survey",
        "asset_value": 760000000.00,
        "owner": "Ministry of Lands & Survey",
        "status": "Active"
    },
    {
        "asset_id": "JSG-LAND-0002",
        "asset_name": "Agricultural Development Land — Kiyawa LGA (500 Ha)",
        "category": "Land",
        "department": "Ministry of Agriculture",
        "asset_value": 340000000.00,
        "owner": "Ministry of Agriculture",
        "status": "Active"
    },

    # ── Technology ────────────────────────────────────────────────
    {
        "asset_id": "JSG-TECH-0001",
        "asset_name": "State Data Centre — Servers & Network Infrastructure",
        "category": "Technology",
        "department": "Ministry of ICT",
        "asset_value": 480000000.00,
        "owner": "Ministry of ICT",
        "status": "Active"
    },
    {
        "asset_id": "JSG-TECH-0002",
        "asset_name": "CCTV Surveillance System — Government House & Secretariat",
        "category": "Technology",
        "department": "Office of the Governor",
        "asset_value": 38000000.00,
        "owner": "Office of the Governor",
        "status": "Active"
    },
    {
        "asset_id": "JSG-TECH-0003",
        "asset_name": "Computer Workstations (150 Units) — Civil Service",
        "category": "Technology",
        "department": "Head of Civil Service",
        "asset_value": 72000000.00,
        "owner": "Head of Civil Service",
        "status": "Active"
    },
]

# ─────────────────────────────────────────────────────────────────
#  TRANSFER SCENARIOS (run after registration)
# ─────────────────────────────────────────────────────────────────

SEED_TRANSFERS = [
    {
        "asset_id": "JSG-VEH-0003",
        "from_owner": "Ministry of Health",
        "to_owner": "Ringim General Hospital",
        "reason": "Reallocation under Rural Health Access Programme — Ministerial Directive MD/MOH/2024/117",
        "authorized_by": "admin"
    },
    {
        "asset_id": "JSG-EQP-0003",
        "from_owner": "Ministry of Agriculture",
        "to_owner": "Kiyawa LGA Agricultural Unit",
        "reason": "Deployment to Kiyawa LGA under Dry Season Farming Initiative 2024",
        "authorized_by": "admin"
    },
    {
        "asset_id": "JSG-TECH-0003",
        "from_owner": "Head of Civil Service",
        "to_owner": "Ministry of Finance & Economic Planning",
        "reason": "Budget reallocation — IPPIS digital upgrade project Q1 2025",
        "authorized_by": "admin"
    },
]

# ─────────────────────────────────────────────────────────────────
#  AUDIT SCENARIOS
# ─────────────────────────────────────────────────────────────────

SEED_AUDITS = [
    {
        "asset_id": "JSG-BLDG-0005",
        "audit_type": "Routine",
        "findings": "Annual physical verification completed. Teaching hospital main block is in good condition. Recommended minor repairs to the east wing roof. Asset value consistent with 2024 government valuation schedule."
    },
    {
        "asset_id": "JSG-INF-0001",
        "audit_type": "Compliance",
        "findings": "Road project Phase 1 (47km) fully completed and commissioned. Quality assurance inspection passed. Drainage systems functional. Reflectors and road markings conform to Federal Road Safety standards. Asset certified for 10-year maintenance-free period."
    },
    {
        "asset_id": "JSG-EQP-0002",
        "audit_type": "Special",
        "findings": "CT Scan machine verified operational with calibration certificate current until December 2025. Preventive maintenance log up to date. Asset utilization at 78% capacity. Recommended procurement of additional contrast media supply."
    },
    {
        "asset_id": "JSG-VEH-0001",
        "audit_type": "Routine",
        "findings": "Vehicle in excellent condition. Mileage: 43,200 km. All documentation current (insurance, road worthiness). Regular service at Toyota Authorized Centre completed February 2025."
    },
]


# ─────────────────────────────────────────────────────────────────
#  RUNNER
# ─────────────────────────────────────────────────────────────────

def login():
    print("  🔐 Authenticating as admin…")
    res = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "Admin@2025!"})
    if res.status_code != 200:
        raise SystemExit(f"  ❌ Login failed: {res.text}")
    token = res.json()["token"]
    print("  ✅ Authenticated")
    return token


def seed_assets(token):
    headers = {"Authorization": f"Bearer {token}"}
    print(f"\n📦 Registering {len(SEED_ASSETS)} government assets onto blockchain…\n")
    ok = 0
    skip = 0
    for asset in SEED_ASSETS:
        res = requests.post(f"{BASE}/assets/register", json=asset, headers=headers)
        data = res.json()
        if res.status_code == 201:
            print(f"  ✅ {asset['asset_id']:20s} → Block #{data.get('block_index')} | {asset['asset_name'][:50]}")
            ok += 1
        else:
            print(f"  ⚠️  {asset['asset_id']:20s} → {data.get('error','?')} (skipped)")
            skip += 1
        time.sleep(0.3)  # small pause to avoid flooding
    print(f"\n  Registered: {ok} | Skipped: {skip}")
    return ok


def seed_transfers(token):
    headers = {"Authorization": f"Bearer {token}"}
    print(f"\n🔄 Recording {len(SEED_TRANSFERS)} asset transfers…\n")
    for t in SEED_TRANSFERS:
        res = requests.post(f"{BASE}/assets/transfer", json=t, headers=headers)
        data = res.json()
        if res.status_code == 200:
            print(f"  ✅ {t['asset_id']:20s} → {t['from_owner'][:25]} ➜ {t['to_owner'][:25]}")
        else:
            print(f"  ⚠️  {t['asset_id']:20s} → {data.get('error','?')}")
        time.sleep(0.3)


def seed_audits(token):
    headers = {"Authorization": f"Bearer {token}"}
    print(f"\n📋 Recording {len(SEED_AUDITS)} audit entries…\n")
    for a in SEED_AUDITS:
        res = requests.post(f"{BASE}/assets/audit", json=a, headers=headers)
        data = res.json()
        if res.status_code == 200:
            print(f"  ✅ {a['asset_id']:20s} → {a['audit_type']} audit recorded (Block #{data.get('block_index')})")
        else:
            print(f"  ⚠️  {a['asset_id']:20s} → {data.get('error','?')}")
        time.sleep(0.3)


def print_summary(token):
    headers = {"Authorization": f"Bearer {token}"}
    dashboard = requests.get(f"{BASE}/dashboard", headers=headers).json()
    chain = requests.get(f"{BASE}/blockchain/stats", headers=headers).json()
    val = requests.get(f"{BASE}/blockchain/validate", headers=headers).json()

    print("\n" + "=" * 62)
    print("  SARAUTA SEED COMPLETE — BLOCKCHAIN SUMMARY")
    print("=" * 62)
    print(f"  Total Assets Registered : {dashboard.get('total_assets', 0)}")
    print(f"  Total Asset Value       : ₦{dashboard.get('total_value', 0):,.2f}")
    print(f"  Total Transactions      : {dashboard.get('total_transactions', 0)}")
    print(f"  Total Blocks Mined      : {chain.get('total_blocks', 0)}")
    print(f"  Pending Transactions    : {chain.get('pending_transactions', 0)}")
    print(f"  Chain Integrity         : {'✅ VALID' if val.get('valid') else '⚠️ INVALID'}")
    print(f"  Network                 : {chain.get('network', 'SARAUTA-MAINNET')}")
    print("=" * 62)
    print("\n  🚀 Open http://localhost:5000 in your browser")
    print("  📄 Pages:")
    print("     login.html   — Staff login portal")
    print("     index.html   — Dashboard & asset management")
    print("     verify.html  — Public asset verification")
    print("=" * 62)


if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  SARAUTA BLOCKCHAIN SEED DATA")
    print("  Jigawa State Government Asset Registry")
    print("=" * 62)

    try:
        # Health check
        health = requests.get(f"{BASE}/health", timeout=5)
        print(f"\n  ✅ Server online: {health.json()['system']}")
    except Exception:
        print("\n  ❌ Cannot reach server. Start app.py first:")
        print("     python app.py")
        raise SystemExit(1)

    token = login()
    seed_assets(token)
    seed_transfers(token)
    seed_audits(token)
    print_summary(token)
