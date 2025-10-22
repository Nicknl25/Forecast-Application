from qb_app.qb_callback_app import app  # Flask app

# Import additional web routes so they register with the app
import qb_app.web_routes  # noqa: F401

# Register new blueprints
try:
    from qb_app.routes_auth import auth_bp
    from qb_app.routes_qb_connect import qb_connect_bp
    from qb_app.routes_user_dashboard import user_dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(qb_connect_bp)
    app.register_blueprint(user_dashboard_bp)
except Exception as e:  # avoid crashing import if optional
    # You can remove this try/except in production once stable
    print(f"Blueprint registration warning: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)


import qb_app.scheduler  # start background jobs
