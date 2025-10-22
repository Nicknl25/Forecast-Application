import datetime as dt
from typing import Optional, Dict, Any, List

from flask import Blueprint, jsonify, request

from qb_app.db import get_connection, fetchone_dict, fetchall_dict
from qb_app.routes_auth import jwt_required


user_dashboard_bp = Blueprint("user_dashboard_bp", __name__, url_prefix="/api")


def _ensure_company_tables(cur) -> None:
    # companies table
    cur.execute(
        """
        IF NOT EXISTS (
          SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[companies]') AND type in (N'U')
        )
        BEGIN
          CREATE TABLE companies (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(255),
            owner_id INT,
            subscription_plan NVARCHAR(100),
            status NVARCHAR(50) DEFAULT 'Active',
            created_at DATETIME DEFAULT GETUTCDATE()
          )
        END
        """
    )
    # optional settings columns on companies
    cur.execute("IF COL_LENGTH('companies','industry') IS NULL ALTER TABLE companies ADD industry NVARCHAR(100) NULL")
    cur.execute("IF COL_LENGTH('companies','timezone') IS NULL ALTER TABLE companies ADD timezone NVARCHAR(100) NULL")
    cur.execute("IF COL_LENGTH('companies','currency') IS NULL ALTER TABLE companies ADD currency NVARCHAR(10) NULL")
    cur.execute("IF COL_LENGTH('companies','address') IS NULL ALTER TABLE companies ADD address NVARCHAR(255) NULL")
    cur.execute("IF COL_LENGTH('companies','phone') IS NULL ALTER TABLE companies ADD phone NVARCHAR(50) NULL")
    cur.execute("IF COL_LENGTH('companies','email') IS NULL ALTER TABLE companies ADD email NVARCHAR(255) NULL")

    # user_company_map table
    cur.execute(
        """
        IF NOT EXISTS (
          SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[user_company_map]') AND type in (N'U')
        )
        BEGIN
          CREATE TABLE user_company_map (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT,
            company_id INT,
            role NVARCHAR(50),
            status NVARCHAR(50) DEFAULT 'Active',
            last_login DATETIME NULL
          )
        END
        """
    )

    # audit_log table
    cur.execute(
        """
        IF NOT EXISTS (
          SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[audit_log]') AND type in (N'U')
        )
        BEGIN
          CREATE TABLE audit_log (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NULL,
            company_id INT NULL,
            action NVARCHAR(100) NOT NULL,
            details NVARCHAR(MAX) NULL,
            created_at DATETIME DEFAULT GETUTCDATE()
          )
        END
        """
    )


def _fmt_date(d) -> Optional[str]:
    try:
        if d is None:
            return None
        if isinstance(d, dt.datetime):
            return d.date().isoformat()
        if isinstance(d, dt.date):
            return d.isoformat()
        return str(d)
    except Exception:
        return None


