# Requires: Az PowerShell modules
# Install-Module Az -Scope CurrentUser -Repository PSGallery
# Connect-AzAccount
# Select-AzSubscription -SubscriptionId <id>

param(
  [string]$ResourceGroup = "",
  [string]$Location = "",
  [string]$Plan = "",
  [string]$WebAppName = "",
  [string]$FuncAppName = "",
  [string]$StorageAccount = "",
  [string]$PythonVersion = "3.11",

  # Secrets and app settings
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
  [bool]$DeployFuncApp = $true,
  [bool]$AlwaysOn = $true,

  # Optional .env path
  [string]$EnvPath = ".env"
)

function Ensure-Module {
  param([string]$Name)
  if (-not (Get-Module -ListAvailable -Name $Name)) {
    Write-Host "Installing module $Name..." -ForegroundColor Yellow
    Install-Module $Name -Scope CurrentUser -Force -Confirm:$false
  }
  Import-Module $Name -ErrorAction SilentlyContinue | Out-Null
}

Ensure-Module -Name Az.Accounts
Ensure-Module -Name Az.Resources
Ensure-Module -Name Az.Websites
Ensure-Module -Name Az.Storage
Ensure-Module -Name Az.Functions

# Load .env if present and map to parameters (values in params override .env)
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
    # Strip surrounding quotes if present
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

# Map .env keys to params
Set-FromEnvIfEmpty ResourceGroup RG
Set-FromEnvIfEmpty Location LOC
Set-FromEnvIfEmpty Plan PLAN
Set-FromEnvIfEmpty WebAppName WEBAPP_NAME
Set-FromEnvIfEmpty FuncAppName FUNCAPP_NAME
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
if ($envVals.ContainsKey('DEPLOY_FUNCAPP')) { $DeployFuncApp = [System.Convert]::ToBoolean($envVals['DEPLOY_FUNCAPP']) }
if ($envVals.ContainsKey('ALWAYS_ON')) { $AlwaysOn = [System.Convert]::ToBoolean($envVals['ALWAYS_ON']) }

# Validate required
$required = @('ResourceGroup','Location','Plan','WebAppName','FuncAppName','StorageAccount','QB_CLIENT_ID','QB_CLIENT_SECRET','ENCRYPTION_SECRET','SQL_SERVER','SQL_DB','SQL_USER','SQL_PASSWORD','TEST_FUNCTION_KEY')
$missing = @()
foreach ($r in $required) { if ([string]::IsNullOrWhiteSpace((Get-Variable -Name $r -ValueOnly))) { $missing += $r } }
if ($missing.Count -gt 0) {
  Write-Error "Missing required parameters: $($missing -join ', '). Provide via -Param or in $EnvPath."
  exit 1
}

