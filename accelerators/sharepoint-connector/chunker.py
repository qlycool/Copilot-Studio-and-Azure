"""
Text chunking with overlap.
Splits extracted document text into chunks suitable for embedding and indexing.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """A chunk of text with its position metadata."""
    chunk_id: str
    text: str
    index: int
    total_chunks: int


def chunk_text(
    text: str,
    doc_id: str,
    chunk_size: int = 2000,
    chunk_overlap: int = 200,
) -> list[TextChunk]:
    """
    Split text into overlapping chunks.

    Args:
        text: The full document text.
        doc_id: Unique document identifier (used to build chunk IDs).
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Number of overlapping characters between consecutive chunks.

    Returns:
        List of TextChunk objects.
    """
    if not text or not text.strip():
        return []

    # Guard against misconfiguration that would cause infinite loops
    if chunk_overlap >= chunk_size:
        logger.warning(
            f"chunk_overlap ({chunk_overlap}) >= chunk_size ({chunk_size}), "
            f"clamping overlap to {chunk_size // 4}"
        )
        chunk_overlap = chunk_size // 4

    text = text.strip()

    # If text fits in a single chunk, return as-is
    if len(text) <= chunk_size:
        return [TextChunk(
            chunk_id=f"{doc_id}_c00000",
            text=text,
            index=0,
            total_chunks=1,
        )]

    chunks: list[TextChunk] = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence or paragraph boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind("\n\n", start + chunk_size // 2, end)
            if para_break > start:
                end = para_break + 2
            else:
                # Look for sentence break
                for sep in (". ", ".\n", "! ", "? ", ";\n", "\n"):
                    sep_pos = text.rfind(sep, start + chunk_size // 2, end)
                    if sep_pos > start:
                        end = sep_pos + len(sep)
                        break

        chunk_text_content = text[start:end].strip()

        if chunk_text_content:
            chunks.append(TextChunk(
                chunk_id=f"{doc_id}_c{chunk_index:05d}",
                text=chunk_text_content,
                index=chunk_index,
                total_chunks=0,  # Will be set after all chunks are created
            ))
            chunk_index += 1

        # Move start forward, accounting for overlap
        start = end - chunk_overlap
        if start >= len(text):
            break

    # Set total_chunks on all chunks
    total = len(chunks)
    for chunk in chunks:
        chunk.total_chunks = total

    logger.debug(f"Split doc {doc_id} into {total} chunks (size={chunk_size}, overlap={chunk_overlap})")
    return chunks
