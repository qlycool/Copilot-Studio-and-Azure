# AI Foundry Outputs
# output "ai_foundry_project_connection_string" {
#   description = "The connection string to the AI Foundry project"
#   value       = module.ai_foundry.project_connection_string
# }

# output "ai_foundry_deployment_name" {
#   description = "The name of the GPT-4o deployment in AI Foundry"
#   value       = module.ai_foundry.deployment_name
# }

# Azure OpenAI Outputs
output "openai_endpoint" {
  description = "The endpoint URL for Azure OpenAI service"
  value       = module.openai.openai_endpoint
}

output "openai_name" {
  description = "The name of the Azure OpenAI service"
  value       = module.openai.openai_name
}

output "openai_gpt4o_deployment_name" {
  description = "The name of the GPT-4o deployment"
  value       = module.openai.gpt4o_deployment_name
}

output "openai_embedding_deployment_name" {
  description = "The name of the text-embedding-ada-002 deployment"
  value       = module.openai.embedding_deployment_name
}

# AI Search Outputs
output "ai_search_service_name" {
  description = "The name of the Azure AI Search service"
  value       = module.search.search_service_name
}

output "ai_search_endpoint" {
  description = "The endpoint URL for Azure AI Search service"
  value       = module.search.search_endpoint
}

output "ai_search_index_name" {
  description = "The default search index name"
  value       = module.search.search_index_name
}

# Resource Group Output
output "resource_group_name" {
  description = "The name of the resource group"
  value       = azurerm_resource_group.rg.name
}

output "resource_group_location" {
  description = "The location of the resource group"
  value       = azurerm_resource_group.rg.location
}
