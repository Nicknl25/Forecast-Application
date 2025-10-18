import os
import time
import json
import pyodbc
import requests
from datetime import datetime
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from qb_app.db import get_connection, fetchone_dict
import logging

# === Logging setup ===
logging.basicConfig(level=logging.INFO, format="%(message)s")

def log(msg):
    """Unified print + log output."""
    print(msg)
    logging.info(msg)

# === Load environment (works locally or in Azure) ===
load_dotenv()

SERVER = os.getenv("SQL_SERVER")
DB = os.getenv("SQL_DB")
USER = os.getenv("SQL_USER")
PASSWORD = os.getenv("SQL_PASSWORD")
ENCRYPTION_SECRET = os.getenv("ENCRYPTION_SECRET")

# === Retry logic for Azure wake-up ===
def connect_with_retry(max_retries=5, delay=20):
    """Tries multiple times to connect to SQL in case the Azure SQL serverless database is paused."""
    for attempt in range(1, max_retries + 1):
        try:
            log(f"Attempt {attempt}: Connecting to {SERVER}/{DB}...")
            conn = get_connection()
            log("✅ SQL connection established.")
            return conn
        except Exception as e:
            log(f"⚠️ Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                log(f"⏳ Waiting {delay}s before retry...")
                time.sleep(delay)
            else:
                raise

# === Get QuickBooks credentials ===
def get_client_auth(conn):
    """Fetches the active QuickBooks client credentials from SQL."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, realm_id, access_token_enc FROM client_auth WHERE active = 1")
    record = fetchone_dict(cursor)
    if not record:
        raise Exception("No active QuickBooks client found.")
    fernet = Fernet(ENCRYPTION_SECRET)
    access_token = fernet.decrypt(record["access_token_enc"].encode()).decode()
    return record["id"], record["realm_id"], access_token

# === Fetch data from QuickBooks ===
def fetch_qb_data(entity, realm_id, access_token):
    """Fetches transaction data for a given entity from QuickBooks."""
    url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/query"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/text"
    }

    # 5-year lookback
    query = f"select * from {entity} where TxnDate >= '2020-01-01' startposition 1 maxresults 1000"
    response = requests.post(url, headers=headers, data=query)
    if response.status_code != 200:
        log(f"❌ {entity} error {response.status_code}: {response.text}")
        return []
    data = response.json()
    return data.get("QueryResponse", {}).get(entity, [])

# === Insert transactions into SQL ===
def insert_transactions(conn, client_auth_id, entity, transactions):
    """Inserts transaction records into qb_transactions table."""
    if not transactions:
        log(f"⚠️ No {entity} records found.")
        return

    cursor = conn.cursor()
    inserted_count = 0

    for t in transactions:
        try:
            TxnId = t.get("Id")
            DocNumber = t.get("DocNumber")
            TxnDate = t.get("TxnDate")
            TotalAmt = t.get("TotalAmt")
            Currency = t.get("CurrencyRef", {}).get("value")
            ExchangeRate = t.get("ExchangeRate")
            PrivateNote = t.get("PrivateNote")
            Customer = t.get("CustomerRef", {}).get("name")
            Vendor = t.get("VendorRef", {}).get("name")
            EntityRef = t.get("EntityRef", {}).get("name")
            AccountRef = t.get("AccountRef", {}).get("name") if "AccountRef" in t else None
            CreatedTime = t.get("MetaData", {}).get("CreateTime")
            UpdatedTime = t.get("MetaData", {}).get("LastUpdatedTime")

            for line in t.get("Line", []):
                detail = (
                    line.get("AccountBasedExpenseLineDetail") or
                    line.get("SalesItemLineDetail") or
                    line.get("JournalEntryLineDetail") or
                    line.get("DepositLineDetail") or
                    line.get("PaymentLineDetail") or
                    {}
                )

                AccountName = detail.get("AccountRef", {}).get("name")
                AccountId = detail.get("AccountRef", {}).get("value")
                GLCode = AccountId
                Class = detail.get("ClassRef", {}).get("name")
                Department = detail.get("DepartmentRef", {}).get("name")
                Item = detail.get("ItemRef", {}).get("name")
                TaxCode = detail.get("TaxCodeRef", {}).get("value")
                BillableStatus = detail.get("BillableStatus")
                LinkedTxnIds = ", ".join(
                    [lt.get("TxnId") for lt in line.get("LinkedTxn", [])]
                ) if line.get("LinkedTxn") else None
                LineAmount = line.get("Amount")
                Description = line.get("Description")

                cursor.execute("""
                    INSERT INTO qb_transactions (
                        client_auth_id, TxnId, DocNumber, TxnType, TxnDate, TotalAmt, LineAmount,
                        Currency, ExchangeRate, AccountName, AccountId, GLCode, Class,
                        Department, Item, TaxCode, BillableStatus, LinkedTxnIds,
                        Customer, Vendor, AccountRef, Description, Memo, CreatedTime, UpdatedTime, InsertedAt
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,GETUTCDATE())
                """, (
                    client_auth_id, TxnId, DocNumber, entity, TxnDate, TotalAmt, LineAmount,
                    Currency, ExchangeRate, AccountName, AccountId, GLCode, Class,
                    Department, Item, TaxCode, BillableStatus, LinkedTxnIds,
                    Customer or EntityRef, Vendor or EntityRef, AccountRef,
                    Description, PrivateNote, CreatedTime, UpdatedTime
                ))

                inserted_count += 1
        except Exception as e:
            log(f"❌ Insert error for {entity}: {e}")
            continue

    conn.commit()
    log(f"✅ Inserted {inserted_count} {entity} records.")

# === Main process ===
def main(client_id=None):
    """Load full QuickBooks transaction history for a new client."""
    if client_id is None:
        raise Exception("❌ client_id is required to run load_all_transactions.")

    conn = connect_with_retry()

    # --- Fetch auth details for the specified client ---
    cursor = conn.cursor()
    cursor.execute("SELECT id, realm_id, access_token_enc FROM client_auth WHERE id = ?", (client_id,))
    record = fetchone_dict(cursor)

    if not record:
        raise Exception(f"❌ No QuickBooks client found with id={client_id}")

    client_auth_id = record["id"]
    realm_id = record["realm_id"]
    fernet = Fernet(ENCRYPTION_SECRET)
    access_token = fernet.decrypt(record["access_token_enc"].encode()).decode()

    entities = [
        "Invoice", "SalesReceipt", "Payment", "CreditMemo", "RefundReceipt",
        "Purchase", "Bill", "BillPayment", "VendorCredit", "Check",
        "Deposit", "Transfer", "JournalEntry", "TimeActivity", "PurchaseOrder"
    ]

    log(f"\n📘 Starting initial QuickBooks transaction history load for NEW client {client_auth_id} ({realm_id})...\n")

    # === Step 1: Load transactions ===
    for entity in entities:
        log(f"🔹 Fetching {entity} records...")
        txns = fetch_qb_data(entity, realm_id, access_token)
        insert_transactions(conn, client_auth_id, entity, txns)

    # === Step 2: Load reference data ===
    try:
        from qb_app.load_qb_reference_data import load_all_reference_data
        log(f"\n📦 Now loading reference data for client {client_auth_id} ({realm_id})...")
        log(">>> ENTERING reference-data section <<<")
        load_all_reference_data(realm_id, access_token, client_auth_id, conn)
        log(">>> EXITING reference-data section <<<")
        log(f"✅ Finished reference data load for client {client_auth_id}\n")
    except Exception as e:
        log(f"⚠️ Reference data load failed: {e}")

    conn.close()
    log("\n🎉 Initial QuickBooks transaction history load complete for new client!")
