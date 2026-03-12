"""
Main indexer orchestrator.
Coordinates the full SharePoint → Azure AI Search pipeline:
  1. Discover & list files from SharePoint via Graph API
  2. Download file content
  3. Extract text
  4. Chunk text
  5. Generate embeddings
  6. Push to Azure AI Search index
"""

import logging
import hashlib
import threading
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from config import AppConfig, load_config
from sharepoint_client import SharePointClient, SharePointFile
from document_processor import extract_text
from chunker import chunk_text
from embeddings_client import EmbeddingsClient
from search_client import SearchPushClient

logger = logging.getLogger(__name__)


@dataclass
class IndexerStats:
    """Thread-safe statistics for an indexer run."""
    files_discovered: int = 0
    files_processed: int = 0
    files_skipped_fresh: int = 0
    files_skipped_error: int = 0
    chunks_uploaded: int = 0
    errors: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_processed(self, chunks: int) -> None:
        with self._lock:
            self.files_processed += 1
            self.chunks_uploaded += chunks

    def record_skipped_fresh(self) -> None:
        with self._lock:
            self.files_skipped_fresh += 1

    def record_error(self, message: str) -> None:
        with self._lock:
            self.files_skipped_error += 1
            self.errors.append(message)

    def summary(self) -> str:
        return (
            f"Indexer run complete: "
            f"{self.files_discovered} discovered, "
            f"{self.files_processed} processed, "
            f"{self.files_skipped_fresh} skipped (fresh), "
            f"{self.files_skipped_error} errors, "
            f"{self.chunks_uploaded} chunks uploaded"
        )


def _make_parent_id(drive_id: str, item_id: str) -> str:
    """Create a stable parent ID for a SharePoint file."""
    raw = f"{drive_id}:{item_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _is_fresh(
    search_client: SearchPushClient,
    parent_id: str,
    file_last_modified: datetime,
) -> bool:
    """Check if the indexed version is already up to date."""
    existing = search_client.check_freshness(parent_id)
    if existing is None:
        return False  # Not in index yet

    # Parse the indexed timestamp
    try:
        if isinstance(existing, str):
            indexed_dt = datetime.fromisoformat(existing.replace("Z", "+00:00"))
        else:
            indexed_dt = existing
        # Skip if SharePoint version is ≤1s newer (clock tolerance)
        return (file_last_modified - indexed_dt).total_seconds() <= 1.0
    except Exception as e:
        logger.debug("Freshness check parse error for %s: %s", parent_id, e)
        return False


def _process_single_file(
    sp_file: SharePointFile,
    config: AppConfig,
    embeddings: EmbeddingsClient,
    search: SearchPushClient,
    stats: IndexerStats,
) -> None:
    """Process one file: extract → chunk → embed → push."""
    parent_id = _make_parent_id(sp_file.drive_id, sp_file.id)

    # --- Freshness check ---
    if _is_fresh(search, parent_id, sp_file.last_modified):
        stats.record_skipped_fresh()
        logger.debug(f"Skipping (fresh): {sp_file.name}")
        return

    # --- Extract text ---
    if not sp_file.content:
        logger.warning(f"No content for {sp_file.name}, skipping")
        stats.record_error(f"No content: {sp_file.name}")
        return

    text = extract_text(sp_file.name, sp_file.content)
    if not text.strip():
        logger.warning(f"No text extracted from {sp_file.name}, skipping")
        stats.record_error(f"No text extracted: {sp_file.name}")
        return

    # --- Chunk ---
    chunks = chunk_text(
        text,
        doc_id=parent_id,
        chunk_size=config.indexer.chunk_size,
        chunk_overlap=config.indexer.chunk_overlap,
    )
    if not chunks:
        logger.warning(f"No chunks generated for {sp_file.name}")
        stats.record_error(f"No chunks: {sp_file.name}")
        return

    # --- Generate embeddings ---
    chunk_texts = [c.text for c in chunks]
    try:
        vectors = embeddings.generate_embeddings_batch(chunk_texts)
    except Exception as e:
        logger.error(f"Embedding failed for {sp_file.name}: {e}")
        stats.record_error(f"Embedding error: {sp_file.name} - {e}")
        return

    # --- Delete old chunks for this document ---
    try:
        search.delete_documents_by_parent(parent_id)
    except Exception as e:
        logger.warning(f"Could not delete old chunks for {sp_file.name}: {e}")

    # --- Build index documents ---
    docs = []
    for chunk, vector in zip(chunks, vectors):
        doc = {
            "chunk_id": chunk.chunk_id,
            "parent_id": parent_id,
            "chunk": chunk.text,
            "title": sp_file.name,
            "source_url": sp_file.web_url,
            "last_modified": sp_file.last_modified.isoformat(),
            "content_type": sp_file.content_type,
            "file_size": sp_file.size,
            "created_by": sp_file.created_by,
            "modified_by": sp_file.modified_by,
            "drive_name": sp_file.drive_name,
            "permission_ids": sp_file.permissions or [],
            "text_vector": vector,
        }
        docs.append(doc)

    # --- Push to Azure AI Search ---
    try:
        uploaded = search.upload_documents(docs)
        stats.record_processed(uploaded)
        logger.info(f"Indexed: {sp_file.name} ({len(chunks)} chunks)")
    except Exception as e:
        logger.error(f"Upload failed for {sp_file.name}: {e}")
        stats.record_error(f"Upload error: {sp_file.name} - {e}")