def _get_or_create_company_for_user(cur, user_id: int) -> int:
    _ensure_company_tables(cur)
    # Does user already have a mapping?
    cur.execute(
        "SELECT TOP 1 company_id FROM user_company_map WHERE user_id = ? ORDER BY id",
        (int(user_id),),
    )
    row = cur.fetchone()
    if row and row[0] is not None:
        return int(row[0])

    # Check if user owns a company already
    cur.execute("SELECT id, name FROM companies WHERE owner_id = ?", (int(user_id),))
    row = cur.fetchone()
    if row and row[0] is not None:
        company_id = int(row[0])
        # Ensure owner mapping exists
        cur.execute(
            """
            IF NOT EXISTS (
              SELECT 1 FROM user_company_map WHERE user_id = ? AND company_id = ?
            )
            BEGIN
              INSERT INTO user_company_map (user_id, company_id, role, status)
              VALUES (?, ?, 'Owner', 'Active')
            END
            """,
            (int(user_id), company_id, int(user_id), company_id),
        )
        return company_id

    # Otherwise, create a new company from the user's profile (if available)
    cur.execute("SELECT company_name, email FROM users WHERE id = ?", (int(user_id),))
    user_row = cur.fetchone()
    default_company_name = None
    if user_row:
        default_company_name = user_row[0] or None
        if not default_company_name:
            default_company_name = (user_row[1] or "").split("@")[0] or "New Company"
    name = default_company_name or "New Company"
    cur.execute(
        """
        INSERT INTO companies (name, owner_id, subscription_plan, status)
        OUTPUT inserted.id
        VALUES (?, ?, 'Starter', 'Active')
        """,
        (name, int(user_id)),
    )
    new_id_row = cur.fetchone()
    if not new_id_row or new_id_row[0] is None:
        # Fallback retrieval
        cur.execute(
            "SELECT TOP 1 id FROM companies WHERE owner_id = ? ORDER BY id DESC",
            (int(user_id),),
        )
        r2 = cur.fetchone()
        if not r2 or r2[0] is None:
            raise RuntimeError("Failed to create or find company")
        company_id = int(r2[0])
    else:
        company_id = int(new_id_row[0])

    # Create owner mapping
    cur.execute(
        """
        INSERT INTO user_company_map (user_id, company_id, role, status)
        VALUES (?, ?, 'Owner', 'Active')
        """,
        (int(user_id), company_id),
    )
    return company_id


def _log_audit(cur, user_id: Optional[int], company_id: Optional[int], action: str, details: Optional[str]):
    try:
        _ensure_company_tables(cur)
        cur.execute(
            "INSERT INTO audit_log (user_id, company_id, action, details) VALUES (?, ?, ?, ?)",
            (user_id, company_id, action, details),
        )
    except Exception:
        # Silent per instructions
        pass


@user_dashboard_bp.get("/company/audit-log")
@jwt_required()
def company_audit_log():
    try:
        user_id = int(getattr(request, "user_id", 0) or 0)
        conn = get_connection()
        cur = conn.cursor()
        company_id = _get_or_create_company_for_user(cur, user_id)

        # Role check: only Owner/Admin may view
        cur.execute(
            "SELECT role FROM user_company_map WHERE user_id = ? AND company_id = ?",
            (int(user_id), company_id),
        )
        r = cur.fetchone()
        role = (r[0] if r and r[0] is not None else "").strip()
        if role not in ("Owner", "Admin"):
            conn.close()
            return jsonify({"error": "Forbidden"}), 403

        email = (request.args.get("email") or "").strip()
        start = request.args.get("start")
        end = request.args.get("end")

        where_clauses = ["a.company_id = ?"]
        params: List[Any] = [company_id]
        if email:
            where_clauses.append("u.email LIKE ?")
            params.append(f"%{email}%")
        if start and end:
            where_clauses.append("a.created_at BETWEEN ? AND ?")
            params.extend([start, end])

        sql = f"""
            SELECT a.created_at, u.email AS user_email, a.action, a.details
            FROM audit_log a
            LEFT JOIN users u ON u.id = a.user_id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY a.created_at DESC
        """
        cur.execute(sql, tuple(params))
        rows = fetchall_dict(cur)
        conn.commit()
        conn.close()
        events = [
            {
                "timestamp": _fmt_date(r.get("created_at")),
                "user_email": r.get("user_email"),
                "action": r.get("action"),
                "details": r.get("details"),
            }
            for r in rows
        ]
        return jsonify({"events": events})
    except Exception as e:
        return jsonify({"events": [], "error": str(e)}), 200

