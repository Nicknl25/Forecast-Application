import os
from datetime import datetime
from flask import Blueprint, jsonify, request

from qb_app.db import get_connection, fetchall_dict, fetchone_dict
from qb_app.utils import admin_required


admin_bp = Blueprint("admin_bp", __name__, url_prefix="/api/admin")


def _ensure_subscriptions_table(cur) -> None:
    cur.execute(
        """
        IF NOT EXISTS (
          SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[subscriptions]') AND type in (N'U')
        )
        BEGIN
          CREATE TABLE [dbo].[subscriptions](
            [id] INT IDENTITY(1,1) PRIMARY KEY,
            [client_id] INT NULL,
            [provider] NVARCHAR(50) NULL DEFAULT 'stripe',
            [provider_customer_id] NVARCHAR(255) NULL,
            [provider_subscription_id] NVARCHAR(255) NULL,
            [plan] NVARCHAR(50) NULL DEFAULT 'free',
            [status] NVARCHAR(20) NULL DEFAULT 'inactive',
            [monthly_fee] DECIMAL(10,2) NULL DEFAULT 0,
            [last_payment_date] DATETIME NULL,
            [next_payment_due] DATETIME NULL,
            [created_at] DATETIME NULL DEFAULT GETUTCDATE(),
            CONSTRAINT [FK_subscriptions_client_auth] FOREIGN KEY ([client_id]) REFERENCES [dbo].[client_auth]([id])
          )
        END
        """
    )


@admin_bp.get("/business_summary")
@admin_required
def business_summary():
    try:
        conn = get_connection()
        cur = conn.cursor()
        _ensure_subscriptions_table(cur)
        cur.execute("SELECT COUNT(*) AS cnt FROM client_auth")
        total_clients = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(*) AS cnt FROM subscriptions WHERE status = 'active'")
        paying_clients = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COALESCE(SUM(monthly_fee), 0) AS mrr FROM subscriptions WHERE status = 'active'")
        mrr = float(cur.fetchone()[0] or 0)
        conn.close()
        arpu = round(mrr / paying_clients, 2) if paying_clients else 0
        return jsonify({
            "total_clients": total_clients,
            "paying_clients": paying_clients,
            "mrr": mrr,
            "arpu": arpu,
        })
    except Exception as e:
        return jsonify({"error": str(e), "total_clients": 0, "paying_clients": 0, "mrr": 0, "arpu": 0}), 200


@admin_bp.get("/system_health")
@admin_required
def system_health():
    # Lightweight introspection; avoid heavy imports if scheduler unavailable
    status = {
        "container_uptime": "OK",
        "scheduler_status": "unknown",
        "jobs": [],
    }
    try:
        from qb_app import scheduler as _sched  # noqa: WPS433

        status["scheduler_status"] = "running"
        jobs = []
        try:
            # Best-effort next run hints
            jobs.append({
                "name": "job_token_refresh",
                "last_run": None,
                "next_run": "configured",
                "status": "scheduled",
            })
            jobs.append({
                "name": "job_daily_sync",
                "last_run": None,
                "next_run": "configured",
                "status": "scheduled",
            })
        except Exception:
            pass
        status["jobs"] = jobs
    except Exception:
        status["scheduler_status"] = "unavailable"
    return jsonify(status)


@admin_bp.get("/users")
@admin_required
def list_users():
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Return user records shaped for admin table
        cur.execute("SELECT id, company_name, email FROM users ORDER BY id DESC")
        rows = fetchall_dict(cur)
        conn.close()
        out = [
            {
                "id": int(r.get("id")) if r.get("id") is not None else None,
                "name": r.get("company_name") or "",
                "email": r.get("email") or "",
                "plan": "free",
                "role": "Owner",
                "created_at": None,
            }
            for r in rows
        ]
        return jsonify(out)
    except Exception as e:
        return jsonify([]), 200


