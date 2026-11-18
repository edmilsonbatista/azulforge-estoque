variable "subscription_id" {
  description = "ID da assinatura Azure que receberá os recursos."
  type        = string
}

variable "location" {
  description = "Região do grupo de recursos e do Cosmos DB."
  type        = string
  default     = "brazilsouth"
}

variable "app_location" {
  description = "Região do Azure Container Apps e do Container Registry."
  type        = string
  default     = "brazilsouth"
}

variable "name_prefix" {
  description = "Prefixo curto usado nos nomes dos recursos."
  type        = string
  default     = "azulforge-estoque"

  validation {
    condition     = length(var.name_prefix) <= 21 && can(regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", var.name_prefix))
    error_message = "Use até 21 caracteres minúsculos, números ou hífens, começando e terminando com letra ou número."
  }
}