@user_dashboard_bp.get("/company/info")
@jwt_required()
def company_info():
    try:
        user_id = int(getattr(request, "user_id", 0) or 0)
        conn = get_connection()
        cur = conn.cursor()
        company_id = _get_or_create_company_for_user(cur, user_id)

        # Company core info
        cur.execute(
            "SELECT id, name, subscription_plan, status, created_at, industry, timezone, currency, address, phone, email FROM companies WHERE id = ?",
            (company_id,),
        )
        comp = fetchone_dict(cur)

        # Active users count
        cur.execute(
            "SELECT COUNT(1) FROM user_company_map WHERE company_id = ? AND status = 'Active'",
            (company_id,),
        )
        cnt_row = cur.fetchone()
        user_count = int(cnt_row[0]) if cnt_row and cnt_row[0] is not None else 0
        conn.commit()
        conn.close()

        return jsonify(
            {
                "company_id": int(comp["id"]) if comp and comp.get("id") is not None else company_id,
                "company_name": comp.get("name") if comp else "Acme LLC",
                "subscription_plan": comp.get("subscription_plan") if comp else "Starter",
                "status": comp.get("status") if comp else "Active",
                "created_at": _fmt_date(comp.get("created_at") if comp else None) or dt.date.today().isoformat(),
                "user_count": user_count,
                "industry": comp.get("industry") if comp else None,
                "timezone": comp.get("timezone") if comp else None,
                "currency": comp.get("currency") if comp else None,
                "address": comp.get("address") if comp else None,
                "phone": comp.get("phone") if comp else None,
                "email": comp.get("email") if comp else None,
            }
        )
    except Exception:
        # Fallback mock
        return jsonify(
            {
                "company_name": "Acme LLC",
                "subscription_plan": "Starter",
                "status": "Active",
                "created_at": dt.date.today().isoformat(),
                "user_count": 3,
            }
        )


@user_dashboard_bp.get("/company/users")
@jwt_required()
def company_users():
    try:
        user_id = int(getattr(request, "user_id", 0) or 0)
        conn = get_connection()
        cur = conn.cursor()
        company_id = _get_or_create_company_for_user(cur, user_id)

        cur.execute(
            """
            SELECT m.id AS map_id, u.id AS user_id, u.email, u.company_name, m.role, m.status, m.last_login
            FROM user_company_map m
            JOIN users u ON u.id = m.user_id
            WHERE m.company_id = ?
            ORDER BY u.email
            """,
            (company_id,),
        )
        rows = fetchall_dict(cur)
        conn.commit()
        conn.close()

        def derive_name(r: Dict[str, Any]) -> str:
            name = (r.get("company_name") or "").strip()
            if name:
                return name
            email = (r.get("email") or "").strip()
            if "@" in email:
                return email.split("@")[0]
            return email or "User"

        users = [
            {
                "id": int(r.get("user_id")) if r.get("user_id") is not None else None,
                "email": r.get("email"),
                "name": derive_name(r),
                "role": r.get("role") or "Member",
                "status": r.get("status") or "Active",
                "last_login": _fmt_date(r.get("last_login")),
            }
            for r in rows
        ]
        return jsonify({"users": users})
    except Exception as e:
        return jsonify({"users": [], "error": str(e)}), 200


