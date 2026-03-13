"""
Configuration loader for the SharePoint → Azure AI Search connector.
Reads from environment variables (supports .env file via python-dotenv).

Authentication:
  - Foundry (embeddings): always uses DefaultAzureCredential
  - Azure AI Search: always uses DefaultAzureCredential
  - Graph API (SharePoint): DefaultAzureCredential by default, client secret as optional fallback

For Graph API (SharePoint), DefaultAzureCredential is used directly.
The app registration still needs Sites.Read.All + Files.Read.All application
permissions granted, and the managed identity (or local principal) must be
assigned as a federated credential on that app registration.
"""

import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


def _get_required(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value


def _get_optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass(frozen=True)
class EntraConfig:
    """Entra ID config. client_id/client_secret are only needed when NOT using managed identity."""
    tenant_id: str
    client_id: str = ""
    client_secret: str = ""

    @property
    def use_managed_identity(self) -> bool:
        """Use managed identity when no client secret is provided."""
        return not self.client_secret


@dataclass(frozen=True)
class SharePointConfig:
    site_url: str
    libraries: list[str] = field(default_factory=list)

    @property
    def hostname(self) -> str:
        """Extract hostname from site URL, e.g. 'yourcompany.sharepoint.com'"""
        return urlparse(self.site_url).hostname or ""

    @property
    def site_path(self) -> str:
        """Extract site path, e.g. '/sites/YourSite'"""
        return urlparse(self.site_url).path.rstrip("/")


@dataclass(frozen=True)
class SearchConfig:
    endpoint: str
    index_name: str


@dataclass(frozen=True)
class OpenAIConfig:
    endpoint: str
    embedding_deployment: str
    embedding_dimensions: int = 1536


@dataclass(frozen=True)
class IndexerConfig:
    indexed_extensions: list[str] = field(default_factory=lambda: [
        ".pdf", ".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm",
        ".txt", ".md", ".csv", ".json", ".xml", ".kml",
        ".html", ".htm",
        ".rtf", ".eml", ".epub", ".msg",
        ".odt", ".ods", ".odp",
        ".zip", ".gz",
    ])
    chunk_size: int = 2000
    chunk_overlap: int = 200
    max_concurrency: int = 4
    max_file_size_mb: int = 100
    incremental_minutes: int = 0


@dataclass(frozen=True)
class AppConfig:
    entra: EntraConfig
    sharepoint: SharePointConfig
    search: SearchConfig
    openai: OpenAIConfig
    indexer: IndexerConfig


def load_config() -> AppConfig:
    """Load and validate all configuration from environment variables."""
    libraries_raw = _get_optional("SHAREPOINT_LIBRARIES", "")
    libraries = [lib.strip() for lib in libraries_raw.split(",") if lib.strip()] if libraries_raw else []

    extensions_raw = _get_optional(
        "INDEXED_EXTENSIONS",
        ".pdf,.docx,.docm,.xlsx,.xlsm,.pptx,.pptm,.txt,.md,.csv,.json,.xml,.kml,"
        ".html,.htm,.rtf,.eml,.epub,.msg,.odt,.ods,.odp,.zip,.gz"
    )
    extensions = [ext.strip() for ext in extensions_raw.split(",") if ext.strip()]

    return AppConfig(
        entra=EntraConfig(
            tenant_id=_get_required("TENANT_ID"),
            client_id=_get_optional("CLIENT_ID"),
            client_secret=_get_optional("CLIENT_SECRET"),
        ),
        sharepoint=SharePointConfig(
            site_url=_get_required("SHAREPOINT_SITE_URL"),
            libraries=libraries,
        ),
        search=SearchConfig(
            endpoint=_get_required("SEARCH_ENDPOINT"),
            index_name=_get_optional("SEARCH_INDEX_NAME", "sharepoint-index"),
        ),
        openai=OpenAIConfig(
            endpoint=_get_required("FOUNDRY_ENDPOINT"),
            embedding_deployment=_get_optional("FOUNDRY_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
            embedding_dimensions=int(_get_optional("FOUNDRY_EMBEDDING_DIMENSIONS", "1536")),
        ),
        indexer=IndexerConfig(
            indexed_extensions=extensions,
            chunk_size=int(_get_optional("CHUNK_SIZE", "2000")),
            chunk_overlap=int(_get_optional("CHUNK_OVERLAP", "200")),
            max_concurrency=int(_get_optional("MAX_CONCURRENCY", "4")),
            max_file_size_mb=int(_get_optional("MAX_FILE_SIZE_MB", "100")),
            incremental_minutes=int(_get_optional("INCREMENTAL_MINUTES", "0")),
        ),
    )
