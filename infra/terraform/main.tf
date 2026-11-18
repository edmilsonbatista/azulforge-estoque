locals {
  environments = toset(["dev", "hml", "prod"])
}

resource "random_string" "suffix" {
  length  = 6
  lower   = true
  upper   = false
  numeric = true
  special = false
}

resource "azurerm_resource_group" "stock" {
  name     = "rg-${var.name_prefix}-${random_string.suffix.result}"
  location = var.location
}

resource "azurerm_container_registry" "stock" {
  name                = replace("${var.name_prefix}${random_string.suffix.result}", "-", "")
  resource_group_name = azurerm_resource_group.stock.name
  location            = var.app_location
  sku                 = "Basic"
  admin_enabled       = false
}

resource "azurerm_container_app_environment" "stock" {
  name                = "cae-${var.name_prefix}-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.stock.name
  location            = var.app_location
}

resource "azurerm_user_assigned_identity" "environment" {
  for_each = local.environments

  name                = "id-${var.name_prefix}-${each.key}-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.stock.name
  location            = var.app_location
}

resource "azurerm_container_app" "environment" {
  for_each = local.environments

  name                         = "${var.name_prefix}-${each.key}-${random_string.suffix.result}"
  resource_group_name          = azurerm_resource_group.stock.name
  container_app_environment_id = azurerm_container_app_environment.stock.id
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.environment[each.key].id]
  }

  registry {
    server   = azurerm_container_registry.stock.login_server
    identity = azurerm_user_assigned_identity.environment[each.key].id
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "azulforge-estoque"
      image  = "mcr.microsoft.com/k8se/quickstart:latest"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "APP_ENV"
        value = each.key
      }

      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.environment[each.key].client_id
      }

      env {
        name  = "STORAGE_BACKEND"
        value = "cosmos"
      }

      env {
        name  = "COSMOS_ENDPOINT"
        value = azurerm_cosmosdb_account.stock.endpoint
      }

      env {
        name  = "COSMOS_DATABASE"
        value = azurerm_cosmosdb_sql_database.stock.name
      }

      env {
        name  = "COSMOS_CONTAINER"
        value = azurerm_cosmosdb_sql_container.environment[each.key].name
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].container[0].image,
    ]
  }
}

resource "azurerm_role_assignment" "registry_pull" {
  for_each = local.environments

  scope                = azurerm_container_registry.stock.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.environment[each.key].principal_id
}

resource "azurerm_cosmosdb_account" "stock" {
  name                = "cosmos-${var.name_prefix}-${random_string.suffix.result}"
  location            = azurerm_resource_group.stock.location
  resource_group_name = azurerm_resource_group.stock.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"
  free_tier_enabled   = true

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.stock.location
    failover_priority = 0
  }

  local_authentication_enabled = false
}

resource "azurerm_cosmosdb_sql_database" "stock" {
  name                = "azulforge-estoque"
  resource_group_name = azurerm_resource_group.stock.name
  account_name        = azurerm_cosmosdb_account.stock.name
  throughput          = 1000
}

resource "azurerm_cosmosdb_sql_container" "environment" {
  for_each = local.environments

  name                = "products-${each.key}"
  resource_group_name = azurerm_resource_group.stock.name
  account_name        = azurerm_cosmosdb_account.stock.name
  database_name       = azurerm_cosmosdb_sql_database.stock.name
  partition_key_paths = ["/id"]
}

resource "azurerm_cosmosdb_sql_role_assignment" "environment" {
  for_each = local.environments

  resource_group_name = azurerm_resource_group.stock.name
  account_name        = azurerm_cosmosdb_account.stock.name
  role_definition_id  = "${azurerm_cosmosdb_account.stock.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id        = azurerm_user_assigned_identity.environment[each.key].principal_id
  scope               = "${azurerm_cosmosdb_account.stock.id}/dbs/${azurerm_cosmosdb_sql_database.stock.name}/colls/${azurerm_cosmosdb_sql_container.environment[each.key].name}"
}
