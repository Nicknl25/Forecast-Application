# Finance Functions — Web App and Function App Split

[![Deploy Container to Azure Web App](https://github.com/Nicknl25/Forecast-Application/actions/workflows/deploy-container.yml/badge.svg?branch=main)](https://github.com/Nicknl25/Forecast-Application/actions/workflows/deploy-container.yml)

This repository is split between:
<!-- chore: trigger redeploy for scheduler verification -->

- Azure Web App (HTTP endpoints)
- Azure Function App (timers only)

The Web App hosts all HTTP routes via Flask/Gunicorn. The Function App runs only the scheduled jobs (daily QuickBooks sync and token refresh).

## Structure

- Web App entry: `wsgi.py`
- Web routes: `qb_app/web_routes.py`
- QuickBooks callback Flask app: `qb_app/qb_callback_app.py`
- Timers (Functions):
  - `daily_qb_sync/` (3:00 daily)
  - `qb_token_refresh/` (hourly)
- `host.json` has a functions allowlist so the Function App only runs the two timers.

## Deploy — Azure Web App (HTTP Only)

- Runtime: Python 3.11 or 3.12 (Linux recommended)
- Startup command:
  - `gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app`
- Environment/App Settings:
  - QuickBooks: `QB_CLIENT_ID`, `QB_CLIENT_SECRET`, `QB_REDIRECT_URI`
  - Crypto: `ENCRYPTION_SECRET` (Fernet key)
  - SQL: `SQL_SERVER`, `SQL_DB`, `SQL_USER`, `SQL_PASSWORD`
  - Triggers/ops: `APP_BASE_URL` (this Web App base URL), `TEST_FUNCTION_KEY` (shared key for protected routes)
- Redirect URI in your Intuit app should be:
  - `<WebAppBase>/api/qb/oauth/callback`

### Web App Routes

- `GET /` — health check
- `GET /api/qb/oauth/callback` — QuickBooks OAuth callback
- `GET|POST /api/manual_trigger_test?target=<module>&...&code=<key>` — manual trigger (executes function modules)
- `GET /api/onboard_client?client_id=<id>&code=<key>` — onboarding trigger

Notes:
- `code` can also be provided via header `x-functions-key`.
- `TEST_FUNCTION_KEY` must match for protected routes if set.

## Deploy — Azure Function App (Timers Only)

- Keep deploying this repo to the Function App. The host is restricted to:
  - `daily_qb_sync`
  - `qb_token_refresh`
- `host.json` includes:
  - `"functions": ["daily_qb_sync", "qb_token_refresh"]`
- Required settings on the Function App:
  - `ENCRYPTION_SECRET`, `SQL_SERVER`, `SQL_DB`, `SQL_USER`, `SQL_PASSWORD`

## Local Development

- Web App: `python wsgi.py` then visit `http://localhost:8000/`
- Example calls:
  - `/api/onboard_client?client_id=123&code=<TEST_FUNCTION_KEY>`
  - `/api/manual_trigger_test?target=onboard_client&client_id=123&code=<TEST_FUNCTION_KEY>`

## Requirements

- Deps for Web App serving are in root `requirements.txt`. Key packages:
  - `Flask`, `gunicorn`, `cryptography`, `azure-functions`, `pymssql`, `requests`, `python-dotenv`

## Notes

- The former HTTP-trigger Function folders were removed/disabled. Only timers run in the Function App.
- For fully serverless timers, you can keep the Function App as-is; for alternative scheduling you could migrate timers to WebJobs if desired.

## Azure CLI Snippet

The following example creates a Linux Web App for HTTP endpoints and a Linux Consumption Function App for timers, configures required settings, and shows basic deploy commands. Replace placeholder values in ALL_CAPS.

```
# Variables
RG="YOUR_RESOURCE_GROUP"
LOC="eastus"
PLAN="YOUR_APPSVC_PLAN"
WEBAPP_NAME="your-webapp-name"           # must be globally unique
FUNCAPP_NAME="your-funcapp-name"         # must be globally unique
STORAGE="yourfuncstoracct"               # 3-24 lower-case letters/numbers

# Create resource group
az group create -n $RG -l $LOC

# Create Linux App Service plan (for Web App)
az appservice plan create -g $RG -n $PLAN --sku B1 --is-linux

# Create Web App (Python 3.11)
az webapp create -g $RG -p $PLAN -n $WEBAPP_NAME --runtime "PYTHON:3.11"

# Configure Web App settings
APP_BASE_URL="https://$WEBAPP_NAME.azurewebsites.net"
az webapp config appsettings set -g $RG -n $WEBAPP_NAME --settings \
  QB_CLIENT_ID=YOUR_QB_CLIENT_ID \
  QB_CLIENT_SECRET=YOUR_QB_CLIENT_SECRET \
  QB_REDIRECT_URI=$APP_BASE_URL/api/qb/oauth/callback \
  ENCRYPTION_SECRET=YOUR_FERNET_KEY \
  SQL_SERVER=YOUR_SQL_SERVER \
  SQL_DB=YOUR_SQL_DB \
  SQL_USER=YOUR_SQL_USER \
  SQL_PASSWORD=YOUR_SQL_PASSWORD \
  APP_BASE_URL=$APP_BASE_URL \
  TEST_FUNCTION_KEY=YOUR_SHARED_KEY

# Set Web App startup command (Gunicorn)
az webapp config set -g $RG -n $WEBAPP_NAME --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app"

# (Optional) Keep Web App warm
az webapp config set -g $RG -n $WEBAPP_NAME --always-on true

# Create storage for the Function App
az storage account create -g $RG -n $STORAGE -l $LOC --sku Standard_LRS

# Create Linux Consumption Function App (Python 3.11, v4)
az functionapp create -g $RG -n $FUNCAPP_NAME \
  --consumption-plan-location $LOC \
  --runtime python --runtime-version 3.11 --functions-version 4 \
  --os-type Linux \
  --storage-account $STORAGE

# Configure Function App settings (timers)
az functionapp config appsettings set -g $RG -n $FUNCAPP_NAME --settings \
  ENCRYPTION_SECRET=YOUR_FERNET_KEY \
  SQL_SERVER=YOUR_SQL_SERVER \
  SQL_DB=YOUR_SQL_DB \
  SQL_USER=YOUR_SQL_USER \
  SQL_PASSWORD=YOUR_SQL_PASSWORD

# Deploy code
# Option A: Web App deploy from current folder (zip deploy)
az webapp deploy -g $RG -n $WEBAPP_NAME --src-path . --type zip

# Option B: Function App deploy a zip package of this repo
# Ensure host.json includes only ["daily_qb_sync", "qb_token_refresh"]
zip -r functionapp.zip .
az functionapp deployment source config-zip -g $RG -n $FUNCAPP_NAME --src functionapp.zip
```

## Automated Container Deployment

This repository auto-builds and deploys the Docker image to Azure Web App on every push to `main` via GitHub Actions.

- Workflow: `.github/workflows/deploy-container.yml`
- Registry: `financeacrignat.azurecr.io`
- Web App: `finance-webapp-test` (resource group `finance-rg`)

To enable:
- Add repository secret `AZURE_CREDENTIALS` (Service Principal JSON with ACR push + Web App manage permissions).
- Optionally add `ACR_USERNAME` and `ACR_PASSWORD` if you prefer explicit pull credentials; otherwise the workflow enables ACR admin and configures pull automatically.

The workflow summary includes the “Deployed image SHA.” You can also view deployment status via the badge near the top of this README.
