# Deploy Flask Web App via Azure CLI
# Zips only app sources and deploys to Azure Web App

param(
  [string]$ResourceGroup = "",
  [string]$Location = "",
  [string]$Plan = "",
  [string]$WebAppName = "",
  [string]$StorageAccount = "",
  [string]$PythonVersion = "3.11",

  # Secrets and app settings (optional, typically provided via .env)
  [string]$QB_CLIENT_ID = "",
  [string]$QB_CLIENT_SECRET = "",
  [string]$ENCRYPTION_SECRET = "",
  [string]$SQL_SERVER = "",
  [string]$SQL_DB = "",
  [string]$SQL_USER = "",
  [string]$SQL_PASSWORD = "",
  [string]$TEST_FUNCTION_KEY = "",

  # Toggles
  [bool]$DeployWebApp = $true,
  [bool]$DeployFuncApp = $false,
  [bool]$AlwaysOn = $true,

  # Optional .env path
  [string]$EnvPath = ".env"
)

$ErrorActionPreference = 'Stop'

function Load-DotEnv {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return @{} }
  $ht = @{}
  Get-Content -Path $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $eq = $line.IndexOf('=')
    if ($eq -lt 1) { return }
    $k = $line.Substring(0, $eq).Trim()
    $v = $line.Substring($eq+1).Trim()
    if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
      $v = $v.Substring(1, $v.Length-2)
    }
    $ht[$k] = $v
  }
  return $ht
}

$envVals = Load-DotEnv -Path $EnvPath

function Set-FromEnvIfEmpty {
  param([string]$ParamName, [string]$EnvKey)
  if (-not (Get-Variable -Name $ParamName -ErrorAction SilentlyContinue)) { return }
  $cur = Get-Variable -Name $ParamName -ValueOnly
  if ([string]::IsNullOrWhiteSpace($cur)) {
    if ($envVals.ContainsKey($EnvKey)) {
      Set-Variable -Name $ParamName -Value $envVals[$EnvKey] -Scope Script
    }
  }
}

# Map .env keys to params (non-empty params win)
Set-FromEnvIfEmpty ResourceGroup RG
Set-FromEnvIfEmpty Location LOC
Set-FromEnvIfEmpty Plan PLAN
Set-FromEnvIfEmpty WebAppName WEBAPP_NAME
Set-FromEnvIfEmpty StorageAccount STORAGE
Set-FromEnvIfEmpty PythonVersion PYTHON_VERSION
Set-FromEnvIfEmpty QB_CLIENT_ID QB_CLIENT_ID
Set-FromEnvIfEmpty QB_CLIENT_SECRET QB_CLIENT_SECRET
Set-FromEnvIfEmpty ENCRYPTION_SECRET ENCRYPTION_SECRET
Set-FromEnvIfEmpty SQL_SERVER SQL_SERVER
Set-FromEnvIfEmpty SQL_DB SQL_DB
Set-FromEnvIfEmpty SQL_USER SQL_USER
Set-FromEnvIfEmpty SQL_PASSWORD SQL_PASSWORD
Set-FromEnvIfEmpty TEST_FUNCTION_KEY TEST_FUNCTION_KEY

if ($envVals.ContainsKey('DEPLOY_WEBAPP')) { $DeployWebApp = [System.Convert]::ToBoolean($envVals['DEPLOY_WEBAPP']) }
if ($envVals.ContainsKey('ALWAYS_ON')) { $AlwaysOn = [System.Convert]::ToBoolean($envVals['ALWAYS_ON']) }

# Validate required
$required = @('ResourceGroup','WebAppName')
$missing = @()
foreach ($r in $required) { if ([string]::IsNullOrWhiteSpace((Get-Variable -Name $r -ValueOnly))) { $missing += $r } }
if ($missing.Count -gt 0) {
  Write-Error "Missing required parameters: $($missing -join ', '). Provide via -Param or in $EnvPath."
  exit 1
}

try {
  # Expose required env vars for az commands
  if (-not $ResourceGroup) { throw "ResourceGroup is required (or RG in .env)" }
  if (-not $WebAppName) { throw "WebAppName is required (or WEBAPP_NAME in .env)" }
  $env:AZURE_RESOURCE_GROUP = $ResourceGroup
  $env:AZURE_WEBAPP_NAME = $WebAppName

  Write-Host "Using resource group: $($env:AZURE_RESOURCE_GROUP)" -ForegroundColor Cyan
  Write-Host "Using Web App: $($env:AZURE_WEBAPP_NAME)" -ForegroundColor Cyan

  # 1) Zip only app sources (exclude envs/node_modules)
  $webZip = Join-Path (Get-Location) "webapp.zip"
  if (Test-Path $webZip) { Remove-Item $webZip -Force }
  Write-Host "Zipping app sources…" -ForegroundColor Green
  Compress-Archive -Path "./qb_app","./tithe-frontend/dist","./wsgi.py","./requirements.txt","./Dockerfile" -DestinationPath "webapp.zip" -Force

  # 2) Apply app settings from .env using parsed KEY=VALUE pairs
  Write-Host "Applying app settings from $EnvPath …" -ForegroundColor Green
  $kv = @()
  if (Test-Path $EnvPath) {
    Get-Content $EnvPath | ForEach-Object {
      $line = $_.Trim()
      if (-not $line) { return }
      if ($line.StartsWith('#')) { return }
      if (-not $line.Contains('=')) { return }
      $eq = $line.IndexOf('=')
      if ($eq -lt 1) { return }
      $k = $line.Substring(0, $eq).Trim()
      $v = $line.Substring($eq+1).Trim()
      if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
        $v = $v.Substring(1, $v.Length-2)
      }
      if ($k) { $kv += "$k=$v" }
    }
  }
  if ($kv.Count -gt 0) {
    az webapp config appsettings set --resource-group $env:AZURE_RESOURCE_GROUP --name $env:AZURE_WEBAPP_NAME --settings $kv | Out-Null
  } else {
    Write-Warning "No app settings parsed from $EnvPath; skipping appsettings update."
  }

  # 2b) Ensure Oryx build is enabled
  Write-Host "Enabling Oryx build flags on Web App…" -ForegroundColor Green
  az webapp config appsettings set --name $env:AZURE_WEBAPP_NAME --resource-group $env:AZURE_RESOURCE_GROUP --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true ENABLE_ORYX_BUILD=true | Out-Null

  # 3) Deploy zip to Web App
  Write-Host "Deploying to Azure Web App…" -ForegroundColor Green
  az webapp deploy --resource-group $env:AZURE_RESOURCE_GROUP --name $env:AZURE_WEBAPP_NAME --src-path $webZip | Out-Null

  Write-Host "Done.  Web: https://$WebAppName.azurewebsites.net" -ForegroundColor Green

  $ts = (Get-Date).ToString('u')
  Write-Host "Summary ($ts):" -ForegroundColor Cyan
  Write-Host " - Zipped source to $webZip"
  Write-Host " - Applied app settings from $EnvPath"
  Write-Host " - Deployed to Web App $WebAppName in RG $ResourceGroup"
}
catch {
  Write-Host "Deployment failed" -ForegroundColor Red
  Write-Error $_
  exit 1
}
