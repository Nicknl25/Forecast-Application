# Container deployment script for Tithe Financial Web App
# Builds Docker image, pushes to ACR, points Web App to latest tag, and restarts.

param(
  [string]$EnvPath = ".env",
  [string]$ImageName = "finance-webapp",
  [string]$Tag = "latest"
)

$ErrorActionPreference = 'Stop'

function Load-DotEnv {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return @{} }
  $ht = @{}
  Get-Content -Path $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
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

function Get-FromEnvOrDefault {
  param([hashtable]$EnvVals, [string]$Key, [string]$Default)
  if ($EnvVals.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($EnvVals[$Key])) { return $EnvVals[$Key] }
  return $Default
}

try {
  $envVals = Load-DotEnv -Path $EnvPath

  $rg = Get-FromEnvOrDefault $envVals 'RG' 'finance-rg'
  $webApp = Get-FromEnvOrDefault $envVals 'WEBAPP_NAME' 'finance-webapp-test'

  # Determine ACR login server and name
  $acrLoginServer = Get-FromEnvOrDefault $envVals 'DOCKER_REGISTRY_SERVER_URL' 'https://financeacrignat.azurecr.io'
  $acrLoginServer = $acrLoginServer.Trim().TrimEnd('/')
  if ($acrLoginServer.StartsWith('http')) { $acrLoginServer = $acrLoginServer -replace '^https?://','' }
  $acrName = ($acrLoginServer -split '\.')[0]

  $fullImage = "$acrLoginServer/$($ImageName):$Tag"

  # Verify Docker presence
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker CLI not found. Please install Docker and ensure 'docker' is on PATH."
    exit 1
  }

  # Verify Azure CLI login
  try { $null = az account show | Out-Null } catch { Write-Error "Azure CLI not logged in. Run 'az login' first."; exit 1 }

  Write-Host "Building Docker image: $fullImage" -ForegroundColor Cyan
  docker build -t $fullImage .

  Write-Host "Logging into ACR: $acrName" -ForegroundColor Cyan
  az acr login --name $acrName | Out-Null

  Write-Host "Pushing image: $fullImage" -ForegroundColor Cyan
  docker push $fullImage

  Write-Host "Pointing Web App $webApp to image: $fullImage" -ForegroundColor Cyan
  az webapp config container set -g $rg -n $webApp --container-image-name $fullImage | Out-Null

  Write-Host "Restarting Web App: $webApp" -ForegroundColor Cyan
  az webapp restart -g $rg -n $webApp | Out-Null

  $ts = (Get-Date).ToString('u')
  Write-Host "Container deploy complete ($ts)." -ForegroundColor Green
  Write-Host " - Image: $fullImage"
  Write-Host " - Web App: $webApp (RG: $rg)"
  Write-Host "Open: https://$webApp.azurewebsites.net"
}
catch {
  Write-Host "Container deployment failed" -ForegroundColor Red
  Write-Error $_
  exit 1
}
