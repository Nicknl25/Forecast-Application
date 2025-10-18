import os
import secrets
from urllib.parse import urlencode, quote

from flask import Blueprint, jsonify, request

from qb_app.routes_auth import jwt_required


qb_connect_bp = Blueprint("qb_connect_bp", __name__, url_prefix="/api/qb")


@qb_connect_bp.get("/connect")
@jwt_required()
def qb_connect():
    client_id = os.getenv("QB_CLIENT_ID") or os.getenv("CLIENT_ID")
    redirect_uri = os.getenv("QB_REDIRECT_URI") or os.getenv("REDIRECT_URI")
    # Expand default scopes for user profile where supported
    scope = (
        os.getenv("QB_SCOPES")
        or os.getenv("QB_SCOPE")
        or "com.intuit.quickbooks.accounting openid profile email"
    )
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

    # Link state to requesting user
    try:
        user_id = int(getattr(request, 'user_id', 0) or 0)
    except Exception:
        user_id = 0
    state = f"user_{user_id}" if user_id else secrets.token_urlsafe(16)

    # Build URL parameters without pre-encoding; urlencode will encode once
    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": scope,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    # Encode once; use quote (not quote_plus) so spaces become %20 (QB compatible)
    auth_url = f"{auth_base}?{urlencode(params, quote_via=quote)}"

    # Log the exact URL and redirect_uri parameter for diagnostics
    try:
        from urllib.parse import urlparse, parse_qs, unquote

        parsed = urlparse(auth_url)
        qs = parse_qs(parsed.query)
        raw_redirect = (qs.get("redirect_uri", [""])[0])
        once = unquote(raw_redirect) if raw_redirect else ""
        twice = unquote(once) if once else ""
        print("QB CONNECT full URL:", auth_url)
        print("QB CONNECT redirect_uri raw:", raw_redirect)
        print("QB CONNECT redirect_uri decoded_once:", once)
        print("QB CONNECT redirect_uri decoded_twice:", twice)
        if "%25" in raw_redirect:
            print("QB CONNECT note: redirect_uri appears double-encoded (%25 present)")
    except Exception as e:
        print("QB CONNECT logging error:", repr(e))

    print(f"QuickBooks auth URL generated for user_id={user_id}")
    return jsonify({"auth_url": auth_url})
