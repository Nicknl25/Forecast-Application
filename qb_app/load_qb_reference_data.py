import os
import time
import requests
# Using shared DB connection from caller; no direct DB driver import needed.
from dotenv import load_dotenv
import logging

# === Logging setup ===
logging.basicConfig(level=logging.INFO, format="%(message)s")

def log(msg):
    """Unified print + log output."""
    print(msg)
    logging.info(msg)

# === Load environment (works locally or Azure) ===
load_dotenv()

SERVER = os.getenv("SQL_SERVER")
DB = os.getenv("SQL_DB")
USER = os.getenv("SQL_USER")
PASSWORD = os.getenv("SQL_PASSWORD")

# ==============================================================
# 🧩 Shared Helper: Auto-Add Missing Columns
# ==============================================================

def ensure_columns_exist(table, columns, conn):
    """
    Checks if all columns in 'columns' exist in the SQL table.
    If any are missing, it auto-creates them as NVARCHAR(MAX).
    """
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{table.replace('dbo.', '')}'
    """)
    existing_cols = {row[0] for row in cursor.fetchall()}

    missing = [col for col in columns if col not in existing_cols and col != "client_auth_id"]

    for col in missing:
        try:
            alter_sql = f"ALTER TABLE {table} ADD [{col}] NVARCHAR(MAX) NULL;"
            cursor.execute(alter_sql)
            log(f"🧱 Added missing column '{col}' to {table}")
        except Exception as e:
            log(f"⚠️ Failed to add column {col} to {table}: {e}")

    conn.commit()

# ==============================================================
# 🧩 Shared Helper: Run UPSERT (auto-extends schema)
# ==============================================================

def upsert_to_sql(table, records, client_auth_id, conn):
    """
    Inserts or updates QuickBooks reference data into Azure SQL.
    Automatically adds new columns if missing.
    """
    if not records:
        log(f"⚠️ No records returned for {table}")
        return

    cursor = conn.cursor()
    inserted = 0

    for rec in records:
        # Flatten only primitive fields (skip nested JSON)
        clean_rec = {k: v for k, v in rec.items()
                     if isinstance(v, (str, int, float, bool, type(None)))}
        if "Id" not in clean_rec:
            continue

        # ✅ Auto-create missing columns
        ensure_columns_exist(table, clean_rec.keys(), conn)

        cols = list(clean_rec.keys())
        vals = [clean_rec[c] for c in cols]
        updates = [f"{c} = ?" for c in cols]

        sql = f"""
        MERGE {table} AS target
        USING (SELECT ? AS client_auth_id, {', '.join(['?'] * len(cols))}) AS src ({', '.join(['client_auth_id'] + cols)})
        ON target.client_auth_id = src.client_auth_id AND target.Id = src.Id
        WHEN MATCHED THEN
            UPDATE SET {', '.join(updates)}
        WHEN NOT MATCHED THEN
            INSERT ({', '.join(['client_auth_id'] + cols)})
            VALUES ({', '.join(['?'] * (len(cols) + 1))});
        """

        params = [client_auth_id] + vals + vals + [client_auth_id] + vals

        try:
            cursor.execute(sql, tuple(params))
            inserted += 1
        except Exception as e:
            log(f"❌ SQL UPSERT failed for {table}: {e}")

    conn.commit()
    log(f"✅ {table} upserted ({inserted} rows)")

# ==============================================================
# 🧩 Shared Helper: Query QuickBooks (with pagination)
# ==============================================================

def qb_query(entity, realm_id, access_token):
    """Queries all records for a given QuickBooks entity, handling pagination."""
    all_records = []
    start_position = 1
    max_results = 1000  # QB API max per page

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    while True:
        query = f"SELECT * FROM {entity} STARTPOSITION {start_position} MAXRESULTS {max_results}"
        url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/query?query={query}"

        try:
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            records = data.get("QueryResponse", {}).get(entity, [])

            if not records:
                break

            all_records.extend(records)
            log(f"   → Retrieved {len(records)} records (total {len(all_records)}) for {entity}")

            if len(records) < max_results:
                break

            start_position += max_results
            time.sleep(0.3)  # avoid rate limiting
        except Exception as e:
            log(f"❌ Failed to load {entity}: {e}")
            break

    log(f"✅ Finished loading {len(all_records)} total {entity} records")
    return all_records

# ==============================================================
# 🧩 Entity Loaders
# ==============================================================

def load_accounts(realm_id, token, client_auth_id, conn):
    data = qb_query("Account", realm_id, token)
    if data:
        log("\n🔍 Keys in Account response: " + str(list(data[0].keys())))
    upsert_to_sql("qb_accounts", data, client_auth_id, conn)

def load_classes(realm_id, token, client_auth_id, conn):
    data = qb_query("Class", realm_id, token)
    if data:
        log("\n🔍 Keys in Class response: " + str(list(data[0].keys())))
    upsert_to_sql("qb_classes", data, client_auth_id, conn)

def load_customers(realm_id, token, client_auth_id, conn):
    data = qb_query("Customer", realm_id, token)
    if data:
        log("\n🔍 Keys in Customer response: " + str(list(data[0].keys())))
    upsert_to_sql("qb_customers", data, client_auth_id, conn)

def load_employees(realm_id, token, client_auth_id, conn):
    data = qb_query("Employee", realm_id, token)
    if data:
        log("\n🔍 Keys in Employee response: " + str(list(data[0].keys())))
    upsert_to_sql("qb_employees", data, client_auth_id, conn)

def load_items(realm_id, token, client_auth_id, conn):
    data = qb_query("Item", realm_id, token)
    if data:
        log("\n🔍 Keys in Item response: " + str(list(data[0].keys())))
    upsert_to_sql("qb_items", data, client_auth_id, conn)

def load_vendors(realm_id, token, client_auth_id, conn):
    data = qb_query("Vendor", realm_id, token)
    if data:
        log("\n🔍 Keys in Vendor response: " + str(list(data[0].keys())))
    upsert_to_sql("qb_vendors", data, client_auth_id, conn)

# ==============================================================
# 🧩 Master Wrapper: Load All Reference Data
# ==============================================================

def load_all_reference_data(realm_id, access_token, client_auth_id, conn):
    """Loads all non-transaction QuickBooks reference data."""
    log(f"\n📦 Loading reference data for client {client_auth_id} ({realm_id})")

    loaders = [
        load_accounts,
        load_classes,
        load_customers,
        load_employees,
        load_items,
        load_vendors
    ]

    for fn in loaders:
        log(f"→ Running {fn.__name__}()")
        fn(realm_id, access_token, client_auth_id, conn)
        time.sleep(0.5)  # small pause to avoid rate limiting

    log("✅ All reference tables loaded\n")
