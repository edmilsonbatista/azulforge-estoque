output "resource_group_name" {
  value = azurerm_resource_group.stock.name
}

output "cosmos_account_name" {
  value = azurerm_cosmosdb_account.stock.name
}

output "container_registry_name" {
  value = azurerm_container_registry.stock.name
}

output "container_app_names" {
  value = {
    for environment, app in azurerm_container_app.environment : environment => app.name
  }
}

output "urls" {
  value = {
    for environment, app in azurerm_container_app.environment : environment => "https://${app.ingress[0].fqdn}"
  }
}
