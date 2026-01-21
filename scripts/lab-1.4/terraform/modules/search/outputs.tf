output "search_service_name" {
  description = "The name of the Azure AI Search service"
  value       = azurerm_search_service.search.name
}

output "search_endpoint" {
  description = "The endpoint URL for Azure AI Search service"
  value       = "https://${azurerm_search_service.search.name}.search.windows.net"
}

output "search_id" {
  description = "The resource ID of the Azure AI Search service"
  value       = azurerm_search_service.search.id
}

output "search_index_name" {
  description = "The default search index name"
  value       = "gptkbindex"
}

