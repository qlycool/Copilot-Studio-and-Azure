"""Tests for config.py — configuration loading and validation."""

import os
import pytest
from unittest.mock import patch

# Import at module level so load_dotenv() runs BEFORE any env patching
from config import load_config

# Minimal required env vars for a valid config
_REQUIRED_ENV = {
    "TENANT_ID": "test-tenant-id",
    "SHAREPOINT_SITE_URL": "https://contoso.sharepoint.com/sites/TestSite",
    "SEARCH_ENDPOINT": "https://my-search.search.windows.net",
    "FOUNDRY_ENDPOINT": "https://my-foundry.services.ai.azure.com",
}


class TestLoadConfigRequired:
    """Test that missing required vars raise EnvironmentError."""

    def test_missing_tenant_id(self):
        env = {k: v for k, v in _REQUIRED_ENV.items() if k != "TENANT_ID"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(EnvironmentError, match="TENANT_ID"):
                load_config()

    def test_missing_sharepoint_site_url(self):
        env = {k: v for k, v in _REQUIRED_ENV.items() if k != "SHAREPOINT_SITE_URL"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(EnvironmentError, match="SHAREPOINT_SITE_URL"):
                load_config()

    def test_missing_search_endpoint(self):
        env = {k: v for k, v in _REQUIRED_ENV.items() if k != "SEARCH_ENDPOINT"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(EnvironmentError, match="SEARCH_ENDPOINT"):
                load_config()

    def test_missing_foundry_endpoint(self):
        env = {k: v for k, v in _REQUIRED_ENV.items() if k != "FOUNDRY_ENDPOINT"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(EnvironmentError, match="FOUNDRY_ENDPOINT"):
                load_config()


class TestLoadConfigDefaults:
    """Test default values when optional vars are not set."""

    def test_defaults(self):
        with patch.dict(os.environ, _REQUIRED_ENV, clear=True):
            cfg = load_config()

        assert cfg.entra.tenant_id == "test-tenant-id"
        assert cfg.entra.client_id == ""
        assert cfg.entra.client_secret == ""
        assert cfg.entra.use_managed_identity is True

        assert cfg.sharepoint.site_url == "https://contoso.sharepoint.com/sites/TestSite"
        assert cfg.sharepoint.libraries == []

        assert cfg.search.index_name == "sharepoint-index"

        assert cfg.openai.embedding_deployment == "text-embedding-3-large"
        assert cfg.openai.embedding_dimensions == 1536

        assert cfg.indexer.chunk_size == 2000
        assert cfg.indexer.chunk_overlap == 200
        assert cfg.indexer.max_concurrency == 4
        assert cfg.indexer.max_file_size_mb == 100
        assert cfg.indexer.incremental_minutes == 0

    def test_default_extensions_count(self):
        with patch.dict(os.environ, _REQUIRED_ENV, clear=True):
            cfg = load_config()

        # Default should include all 24 supported extensions
        assert len(cfg.indexer.indexed_extensions) == 24
        assert ".pdf" in cfg.indexer.indexed_extensions
        assert ".zip" in cfg.indexer.indexed_extensions
        assert ".gz" in cfg.indexer.indexed_extensions


class TestLoadConfigCustomValues:
    """Test that custom env vars override defaults."""

    def test_custom_values(self):
        env = {
            **_REQUIRED_ENV,
            "CLIENT_ID": "my-client-id",
            "CLIENT_SECRET": "my-secret",
            "SHAREPOINT_LIBRARIES": "Documents, Reports, Archive",
            "SEARCH_INDEX_NAME": "custom-index",
            "FOUNDRY_EMBEDDING_DEPLOYMENT": "text-embedding-3-large",
            "FOUNDRY_EMBEDDING_DIMENSIONS": "3072",
            "CHUNK_SIZE": "1500",
            "CHUNK_OVERLAP": "150",
            "MAX_CONCURRENCY": "8",
            "MAX_FILE_SIZE_MB": "50",
            "INCREMENTAL_MINUTES": "60",
            "INDEXED_EXTENSIONS": ".pdf,.docx,.txt",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()

        assert cfg.entra.client_id == "my-client-id"
        assert cfg.entra.client_secret == "my-secret"
        assert cfg.entra.use_managed_identity is False

        assert cfg.sharepoint.libraries == ["Documents", "Reports", "Archive"]

        assert cfg.search.index_name == "custom-index"

        assert cfg.openai.embedding_deployment == "text-embedding-3-large"
        assert cfg.openai.embedding_dimensions == 3072

        assert cfg.indexer.chunk_size == 1500
        assert cfg.indexer.chunk_overlap == 150
        assert cfg.indexer.max_concurrency == 8
        assert cfg.indexer.max_file_size_mb == 50
        assert cfg.indexer.incremental_minutes == 60
        assert cfg.indexer.indexed_extensions == [".pdf", ".docx", ".txt"]


class TestSharePointConfigProperties:
    """Test computed properties on SharePointConfig."""

    def test_hostname_extraction(self):
        with patch.dict(os.environ, _REQUIRED_ENV, clear=True):
            cfg = load_config()
        assert cfg.sharepoint.hostname == "contoso.sharepoint.com"

    def test_site_path_extraction(self):
        with patch.dict(os.environ, _REQUIRED_ENV, clear=True):
            cfg = load_config()
        assert cfg.sharepoint.site_path == "/sites/TestSite"

    def test_site_path_strips_trailing_slash(self):
        env = {**_REQUIRED_ENV, "SHAREPOINT_SITE_URL": "https://contoso.sharepoint.com/sites/TestSite/"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        assert cfg.sharepoint.site_path == "/sites/TestSite"


class TestEntraConfigManagedIdentity:
    """Test use_managed_identity logic."""

    def test_managed_identity_when_no_secret(self):
        env = {**_REQUIRED_ENV, "CLIENT_ID": "some-id"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        assert cfg.entra.use_managed_identity is True

    def test_not_managed_identity_when_secret_set(self):
        env = {**_REQUIRED_ENV, "CLIENT_ID": "some-id", "CLIENT_SECRET": "secret"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        assert cfg.entra.use_managed_identity is False
