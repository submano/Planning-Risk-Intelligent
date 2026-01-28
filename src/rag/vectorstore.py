"""
Vector store manager for Planning & Risk Intelligence.

Handles embedding generation, vector storage, and similarity search
using ChromaDB as the primary vector store.
"""

import os
from pathlib import Path
from typing import Optional

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from dotenv import load_dotenv

load_dotenv()


class VectorStoreManager:
    """Manages vector store operations for RAG system."""

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "planning_risk_intelligence",
        embedding_model: str = "text-embedding-3-small",
        embeddings: Optional[Embeddings] = None,
    ):
        """
        Initialize vector store manager.

        Args:
            persist_directory: Directory to persist the vector store
            collection_name: Name of the collection in the vector store
            embedding_model: OpenAI embedding model to use
            embeddings: Optional custom embeddings instance
        """
        self.persist_directory = persist_directory or os.getenv(
            "CHROMA_PERSIST_DIRECTORY", "./data/chroma_db"
        )
        self.collection_name = collection_name or os.getenv(
            "COLLECTION_NAME", "planning_risk_intelligence"
        )

        # Ensure persist directory exists
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

        # Initialize embeddings
        if embeddings:
            self.embeddings = embeddings
        else:
            self.embeddings = OpenAIEmbeddings(
                model=embedding_model or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
            )

        self._vectorstore: Optional[Chroma] = None

    @property
    def vectorstore(self) -> Chroma:
        """Get or create the vector store instance."""
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory,
            )
        return self._vectorstore

    def add_documents(
        self,
        documents: list[Document],
        batch_size: int = 100,
    ) -> list[str]:
        """
        Add documents to the vector store.

        Args:
            documents: List of documents to add
            batch_size: Number of documents to process at once

        Returns:
            List of document IDs
        """
        all_ids = []

        # Process in batches to avoid memory issues
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            ids = self.vectorstore.add_documents(batch)
            all_ids.extend(ids)
            print(f"Added batch {i // batch_size + 1}: {len(batch)} documents")

        return all_ids

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[dict] = None,
    ) -> list[Document]:
        """
        Perform similarity search.

        Args:
            query: Search query
            k: Number of results to return
            filter: Optional metadata filter

        Returns:
            List of most similar documents
        """
        if filter:
            return self.vectorstore.similarity_search(query, k=k, filter=filter)
        return self.vectorstore.similarity_search(query, k=k)

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 5,
        filter: Optional[dict] = None,
    ) -> list[tuple[Document, float]]:
        """
        Perform similarity search with relevance scores.

        Args:
            query: Search query
            k: Number of results to return
            filter: Optional metadata filter

        Returns:
            List of (document, score) tuples
        """
        if filter:
            return self.vectorstore.similarity_search_with_score(query, k=k, filter=filter)
        return self.vectorstore.similarity_search_with_score(query, k=k)

    def max_marginal_relevance_search(
        self,
        query: str,
        k: int = 5,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: Optional[dict] = None,
    ) -> list[Document]:
        """
        Perform MMR search for diversity in results.

        Args:
            query: Search query
            k: Number of results to return
            fetch_k: Number of documents to fetch before reranking
            lambda_mult: Diversity factor (0 = max diversity, 1 = max relevance)
            filter: Optional metadata filter

        Returns:
            List of documents with diverse results
        """
        if filter:
            return self.vectorstore.max_marginal_relevance_search(
                query, k=k, fetch_k=fetch_k, lambda_mult=lambda_mult, filter=filter
            )
        return self.vectorstore.max_marginal_relevance_search(
            query, k=k, fetch_k=fetch_k, lambda_mult=lambda_mult
        )

    def delete_collection(self) -> None:
        """Delete the entire collection."""
        self.vectorstore.delete_collection()
        self._vectorstore = None

    def delete_documents(self, ids: list[str]) -> None:
        """Delete specific documents by ID."""
        self.vectorstore.delete(ids=ids)

    def get_collection_stats(self) -> dict:
        """Get statistics about the collection."""
        collection = self.vectorstore._collection
        return {
            "name": self.collection_name,
            "count": collection.count(),
            "persist_directory": self.persist_directory,
        }

    def search_by_doc_type(
        self,
        query: str,
        doc_type: str,
        k: int = 5,
    ) -> list[Document]:
        """
        Search within a specific document type.

        Args:
            query: Search query
            doc_type: Document type to filter by
            k: Number of results

        Returns:
            List of matching documents
        """
        return self.similarity_search(query, k=k, filter={"doc_type": doc_type})

    def search_schedule_documents(
        self,
        query: str,
        k: int = 5,
    ) -> list[Document]:
        """Search only schedule-related documents."""
        schedule_types = [
            "project_overview",
            "schedule_summary",
            "critical_path",
            "wbs_hierarchy",
            "wbs_activities",
            "delayed_activities",
            "milestones",
        ]
        results = []
        for doc_type in schedule_types:
            results.extend(self.search_by_doc_type(query, doc_type, k=2))
        # Sort by relevance and return top k
        return results[:k]

    def search_risk_documents(
        self,
        query: str,
        k: int = 5,
    ) -> list[Document]:
        """Search only risk-related documents."""
        risk_types = [
            "risk_overview",
            "risk_category_summary",
            "high_priority_risks",
            "risk_detail",
            "mitigation_summary",
        ]
        results = []
        for doc_type in risk_types:
            results.extend(self.search_by_doc_type(query, doc_type, k=2))
        return results[:k]


def create_vectorstore_from_documents(
    documents: list[Document],
    persist_directory: str = "./data/chroma_db",
    collection_name: str = "planning_risk_intelligence",
) -> VectorStoreManager:
    """
    Convenience function to create a new vector store from documents.

    Args:
        documents: Documents to add
        persist_directory: Where to persist the store
        collection_name: Name of the collection

    Returns:
        Initialized VectorStoreManager with documents added
    """
    manager = VectorStoreManager(
        persist_directory=persist_directory,
        collection_name=collection_name,
    )
    manager.add_documents(documents)
    return manager
