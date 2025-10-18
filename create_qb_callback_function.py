import os
import textwrap

# === Define paths ===
base_dir = os.getcwd()
folder = os.path.join(base_dir, "qb_callback_app")
init_file = os.path.join(folder, "__init__.py")
function_json = os.path.join(folder, "function.json")

# === Ensure the folder exists ===
os.makedirs(folder, exist_ok=True)

# === Write __init__.py ===
if not os.path.exists(init_file):
    callback_code = textwrap.dedent("""
        import logging
        import azure.functions as func
        from qb_app.qb_callback_app import app as flask_app

        # === Azure HTTP Trigger entry point ===
        def main(req: func.HttpRequest) -> func.HttpResponse:
            logging.info("✅ QuickBooks callback function triggered.")
            return func.WsgiMiddleware(flask_app.wsgi_app).handle(req)
    """).strip()

    with open(init_file, "w", encoding="utf-8") as f:
        f.write(callback_code)
    print(f"✅ Created {init_file}")
else:
    print(f"ℹ️ {init_file} already exists; not overwritten.")

# === Write function.json ===
if not os.path.exists(function_json):
    json_content = textwrap.dedent("""
        {
          "scriptFile": "__init__.py",
          "bindings": [
            {
              "authLevel": "anonymous",
              "type": "httpTrigger",
              "direction": "in",
              "name": "req",
              "route": "qb/oauth/callback",
              "methods": ["get", "post"]
            },
            {
              "type": "http",
              "direction": "out",
              "name": "$return"
            }
          ]
        }
    """).strip()

    with open(function_json, "w", encoding="utf-8") as f:
        f.write(json_content)
    print(f"✅ Created {function_json}")
else:
    print(f"ℹ️ {function_json} already exists; not overwritten.")

print("\n🎉 qb_callback_app function folder ready for deployment.")