@user_dashboard_bp.patch("/company/users/<int:uid>")
@jwt_required()
def update_company_user(uid: int):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = (data.get("role") or "").strip()
    try:
        requester_id = int(getattr(request, "user_id", 0) or 0)
        conn = get_connection()
        cur = conn.cursor()
        company_id = _get_or_create_company_for_user(cur, requester_id)

        # Ensure the user is part of this company
        cur.execute(
            "SELECT id, role FROM user_company_map WHERE user_id = ? AND company_id = ?",
            (int(uid), company_id),
        )
        map_row = cur.fetchone()
        if not map_row:
            conn.close()
            return jsonify({"error": "User not part of this company"}), 404

        # Build users update
        user_sets = []
        uparams: List[Any] = []
        if name:
            user_sets.append("company_name = ?")
            uparams.append(name)
        if email:
            # Ensure no other user has the email
            cur.execute("SELECT id FROM users WHERE email = ? AND id <> ?", (email, int(uid)))
            if cur.fetchone():
                conn.close()
                return jsonify({"error": "Email already in use"}), 400
            user_sets.append("email = ?")
            uparams.append(email)
        if user_sets:
            sql = f"UPDATE users SET {', '.join(user_sets)} WHERE id = ?"
            uparams.append(int(uid))
            cur.execute(sql, tuple(uparams))

        # Update role if provided
        if role:
            cur.execute(
                "UPDATE user_company_map SET role = ? WHERE user_id = ? AND company_id = ?",
                (role, int(uid), company_id),
            )

        _log_audit(cur, requester_id, company_id, "update_user", f"user_id={uid}; fields={','.join([s.split('=')[0].strip() for s in user_sets])}{'; role' if role else ''}")

        # Return updated record
        cur.execute(
            """
            SELECT m.id AS map_id, u.id AS user_id, u.email, u.company_name, m.role, m.status, m.last_login
            FROM user_company_map m
            JOIN users u ON u.id = m.user_id
            WHERE m.company_id = ? AND u.id = ?
            """,
            (company_id, int(uid)),
        )
        r = fetchone_dict(cur)
        conn.commit()
        conn.close()
        if not r:
            return jsonify({"error": "User not found after update"}), 404
        updated = {
            "id": int(r.get("user_id")),
            "email": r.get("email"),
            "name": (r.get("company_name") or "").strip() or ((r.get("email") or "").split("@")[0] if "@" in (r.get("email") or "") else r.get("email") or "User"),
            "role": r.get("role") or "Member",
            "status": r.get("status") or "Active",
            "last_login": _fmt_date(r.get("last_login")),
        }
        return jsonify({"user": updated})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_dashboard_bp.post("/company/users")
