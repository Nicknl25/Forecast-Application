import os
import time
import requests
from flask import Flask, request, redirect
from flask_cors import CORS
from dotenv import load_dotenv
from encrypt_qb_token import encrypt_token
from qb_app.db import get_connection
from qb_app.job_runner import submit_onboarding
import sys, logging
from qb_app import app

# Load environment variables
load_dotenv()
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.INFO)
app.config['PROPAGATE_EXCEPTIONS'] = True
CORS(app, resources={r"/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization"])


def log(message: str) -> None:
    """Log to console and append to a file if available."""
    print(message)
    try:
        app.logger.info(message)
    except Exception:
        pass
    try:
        log_path = "/home/site/wwwroot/qb_app/logs/callback_debug.log"
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


@app.route("/api/qb/oauth/callback")
def qb_callback():
    """QuickBooks OAuth callback: store tokens and run onboarding."""

    log("=== QuickBooks CALLBACK STARTED ===")

    code = request.args.get("code")
    realm_id = request.args.get("realmId")
    state = request.args.get("state")
    log(f"[oauth_callback] received code={'yes' if bool(code) else 'no'}, realm_id={realm_id}, state={state}")
    state = request.args.get("state")
    user_id = None
    try:
        if state and state.startswith("user_"):
            user_id = int(state.replace("user_", ""))
    except Exception:
        user_id = None

    if not code or not realm_id:
        msg = "Missing 'code' or 'realmId' in redirect URL."
        log(msg)
        return msg, 400

    # 1) Exchange the auth code for tokens
    try:
        log("Step 1: Requesting OAuth tokens from QuickBooks...")
        redirect_uri = (
            os.getenv("QB_REDIRECT_URI")
            or os.getenv("REDIRECT_URI")
            or "https://finance-webapp-test-b0hdb2accff8fcgp.westus2-01.azurewebsites.net/api/qb/oauth/callback"
        )
        log(f"Using redirect_uri: {redirect_uri}")
        # Small buffer to accommodate slow Intuit redirects
        time.sleep(1)
        response = requests.post(
            "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
            auth=(os.getenv("QB_CLIENT_ID"), os.getenv("QB_CLIENT_SECRET")),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            timeout=20,
        )
        try:
            data = response.json()
        except Exception:
            data = {"parse_error": True, "status": response.status_code, "text": response.text[:500]}
        log(f"Step 1 response: {data}")
    except Exception as e:
        msg = f"Error exchanging tokens: {e}"
        log(msg)
        return msg, 500

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    expires_in = data.get("expires_in", 3600)

    if not access_token or not refresh_token:
        msg = f"Missing tokens in response: {data}"
        log(msg)
        return msg, 400

    # 2) Encrypt tokens
    try:
        access_token_enc = encrypt_token(access_token)
        refresh_token_enc = encrypt_token(refresh_token)
        log("Step 2: Tokens encrypted successfully.")
    except Exception as e:
        msg = f"Encryption failed: {e}"
        log(msg)
        return msg, 500

    # 3) Connect to SQL
    try:
        log("Step 3: Connecting to Azure SQL...")
        conn = get_connection()
        cur = conn.cursor()
        log("SQL connection successful.")
    except Exception as e:
        msg = f"Database connection failed: {e}"
        log(msg)
        return msg, 500

    # 4) Upsert or insert client_auth
    try:
        log("Step 4: Checking if realm_id already exists...")
        cur.execute("SELECT id FROM client_auth WHERE realm_id = ?", (realm_id,))
        row = cur.fetchone()

        if row:
            client_id_existing = int(row[0])
            log("Existing client found. Updating tokens...")
            cur.execute(
                """
                UPDATE client_auth
                SET access_token_enc = ?,
                    refresh_token_enc = ?,
                    token_expiry = DATEADD(SECOND, ?, GETUTCDATE()),
                    last_refresh = GETUTCDATE()
                WHERE realm_id = ?
                """,
                (access_token_enc, refresh_token_enc, expires_in, realm_id),
            )
            # Also store tokens linked to the requesting user if provided
            try:
                cur.execute(
                    """
                    IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[quickbooks_tokens]') AND type in (N'U'))
                    BEGIN
                        CREATE TABLE quickbooks_tokens (
                            id INT IDENTITY(1,1) PRIMARY KEY,
                            user_id INT NOT NULL,
                            realm_id NVARCHAR(100),
                            access_token NVARCHAR(MAX),
                            refresh_token NVARCHAR(MAX),
                            expires_at DATETIME,
                            CONSTRAINT FK_quickbooks_tokens_users FOREIGN KEY (user_id) REFERENCES users(id)
                        )
                    END
                    """
                )
                if user_id:
                    cur.execute(
                        """
                        INSERT INTO quickbooks_tokens (user_id, realm_id, access_token, refresh_token, expires_at)
                        VALUES (?, ?, ?, ?, DATEADD(SECOND, ?, GETUTCDATE()))
                        """,
                        (int(user_id), realm_id, access_token_enc, refresh_token_enc, expires_in),
                    )
                    log(f"Stored QuickBooks tokens for user_id={user_id}, realm_id={realm_id}")
            except Exception as e:
                log(f"quickbooks_tokens table insert warning: {e}")
            conn.commit()
            conn.close()

            # Queue onboarding for existing client (async)
            try:
                submit_onboarding(client_id_existing, logger=log)
                log("Onboarding queued (existing client).")
            except Exception as e:
                log(f"Onboarding enqueue error (existing client): {e}")

            log("Existing client updated successfully.")
            return "QuickBooks connection refreshed successfully! Initial data load started automatically."

        # Otherwise, new client
        log("Fetching company info for new client...")
        company_name = "Unknown Company"
        try:
            company_url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/companyinfo/{realm_id}"
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            r = requests.get(company_url, headers=headers)
            if r.status_code == 200:
                company_name = r.json().get("CompanyInfo", {}).get("CompanyName", "Unknown Company")
            log(f"Company name: {company_name}")
        except Exception as e:
            log(f"Could not fetch company name: {e}")

        log("Inserting new client into client_auth table...")
        cur.execute(
            """
            INSERT INTO client_auth (client_name, realm_id, access_token_enc, refresh_token_enc, token_expiry, active)
            OUTPUT inserted.id
            VALUES (?, ?, ?, ?, DATEADD(SECOND, ?, GETUTCDATE()), 1);
            """,
            (company_name, realm_id, access_token_enc, refresh_token_enc, expires_in),
        )
        row_id = cur.fetchone()
        new_client_id = int(row_id[0]) if row_id and row_id[0] is not None else None
        if not new_client_id:
            log("INSERT did not return id; selecting id by realm_id...")
            cur.execute("SELECT id FROM client_auth WHERE realm_id = ?", (realm_id,))
            row2 = cur.fetchone()
            if not row2 or row2[0] is None:
                raise Exception("Could not retrieve client_id after insert")
            new_client_id = int(row2[0])
        # Also store tokens linked to the requesting user if provided
        try:
            cur.execute(
                """
                IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[quickbooks_tokens]') AND type in (N'U'))
                BEGIN
                    CREATE TABLE quickbooks_tokens (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        user_id INT NOT NULL,
                        realm_id NVARCHAR(100),
                        access_token NVARCHAR(MAX),
                        refresh_token NVARCHAR(MAX),
                        expires_at DATETIME,
                        CONSTRAINT FK_quickbooks_tokens_users FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                END
                """
            )
            if user_id:
                cur.execute(
                    """
                    INSERT INTO quickbooks_tokens (user_id, realm_id, access_token, refresh_token, expires_at)
                    VALUES (?, ?, ?, ?, DATEADD(SECOND, ?, GETUTCDATE()))
                    """,
                    (int(user_id), realm_id, access_token_enc, refresh_token_enc, expires_in),
                )
                log(f"Stored QuickBooks tokens for user_id={user_id}, realm_id={realm_id}")
        except Exception as e:
            log(f"quickbooks_tokens table insert warning: {e}")
        conn.commit()
        conn.close()
        log(f"New client inserted successfully (id={new_client_id})")

    except Exception as e:
        msg = f"Database error: {e}"
        log(msg)
        return msg, 500

    # 5) Queue onboarding automatically (background job)
    try:
        submit_onboarding(new_client_id, logger=log)
        log("Onboarding queued (new client).")
    except Exception as e:
        log(f"Could not enqueue onboarding automatically: {e}")

    log("=== CALLBACK COMPLETED SUCCESSFULLY ===")
    # Try to redirect back to dashboard if FRONTEND_DASHBOARD_URL is set
    try:
        dash = os.getenv("FRONTEND_DASHBOARD_URL")
        if dash:
            return redirect(dash)
    except Exception:
        pass
    return (
        f"QuickBooks connected successfully for client {new_client_id}! "
        f"Initial data load started automatically. You can close this window."
    )


if __name__ == "__main__":
    app.run(debug=True)
