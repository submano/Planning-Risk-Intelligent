"""
Hybrid Retriever for Planning & Risk Intelligence.

Combines ChromaDB vector search with Neo4j graph traversal
for comprehensive query responses.
"""

import re
from typing import Optional

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from src.rag.vectorstore import VectorStoreManager


class HybridRetriever(BaseRetriever):
    """
    Hybrid retriever that combines:
    1. ChromaDB semantic search for document retrieval
    2. Neo4j graph traversal for relationship-based queries

    Automatically detects when graph traversal is beneficial
    and combines results from both sources.
    """

    vectorstore_manager: VectorStoreManager = Field(description="Vector store manager")
    graph_store: Optional[object] = Field(default=None, description="Neo4j graph store")
    top_k: int = Field(default=5, description="Number of documents to retrieve")
    use_graph: bool = Field(default=True, description="Enable graph traversal")

    class Config:
        arbitrary_types_allowed = True

    # Query patterns that benefit from graph traversal
    GRAPH_QUERY_PATTERNS = {
        "critical_path": [
            r"critical path",
            r"critical activities",
            r"zero float",
            r"no float",
        ],
        "predecessors": [
            r"predecessor",
            r"what comes before",
            r"depends on",
            r"driving",
            r"before activity",
            r"before \w+\d+",
        ],
        "successors": [
            r"successor",
            r"what comes after",
            r"depends on it",
            r"downstream",
            r"after activity",
            r"after \w+\d+",
        ],
        "delay_impact": [
            r"if .* delay",
            r"delay impact",
            r"what happens if",
            r"impact of delay",
            r"late",
            r"slips?",
        ],
        "trace": [
            r"trace",
            r"path between",
            r"how .* connect",
            r"relationship between",
            r"link between",
        ],
        "risk_cascade": [
            r"risk .* affect",
            r"cascade",
            r"ripple effect",
            r"downstream risk",
            r"risk impact on",
        ],
        "activity_risks": [
            r"risks? (?:for|on|affecting)",
            r"what risks? affect",
            r"risky activities",
        ],
    }

    def _needs_graph_traversal(self, query: str) -> tuple[bool, str]:
        """
        Determine if query needs graph traversal.

        Returns:
            Tuple of (needs_graph, query_type)
        """
        query_lower = query.lower()

        for query_type, patterns in self.GRAPH_QUERY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return True, query_type

        # Check for activity codes that might need context
        activity_match = re.search(r'\b([A-Z]-?\d{3,})\b', query, re.IGNORECASE)
        if activity_match:
            # If asking about specific activity, graph context helps
            if any(kw in query_lower for kw in ["what", "show", "tell", "explain", "impact"]):
                return True, "activity_context"

        return False, "none"

    def _get_graph_context(self, query: str, query_type: str) -> list[Document]:
        """
        Get relevant context from Neo4j graph.

        Args:
            query: User query
            query_type: Type of graph query needed

        Returns:
            List of Documents with graph context
        """
        if not self.graph_store:
            return []

        try:
            from src.graph.retriever import GraphRetriever

            graph_retriever = GraphRetriever(self.graph_store)
            return graph_retriever.retrieve(query)
        except Exception as e:
            print(f"Graph retrieval warning: {e}")
            return []

    def _get_vector_results(self, query: str, k: int) -> list[Document]:
        """Get results from ChromaDB vector store."""
        try:
            return self.vectorstore_manager.max_marginal_relevance_search(
                query,
                k=k,
                fetch_k=k * 2,
                lambda_mult=0.7,
            )
        except Exception:
            # Fallback to simple similarity search
            return self.vectorstore_manager.similarity_search(query, k=k)

    def _merge_results(
        self,
        vector_docs: list[Document],
        graph_docs: list[Document],
        query_type: str,
    ) -> list[Document]:
        """
        Merge and deduplicate results from both sources.

        Prioritizes graph results for relationship queries,
        vector results for semantic queries.
        """
        merged = []
        seen_content = set()

        # For relationship queries, prioritize graph results
        if query_type in ["predecessors", "successors", "trace", "delay_impact", "risk_cascade"]:
            priority_docs = graph_docs + vector_docs
        else:
            # For other queries, interleave results
            priority_docs = []
            max_len = max(len(vector_docs), len(graph_docs))
            for i in range(max_len):
                if i < len(graph_docs):
                    priority_docs.append(graph_docs[i])
                if i < len(vector_docs):
                    priority_docs.append(vector_docs[i])

        # Deduplicate by content similarity
        for doc in priority_docs:
            content_key = doc.page_content[:200].strip()
            if content_key not in seen_content:
                seen_content.add(content_key)
                merged.append(doc)

        return merged

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        """
        Retrieve documents using hybrid approach.

        Args:
            query: User query
            run_manager: Callback manager

        Returns:
            List of relevant documents from both sources
        """
        documents = []
        needs_graph, query_type = self._needs_graph_traversal(query)

        # Get vector store results
        vector_k = self.top_k
        if needs_graph and self.use_graph:
            # Get fewer vector results if we're also using graph
            vector_k = max(3, self.top_k - 2)

        vector_docs = self._get_vector_results(query, vector_k)

        # Get graph results if needed and available
        graph_docs = []
        if needs_graph and self.use_graph and self.graph_store:
            graph_docs = self._get_graph_context(query, query_type)

        # Merge results
        if graph_docs:
            documents = self._merge_results(vector_docs, graph_docs, query_type)
        else:
            documents = vector_docs

        # Ensure we don't exceed top_k
        return documents[:self.top_k + 3]  # Allow slightly more for hybrid


def create_hybrid_retriever(
    vectorstore_manager: VectorStoreManager,
    graph_store: Optional[object] = None,
    top_k: int = 5,
    use_graph: bool = True,
) -> HybridRetriever:
    """
    Factory function to create a hybrid retriever.

    Args:
        vectorstore_manager: ChromaDB vector store manager
        graph_store: Optional Neo4j graph store
        top_k: Number of documents to retrieve
        use_graph: Whether to enable graph traversal

    Returns:
        Configured HybridRetriever instance
    """
    return HybridRetriever(
        vectorstore_manager=vectorstore_manager,
        graph_store=graph_store,
        top_k=top_k,
        use_graph=use_graph,
    )