try {
  # RG
  Write-Host "Ensuring resource group $ResourceGroup ($Location)" -ForegroundColor Cyan
  New-AzResourceGroup -Name $ResourceGroup -Location $Location -Force -ErrorAction SilentlyContinue | Out-Null

  # Ensure required resource providers are registered
  Write-Host "Registering resource providers (Microsoft.Web, Storage, Insights) if needed" -ForegroundColor Cyan
  $providers = @('Microsoft.Web','Microsoft.Storage','Microsoft.Insights')
  foreach ($p in $providers) {
    try { Register-AzResourceProvider -ProviderNamespace $p -ErrorAction SilentlyContinue | Out-Null } catch {}
  }

  # App Service Plan (Linux)
  $webPlanExists = $true
  if (-not (Get-AzAppServicePlan -Name $Plan -ResourceGroupName $ResourceGroup -ErrorAction SilentlyContinue)) {
    Write-Host "Creating App Service plan $Plan (Linux, Basic B1)" -ForegroundColor Cyan
    $webPlanExists = $false
    try {
      New-AzAppServicePlan -Name $Plan -ResourceGroupName $ResourceGroup -Location $Location -Tier "Basic" -WorkerSize "Small" -Linux | Out-Null
      $webPlanExists = $true
    }
    catch {
      Write-Warning "Could not create App Service plan (Unauthorized or policy). Ensure Contributor role and provider registration, or pre-create the plan in the portal. Error: $($_.Exception.Message)"
    }
  }

  # Web App
  $webExists = $true
  if (-not (Get-AzWebApp -Name $WebAppName -ResourceGroupName $ResourceGroup -ErrorAction SilentlyContinue)) {
    Write-Host "Creating Web App $WebAppName" -ForegroundColor Cyan
    $webExists = $false
    try {
      New-AzWebApp -Name $WebAppName -ResourceGroupName $ResourceGroup -Location $Location -AppServicePlan $Plan | Out-Null
      $webExists = $true
    }
    catch {
      Write-Warning "Could not create Web App (Unauthorized or policy). Ensure Contributor role and provider registration, or pre-create the site in the portal. Error: $($_.Exception.Message)"
    }
  }

  if ($webExists) {
    # Set runtime and startup (handles older Az.Websites without -LinuxFxVersion)
    Write-Host "Configuring Web App runtime and startup" -ForegroundColor Cyan
    $canLinuxFx = $false
    $cmd = Get-Command Set-AzWebApp -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Parameters.ContainsKey('LinuxFxVersion')) { $canLinuxFx = $true }

    if ($canLinuxFx) {
      Set-AzWebApp -Name $WebAppName -ResourceGroupName $ResourceGroup -LinuxFxVersion "PYTHON|$PythonVersion" -AppCommandLine 'gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app' | Out-Null
    } else {
      # Fallback: ARM update of sites/config/web
      $props = @{ linuxFxVersion = "PYTHON|$PythonVersion"; appCommandLine = 'gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app' }
      Set-AzResource -ResourceGroupName $ResourceGroup -ResourceType "Microsoft.Web/sites/config" -ResourceName "$WebAppName/web" -ApiVersion "2022-03-01" -PropertyObject $props -Force | Out-Null
    }
  } else {
    Write-Warning "Skipping Web App config because creation failed or site not found."
  }

  $AppBase = "https://$WebAppName.azurewebsites.net"
  $WebAppSettings = @{
    "QB_CLIENT_ID"                   = $QB_CLIENT_ID
    "QB_CLIENT_SECRET"               = $QB_CLIENT_SECRET
    "QB_REDIRECT_URI"                = "$AppBase/api/qb/oauth/callback"
    "ENCRYPTION_SECRET"              = $ENCRYPTION_SECRET
    "SQL_SERVER"                     = $SQL_SERVER
    "SQL_DB"                         = $SQL_DB
    "SQL_USER"                       = $SQL_USER
    "SQL_PASSWORD"                   = $SQL_PASSWORD
    "APP_BASE_URL"                   = $AppBase
    "TEST_FUNCTION_KEY"              = $TEST_FUNCTION_KEY
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "1"
  }
  Write-Host "Setting Web App app settings" -ForegroundColor Cyan
  if ($webExists) {
    Set-AzWebApp -Name $WebAppName -ResourceGroupName $ResourceGroup -AppSettings $WebAppSettings | Out-Null
  } else {
    Write-Warning "Skipping Web App app settings because site not found."
  }

  # Always On (optional)
  if ($webExists -and $AlwaysOn) {
    try { Set-AzWebApp -Name $WebAppName -ResourceGroupName $ResourceGroup -AlwaysOn $true | Out-Null } catch {}
  }

  # Storage for Function App
  if (-not (Get-AzStorageAccount -Name $StorageAccount -ResourceGroupName $ResourceGroup -ErrorAction SilentlyContinue)) {
    Write-Host "Creating Storage Account $StorageAccount" -ForegroundColor Cyan
    New-AzStorageAccount -Name $StorageAccount -ResourceGroupName $ResourceGroup -Location $Location -SkuName "Standard_LRS" -Kind "StorageV2" | Out-Null
  }

  # Function App (Linux Consumption)
  $funcExists = $true
  if (-not (Get-AzFunctionApp -Name $FuncAppName -ResourceGroupName $ResourceGroup -ErrorAction SilentlyContinue)) {
    Write-Host "Creating Function App $FuncAppName" -ForegroundColor Cyan
    $funcExists = $false
    try {
      $faCmd = Get-Command New-AzFunctionApp -ErrorAction SilentlyContinue
      if ($faCmd -and $faCmd.Parameters.ContainsKey('OperatingSystem')) {
        New-AzFunctionApp -Name $FuncAppName -ResourceGroupName $ResourceGroup -Location $Location `
          -StorageAccountName $StorageAccount `
          -Runtime "python" -RuntimeVersion $PythonVersion -FunctionsVersion 4 `
          -OperatingSystem Linux -ConsumptionPlanLocation $Location | Out-Null
      } else {
        # Older module: omit OperatingSystem (may default to Windows; acceptable for Python Functions)
        New-AzFunctionApp -Name $FuncAppName -ResourceGroupName $ResourceGroup -Location $Location `
          -StorageAccountName $StorageAccount `
          -Runtime "python" -RuntimeVersion $PythonVersion -FunctionsVersion 4 `
          -ConsumptionPlanLocation $Location | Out-Null
      }
      $funcExists = $true
    } catch {
      Write-Warning "Could not create Function App (Unauthorized or policy). Ensure Contributor role and provider registration, or pre-create the Function App in the portal. Error: $($_.Exception.Message)"
    }
  }

  $FuncAppSettings = @{
    "ENCRYPTION_SECRET"              = $ENCRYPTION_SECRET
    "SQL_SERVER"                     = $SQL_SERVER
    "SQL_DB"                         = $SQL_DB
    "SQL_USER"                       = $SQL_USER
    "SQL_PASSWORD"                   = $SQL_PASSWORD
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "1"
  }
  if ($funcExists) {
    Write-Host "Setting Function App app settings" -ForegroundColor Cyan
    if (Get-Command Set-AzFunctionAppSetting -ErrorAction SilentlyContinue) {
      Set-AzFunctionAppSetting -Name $FuncAppName -ResourceGroupName $ResourceGroup -AppSettings $FuncAppSettings | Out-Null
    } else {
      Update-AzFunctionApp -Name $FuncAppName -ResourceGroupName $ResourceGroup -AppSettings $FuncAppSettings | Out-Null
    }
  } else {
    Write-Warning "Skipping Function App settings because app not found."
  }

  # Deploy Web App (zip deploy)
  if ($DeployWebApp -and $webExists) {
    Write-Host "Zipping and deploying Web App" -ForegroundColor Green
    $webZip = Join-Path (Get-Location) "webapp.zip"
    if (Test-Path $webZip) { Remove-Item $webZip -Force }
    Compress-Archive -Path * -DestinationPath $webZip -Force
    Publish-AzWebApp -Name $WebAppName -ResourceGroupName $ResourceGroup -ArchivePath $webZip | Out-Null
  }

  # Deploy Function App (zip deploy)
  if ($DeployFuncApp -and $funcExists) {
    Write-Host "Zipping and deploying Function App" -ForegroundColor Green
    $funcZip = Join-Path (Get-Location) "functionapp.zip"
    if (Test-Path $funcZip) { Remove-Item $funcZip -Force }
    Compress-Archive -Path * -DestinationPath $funcZip -Force
    Publish-AzWebApp -Name $FuncAppName -ResourceGroupName $ResourceGroup -ArchivePath $funcZip | Out-Null
  }

  Write-Host "Done. Web: $AppBase" -ForegroundColor Green
}
catch {
  Write-Error $_
  exit 1
}
