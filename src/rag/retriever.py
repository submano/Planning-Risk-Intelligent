"""
Custom retriever for Planning & Risk Intelligence.

Implements intelligent retrieval strategies that understand the domain
and can route queries to appropriate document types.
"""

from enum import Enum
from typing import Optional

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from src.rag.vectorstore import VectorStoreManager


class QueryType(str, Enum):
    """Types of queries the system can handle."""
    SCHEDULE = "schedule"
    RISK = "risk"
    COMBINED = "combined"
    CRITICAL_PATH = "critical_path"
    MITIGATION = "mitigation"
    COST = "cost"
    GENERAL = "general"


class PlanningRiskRetriever(BaseRetriever):
    """
    Custom retriever that intelligently routes queries
    to appropriate document types based on query analysis.
    """

    vectorstore_manager: VectorStoreManager = Field(description="Vector store manager")
    top_k: int = Field(default=5, description="Number of documents to retrieve")
    use_mmr: bool = Field(default=True, description="Use MMR for diverse results")
    mmr_lambda: float = Field(default=0.7, description="MMR diversity factor")

    class Config:
        arbitrary_types_allowed = True

    def _classify_query(self, query: str) -> QueryType:
        """
        Classify the query to determine retrieval strategy.

        Args:
            query: User's query string

        Returns:
            QueryType indicating the best retrieval strategy
        """
        query_lower = query.lower()

        # Risk-related keywords
        risk_keywords = [
            "risk", "risks", "threat", "threats", "mitigation", "mitigate",
            "contingency", "probability", "impact", "emv", "expected monetary",
            "risk score", "risk register", "risk owner", "risk category",
        ]

        # Schedule-related keywords
        schedule_keywords = [
            "schedule", "activity", "activities", "task", "tasks", "duration",
            "milestone", "milestones", "wbs", "work breakdown", "predecessor",
            "successor", "relationship", "dependency", "float", "slack",
            "baseline", "progress", "percent complete", "start date", "finish date",
            "planned", "actual", "forecast",
        ]

        # Critical path keywords
        critical_keywords = [
            "critical path", "critical activities", "zero float", "delay",
            "delayed", "behind schedule", "schedule variance",
        ]

        # Mitigation-specific
        mitigation_keywords = [
            "mitigation", "mitigate", "response plan", "treatment",
            "contingency", "action plan", "risk response",
        ]

        # Cost-related
        cost_keywords = [
            "cost", "budget", "financial", "emv", "expected monetary value",
            "cost impact", "expense", "spend",
        ]

        # Check for combined queries
        has_risk = any(kw in query_lower for kw in risk_keywords)
        has_schedule = any(kw in query_lower for kw in schedule_keywords)

        if has_risk and has_schedule:
            return QueryType.COMBINED

        if any(kw in query_lower for kw in critical_keywords):
            return QueryType.CRITICAL_PATH

        if any(kw in query_lower for kw in mitigation_keywords):
            return QueryType.MITIGATION

        if any(kw in query_lower for kw in cost_keywords):
            return QueryType.COST

        if has_risk:
            return QueryType.RISK

        if has_schedule:
            return QueryType.SCHEDULE

        return QueryType.GENERAL

    def _get_retrieval_filter(self, query_type: QueryType) -> Optional[dict]:
        """Get metadata filter based on query type."""
        filters = {
            QueryType.SCHEDULE: {
                "doc_type": {
                    "$in": [
                        "project_overview",
                        "schedule_summary",
                        "critical_path",
                        "wbs_activities",
                        "milestones",
                    ]
                }
            },
            QueryType.RISK: {
                "doc_type": {
                    "$in": [
                        "risk_overview",
                        "risk_category_summary",
                        "high_priority_risks",
                        "risk_detail",
                    ]
                }
            },
            QueryType.CRITICAL_PATH: {
                "doc_type": {
                    "$in": ["critical_path", "delayed_activities", "schedule_summary"]
                }
            },
            QueryType.MITIGATION: {
                "doc_type": {
                    "$in": ["mitigation_summary", "risk_detail", "high_priority_risks"]
                }
            },
            QueryType.COST: {
                "doc_type": {
                    "$in": [
                        "risk_overview",
                        "risk_detail",
                        "risk_category_summary",
                        "project_overview",
                    ]
                }
            },
        }
        return filters.get(query_type)

    def _get_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        """
        Retrieve documents for a query.

        Args:
            query: User query
            run_manager: Callback manager

        Returns:
            List of relevant documents
        """
        # Classify the query
        query_type = self._classify_query(query)

        # Get appropriate filter
        filter_dict = self._get_retrieval_filter(query_type)

        # Determine k based on query type
        k = self.top_k
        if query_type == QueryType.COMBINED:
            k = self.top_k + 3  # Get more results for combined queries

        # Retrieve documents
        if self.use_mmr:
            # Note: ChromaDB's MMR doesn't support complex filters well
            # So we do a simple search with filter, then add MMR results
            if filter_dict:
                # Get filtered results
                filtered_results = self.vectorstore_manager.similarity_search(
                    query, k=k, filter=None  # Skip filter for now due to Chroma limitations
                )
                # Filter manually
                documents = [
                    doc
                    for doc in filtered_results
                    if self._matches_filter(doc, filter_dict)
                ][:k]

                # If not enough results, get general MMR results
                if len(documents) < k:
                    mmr_results = self.vectorstore_manager.max_marginal_relevance_search(
                        query,
                        k=k - len(documents),
                        fetch_k=k * 2,
                        lambda_mult=self.mmr_lambda,
                    )
                    documents.extend(mmr_results)
            else:
                documents = self.vectorstore_manager.max_marginal_relevance_search(
                    query,
                    k=k,
                    fetch_k=k * 2,
                    lambda_mult=self.mmr_lambda,
                )
        else:
            documents = self.vectorstore_manager.similarity_search(
                query, k=k, filter=None
            )
            if filter_dict:
                documents = [
                    doc
                    for doc in documents
                    if self._matches_filter(doc, filter_dict)
                ][:k]

        return documents

    def _matches_filter(self, doc: Document, filter_dict: dict) -> bool:
        """Check if document matches filter criteria."""
        if not filter_dict:
            return True

        for key, value in filter_dict.items():
            doc_value = doc.metadata.get(key)
            if isinstance(value, dict) and "$in" in value:
                if doc_value not in value["$in"]:
                    return False
            elif doc_value != value:
                return False
        return True


