"""Azure Key Vault integration for loading secrets."""

from dbrx_api.keyvault.client import load_secrets_from_keyvault

__all__ = ["load_secrets_from_keyvault"]
