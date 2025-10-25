import os
from flask import Blueprint, jsonify, request

from qb_app.routes_auth import jwt_required
from qb_app.db import get_connection, fetchone_dict
from qb_app.job_runner import submit_onboarding


integrations_bp = Blueprint("integrations_bp", __name__, url_prefix="/api/integrations")


def _already_onboarded(cur, client_id: int) -> bool:
    try:
        # Check if any transactions exist for this client
        cur.execute(
            """
            IF OBJECT_ID('dbo.qb_transactions', 'U') IS NOT NULL
            SELECT TOP 1 1 FROM qb_transactions WHERE client_auth_id = ?
            ELSE SELECT 0
            """,
            (int(client_id),),
        )
        row = cur.fetchone()
        if not row:
            return False
        # When table absent, SELECT 0 returns a single row with 0
        try:
            return bool(row[0])
        except Exception:
            return False
    except Exception:
        return False


@integrations_bp.post("/start_onboarding")
@jwt_required()
def start_onboarding():
    """Start onboarding for the authenticated user's connected QuickBooks realm.

    Looks up the user's realm_id in quickbooks_tokens, maps to client_auth.id,
    and queues the onboarding job if not already completed.
    """
    try:
        user_id = int(getattr(request, "user_id", 0) or 0)
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        conn = get_connection()
        cur = conn.cursor()

        # Find the user's latest linked realm (if any)
        try:
            cur.execute(
                """
                IF OBJECT_ID('dbo.quickbooks_tokens','U') IS NULL
                    SELECT NULL AS realm_id
                ELSE
                    SELECT TOP 1 realm_id FROM quickbooks_tokens WHERE user_id = ? ORDER BY id DESC
                """,
                (user_id,),
            )
            row = cur.fetchone()
            realm_id = row[0] if row and row[0] is not None else None
        except Exception:
            realm_id = None

        if not realm_id:
            conn.close()
            return jsonify({"error": "not_connected", "message": "Connect QuickBooks first"}), 400

        # Map to client_auth id
        cur.execute("SELECT id FROM client_auth WHERE realm_id = ?", (realm_id,))
        row = cur.fetchone()
        if not row or row[0] is None:
            conn.close()
            return jsonify({"error": "no_client_record", "message": "Client record not found for realm"}), 400
        client_id = int(row[0])

        # Safety: skip if already onboarded
        if _already_onboarded(cur, client_id):
            conn.close()
            return jsonify({"ok": True, "already_onboarded": True}), 200

        conn.close()
        submit_onboarding(client_id)
        return jsonify({"ok": True, "started": True, "client_id": client_id}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500

