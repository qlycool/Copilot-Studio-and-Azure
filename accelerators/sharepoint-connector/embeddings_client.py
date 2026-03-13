"""
Azure Foundry embeddings client.
Generates vector embeddings for text chunks with rate-limit handling.
Authenticates via DefaultAzureCredential (managed identity / Azure CLI).
"""

import logging
import time
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI, RateLimitError, APITimeoutError, APIConnectionError

from config import OpenAIConfig

logger = logging.getLogger(__name__)


def _build_openai_client(config: OpenAIConfig) -> AzureOpenAI:
    """Build the AzureOpenAI client using DefaultAzureCredential."""
    logger.info("Embeddings client: using DefaultAzureCredential (managed identity)")
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=config.endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2024-06-01",
    )


class EmbeddingsClient:
    """Client for generating embeddings via Azure OpenAI / Foundry."""

    def __init__(self, config: OpenAIConfig):
        self._config = config
        self._client = _build_openai_client(config)
        self._deployment = config.embedding_deployment
        self._dimensions = config.embedding_dimensions
        # Only text-embedding-3-* models support the dimensions parameter
        self._supports_dimensions = "embedding-3" in config.embedding_deployment

    def generate_embeddings_batch(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        """
        Generate embeddings for a list of texts in batches.
        Returns embeddings in the same order as input texts.
        """
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            max_retries = 8
            for attempt in range(max_retries):
                try:
                    kwargs: dict = dict(model=self._deployment, input=batch)
                    if self._supports_dimensions:
                        kwargs["dimensions"] = self._dimensions
                    response = self._client.embeddings.create(**kwargs)
                    # Sort by index to maintain order
                    sorted_data = sorted(response.data, key=lambda x: x.index)
                    batch_embeddings = [item.embedding for item in sorted_data]
                    all_embeddings.extend(batch_embeddings)
                    break
                except RateLimitError as e:
                    retry_after = getattr(e, "retry_after", None) or (2 ** attempt)
                    retry_after = min(retry_after, 60)
                    logger.warning(f"Rate limited on batch. Retrying in {retry_after}s")
                    time.sleep(retry_after)
                except (APITimeoutError, APIConnectionError) as e:
                    wait = min(2 ** attempt, 30)
                    logger.warning(f"Transient error on batch: {e}. Retrying in {wait}s")
                    time.sleep(wait)
            else:
                raise RuntimeError(f"Failed to generate embeddings for batch starting at index {i}")

            logger.debug(f"Embedded batch {i // batch_size + 1} ({len(batch)} texts)")

        return all_embeddings

    def close(self) -> None:
        """Close the underlying OpenAI client."""
        self._client.close()