@jwt_required()
def add_company_user():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = (data.get("role") or "Member").strip() or "Member"
    if not email:
        return jsonify({"error": "email is required"}), 400
    try:
        requester_id = int(getattr(request, "user_id", 0) or 0)
        conn = get_connection()
        cur = conn.cursor()
        company_id = _get_or_create_company_for_user(cur, requester_id)

        # Company name for defaulting user.company_name
        cur.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
        row = cur.fetchone()
        company_name = row[0] if row and row[0] else None

        # 1) Find or create user
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        urow = cur.fetchone()
        if urow and urow[0] is not None:
            new_uid = int(urow[0])
        else:
            # Generate safe placeholder password hash to satisfy NOT NULL constraint
            from werkzeug.security import generate_password_hash  # local import to avoid global dep
            import secrets

            placeholder_pw = generate_password_hash("temp_" + secrets.token_hex(4))
            # Prefer OUTPUT to retrieve id; fall back to select by email
            try:
                cur.execute(
                    """
                    INSERT INTO users (email, company_name, password_hash)
                    OUTPUT inserted.id
                    VALUES (?, ?, ?)
                    """,
                    (email, company_name or name or "", placeholder_pw),
                )
                r = cur.fetchone()
                new_uid = int(r[0]) if r and r[0] is not None else None
            except Exception:
                # Fallback insert without OUTPUT, then select id by email
                cur.execute(
                    "INSERT INTO users (email, company_name, password_hash) VALUES (?, ?, ?)",
                    (email, company_name or name or "", placeholder_pw),
                )
                cur.execute("SELECT id FROM users WHERE email = ?", (email,))
                rr = cur.fetchone()
                if not rr or rr[0] is None:
                    raise RuntimeError("Failed to retrieve new user id")
                new_uid = int(rr[0])

        # 2) Link to company; if an existing mapping is inactive, reactivate it instead of erroring
        cur.execute(
            "SELECT id, status FROM user_company_map WHERE user_id = ? AND company_id = ?",
            (new_uid, company_id),
        )
        existing = cur.fetchone()
        if existing and existing[0] is not None:
            map_id = int(existing[0])
            existing_status = (existing[1] or "").strip()
            if existing_status.lower() != "active".lower():
                cur.execute(
                    "UPDATE user_company_map SET status = 'Active', role = ? WHERE id = ?",
                    (role, map_id),
                )
            else:
                conn.close()
                return jsonify({"error": "User already part of company"}), 400
        else:
            cur.execute(
                "INSERT INTO user_company_map (user_id, company_id, role, status) VALUES (?, ?, ?, 'Active')",
                (new_uid, company_id, role),
            )

        # If a display name is provided, update users.company_name for consistency
        if name:
            try:
                cur.execute("UPDATE users SET company_name = ? WHERE id = ?", (name, new_uid))
            except Exception:
                pass

        # 3) Audit log
        _log_audit(cur, requester_id, company_id, f"add_user:{email}", f"role={role}")

        conn.commit()
        conn.close()
        return jsonify({"message": "User added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_dashboard_bp.delete("/company/users/<int:uid>")
@jwt_required()
def remove_company_user(uid: int):
    try:
        requester_id = int(getattr(request, "user_id", 0) or 0)
        conn = get_connection()
        cur = conn.cursor()
        company_id = _get_or_create_company_for_user(cur, requester_id)

        # Prevent removing owner
        cur.execute("SELECT owner_id FROM companies WHERE id = ?", (company_id,))
        row = cur.fetchone()
        owner_id = int(row[0]) if row and row[0] is not None else None
        if owner_id is not None and int(uid) == owner_id:
            conn.close()
            return jsonify({"error": "Cannot remove company owner"}), 400

        # Ensure mapping exists
        cur.execute(
            "SELECT id, role FROM user_company_map WHERE user_id = ? AND company_id = ?",
            (int(uid), company_id),
        )
        m = cur.fetchone()
        if not m or m[0] is None:
            conn.close()
            return jsonify({"error": "User not in company"}), 404

        cur.execute(
            "DELETE FROM user_company_map WHERE user_id = ? AND company_id = ?",
            (int(uid), company_id),
        )
        _log_audit(cur, requester_id, company_id, "remove_user", f"user_id={uid}")
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_dashboard_bp.patch("/company/settings")
@jwt_required()
def update_company_settings():
    data = request.get_json(silent=True) or {}
    company_name = (data.get("company_name") or data.get("name") or "").strip()
    industry = (data.get("industry") or "").strip()
    timezone = (data.get("timezone") or "").strip()
    currency = (data.get("currency") or "").strip()
    address = (data.get("address") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()
    try:
        user_id = int(getattr(request, "user_id", 0) or 0)
        conn = get_connection()
        cur = conn.cursor()
        company_id = _get_or_create_company_for_user(cur, user_id)

        _ensure_company_tables(cur)

        sets = []
        params: List[Any] = []
        if company_name:
            sets.append("name = ?")
            params.append(company_name)
        if industry:
            sets.append("industry = ?")
            params.append(industry)
        if timezone:
            sets.append("timezone = ?")
            params.append(timezone)
        if currency:
            sets.append("currency = ?")
            params.append(currency)
        if address:
            sets.append("address = ?")
            params.append(address)
        if phone:
            sets.append("phone = ?")
            params.append(phone)
        if email:
            sets.append("email = ?")
            params.append(email)
        if not sets:
            conn.close()
            return jsonify({"error": "No fields to update"}), 400

        sql = f"UPDATE companies SET {', '.join(sets)} WHERE id = ?"
        params.append(company_id)
        cur.execute(sql, tuple(params))
        _log_audit(cur, user_id, company_id, "update_company", f"fields={','.join([s.split('=')[0].strip() for s in sets])}")

        cur.execute(
            "SELECT id, name, subscription_plan, status, created_at, industry, timezone, currency, address, phone, email FROM companies WHERE id = ?",
            (company_id,),
        )
        comp = fetchone_dict(cur)
        conn.commit()
        conn.close()
        return jsonify(
            {
                "company_id": int(comp["id"]) if comp and comp.get("id") is not None else company_id,
                "company_name": comp.get("name") if comp else company_name,
                "industry": comp.get("industry") if comp else industry,
                "timezone": comp.get("timezone") if comp else timezone,
                "currency": comp.get("currency") if comp else currency,
                "address": comp.get("address") if comp else address,
                "phone": comp.get("phone") if comp else phone,
                "email": comp.get("email") if comp else email,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
