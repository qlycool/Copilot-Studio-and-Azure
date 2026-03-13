<#
.SYNOPSIS
    Deploy the SharePoint Connector as an Azure Function App.

.DESCRIPTION
    1. Creates infrastructure via Bicep (Function App, Storage, App Insights, RBAC)
    2. Deploys the function code via Azure Functions Core Tools

.PARAMETER ResourceGroup
    Target resource group name.

.PARAMETER Location
    Azure region (default: swedencentral).

.PARAMETER BaseName
    Base name for all resources (default: sp-indexer).

.EXAMPLE
    .\deploy.ps1 -ResourceGroup sharepoint-testing
#>

param(
    [Parameter(Mandatory)]
    [string]$ResourceGroup,

    [string]$Location = "swedencentral",
    [string]$BaseName = "sp-indexer"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Write-Host "`n=== SharePoint Connector — Deployment ===" -ForegroundColor Cyan

# ------------------------------------------------------------------
# Step 1: Deploy infrastructure via Bicep
# ------------------------------------------------------------------
Write-Host "`n[1/4] Deploying infrastructure (Bicep)..." -ForegroundColor Yellow

$bicepFile = Join-Path $scriptDir "main.bicep"
$paramFile = Join-Path $scriptDir "main.bicepparam"

az deployment group create `
    --resource-group $ResourceGroup `
    --template-file $bicepFile `
    --parameters $paramFile `
    --parameters baseName=$BaseName location=$Location `
    --output table

if ($LASTEXITCODE -ne 0) {
    Write-Error "Bicep deployment failed"
    exit 1
}

# Get outputs
$outputs = az deployment group show `
    --resource-group $ResourceGroup `
    --name "main" `
    --query "properties.outputs" `
    --output json | ConvertFrom-Json

$functionAppName = $outputs.functionAppName.value
$principalId = $outputs.functionAppPrincipalId.value

Write-Host "  Function App: $functionAppName" -ForegroundColor Green
Write-Host "  Managed Identity: $principalId" -ForegroundColor Green

# ------------------------------------------------------------------
# Step 2: Ensure requirements.txt is up to date
# ------------------------------------------------------------------
Write-Host "`n[2/4] Updating requirements.txt..." -ForegroundColor Yellow
Push-Location $projectRoot
uv export --no-hashes --extra func --no-dev 2>$null | Set-Content -Path requirements.txt -Encoding UTF8
Pop-Location
Write-Host "  requirements.txt updated" -ForegroundColor Green

# ------------------------------------------------------------------
# Step 3: Deploy function code
# ------------------------------------------------------------------
Write-Host "`n[3/4] Deploying function code..." -ForegroundColor Yellow
Push-Location $projectRoot

# Azure Functions Core Tools deployment
func azure functionapp publish $functionAppName --python

if ($LASTEXITCODE -ne 0) {
    Write-Error "Function deployment failed"
    Pop-Location
    exit 1
}
Pop-Location
Write-Host "  Code deployed successfully" -ForegroundColor Green

# ------------------------------------------------------------------
# Step 4: Post-deployment info
# ------------------------------------------------------------------
Write-Host "`n[4/4] Post-deployment checklist" -ForegroundColor Yellow
Write-Host @"

  Deployment complete!

  Function App:       $functionAppName
  Managed Identity:   $principalId

  IMPORTANT — Manual steps required:
  ═══════════════════════════════════════════════════════════════
  1. Graph API permissions for the managed identity:
     The Function App's managed identity ($principalId) needs
     Graph API access to your SharePoint site.

     Option A: Use an app registration with Sites.Read.All +
               Files.Read.All, and set CLIENT_ID / CLIENT_SECRET
               in the Function App settings.

     Option B: Grant the managed identity direct Graph permissions
               via PowerShell (requires admin consent):

       Connect-MgGraph -Scopes "Application.ReadWrite.All"
       `$msi = Get-MgServicePrincipal -Filter "displayName eq '$functionAppName'"
       `$graph = Get-MgServicePrincipal -Filter "appId eq '00000003-0000-0000-c000-000000000000'"
       `$role = `$graph.AppRoles | Where-Object { `$_.Value -eq 'Sites.Read.All' }
       New-MgServicePrincipalAppRoleAssignment -ServicePrincipalId `$msi.Id -PrincipalId `$msi.Id -ResourceId `$graph.Id -AppRoleId `$role.Id

  2. Verify the timer is running:
     az functionapp show --name $functionAppName --resource-group $ResourceGroup --query "state"

  3. Check logs:
     func azure functionapp logstream $functionAppName
  ═══════════════════════════════════════════════════════════════
"@ -ForegroundColor White
