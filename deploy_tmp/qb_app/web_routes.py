import os
import io
import sys
import inspect
import importlib
import socket
from flask import request, jsonify

from qb_app.qb_callback_app import app, log
from qb_app.db import get_connection


@app.get("/")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/manual_trigger_test", methods=["GET", "POST"])
def manual_trigger_test():
    try:
        provided = request.args.get("code") or request.headers.get("x-functions-key")
        required = os.getenv("TEST_FUNCTION_KEY")
        if required and provided != required:
            return ("Unauthorized: invalid or missing code.", 401)

        target = request.args.get("target")
        if not target:
            return ("Missing ?target=<function_module>", 400)

        log_stream = io.StringIO()
        sys_stdout, sys_stderr = sys.stdout, sys.stderr
        sys.stdout = log_stream
        sys.stderr = log_stream
        try:
            module_name = f"{target}.__init__"
            func_module = importlib.import_module(module_name)

            params = {k: v for k, v in request.args.items() if k not in ("target", "code")}

            class MockTimer:
                past_due = False

            if hasattr(func_module, "main"):
                fn = func_module.main
                sig = inspect.signature(fn)
                if len(sig.parameters) == 1:
                    fn(MockTimer())
                elif len(sig.parameters) == 0:
                    fn()
                else:
                    fn(**params)
            else:
                return (f"Function module '{target}' has no main().", 400)
        finally:
            sys.stdout = sys_stdout
            sys.stderr = sys_stderr

        logs = log_stream.getvalue()
        return (f"OK: '{target}' executed.\n\n==== LOG OUTPUT ====\n{logs}", 200)
    except Exception as e:
        return (f"Error executing manual trigger: {e}", 500)


@app.get("/api/onboard_client")
def onboard_client():
    try:
        client_id = request.args.get("client_id")
        if not client_id:
            return ("Missing ?client_id=<value>", 400)

        provided = request.args.get("code") or request.headers.get("x-functions-key")
        required = os.getenv("TEST_FUNCTION_KEY")
        if required and provided != required:
            return ("Unauthorized: invalid or missing code.", 401)

        from qb_app import load_all_transactions
        log(f"Starting onboarding for client_id={client_id}")
        load_all_transactions.main(client_id=int(client_id))
        return (f"Onboarding process completed for client_id={client_id}", 200)
    except Exception as e:
        err = f"Error executing onboard_client: {e}"
        log(err)
        return (err, 500)


@app.get("/api/db/ping")
def db_ping():
    # Optional admin header gate (disabled by default)
    if os.getenv("ADMIN_HEADER_ENABLED", "0").strip() in ("1", "true", "yes"):
        header_name = os.getenv("ADMIN_HEADER_NAME", "x-admin-key")
        expected = os.getenv("ADMIN_HEADER_VALUE", "")
        provided = request.headers.get(header_name)
        if not expected or provided != expected:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        # Do not expose credentials; return error text only
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/api/db/diag")
def db_diag():
    # Optional admin header gate (disabled by default)
    if os.getenv("ADMIN_HEADER_ENABLED", "0").strip() in ("1", "true", "yes"):
        header_name = os.getenv("ADMIN_HEADER_NAME", "x-admin-key")
        expected = os.getenv("ADMIN_HEADER_VALUE", "")
        provided = request.headers.get(header_name)
        if not expected or provided != expected:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
    """Run in-container diagnostics: DNS, TCP 1433, pyodbc drivers, and connect tests.

    Returns JSON with results. Does not modify data.
    """
    results = {}

    server = (os.getenv("SQL_SERVER") or "").strip()
    db = (os.getenv("SQL_DB") or "").strip()
    user = (os.getenv("SQL_USER") or "").strip()
    pw = (os.getenv("SQL_PASSWORD") or "").strip()

    results["env"] = {"server": server, "db": db, "user": user, "has_password": bool(pw)}

    # DNS resolution
    try:
        addrs = socket.getaddrinfo(server, 1433, proto=socket.IPPROTO_TCP)
        results["dns"] = {
            "ok": True,
            "addresses": list({f"{a[4][0]}" for a in addrs}),
        }
    except Exception as e:  # noqa: BLE001
        results["dns"] = {"ok": False, "error": str(e)}

    # TCP reachability
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((server, 1433))
        sock.close()
        results["tcp_1433"] = {"ok": True}
    except Exception as e:  # noqa: BLE001
        results["tcp_1433"] = {"ok": False, "error": str(e)}

    # pyodbc driver inventory
    try:
        import pyodbc  # noqa: F401

        drivers = pyodbc.drivers()
        results["pyodbc_drivers"] = drivers
        has_odbc18 = any("ODBC Driver 18 for SQL Server" in d for d in drivers)
        results["has_odbc18"] = has_odbc18
    except Exception as e:  # noqa: BLE001
        results["pyodbc_drivers_error"] = str(e)

    # Connection tests: current (TrustServerCertificate=no) and relaxed (yes)
    def _conn_result(trust_yes: bool):
        try:
            import pyodbc

            conn_str = (
                "Driver={ODBC Driver 18 for SQL Server};"
                f"Server=tcp:{server},1433;"
                f"Database={db};"
                f"Uid={user};"
                f"Pwd={pw};"
                "Encrypt=yes;"
                f"TrustServerCertificate={'yes' if trust_yes else 'no'};"
                "Connection Timeout=10;"
            )
            cn = pyodbc.connect(conn_str)
            cur = cn.cursor()
            cur.execute("SELECT 1")
            cn.close()
            return {"ok": True}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    results["pyodbc_connect_trust_no"] = _conn_result(False)
    results["pyodbc_connect_trust_yes"] = _conn_result(True)

    return jsonify(results)
