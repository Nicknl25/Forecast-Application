import os
import datetime as dt
from functools import wraps
import jwt
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from qb_app.qb_callback_app import app

from qb_app.db import get_connection, fetchone_dict


auth_bp = Blueprint("auth_bp", __name__, url_prefix="/api/users")


def _get_secret_key() -> str:
    sk = os.getenv("SECRET_KEY")
    if not sk:
        raise RuntimeError("SECRET_KEY is not set in environment")
    return sk


def create_jwt(user_id: int, minutes: int = 30):
    now = dt.datetime.utcnow()
    expires_at = now + dt.timedelta(minutes=minutes)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, _get_secret_key(), algorithm="HS256")
    return token, expires_at


def get_user_from_token(token: str):
    try:
        decoded = jwt.decode(token, _get_secret_key(), algorithms=["HS256"])
        user_id = decoded.get("sub")
        if not user_id:
            return None
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, company_name FROM users WHERE id = ?",
            (user_id,),
        )
        row = fetchone_dict(cur)
        conn.close()
        return row
    except Exception:
        return None


def jwt_required():
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Missing or invalid Authorization header"}), 401
            token = auth_header.split(" ", 1)[1].strip()
            try:
                decoded = jwt.decode(token, _get_secret_key(), algorithms=["HS256"])
            except jwt.ExpiredSignatureError:
                print("Token expired")
                return jsonify({"error": "Token expired"}), 401
            except Exception:
                print("Invalid token")
                return jsonify({"error": "Invalid token"}), 401

            # Verify token is stored and not expired in DB
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "SELECT user_id, expires_at FROM auth WHERE jwt_token = ?",
                    (token,),
                )
                row = cur.fetchone()
                conn.close()
                if not row:
                    print("Token not found in auth table")
                    return jsonify({"error": "Token not found"}), 401
                user_id, expires_at = row[0], row[1]
                # Basic expiry check (DB UTC)
                if hasattr(expires_at, "timestamp"):
                    if dt.datetime.utcnow() > expires_at:
                        print("Token expired by DB check")
                        return jsonify({"error": "Token expired"}), 401
            except Exception as e:
                print("Auth check failed", e)
                return jsonify({"error": "Auth check failed"}), 401

            # Attach user_id for downstream handlers
            request.user_id = decoded.get("sub")
            print("Token verified")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


@auth_bp.post("/register")
def register_user():
    data = request.get_json(silent=True) or {}
    company_name = (data.get("company_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not company_name or not email or not password:
        return jsonify({"error": "company_name, email, and password are required"}), 400

    # Hash the password for storage
    pw_hash = generate_password_hash(password)

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (company_name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (company_name, email, pw_hash),
        )
        conn.commit()
        conn.close()
        print("User registered")
        return jsonify({"message": "User registered"}), 201
    except Exception as e:
        print("Error inserting user", e)
        # If unique constraint fails or any other DB error
        return jsonify({"error": str(e)}), 500


@auth_bp.post("/login")
def login_user():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, company_name, password_hash FROM users WHERE email = ?",
            (email,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            print("Invalid credentials: email not found")
            return jsonify({"error": "Invalid credentials"}), 401

        user_id, _email, _company, pw_hash = row[0], row[1], row[2], row[3]
        if not pw_hash:
            conn.close()
            print("Invalid credentials: no password hash")
            return jsonify({"error": "Invalid credentials"}), 401
        # Validate using werkzeug's password hash checker (new users)
        ok = False
        try:
            ok = check_password_hash(str(pw_hash), password)
        except Exception:
            ok = False
        # Fallback to bcrypt for legacy users
        if not ok:
            try:
                import bcrypt  # lazy import to avoid hard dependency in envs without it
                ok = bcrypt.checkpw(password.encode("utf-8"), str(pw_hash).encode("utf-8"))
            except Exception:
                ok = False
        if not ok:
            conn.close()
            print("Invalid credentials: bad password")
            return jsonify({"error": "Invalid credentials"}), 401

        token, expires_at = create_jwt(int(user_id))
        cur.execute(
            """
            INSERT INTO auth (user_id, jwt_token, expires_at)
            VALUES (?, ?, ?)
            """,
            (int(user_id), token, expires_at),
        )
        conn.commit()
        conn.close()
        print("JWT issued")
        return jsonify({"token": token, "user_id": int(user_id)})
    except Exception as e:
        print("Login error", e)
        return jsonify({"error": str(e)}), 500


@auth_bp.get("/me")
@jwt_required()
def me():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ", 1)[1].strip()
    user = get_user_from_token(token)
    if not user:
        return jsonify({"error": "Invalid or expired token"}), 401
    return jsonify(
        {
            "user_id": int(user["id"]),
            "email": user["email"],
            "company_name": user["company_name"],
        }
    )

# Optional route aliases to support legacy frontend paths
@app.post("/api/auth/login")
@app.post("/api/login")
def login_user_alias():
    return login_user()
