import os
import time
import pyodbc
import requests
import azure.functions as func
from datetime import datetime, timedelta
from encrypt_qb_token import encrypt_token, decrypt_token  # ✅ shared encryption/decryption


# === SQL connection with retry ===
def connect_to_sql(max_retries=3, delay=15):
    """Try multiple times to connect to Azure SQL (handles serverless sleep)."""
    SQL_SERVER = os.getenv("SQL_SERVER")
    SQL_DB = os.getenv("SQL_DB")
    SQL_USER = os.getenv("SQL_USER")
    SQL_PASSWORD = os.getenv("SQL_PASSWORD")

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔌 Connecting to Azure SQL (attempt {attempt})...")
            conn = get_connection()
            print("✅ Connected to Azure SQL.")
            return conn
        except Exception as e:
            print(f"⚠️ Connection attempt {attempt} failed: {e}")
            if attempt < max_retries:
                print(f"⏳ Waiting {delay} seconds before retry...")
                time.sleep(delay)
            else:
                raise Exception("❌ Could not connect to Azure SQL after multiple attempts.")


# === QuickBooks token refresh ===
def refresh_qb_tokens(realm_id, refresh_token):
    QB_CLIENT_ID = os.getenv("QB_CLIENT_ID")
    QB_CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
    url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

    auth_string = requests.auth._basic_auth_str(QB_CLIENT_ID, QB_CLIENT_SECRET)
    headers = {
        "Accept": "application/json",
        "Authorization": auth_string,
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    response = requests.post(url, headers=headers, data=data)
    if response.status_code != 200:
        raise Exception(f"Refresh failed for realm {realm_id}: {response.text}")
    return response.json()


# === SQL update ===
def update_sql(cursor, client_id, access_token, refresh_token, expires_in):
    now = datetime.utcnow()
    expiry = now + timedelta(seconds=expires_in)

    cursor.execute("""
        UPDATE client_auth
        SET access_token_enc = ?,
            refresh_token_enc = ?,
            token_expiry = ?,
            last_refresh = ?,
            last_run_time = GETUTCDATE()
        WHERE id = ?
    """, (
        encrypt_token(access_token),
        encrypt_token(refresh_token),
        expiry,
        now,
        client_id
    ))

    print(f"💾 Tokens updated in SQL for client ID {client_id}")


# === Main Azure Function ===
def main(mytimer: func.TimerRequest) -> None:
    utc_timestamp = datetime.utcnow().replace(tzinfo=None)
    print(f"🚀 Starting QuickBooks Token Refresh at {utc_timestamp} UTC")

    conn = connect_to_sql()
    cursor = conn.cursor()

    cursor.execute("SELECT id, realm_id, refresh_token_enc FROM client_auth WHERE active = 1")
    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description]
    clients = [dict(zip(cols, r)) for r in rows]

    if not clients:
        print("⚠️ No active clients found in client_auth table.")
        conn.close()
        return

    for client in clients:
        try:
            print(f"➡️ Refreshing tokens for realm {client['realm_id']}...")
            decrypted_refresh = decrypt_token(client["refresh_token_enc"])
            response = refresh_qb_tokens(client["realm_id"], decrypted_refresh)

            update_sql(
                cursor=cursor,
                client_id=client["id"],
                access_token=response["access_token"],
                refresh_token=response["refresh_token"],
                expires_in=response["expires_in"]
            )

            conn.commit()
            print(f"✅ Successfully refreshed tokens for realm {client['realm_id']}")
        except Exception as e:
            print(f"❌ Error refreshing tokens for realm {client['realm_id']}: {e}")
            conn.rollback()

    conn.close()
    print("🎯 Token refresh cycle complete.\n")
from qb_app.db import get_connection, fetchall_dict
