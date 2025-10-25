import os
import time
import json
import pyodbc
import requests
import pandas as pd
import smtplib
import azure.functions as func
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# === (OPTIONAL) decrypt helper ===
# If encrypt_qb_token.py exists in same folder later, import instead
def decrypt_token(enc_value):
    from cryptography.fernet import Fernet
    key = os.getenv("ENCRYPTION_SECRET").encode()
    f = Fernet(key)
    return f.decrypt(enc_value.encode()).decode()

# === Load environment (Azure App Settings or local.settings.json) ===
SERVER = os.getenv("SQL_SERVER")
DB = os.getenv("SQL_DB")
USER = os.getenv("SQL_USER")
PASSWORD = os.getenv("SQL_PASSWORD")
EMAIL_ALERT = os.getenv("EMAIL_ALERT")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# === SQL Connection with retry ===
def connect_with_retry(logger, max_retries=5, delay=20):
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Attempt {attempt}: Connecting to {SERVER}/{DB}...")
            conn = get_connection()
            logger.info("✅ SQL connection established.")
            return conn
        except Exception as e:
            logger.warning(f"⚠️ Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                logger.info(f"⏳ Waiting {delay}s before retry...")
                time.sleep(delay)
            else:
                raise

# === Verify realm with QuickBooks ===
def verify_realm(logger, realm_id, access_token):
    url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/companyinfo/{realm_id}"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            logger.info(f"✅ Realm verified: {realm_id}")
            return True
        elif resp.status_code in (401, 403):
            logger.warning(f"⚠️ Realm {realm_id} unauthorized (token mismatch or expired).")
            return False
        elif resp.status_code == 404:
            logger.warning(f"⚠️ Realm {realm_id} not found in QuickBooks.")
            return False
        else:
            logger.warning(f"⚠️ Realm verification failed {realm_id}: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"❌ Realm verification error for {realm_id}: {e}")
        return False

# === Fetch QuickBooks entity data ===
def fetch_qb_data(logger, entity, realm_id, access_token, since_datetime):
    base_url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/query"
    query = f"SELECT * FROM {entity} WHERE Metadata.LastUpdatedTime > '{since_datetime}' ORDERBY Metadata.LastUpdatedTime"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json", "Content-Type": "application/text"}
    try:
        r = requests.post(base_url, headers=headers, data=query)
        if r.status_code == 200:
            return r.json()
        else:
            logger.warning(f"❌ {entity} API error {r.status_code}: {r.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"❌ Request failed for {entity}: {e}")
        return None

# === Log sync results ===
def log_sync_result(conn, client_auth_id, client_name, status, message, runtime_seconds):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sync_run_log (client_auth_id, client_name, status, message, runtime_seconds)
        VALUES (?, ?, ?, ?, ?)
    """, (client_auth_id, client_name, status, message, runtime_seconds))
    conn.commit()

# === Email: send summary report ===
def send_sync_report(logger, results):
    if not results:
        logger.info("No results to report.")
        return

    df = pd.DataFrame(results)
    # Ensure a valid, existing temp directory on Linux containers
    tmp_dir = "/tmp" if os.name != "nt" else (os.getenv("TEMP") or os.getenv("TMP") or ".")
    try:
        os.makedirs(tmp_dir, exist_ok=True)
    except Exception:
        # Best-effort; fall back to current directory
        tmp_dir = "."
    file_name = os.path.join(tmp_dir, f"sync_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    df.to_excel(file_name, index=False)

    client_summary = (
        df.groupby("client_id")["status"]
        .apply(lambda s: "skipped" if all(s == "skipped") else "successful")
        .reset_index()
    )

    total_clients = len(client_summary)
    success_count = (client_summary["status"] == "successful").sum()
    skip_count = (client_summary["status"] == "skipped").sum()

    subject_status = "✅" if skip_count == 0 else "⚠️"
    subject = f"Daily QuickBooks Sync Report – {datetime.now().strftime('%Y-%m-%d')} {subject_status}"

    body = f"""
    Daily QuickBooks sync completed.

    Summary:
    - Total Clients Processed: {total_clients}
    - Successful: {success_count}
    - Skipped: {skip_count}

    See attached Excel file for detailed results.
    """

    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_ALERT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with open(file_name, "rb") as f:
        attachment = MIMEApplication(f.read(), _subtype="xlsx")
        attachment.add_header("Content-Disposition", "attachment", filename=os.path.basename(file_name))
        msg.attach(attachment)

    try:
        with smtplib.SMTP("smtp.office365.com", 587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
            logger.info(f"📧 Email sent successfully to {EMAIL_ALERT}")
    except Exception as e:
        logger.error(f"❌ Failed to send email report: {e}")

# === Main Function (Azure Entry Point) ===
def main(mytimer: func.TimerRequest) -> None:
    import logging
    logger = logging.getLogger("azure")
    utc_timestamp = datetime.utcnow().replace(tzinfo=None)

    logger.info(f"🚀 Starting Daily QuickBooks Sync at {utc_timestamp} UTC")

    try:
        conn = connect_with_retry(logger)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, client_name, realm_id, access_token_enc, refresh_token_enc
            FROM client_auth
            WHERE active = 1
        """)
        rows = cursor.fetchall()
        cols = [c[0] for c in cursor.description]
        clients = [dict(zip(cols, r)) for r in rows]

        if not clients:
            logger.warning("⚠️ No active clients found.")
            return

        entities = ['Invoice', 'SalesReceipt', 'Payment', 'CreditMemo', 'Purchase', 'Bill', 'BillPayment']
        results = []
        total_clients = len(clients)

        for i, client in enumerate(clients, start=1):
            client_id = client["id"]
            client_name = client.get("client_name", f"Client {client_id}")
            realm_id = client["realm_id"]

            logger.info(f"\n=== Processing {client_name} ({i}/{total_clients}) ===")
            start_time = time.time()

            try:
                access_token = decrypt_token(client["access_token_enc"])
                refresh_token = decrypt_token(client["refresh_token_enc"])
            except Exception as e:
                msg = f"Token decryption failed: {e}"
                logger.error(msg)
                log_sync_result(conn, client_id, client_name, "failed", msg, 0)
                continue

            if not verify_realm(logger, realm_id, access_token):
                msg = f"Realm {realm_id} not recognized – skipped"
                logger.warning(msg)
                log_sync_result(conn, client_id, client_name, "skipped", msg, 0)
                continue

            for entity in entities:
                since = "2020-01-01T00:00:00Z"
                logger.info(f"🔁 Syncing {entity} for {client_name} ({realm_id})...")
                try:
                    data = fetch_qb_data(logger, entity, realm_id, access_token, since)
                    status = "successful" if data else "failed"
                    msg = f"{entity} sync {'completed' if data else 'no data'}."
                    runtime = round(time.time() - start_time, 2)
                    log_sync_result(conn, client_id, client_name, status, msg, runtime)
                    results.append({"client_id": client_id, "client_name": client_name, "status": status, "runtime_seconds": runtime, "message": msg})
                    logger.info(f"🕒 {msg} ({runtime}s)")
                except Exception as e:
                    runtime = round(time.time() - start_time, 2)
                    msg = f"Error syncing {entity}: {e}"
                    logger.error(msg)
                    log_sync_result(conn, client_id, client_name, "failed", msg, runtime)
                    continue

            cursor.execute("UPDATE client_auth SET last_run_time = GETUTCDATE() WHERE id = ?", (client_id,))
            conn.commit()
            logger.info(f"✅ Finished {client_name} ({i}/{total_clients})")

        conn.close()
        send_sync_report(logger, results)
        logger.info("🎉 Daily QuickBooks sync completed successfully.")

    except Exception as e:
        logger.error(f"❌ Fatal error during sync: {e}")
from qb_app.db import get_connection