@admin_bp.post("/users/add")
@admin_required
def add_user():
    from werkzeug.security import generate_password_hash  # lazy import

    d = request.get_json(silent=True) or {}
    name = (d.get("name") or d.get("company_name") or "").strip()
    email = (d.get("email") or "").strip().lower()
    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400
    pw_hash = generate_password_hash(os.getenv("DEFAULT_ADMIN_CREATED_PW", "Temp123!"))
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (company_name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, pw_hash),
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/users/<int:user_id>", methods=["PUT", "DELETE"])
@admin_required
def modify_user(user_id: int):
    try:
        conn = get_connection()
        cur = conn.cursor()
        if request.method == "DELETE":
            cur.execute("DELETE FROM users WHERE id = ?", (int(user_id),))
        else:
            d = request.get_json(silent=True) or {}
            # Only allow name/email updates in this lightweight admin endpoint
            sets = []
            params = []
            if (d.get("name") or d.get("company_name")) is not None:
                sets.append("company_name = ?")
                params.append((d.get("name") or d.get("company_name") or "").strip())
            if d.get("email") is not None:
                sets.append("email = ?")
                params.append((d.get("email") or "").strip().lower())
            if sets:
                sql = f"UPDATE users SET {', '.join(sets)} WHERE id = ?"
                params.append(int(user_id))
                cur.execute(sql, tuple(params))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.get("/payments")
@admin_required
def get_payments():
    try:
        conn = get_connection()
        cur = conn.cursor()
        _ensure_subscriptions_table(cur)
        cur.execute(
            """
            SELECT s.id, s.client_id, s.provider, s.plan, s.monthly_fee, s.status,
                   s.last_payment_date, s.next_payment_due,
                   c.client_name
            FROM subscriptions s
            LEFT JOIN client_auth c ON c.id = s.client_id
            ORDER BY s.id DESC
            """
        )
        rows = fetchall_dict(cur)
        conn.close()
        out = [
            {
                "id": int(r.get("id")) if r.get("id") is not None else None,
                "email": r.get("client_name") or "",
                "provider": r.get("provider") or "stripe",
                "plan": r.get("plan") or "free",
                "monthly_fee": float(r.get("monthly_fee") or 0),
                "status": r.get("status") or "inactive",
                "last_payment_date": str(r.get("last_payment_date")) if r.get("last_payment_date") else None,
                "next_payment_due": str(r.get("next_payment_due")) if r.get("next_payment_due") else None,
            }
            for r in rows
        ]
        return jsonify(out)
    except Exception as e:
        return jsonify([]), 200


@admin_bp.post("/payments/retry/<int:sub_id>")
@admin_required
def retry_payment(sub_id: int):
    # Placeholder integration; ready for future provider-specific logic
    return jsonify({"status": "simulated", "subscription_id": int(sub_id)})


