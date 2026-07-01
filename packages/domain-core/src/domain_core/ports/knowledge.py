"""Port to the knowledge base / RAG (Blueprint section 7.6)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class KnowledgePort(ABC):
    """Retrieve grounded answers from the documentation corpus."""

    @abstractmethod
    async def search(self, query: str, language: str, top_k: int = 4) -> list[dict[str, Any]]:
        """Return ranked passages with a source reference for each."""