def _reconcile_deleted_files(
    search: SearchPushClient,
    indexed_parent_ids: set[str],
    current_parent_ids: set[str],
) -> int:
    """Remove chunks for files that no longer exist in SharePoint."""
    orphaned = indexed_parent_ids - current_parent_ids
    removed = 0
    for parent_id in orphaned:
        try:
            search.delete_documents_by_parent(parent_id)
            removed += 1
        except Exception as e:
            logger.warning(f"Failed to remove orphaned chunks for {parent_id}: {e}")
    if removed:
        logger.info(f"Reconciliation: removed chunks for {removed} deleted files")
    return removed


def run_indexer(config: AppConfig | None = None) -> IndexerStats:
    """
    Execute the full indexing pipeline.

    Steps:
      1. Ensure the search index exists
      2. List files from SharePoint (optionally filtered by time)
      3. For each file: download → extract → chunk → embed → push
      4. Reconcile deleted files (full reindex only)
      5. Return statistics
    """
    if config is None:
        config = load_config()

    stats = IndexerStats()
    max_file_size = config.indexer.max_file_size_mb * 1024 * 1024

    # --- Init clients ---
    sp_client = SharePointClient(config.entra, config.sharepoint)
    embeddings = EmbeddingsClient(config.openai)
    search = SearchPushClient(config.search, config.openai.embedding_dimensions)

    try:
        # --- Ensure index ---
        search.ensure_index()

        # --- Determine time filter ---
        modified_since = None
        if config.indexer.incremental_minutes > 0:
            modified_since = datetime.now(timezone.utc) - timedelta(minutes=config.indexer.incremental_minutes)
            logger.info(f"Incremental mode: looking for changes since {modified_since.isoformat()}")
        else:
            logger.info("Full reindex mode")

        # --- List files ---
        raw_files = sp_client.list_all_files(
            modified_since=modified_since,
            extensions=config.indexer.indexed_extensions,
        )
        stats.files_discovered = len(raw_files)
        logger.info(f"Discovered {stats.files_discovered} files to process")

        if not raw_files:
            logger.info("No files to index")
            return stats

        # Build set of current parent IDs for reconciliation
        current_parent_ids = {
            _make_parent_id(item.get("_drive_id", ""), item["id"])
            for item in raw_files
        }

        # --- Process files with concurrency ---
        def _process_item(item: dict) -> None:
            try:
                sp_file = sp_client.build_file_record(
                    item,
                    include_content=True,
                    include_permissions=True,
                    drive_name=item.get("_drive_name", ""),
                    max_file_size=max_file_size,
                )
                _process_single_file(sp_file, config, embeddings, search, stats)
            except Exception as e:
                logger.error(f"Error processing {item.get('name', 'unknown')}: {e}")
                stats.record_error(f"{item.get('name', 'unknown')}: {e}")

        max_workers = min(config.indexer.max_concurrency, len(raw_files))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_process_item, item): item for item in raw_files}
            for future in as_completed(futures):
                # Exceptions are caught inside _process_item
                future.result()

        # --- Reconcile deleted files (full reindex only) ---
        if modified_since is None:
            try:
                indexed_ids = search.get_all_parent_ids()
                _reconcile_deleted_files(search, indexed_ids, current_parent_ids)
            except Exception as e:
                logger.warning(f"Reconciliation skipped: {e}")

        logger.info(stats.summary())
        return stats

    finally:
        sp_client.close()
        embeddings.close()
        search.close()
