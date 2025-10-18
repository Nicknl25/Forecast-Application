import os
import secrets
from urllib.parse import urlencode

from flask import Blueprint, jsonify

from qb_app.routes_auth import jwt_required


qb_connect_bp = Blueprint("qb_connect_bp", __name__, url_prefix="/api/qb")


@qb_connect_bp.get("/connect")
@jwt_required()
def qb_connect():
    client_id = os.getenv("QB_CLIENT_ID") or os.getenv("CLIENT_ID")
    redirect_uri = os.getenv("QB_REDIRECT_URI") or os.getenv("REDIRECT_URI")
    scope = os.getenv("QB_SCOPES") or os.getenv("QB_SCOPE") or "com.intuit.quickbooks.accounting"
    auth_base = (
        os.getenv("QB_AUTH_URL")
        or os.getenv("INTUIT_AUTH_URL")
        or "https://appcenter.intuit.com/connect/oauth2"
    )

    if not client_id or not redirect_uri:
        print("QB connect error: missing client_id or redirect_uri env vars")
        return (
            jsonify({"error": "Missing QB_CLIENT_ID/CLIENT_ID or QB_REDIRECT_URI/REDIRECT_URI"}),
            500,
        )

    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": scope,
        "redirect_uri": redirect_uri,
        "state": secrets.token_urlsafe(16),
    }

    auth_url = f"{auth_base}?{urlencode(params)}"
    print("QuickBooks auth URL generated")
    return jsonify({"auth_url": auth_url})
