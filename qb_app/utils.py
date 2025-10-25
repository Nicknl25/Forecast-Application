from functools import wraps
import os
from flask import request, jsonify

from qb_app.routes_auth import jwt_required
from qb_app.db import get_connection, fetchone_dict


def admin_required(fn):
    """Allow admin access via x-admin-key OR JWT-based admin checks.

    Allowed if any is true:
      - Header x-admin-key equals ADMIN_KEY (no JWT required)
      - Authenticated user id equals ADMIN_USER_ID
      - Authenticated user email equals ADMIN_EMAIL
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        admin_key = (os.getenv("ADMIN_KEY") or "").strip()
        # Treat ADMIN_MASTER_KEY as same as ADMIN_KEY (fallback)
        master_key = (os.getenv("ADMIN_MASTER_KEY") or admin_key or "").strip()
        provided_key = (request.headers.get("x-admin-key") or "").strip()
        if provided_key and (provided_key == admin_key or provided_key == master_key):
            return fn(*args, **kwargs)

        @jwt_required()
        @wraps(fn)
        def inner(*args, **kwargs):
            uid = getattr(request, "user_id", None)
            if not uid:
                return jsonify({"error": "Unauthorized"}), 401

            # 1) Environment overrides
            admin_uid_env = (os.getenv("ADMIN_USER_ID") or "").strip()
            try:
                if admin_uid_env and int(admin_uid_env) == int(uid):
                    return fn(*args, **kwargs)
            except Exception:
                pass

            admin_email_env = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
            user_email = ""
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT email FROM users WHERE id = ?", (int(uid),))
                row = fetchone_dict(cur)
                user_email = ((row or {}).get("email") or "").strip().lower()
                # 2) Admin via env email
                if admin_email_env and user_email and user_email == admin_email_env:
                    conn.close()
                    return fn(*args, **kwargs)
                # 3) Admin via app_admins table
                if user_email:
                    try:
                        cur.execute(
                            """
                            IF OBJECT_ID('dbo.app_admins','U') IS NULL
                                SELECT 0
                            ELSE
                                SELECT CASE WHEN EXISTS (
                                  SELECT 1 FROM app_admins WHERE LOWER(email) = LOWER(?)
                                ) THEN 1 ELSE 0 END
                            """,
                            (user_email,),
                        )
                        r = cur.fetchone()
                        is_admin_tbl = bool(r[0]) if r and r[0] is not None else False
                        conn.close()
                        if is_admin_tbl:
                            return fn(*args, **kwargs)
                    except Exception:
                        conn.close()
                        pass
                else:
                    conn.close()
            except Exception:
                pass

            return jsonify({"error": "Admin access required"}), 403

        return inner(*args, **kwargs)

    return wrapper
