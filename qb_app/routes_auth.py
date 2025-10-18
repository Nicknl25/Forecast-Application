import datetime as dt
from functools import wraps
import bcrypt
import jwt
from flask import Blueprint, request, jsonify

from qb_app.db import get_connection, fetchone_dict
from qb_app import app


auth_bp = Blueprint("auth_bp", __name__, url_prefix="/api/users")


def _get_secret_key() -> str:
    return app.config.get("SECRET_KEY")


def create_jwt(user_id: int, minutes: int = 30):
    # Use timezone-aware UTC consistently to avoid platform-specific timestamp quirks
    now = dt.datetime.now(dt.timezone.utc)
    expires_at = now + dt.timedelta(minutes=minutes)
    now_ts = int(now.timestamp())
    payload = {
        "sub": user_id,
        "iat": now_ts,
        "nbf": now_ts,
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
            if not auth_header or not auth_header.lower().startswith("bearer "):
                return jsonify({"error": "Missing or invalid Authorization header"}), 401
            token = auth_header.split(" ", 1)[1].strip()
            try:
                decoded = jwt.decode(
                    token,
                    _get_secret_key(),
                    algorithms=["HS256"],
                    leeway=30,
                    options={"verify_iat": False, "verify_nbf": False},
                )
            except jwt.ExpiredSignatureError:
                print("Token expired")
                return jsonify({"error": "Token expired"}), 401
            except Exception as e:
                # Temporary diagnostics for token decode failures
                try:
                    import hashlib  # noqa: WPS433
                    import jwt as _jwt  # noqa: WPS433
                    secret = _get_secret_key() or ""
                    secret_fpr = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:10]
                except Exception:
                    secret_fpr = "unavailable"
                try:
                    segs = token.count(".") + 1 if token else 0
                except Exception:
                    segs = 0
                try:
                    pyjwt_ver = getattr(_jwt, "__version__", "unknown")
                except Exception:
                    pyjwt_ver = "unknown"

                # Unverified decode to inspect iat/exp and time drift
                iat_val = None
                exp_val = None
                nbf_val = None
                try:
                    unverified = _jwt.decode(
                        token,
                        options={
                            "verify_signature": False,
                            "verify_exp": False,
                            "verify_nbf": False,
                            "verify_iat": False,
                        },
                    )
                    iat_val = unverified.get("iat")
                    exp_val = unverified.get("exp")
                    nbf_val = unverified.get("nbf")
                except Exception as ue:  # noqa: BLE001
                    print("Unverified decode failed:", repr(ue))

                try:
                    import datetime as _dt  # noqa: WPS433

                    now_dt = _dt.datetime.now(_dt.timezone.utc)
                    now_ts = int(now_dt.timestamp())
                    now_iso = now_dt.isoformat()
                    iat_iso = (
                        _dt.datetime.utcfromtimestamp(int(iat_val)).isoformat() + "Z"
                        if iat_val is not None
                        else "None"
                    )
                    exp_iso = (
                        _dt.datetime.utcfromtimestamp(int(exp_val)).isoformat() + "Z"
                        if exp_val is not None
                        else "None"
                    )
                    nbf_iso = (
                        _dt.datetime.utcfromtimestamp(int(nbf_val)).isoformat() + "Z"
                        if nbf_val is not None
                        else "None"
                    )
                    iat_diff = int(iat_val) - now_ts if iat_val is not None else None
                    exp_diff = int(exp_val) - now_ts if exp_val is not None else None
                    nbf_diff = int(nbf_val) - now_ts if nbf_val is not None else None
                    print(
                        "TIME DRIFT",
                        f"now={now_iso}",
                        f"iat={iat_iso}",
                        f"iat_minus_now_sec={iat_diff}",
                        f"nbf={nbf_iso}",
                        f"nbf_minus_now_sec={nbf_diff}",
                        f"exp={exp_iso}",
                        f"exp_minus_now_sec={exp_diff}",
                    )
                except Exception:
                    pass
                print(
                    "Invalid token",
                    f"type={type(e).__name__}",
                    f"msg={repr(e)}",
                    f"len={len(token) if token else 0}",
                    f"segs={segs}",
                    f"prefix={token[:30] if token else ''}",
                    f"pyjwt={pyjwt_ver}",
                    f"secret_fpr={secret_fpr}",
                )
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

    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    try:
        conn = get_connection()
        cur = conn.cursor()
        # Insert user and attempt to capture the new id
        cur.execute(
            """
            INSERT INTO users (company_name, email, password_hash)
            OUTPUT inserted.id
            VALUES (?, ?, ?)
            """,
            (company_name, email, pw_hash),
        )
        row = cur.fetchone()
        new_user_id = int(row[0]) if row and row[0] is not None else None
        # Fallback select by email if OUTPUT did not return an id
        if new_user_id is None:
            cur.execute("SELECT id FROM users WHERE email = ?", (email,))
            row2 = cur.fetchone()
            if row2 and row2[0] is not None:
                new_user_id = int(row2[0])
        conn.commit()
        conn.close()
        print("User registered")
        payload = {"message": "User registered"}
        if new_user_id is not None:
            payload["user_id"] = new_user_id
        return jsonify(payload), 201
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
        if not bcrypt.checkpw(password.encode("utf-8"), str(pw_hash).encode("utf-8")):
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
    # === Diagnostic JWT decode logging (temporary) ===
    import jwt  # noqa: F401
    import os  # noqa: F401
    import datetime as _dt  # noqa: F401
    from qb_app import app as _app  # local alias to avoid shadowing

    token = request.headers.get("Authorization", "")
    token = token.replace("Bearer ", "").replace("bearer ", "")
    print("\n==== JWT DEBUG ====")
    print("Token prefix:", token[:60])
    print("SECRET_KEY used:", _app.config.get("SECRET_KEY"))
    # Unverified decode to compare times
    try:
        claims = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_nbf": False,
                "verify_iat": False,
            },
        )
        now_dt = _dt.datetime.now(_dt.timezone.utc)
        now_ts = int(now_dt.timestamp())
        now_iso = now_dt.isoformat()
        iat_val = claims.get("iat")
        exp_val = claims.get("exp")
        nbf_val = claims.get("nbf")
        iat_iso = (
            _dt.datetime.utcfromtimestamp(int(iat_val)).isoformat() + "Z"
            if iat_val is not None
            else "None"
        )
        exp_iso = (
            _dt.datetime.utcfromtimestamp(int(exp_val)).isoformat() + "Z"
            if exp_val is not None
            else "None"
        )
        nbf_iso = (
            _dt.datetime.utcfromtimestamp(int(nbf_val)).isoformat() + "Z"
            if nbf_val is not None
            else "None"
        )
        print(
            "NOW UTC:", now_iso,
            "IAT:", iat_iso,
            "IAT_MINUS_NOW_SEC:", (int(iat_val) - now_ts) if iat_val is not None else None,
            "NBF:", nbf_iso,
            "NBF_MINUS_NOW_SEC:", (int(nbf_val) - now_ts) if nbf_val is not None else None,
            "EXP:", exp_iso,
            "EXP_MINUS_NOW_SEC:", (int(exp_val) - now_ts) if exp_val is not None else None,
        )
    except Exception as ue:  # noqa: BLE001
        print("Unverified decode failed:", repr(ue))
    try:
        decoded = jwt.decode(
            token,
            _app.config.get("SECRET_KEY"),
            algorithms=["HS256"],
            leeway=30,
            options={"verify_iat": False, "verify_nbf": False},
        )  # type: ignore[arg-type]
        print("DECODE OK:", decoded)
    except Exception as e:  # noqa: BLE001
        print("DECODE FAILED:", repr(e))
        return jsonify({"error": "Invalid token", "details": str(e)}), 401
    # === End diagnostic logging ===

    # jwt_required already validated token and attached user_id
    uid = getattr(request, "user_id", None)
    if not uid:
        return jsonify({"error": "Invalid or expired token"}), 401
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, email, company_name FROM users WHERE id = ?", (uid,))
        row = fetchone_dict(cur)
        conn.close()
        if not row:
            return jsonify({"error": "User not found"}), 404
        user = row
    except Exception as e:
        return jsonify({"error": f"Lookup failed: {e}"}), 500
    return jsonify(
        {
            "user_id": int(user["id"]),
            "email": user["email"],
            "company_name": user["company_name"],
        }
    )
