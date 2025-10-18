#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/deploy.sh [path_to_env_file]
# Defaults to .env in repo root

ENV_FILE=${1:-.env}

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: env file '$ENV_FILE' not found. Copy .env.example to .env and fill values."
  exit 1
fi

if ! command -v az >/dev/null 2>&1; then
  echo "Error: Azure CLI 'az' not found. Install Azure CLI first."
  exit 1
fi

echo "Loading env from $ENV_FILE"
set -a
source "$ENV_FILE"
set +a

# Required variables
REQUIRED=(RG LOC PLAN WEBAPP_NAME FUNCAPP_NAME STORAGE QB_CLIENT_ID QB_CLIENT_SECRET ENCRYPTION_SECRET SQL_SERVER SQL_DB SQL_USER SQL_PASSWORD TEST_FUNCTION_KEY)
for v in "${REQUIRED[@]}"; do
  if [[ -z "${!v:-}" ]]; then
    echo "Error: missing required var '$v' in $ENV_FILE" >&2
    MISSING=1
  fi
done
if [[ "${MISSING:-0}" -eq 1 ]]; then
  exit 1
fi

PYTHON_VERSION=${PYTHON_VERSION:-3.11}
PLAN_SKU=${PLAN_SKU:-B1}
STORAGE_SKU=${STORAGE_SKU:-Standard_LRS}
ALWAYS_ON=${ALWAYS_ON:-true}
DEPLOY_WEBAPP=${DEPLOY_WEBAPP:-true}
DEPLOY_FUNCAPP=${DEPLOY_FUNCAPP:-true}

echo "Ensuring Azure login..."
az account show >/dev/null 2>&1 || az login >/dev/null

echo "Creating resource group $RG ($LOC)"
az group create -n "$RG" -l "$LOC" >/dev/null

echo "Creating App Service plan $PLAN (Linux, $PLAN_SKU)"
az appservice plan create -g "$RG" -n "$PLAN" --sku "$PLAN_SKU" --is-linux >/dev/null

echo "Creating Web App $WEBAPP_NAME (Python $PYTHON_VERSION)"
az webapp create -g "$RG" -p "$PLAN" -n "$WEBAPP_NAME" --runtime "PYTHON:$PYTHON_VERSION" >/dev/null

APP_BASE_URL="https://$WEBAPP_NAME.azurewebsites.net"
QB_REDIRECT_URI="$APP_BASE_URL/api/qb/oauth/callback"

echo "Configuring Web App settings"
az webapp config appsettings set -g "$RG" -n "$WEBAPP_NAME" --settings \
  QB_CLIENT_ID="$QB_CLIENT_ID" \
  QB_CLIENT_SECRET="$QB_CLIENT_SECRET" \
  QB_REDIRECT_URI="$QB_REDIRECT_URI" \
  ENCRYPTION_SECRET="$ENCRYPTION_SECRET" \
  SQL_SERVER="$SQL_SERVER" \
  SQL_DB="$SQL_DB" \
  SQL_USER="$SQL_USER" \
  SQL_PASSWORD="$SQL_PASSWORD" \
  APP_BASE_URL="$APP_BASE_URL" \
  TEST_FUNCTION_KEY="$TEST_FUNCTION_KEY" >/dev/null

echo "Setting Web App startup command"
az webapp config set -g "$RG" -n "$WEBAPP_NAME" --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app" >/dev/null

if [[ "$ALWAYS_ON" == "true" ]]; then
  echo "Enabling Always On for Web App"
  az webapp config set -g "$RG" -n "$WEBAPP_NAME" --always-on true >/dev/null || true
fi

echo "Creating storage account $STORAGE ($STORAGE_SKU)"
az storage account create -g "$RG" -n "$STORAGE" -l "$LOC" --sku "$STORAGE_SKU" >/dev/null

echo "Creating Function App $FUNCAPP_NAME (Linux Consumption, Python $PYTHON_VERSION)"
az functionapp create -g "$RG" -n "$FUNCAPP_NAME" \
  --consumption-plan-location "$LOC" \
  --runtime python --runtime-version "$PYTHON_VERSION" --functions-version 4 \
  --os-type Linux \
  --storage-account "$STORAGE" >/dev/null

echo "Configuring Function App settings"
az functionapp config appsettings set -g "$RG" -n "$FUNCAPP_NAME" --settings \
  ENCRYPTION_SECRET="$ENCRYPTION_SECRET" \
  SQL_SERVER="$SQL_SERVER" \
  SQL_DB="$SQL_DB" \
  SQL_USER="$SQL_USER" \
  SQL_PASSWORD="$SQL_PASSWORD" >/dev/null

if [[ "$DEPLOY_WEBAPP" == "true" ]]; then
  echo "Deploying to Web App (zip deploy from repo root)"
  az webapp deploy -g "$RG" -n "$WEBAPP_NAME" --src-path . --type zip >/dev/null
else
  echo "Skipping Web App deploy (DEPLOY_WEBAPP=$DEPLOY_WEBAPP)"
fi

if [[ "$DEPLOY_FUNCAPP" == "true" ]]; then
  echo "Preparing Function App zip (excluding .git, venvs, caches)"
  ZIP_PATH=${FUNC_ZIP:-functionapp.zip}
  if command -v zip >/dev/null 2>&1; then
    zip -qr "$ZIP_PATH" . -x "*.git*" "*__pycache__*" "*.venv*" "*venv*" "*deploy.zip*" "*functionapp.zip*"
  else
    echo "Warning: 'zip' not found. Please create $ZIP_PATH manually and re-run the deploy step below." >&2
  fi
  if [[ -f "$ZIP_PATH" ]]; then
    echo "Deploying to Function App from $ZIP_PATH"
    az functionapp deployment source config-zip -g "$RG" -n "$FUNCAPP_NAME" --src "$ZIP_PATH" >/dev/null
  else
    echo "Skipped Function App deploy (zip not available)." >&2
  fi
else
  echo "Skipping Function App deploy (DEPLOY_FUNCAPP=$DEPLOY_FUNCAPP)"
fi

echo "Done. Web: $APP_BASE_URL"