@admin_bp.post("/run_job")
@admin_required
def run_job():
    job = ((request.get_json(silent=True) or {}).get("job") or "").strip().lower()

    try:
        from qb_app import scheduler as _sched  # noqa: WPS433
        import threading

        def _run(fn, name: str):
            try:
                print(f"[scheduler][manual] starting {name}", flush=True)
                fn()
                print(f"[scheduler][manual] finished {name}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[scheduler][manual] error {name}: {e}", flush=True)

        if job in ("token_refresh", "job_token_refresh"):
            t = threading.Thread(target=_run, args=(_sched.job_token_refresh, "job_token_refresh"), daemon=True)
            t.start()
            return jsonify({"status": "started", "job": "token_refresh"})
        if job in ("daily_sync", "job_daily_sync"):
            t = threading.Thread(target=_run, args=(_sched.job_daily_sync, "job_daily_sync"), daemon=True)
            t.start()
            return jsonify({"status": "started", "job": "daily_sync"})

        # Optional: try scheduling via APScheduler instance if exported in future
        try:
            sched = getattr(_sched, "SCHEDULER", None)
            if sched is not None:
                if job in ("token_refresh", "job_token_refresh"):
                    sched.add_job(_sched.job_token_refresh, id="manual_token_refresh", replace_existing=True)
                    return jsonify({"status": "started", "job": "token_refresh"})
                if job in ("daily_sync", "job_daily_sync"):
                    sched.add_job(_sched.job_daily_sync, id="manual_daily_sync", replace_existing=True)
                    return jsonify({"status": "started", "job": "daily_sync"})
        except Exception:
            pass

        return jsonify({"error": "Unknown job"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.get("/logs")
@admin_required
def admin_logs():
    # Best-effort file tail; falls back to empty list
    paths = [
        os.path.join(os.getcwd(), "qb_app", "logs", "callback_debug.log"),
        "/home/site/wwwroot/qb_app/logs/callback_debug.log",
    ]
    lines = []
    for p in paths:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.read().splitlines()
                break
        except Exception:
            continue
    if lines:
        lines = lines[-25:]
    return jsonify({"lines": lines})


@admin_bp.post("/promote")
def promote_user():
    """Securely promote or demote a user to admin using app_admins table.

    Authorization:
      - Header x-admin-key equals ADMIN_KEY (or ADMIN_MASTER_KEY fallback), OR
      - Authenticated user whose email exists in app_admins
    """
    from qb_app.routes_auth import jwt_required  # lazy import

    provided_key = (request.headers.get("x-admin-key") or "").strip()
    admin_key = (os.getenv("ADMIN_KEY") or "").strip()
    master_key = (os.getenv("ADMIN_MASTER_KEY") or admin_key or "").strip()

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    is_admin = bool(data.get("is_admin", True))
    if not email:
        return jsonify({"error": "email is required"}), 400

    def _do_update():
        try:
            conn = get_connection()
            cur = conn.cursor()
            # Operate on app_admins only; do not modify users table
            if is_admin:
                cur.execute(
                    """
                    IF OBJECT_ID('dbo.app_admins','U') IS NULL
                        CREATE TABLE app_admins (email NVARCHAR(255) NOT NULL UNIQUE)
                    IF NOT EXISTS (SELECT 1 FROM app_admins WHERE LOWER(email)=LOWER(?))
                        INSERT INTO app_admins (email) VALUES (?)
                    """,
                    (email, email),
                )
            else:
                cur.execute(
                    """
                    IF OBJECT_ID('dbo.app_admins','U') IS NOT NULL
                        DELETE FROM app_admins WHERE LOWER(email)=LOWER(?)
                    """,
                    (email,),
                )
            conn.commit()
            conn.close()
            return jsonify({"message": f"{email} admin={int(is_admin)}"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Allow admin key without JWT
    if provided_key and (provided_key == admin_key or provided_key == master_key):
        return _do_update()

    # Otherwise require logged-in admin (in app_admins)
    @jwt_required()
    def _inner():
        try:
            uid = int(getattr(request, "user_id", 0) or 0)
            if not uid:
                return jsonify({"error": "Unauthorized"}), 403
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT email FROM users WHERE id = ?", (uid,))
            r = cur.fetchone()
            requester_email = (r[0] if r and r[0] is not None else "").strip().lower()
            if not requester_email:
                conn.close()
                return jsonify({"error": "Unauthorized"}), 403
            cur.execute(
                """
                IF OBJECT_ID('dbo.app_admins','U') IS NULL
                    SELECT 0
                ELSE
                    SELECT CASE WHEN EXISTS (
                      SELECT 1 FROM app_admins WHERE LOWER(email)=LOWER(?)
                    ) THEN 1 ELSE 0 END
                """,
                (requester_email,),
            )
            rr = cur.fetchone()
            is_admin_req = bool(rr[0]) if rr and rr[0] is not None else False
            conn.close()
            if not is_admin_req:
                return jsonify({"error": "Forbidden"}), 403
            return _do_update()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _inner()
