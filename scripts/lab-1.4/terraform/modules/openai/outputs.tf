output "openai_endpoint" {
  description = "The endpoint URL for Azure OpenAI service"
  value       = azurerm_cognitive_account.openai.endpoint
}

output "openai_name" {
  description = "The name of the Azure OpenAI service"
  value       = azurerm_cognitive_account.openai.name
}

output "openai_id" {
  description = "The resource ID of the Azure OpenAI service"
  value       = azurerm_cognitive_account.openai.id
}

output "gpt4o_deployment_name" {
  description = "The name of the GPT-4o deployment"
  value       = azurerm_cognitive_deployment.gpt4o.name
}

output "embedding_deployment_name" {
  description = "The name of the text-embedding-ada-002 deployment"
  value       = azurerm_cognitive_deployment.embedding.name
}

output "openai_primary_key" {
  description = "The primary access key for Azure OpenAI service"
  value       = azurerm_cognitive_account.openai.primary_access_key
  sensitive   = true
}