class MultiQueryRetriever:
    """
    Retriever that generates multiple query variations
    for more comprehensive retrieval.
    """

    def __init__(
        self,
        base_retriever: PlanningRiskRetriever,
        llm=None,
    ):
        """
        Initialize multi-query retriever.

        Args:
            base_retriever: Base retriever to use
            llm: Language model for query generation (optional)
        """
        self.base_retriever = base_retriever
        self.llm = llm

    def _generate_queries(self, query: str) -> list[str]:
        """Generate query variations."""
        queries = [query]

        # Add common variations based on query type
        query_type = self.base_retriever._classify_query(query)

        if query_type == QueryType.RISK:
            queries.extend([
                f"risk assessment {query}",
                f"risk mitigation {query}",
            ])
        elif query_type == QueryType.SCHEDULE:
            queries.extend([
                f"schedule status {query}",
                f"project activities {query}",
            ])
        elif query_type == QueryType.CRITICAL_PATH:
            queries.extend([
                f"critical path analysis {query}",
                f"schedule delays {query}",
            ])

        return queries

    def retrieve(self, query: str) -> list[Document]:
        """
        Retrieve documents using multiple query variations.

        Args:
            query: Original query

        Returns:
            Deduplicated list of documents
        """
        queries = self._generate_queries(query)
        all_docs = []
        seen_contents = set()

        for q in queries:
            docs = self.base_retriever.invoke(q)
            for doc in docs:
                # Deduplicate by content
                content_hash = hash(doc.page_content[:200])
                if content_hash not in seen_contents:
                    seen_contents.add(content_hash)
                    all_docs.append(doc)

        return all_docs
