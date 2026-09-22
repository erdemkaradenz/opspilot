# ==========================================
# 1. PROVIDER VE RESOURCE GROUP
# ==========================================
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "rg-terraform-state"
    storage_account_name = "stterraformopspilot123"
    container_name       = "tfstate"
    key                  = "opspilot.terraform.tfstate"
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

resource "random_string" "suffix" {
  length  = 5
  special = false
  upper   = false
}

resource "azurerm_resource_group" "rg" {
  name     = "rg-opspilot-dev"
  location = "Italy North"
}

# ==========================================
# 2. AĞ MİMARİSİ (VNet & Subnetler)
# ==========================================
resource "azurerm_virtual_network" "vnet" {
  name                = "vnet-opspilot"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = ["10.0.0.0/16"]
}

# PostgreSQL için ayrılmış Subnet
resource "azurerm_subnet" "snet_db" {
  name                 = "snet-postgres"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.1.0/24"]

  delegation {
    name = "fs-delegation"
    service_delegation {
      name    = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

# Container App Environment için ayrılmış Subnet (VNet Entegrasyonu için şart)
resource "azurerm_subnet" "snet_app" {
  name                 = "snet-containerapps"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.2.0/23"] # Container Apps minimum /23 prefix ister

  delegation {
    name = "aca-delegation"
    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

# Kapalı ağdaki veritabanını çözmek için Private DNS
resource "azurerm_private_dns_zone" "dns_db" {
  name                = "opspilot.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "dns_vnet_link" {
  name                  = "dns-link-opspilot"
  private_dns_zone_name = azurerm_private_dns_zone.dns_db.name
  virtual_network_id    = azurerm_virtual_network.vnet.id
  resource_group_name   = azurerm_resource_group.rg.name
}

# ==========================================
# DEĞİŞKENLER (Variables)
# ==========================================
variable "db_password" {
  type      = string
  sensitive = true
}

variable "gemini_api_key" {
  type      = string
  sensitive = true
}

variable "redis_url" {
  type    = string
  default = "redis://localhost:6379"
}

variable "kafka_broker_url" {
  type    = string
  default = "localhost:9092"
}

variable "n8n_webhook_url" {
  type    = string
  default = "https://dummy-n8n.local"
}

variable "otlp_endpoint" {
  type    = string
  default = "http://localhost:4317"
}

# ==========================================
# 3. VERİTABANI (PostgreSQL Flexible Server)
# ==========================================
resource "azurerm_postgresql_flexible_server" "postgres" {
  name                   = "psql-opspilot-${random_string.suffix.result}"
  resource_group_name    = azurerm_resource_group.rg.name
  location               = azurerm_resource_group.rg.location
  version                = "14"
  # Zaten VNet içindeyiz, interneti KESİNLİKLE KAPAT (Zero Trust Kuralı)
  public_network_access_enabled = false
  delegated_subnet_id    = azurerm_subnet.snet_db.id
  private_dns_zone_id    = azurerm_private_dns_zone.dns_db.id
  administrator_login    = "opsadmin"
  administrator_password = var.db_password
  zone                   = "1"
  storage_mb             = 32768
  sku_name               = "B_Standard_B1ms"

  depends_on = [azurerm_private_dns_zone_virtual_network_link.dns_vnet_link]
  lifecycle {
    ignore_changes = [zone]
  }
}

# ==========================================
# 3.1. VERİTABANI EKLENTİSİ (PGVECTOR)
# Yapay zeka ve vektör aramaları için Azure'da izin vermeliyiz
# ==========================================
resource "azurerm_postgresql_flexible_server_configuration" "pg_ext" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.postgres.id
  value     = "vector"
}

# ==========================================
# 4. CONTAINER REGISTRY & GÜVENLİK (IAM)
# ==========================================
resource "azurerm_container_registry" "acr" {
  name                = "acropspilot${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = false
}

# Tavuk-Yumurta sorununu çözen User-Assigned Identity
resource "azurerm_user_assigned_identity" "aca_identity" {
  name                = "uai-opspilot-api"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.aca_identity.principal_id
}

# ==========================================
# 5. SUNUCUSUZ ORTAM (Azure Container Apps)
# ==========================================
resource "azurerm_log_analytics_workspace" "law" {
  name                = "law-opspilot"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_app_environment" "env" {
  name                           = "cae-opspilot"
  location                       = azurerm_resource_group.rg.location
  resource_group_name            = azurerm_resource_group.rg.name
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.law.id
  infrastructure_subnet_id       = azurerm_subnet.snet_app.id # VNet köprüsü kuruldu!
}

resource "azurerm_container_app" "api" {
  name                         = "ca-opspilot-api"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.aca_identity.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.aca_identity.id
  }

  secret {
    name  = "database-url"
    value = "postgresql+asyncpg://opsadmin:${var.db_password}@${azurerm_postgresql_flexible_server.postgres.fqdn}:5432/postgres"
  }
  
  secret {
    name  = "gemini-api-key"
    value = var.gemini_api_key
  }

  template {
    container {
      name   = "api"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.5
      memory = "1Gi"
      
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "GEMINI_API_KEY"
        secret_name = "gemini-api-key"
      }
      env {
        name  = "REDIS_URL"
        value = var.redis_url
      }
      env {
        name  = "KAFKA_BROKER_URL"
        value = var.kafka_broker_url
      }
      env {
        name  = "N8N_WEBHOOK_URL"
        value = var.n8n_webhook_url
      }
      env {
        name  = "OTLP_ENDPOINT"
        value = var.otlp_endpoint
      }
    }

    min_replicas = 0
    max_replicas = 2
  }

  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}