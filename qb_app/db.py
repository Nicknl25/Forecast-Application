import os
import pyodbc


def _build_connection_string():
    server = os.getenv("SQL_SERVER", "").strip()
    db = os.getenv("SQL_DB", "").strip()
    user = os.getenv("SQL_USER", "").strip()
    password = os.getenv("SQL_PASSWORD", "").strip()

    # Normalize server for pyodbc (ensure tcp and port 1433)
    server_clean = server.replace("tcp:", "")
    server_part = f"tcp:{server_clean},1433" if server_clean else ""

    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={server_part};"
        f"Database={db};"
        f"Uid={user};"
        f"Pwd={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=60;"
    )
    return conn_str


def get_connection():
    """Create a new pyodbc connection to Azure SQL using env vars with simple retries."""
    conn_str = _build_connection_string()
    last_err = None
    for attempt in range(1, 4):
        try:
            return pyodbc.connect(conn_str)
        except Exception as e:  # noqa: BLE001
            last_err = e
            try:
                import time

                time.sleep(1.5 * attempt)
            except Exception:
                pass
    raise last_err


def row_to_dict(cursor, row):
    """Convert a single pyodbc row into a dict using column names."""
    if row is None:
        return None
    cols = [c[0] for c in cursor.description]
    return {cols[i]: row[i] for i in range(len(cols))}


def fetchone_dict(cursor):
    """Fetch one row from the cursor and return as dict (or None)."""
    return row_to_dict(cursor, cursor.fetchone())


def fetchall_dict(cursor):
    """Fetch all rows from the cursor and return list of dicts."""
    cols = [c[0] for c in cursor.description]
    return [
        {cols[i]: row[i] for i in range(len(cols))}
        for row in cursor.fetchall()
    ]
