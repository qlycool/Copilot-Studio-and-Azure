using './main.bicep'

param baseName = 'sp-indexer'
param location = 'swedencentral'

// --- Fill in your values ---
param tenantId = '60cb3c79-32ec-4912-b674-c1b68653aa56'
param sharePointSiteUrl = 'https://mngenvmcap278933.sharepoint.com/sites/ExamsHub/'

// Azure AI Search
param searchEndpoint = 'https://sharepoint-search007.search.windows.net'
param searchResourceId = '/subscriptions/fbfbfbe5-9ee2-43ed-b514-f3266c2193ab/resourceGroups/sharepoint-testing/providers/Microsoft.Search/searchServices/sharepoint-search007'
param searchIndexName = 'sharepoint-index'

// Azure OpenAI / Foundry
param foundryEndpoint = 'https://openai-test-sweden-007.services.ai.azure.com'
param foundryResourceId = '/subscriptions/fbfbfbe5-9ee2-43ed-b514-f3266c2193ab/resourceGroups/sharepoint-testing/providers/Microsoft.CognitiveServices/accounts/openai-test-sweden-007'
param foundryEmbeddingDeployment = 'text-embedding-3-large'
param foundryEmbeddingDimensions = '1536'

// Schedule: every hour, incremental (last 65 min to avoid gaps)
param indexerSchedule = '0 0 * * * *'
param incrementalMinutes = '65'
