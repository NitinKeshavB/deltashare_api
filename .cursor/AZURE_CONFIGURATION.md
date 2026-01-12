# Azure Web App Configuration Guide

This guide explains how to configure the DeltaShare API using Azure Web App Application Settings (environment variables).

## Overview

The application uses **pydantic-settings** to read configuration from environment variables. There is no dependency on Azure Key Vault - all configuration is provided through Azure Web App Application Settings.

## Configuration Sources by Environment

| Environment | Configuration Source |
|-------------|---------------------|
| **Local Development** | `.env` file in project root |
| **Azure Web App** | Application Settings (Azure Portal) |

## Required Application Settings

Configure these in **Azure Portal** > **Your Web App** > **Configuration** > **Application settings**:

### Core Settings (Required)

| Setting Name | Description | Example Value |
|-------------|-------------|---------------|
| `client_id` | Azure Service Principal Client ID for Databricks authentication | `e04058ec-8264-4e50-9a8b-...` |
| `client_secret` | Azure Service Principal Client Secret for Databricks authentication | `abc~xyz123...` |
| `account_id` | Databricks Account ID for authentication | `12345678-1234-1234-1234-...` |

### Optional Settings (Logging)

| Setting Name | Description | Default Value |
|-------------|-------------|---------------|
| `enable_blob_logging` | Enable Azure Blob Storage logging | `false` |
| `azure_storage_account_url` | Azure Storage Account URL for logs | None |
| `azure_storage_logs_container` | Blob container name for logs | `deltashare-logs` |
| `enable_postgresql_logging` | Enable PostgreSQL database logging | `false` |
| `postgresql_connection_string` | PostgreSQL connection string | None |
| `postgresql_log_table` | PostgreSQL table name for logs | `application_logs` |
| `postgresql_min_log_level` | Minimum log level for PostgreSQL | `WARNING` |

### Optional Settings (Other)

| Setting Name | Description | Default Value |
|-------------|-------------|---------------|
| `dltshr_workspace_url` | Default Databricks workspace URL (deprecated - use `X-Workspace-URL` header instead) | None |

## How to Configure Azure Web App

### Step 1: Navigate to Application Settings

1. Go to **Azure Portal** (https://portal.azure.com)
2. Navigate to your **Web App** resource
3. Click **Configuration** in the left menu
4. Click **Application settings** tab

### Step 2: Add Required Settings

For each required setting:

1. Click **+ New application setting**
2. Enter the **Name** (e.g., `client_id`)
3. Enter the **Value** (your actual secret/configuration value)
4. Click **OK**

### Step 3: Save and Restart

1. Click **Save** at the top of the Configuration page
2. Click **Continue** when prompted
3. The Web App will automatically restart with the new settings

## Local Development Setup

### Create `.env` File

Create a `.env` file in the project root (this file should **NOT** be committed to git):

```bash
# .env (local development only)

# Databricks Authentication (Required)
client_id=your-service-principal-client-id
client_secret=your-service-principal-secret
account_id=your-databricks-account-id

# Optional: Logging
enable_blob_logging=false
enable_postgresql_logging=false

# Optional: Default workspace URL (use X-Workspace-URL header instead)
dltshr_workspace_url=https://adb-1234567890123456.12.azuredatabricks.net
```

### Verify Configuration

Run the application locally:

```bash
make run-dev
```

The application will:
1. Look for `.env` file
2. Load environment variables from it
3. Log: `"Loading configuration from environment variables"`

## Security Best Practices

### Azure Web App

✅ **DO:**
- Use Application Settings for all secrets
- Enable **Managed Identity** for accessing other Azure resources
- Use **Azure AD authentication** (Easy Auth) for user authentication
- Rotate secrets regularly in Azure Portal

❌ **DON'T:**
- Commit secrets to git repository
- Share production secrets via email/chat
- Use the same secrets across dev/uat/prod environments

### Local Development

✅ **DO:**
- Use separate service principals for local development
- Add `.env` to `.gitignore`
- Use dev/test Databricks workspaces

❌ **DON'T:**
- Commit `.env` file to git
- Use production credentials locally
- Share `.env` files with other developers (they should create their own)

## Troubleshooting

### Application fails to start with "ValidationError"

**Cause:** Required environment variables are missing.

**Solution:**
1. Check that `client_id`, `client_secret`, and `account_id` are set in Azure Portal
2. Verify the setting names match exactly (case-insensitive, but spelling must be correct)
3. Check the Web App logs for specific missing variables

### Settings not updating after changing Application Settings

**Cause:** Web App needs to restart to pick up new environment variables.

**Solution:**
1. Go to Azure Portal > Your Web App > **Overview**
2. Click **Restart**
3. Wait for the application to restart (30-60 seconds)

### Local development can't find settings

**Cause:** `.env` file is missing or in wrong location.

**Solution:**
1. Create `.env` file in project root (same directory as `pyproject.toml`)
2. Verify the file is named exactly `.env` (not `.env.txt`)
3. Check file permissions (should be readable)

## Migration from Key Vault

If you previously used Azure Key Vault, follow these steps:

### 1. Export Secrets from Key Vault

```bash
# List all secrets
az keyvault secret list --vault-name <your-vault-name> --query "[].name" -o tsv

# Get each secret value
az keyvault secret show --vault-name <your-vault-name> --name <secret-name> --query "value" -o tsv
```

### 2. Add to Application Settings

For each secret:
1. Convert name from hyphen-case to lowercase with underscores
   - `client-id` → `client_id`
   - `client-secret` → `client_secret`
2. Add as Application Setting in Azure Portal

### 3. Remove Key Vault Configuration

1. Delete `azure_keyvault_url` from Application Settings (if present)
2. Remove Key Vault access policies if no longer needed
3. Update `.env` file for local development

## Environment Variable Naming Convention

The application uses **lowercase_with_underscores** for environment variables:

| Setting Class Property | Environment Variable |
|-----------------------|---------------------|
| `client_id` | `client_id` |
| `client_secret` | `client_secret` |
| `account_id` | `account_id` |
| `enable_blob_logging` | `enable_blob_logging` |
| `postgresql_connection_string` | `postgresql_connection_string` |

**Note:** Pydantic-settings is configured with `case_sensitive=False`, so variable names are **case-insensitive**. However, lowercase is the recommended standard.

## Reference

- [Azure Web App Application Settings](https://docs.microsoft.com/azure/app-service/configure-common)
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [DeltaShare API Settings](./src/dbrx_api/settings.py)
