"""
Azure AI Search push client.
Creates/updates the search index and uploads document chunks with embeddings.
"""

import logging
import time
from typing import Any

from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
)
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential

from config import SearchConfig

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Index schema definition
# ------------------------------------------------------------------ #

def _build_index(name: str, embedding_dimensions: int) -> SearchIndex:
    """Build the Azure AI Search index schema for SharePoint documents."""
    fields = [
        SimpleField(
            name="chunk_id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SimpleField(
            name="parent_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SearchableField(
            name="chunk",
            type=SearchFieldDataType.String,
        ),
        SearchableField(
            name="title",
            type=SearchFieldDataType.String,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="source_url",
            type=SearchFieldDataType.String,
            filterable=False,
        ),
        SimpleField(
            name="last_modified",
            type=SearchFieldDataType.DateTimeOffset,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="content_type",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="file_size",
            type=SearchFieldDataType.Int64,
            filterable=True,
        ),
        SimpleField(
            name="created_by",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="modified_by",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="drive_name",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        # Permissions for security trimming
        SimpleField(
            name="permission_ids",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
        ),
        # Vector field for embeddings
        SearchField(
            name="text_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=embedding_dimensions,
            vector_search_profile_name="sp-vector-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(name="sp-hnsw"),
        ],
        profiles=[
            VectorSearchProfile(
                name="sp-vector-profile",
                algorithm_configuration_name="sp-hnsw",
            ),
        ],
    )

    semantic_config = SemanticConfiguration(
        name="sp-semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[SemanticField(field_name="chunk")],
        ),
    )

    semantic_search = SemanticSearch(
        default_configuration_name="sp-semantic-config",
        configurations=[semantic_config],
    )

    return SearchIndex(
        name=name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )


# ------------------------------------------------------------------ #
# Search push client
# ------------------------------------------------------------------ #

class SearchPushClient:
    """Client that pushes document chunks directly to Azure AI Search."""

    def __init__(self, config: SearchConfig, embedding_dimensions: int = 1536):
        self._config = config
        self._embedding_dimensions = embedding_dimensions
        self._credential = DefaultAzureCredential()
        logger.info("Search client: using DefaultAzureCredential (managed identity)")

        self._index_client = SearchIndexClient(
            endpoint=config.endpoint,
            credential=self._credential,
        )
        self._search_client: SearchClient | None = None

    def _get_search_client(self) -> SearchClient:
        if self._search_client is None:
            self._search_client = SearchClient(
                endpoint=self._config.endpoint,
                index_name=self._config.index_name,
                credential=self._credential,
            )
        return self._search_client

    # -------------------------------------------------------------- #
    # Index management
    # -------------------------------------------------------------- #

    def ensure_index(self) -> None:
        """Create or update the search index."""
        index = _build_index(self._config.index_name, self._embedding_dimensions)
        try:
            self._index_client.create_or_update_index(index)
            logger.info(f"Index '{self._config.index_name}' is ready")
        except HttpResponseError as e:
            logger.error(f"Failed to create/update index: {e.message}")
            raise

    # -------------------------------------------------------------- #
    # Document operations
    # -------------------------------------------------------------- #

    def upload_documents(self, documents: list[dict[str, Any]], batch_size: int = 500) -> int:
        """
        Upload or merge documents into the index in batches.
        Returns total number of documents successfully uploaded.
        """
        client = self._get_search_client()
        total_uploaded = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            result = self._upload_batch_with_retry(client, batch)
            succeeded = sum(1 for r in result if r.succeeded)
            failed = sum(1 for r in result if not r.succeeded)
            total_uploaded += succeeded

            if failed:
                for r in result:
                    if not r.succeeded:
                        logger.error(f"Failed to upload {r.key}: {r.error_message}")

            logger.info(
                f"Batch {i // batch_size + 1}: "
                f"{succeeded} uploaded, {failed} failed "
                f"({total_uploaded} total so far)"
            )

        return total_uploaded

    def _upload_batch_with_retry(self, client: SearchClient, batch: list[dict], max_retries: int = 5) -> list:
        """Upload a batch with retry on transient errors."""
        for attempt in range(max_retries):
            try:
                return client.upload_documents(documents=batch)
            except HttpResponseError as e:
                if e.status_code == 429 or (e.status_code and e.status_code >= 500):
                    wait = min(2**attempt, 30)
                    logger.warning(f"Search upload error {e.status_code}. Retrying in {wait}s (attempt {attempt + 1})")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError(f"Failed to upload batch after {max_retries} retries")

    def delete_documents_by_parent(self, parent_id: str) -> None:
        """Delete all chunks for a given parent document ID."""
        client = self._get_search_client()
        # Find all chunk_ids for this parent
        results = client.search(
            search_text="*",
            filter=f"parent_id eq '{parent_id}'",
            select=["chunk_id"],
        )
        chunk_ids = [doc["chunk_id"] for doc in results]
        if chunk_ids:
            docs_to_delete = [{"chunk_id": cid} for cid in chunk_ids]
            client.delete_documents(documents=docs_to_delete)
            logger.info(f"Deleted {len(chunk_ids)} chunks for parent '{parent_id}'")

    def check_freshness(self, parent_id: str) -> str | None:
        """
        Check if a document already exists in the index.
        Returns the last_modified timestamp string if found, None otherwise.
        """
        client = self._get_search_client()
        try:
            results = client.search(
                search_text="*",
                filter=f"parent_id eq '{parent_id}'",
                select=["chunk_id", "last_modified"],
                top=1,
            )
            for doc in results:
                return doc.get("last_modified")
        except HttpResponseError as e:
            logger.warning(f"Freshness check failed for {parent_id}: {e.message}")
        except Exception as e:
            logger.warning(f"Freshness check failed for {parent_id}: {e}")
        return None

    def get_all_parent_ids(self) -> set[str]:
        """
        Retrieve all unique parent IDs currently in the index.
        Used for reconciling deleted files.
        """
        client = self._get_search_client()
        parent_ids: set[str] = set()
        try:
            results = client.search(
                search_text="*",
                select=["parent_id"],
            )
            for doc in results:
                pid = doc.get("parent_id")
                if pid:
                    parent_ids.add(pid)
        except Exception as e:
            logger.warning(f"Could not retrieve parent IDs for reconciliation: {e}")
        return parent_ids

    def close(self) -> None:
        """Close clients."""
        if self._search_client:
            self._search_client.close()
        self._index_client.close()
