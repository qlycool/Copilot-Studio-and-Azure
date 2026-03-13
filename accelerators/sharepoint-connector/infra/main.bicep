// SharePoint → Azure AI Search Connector — Azure Function App
// Deploys: Function App (Flex Consumption) + Storage + App Insights
//          + System-assigned Managed Identity with RBAC

@description('Base name for all resources (lowercase, no spaces)')
param baseName string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Tenant ID for Entra ID / Graph API')
param tenantId string

@description('SharePoint site URL (e.g. https://company.sharepoint.com/sites/MySite)')
param sharePointSiteUrl string

@description('Azure AI Search endpoint (e.g. https://my-search.search.windows.net)')
param searchEndpoint string

@description('Azure AI Search resource ID (for RBAC scope)')
param searchResourceId string

@description('Search index name')
param searchIndexName string = 'sharepoint-index'

@description('Azure OpenAI / Foundry endpoint (base URL)')
param foundryEndpoint string

@description('Azure OpenAI resource ID (for RBAC scope)')
param foundryResourceId string

@description('Embedding model deployment name')
param foundryEmbeddingDeployment string = 'text-embedding-3-large'

@description('Embedding dimensions')
param foundryEmbeddingDimensions string = '1536'

@description('CRON schedule for the indexer (default: every hour)')
param indexerSchedule string = '0 0 * * * *'

@description('Incremental sync window in minutes (0 = full reindex)')
param incrementalMinutes string = '60'

@description('SharePoint libraries to index (comma-separated, empty = all)')
param sharePointLibraries string = ''

@description('File extensions to index')
param indexedExtensions string = '.pdf,.docx,.docm,.xlsx,.xlsm,.pptx,.pptm,.txt,.md,.csv,.json,.xml,.kml,.html,.htm,.rtf,.eml,.epub,.msg,.odt,.ods,.odp,.zip,.gz'

// Derived names
var functionAppName = '${baseName}-func'
var storageName = replace('${baseName}st', '-', '')
var appInsightsName = '${baseName}-insights'
var logAnalyticsName = '${baseName}-logs'
var deployContainerName = 'app-package'

// Extract resource names from resource IDs
var searchServiceName = last(split(searchResourceId, '/'))
var cognitiveAccountName = last(split(foundryResourceId, '/'))

// Built-in role definition IDs
var searchDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var searchServiceContributorRoleId = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var storageBlobDataOwnerRoleId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var storageAccountContributorRoleId = '17d1049b-9a84-46fb-8f53-869881c3d3ab'
var storageQueueDataContributorRoleId = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'

// Existing resources for RBAC scoping
resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

resource cognitiveAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: cognitiveAccountName
}

// Storage Account (Functions runtime + deployment packages)
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowSharedKeyAccess: false
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource deployContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: deployContainerName
}

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// Flex Consumption Plan
resource flexPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: '${baseName}-plan'
  location: location
  kind: 'functionapp'
  sku: {
    tier: 'FlexConsumption'
    name: 'FC1'
  }
  properties: {
    reserved: true
  }
}

// Function App (Flex Consumption)
resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: flexPlan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storageAccount.properties.primaryEndpoints.blob}${deployContainerName}'
          authentication: {
            type: 'SystemAssignedIdentity'
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: 40
        instanceMemoryMB: 2048
      }
      runtime: {
        name: 'python'
        version: '3.11'
      }
    }
    siteConfig: {
      appSettings: [
        { name: 'AzureWebJobsStorage__accountName', value: storageAccount.name }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }

        // Connector config
        { name: 'TENANT_ID', value: tenantId }
        { name: 'SHAREPOINT_SITE_URL', value: sharePointSiteUrl }
        { name: 'SHAREPOINT_LIBRARIES', value: sharePointLibraries }
        { name: 'SEARCH_ENDPOINT', value: searchEndpoint }
        { name: 'SEARCH_INDEX_NAME', value: searchIndexName }
        { name: 'FOUNDRY_ENDPOINT', value: foundryEndpoint }
        { name: 'FOUNDRY_EMBEDDING_DEPLOYMENT', value: foundryEmbeddingDeployment }
        { name: 'FOUNDRY_EMBEDDING_DIMENSIONS', value: foundryEmbeddingDimensions }
        { name: 'INDEXED_EXTENSIONS', value: indexedExtensions }
        { name: 'INCREMENTAL_MINUTES', value: incrementalMinutes }
        { name: 'INDEXER_SCHEDULE', value: indexerSchedule }
        { name: 'MAX_FILE_SIZE_MB', value: '100' }
        { name: 'MAX_CONCURRENCY', value: '4' }
        { name: 'CHUNK_SIZE', value: '2000' }
        { name: 'CHUNK_OVERLAP', value: '200' }
      ]
    }
  }
}

// RBAC: Search Index Data Contributor → Function App MI
resource searchDataContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, searchDataContributorRoleId, functionApp.id)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchDataContributorRoleId)
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// RBAC: Search Service Contributor → Function App MI
resource searchServiceContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, searchServiceContributorRoleId, functionApp.id)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributorRoleId)
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// RBAC: Cognitive Services OpenAI User → Function App MI
resource cognitiveServicesAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cognitiveAccount.id, cognitiveServicesOpenAIUserRoleId, functionApp.id)
  scope: cognitiveAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// RBAC: Storage Blob Data Owner → Function App MI (for deployment + triggers)
resource storageBlobDataOwnerAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, storageBlobDataOwnerRoleId, functionApp.id)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerRoleId)
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// RBAC: Storage Account Contributor → Function App MI (for queue/table triggers)
resource storageAccountContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, storageAccountContributorRoleId, functionApp.id)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageAccountContributorRoleId)
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// RBAC: Storage Queue Data Contributor → Function App MI (for Functions runtime)
resource storageQueueDataContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, storageQueueDataContributorRoleId, functionApp.id)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageQueueDataContributorRoleId)
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output functionAppName string = functionApp.name
output functionAppPrincipalId string = functionApp.identity.principalId
