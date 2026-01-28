"""
RAG Chain for Planning & Risk Intelligence.

Implements the complete RAG pipeline combining retrieval and generation
for answering questions about project schedules and risks.

Supports both vector-based retrieval and knowledge graph traversal.
"""

import os
from typing import Any, Optional

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv

from src.rag.retriever import PlanningRiskRetriever
from src.rag.vectorstore import VectorStoreManager

load_dotenv()

# Optional graph imports - only used if graph store is provided
try:
    from src.graph.store import GraphStore
    from src.graph.retriever import GraphRetriever, GraphQueryEngine
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False


# System prompts for different query types
PLANNING_RISK_SYSTEM_PROMPT = """You are an expert Project Planning and Risk Intelligence Assistant.
You have deep knowledge of project management, scheduling (particularly Primavera P6), and risk management.

Your role is to:
1. Analyze project schedule data and identify potential issues
2. Evaluate risks and their impacts on the project
3. Provide actionable insights and recommendations
4. Answer questions accurately based on the provided context
5. Trace schedule dependencies and understand activity relationships

Guidelines:
- Always base your answers on the provided context from the schedule and risk register
- If the context doesn't contain enough information, acknowledge this
- Provide specific details like activity codes, dates, and risk IDs when relevant
- Highlight critical concerns such as critical path issues or high-priority risks
- Suggest practical mitigations and recommendations when appropriate
- Use professional project management terminology

When discussing schedules:
- Reference specific activities by their codes and names
- Highlight critical path activities and their importance
- Note any delays or variances from baseline
- Consider float and schedule flexibility
- Explain predecessor/successor relationships when relevant
- Trace the impact chain for delays or changes

When discussing risks:
- Reference risks by their IDs and titles
- Consider probability, impact, and overall risk score
- Discuss mitigation strategies when relevant
- Consider the expected monetary value (EMV) and schedule impacts
- Explain which activities are affected by each risk
- Consider the downstream cascade effect of risks

When graph data is available:
- Use relationship information to trace dependencies
- Explain how activities connect to each other
- Identify the impact chain for schedule changes
- Show which risks affect which parts of the schedule
"""

RAG_PROMPT_TEMPLATE = """Based on the following context from the project schedule and risk register,
please answer the question. Use specific details from the context when available.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""


def format_documents(docs: list[Document]) -> str:
    """Format documents into a single context string."""
    formatted = []
    for i, doc in enumerate(docs, 1):
        doc_type = doc.metadata.get("doc_type", "unknown")
        source = doc.metadata.get("source", "unknown")
        formatted.append(f"--- Document {i} ({doc_type}) from {source} ---\n{doc.page_content}")
    return "\n\n".join(formatted)


class PlanningRiskRAGChain:
    """
    Complete RAG chain for Planning & Risk Intelligence queries.
    """

    def __init__(
        self,
        vectorstore_manager: VectorStoreManager,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        top_k: int = 5,
    ):
        """
        Initialize the RAG chain.

        Args:
            vectorstore_manager: Vector store manager for retrieval
            model_name: OpenAI model name
            temperature: LLM temperature (lower = more focused)
            max_tokens: Maximum tokens in response
            top_k: Number of documents to retrieve
        """
        self.vectorstore_manager = vectorstore_manager

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model_name or os.getenv("LLM_MODEL", "gpt-4-turbo-preview"),
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Initialize retriever
        self.retriever = PlanningRiskRetriever(
            vectorstore_manager=vectorstore_manager,
            top_k=top_k,
        )

        # Create prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNING_RISK_SYSTEM_PROMPT),
            ("human", RAG_PROMPT_TEMPLATE),
        ])

        # Build the chain
        self.chain = self._build_chain()

    def _build_chain(self):
        """Build the RAG chain."""
        return (
            {
                "context": self.retriever | RunnableLambda(format_documents),
                "question": RunnablePassthrough(),
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )

    def query(self, question: str) -> str:
        """
        Execute a query through the RAG chain.

        Args:
            question: User's question

        Returns:
            Generated answer
        """
        return self.chain.invoke(question)

    def query_with_sources(self, question: str) -> dict[str, Any]:
        """
        Execute a query and return both answer and source documents.

        Args:
            question: User's question

        Returns:
            Dictionary with 'answer' and 'sources' keys
        """
        # Get retrieved documents
        docs = self.retriever.invoke(question)

        # Generate answer
        context = format_documents(docs)
        messages = self.prompt.format_messages(context=context, question=question)
        response = self.llm.invoke(messages)
        answer = response.content

        # Format sources
        sources = [
            {
                "doc_type": doc.metadata.get("doc_type"),
                "source": doc.metadata.get("source"),
                "content_preview": doc.page_content[:200] + "..."
                if len(doc.page_content) > 200
                else doc.page_content,
            }
            for doc in docs
        ]

        return {
            "answer": answer,
            "sources": sources,
            "num_sources": len(sources),
        }

    async def aquery(self, question: str) -> str:
        """
        Execute an async query through the RAG chain.

        Args:
            question: User's question

        Returns:
            Generated answer
        """
        return await self.chain.ainvoke(question)

    def stream(self, question: str):
        """
        Stream the response for a query.

        Args:
            question: User's question

        Yields:
            Response chunks
        """
        for chunk in self.chain.stream(question):
            yield chunk


class HybridRAGChain:
    """
    Hybrid RAG chain that combines vector store and knowledge graph retrieval.

    This chain uses:
    - Vector store for semantic search across documents
    - Knowledge graph for relationship traversal and structural queries
    """

    HYBRID_PROMPT_TEMPLATE = """Based on the following context from both document search and knowledge graph traversal,
please answer the question. Use specific details and relationships from the context when available.

DOCUMENT CONTEXT (from semantic search):
{document_context}

GRAPH CONTEXT (from knowledge graph traversal):
{graph_context}

QUESTION:
{question}

ANSWER:"""

    def __init__(
        self,
        vectorstore_manager: VectorStoreManager,
        graph_store: Optional[Any] = None,  # GraphStore type
        project_id: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        top_k: int = 5,
    ):
        """
        Initialize the hybrid RAG chain.

        Args:
            vectorstore_manager: Vector store manager for semantic retrieval
            graph_store: Optional GraphStore for graph-based retrieval
            project_id: Project ID for graph queries
            model_name: OpenAI model name
            temperature: LLM temperature
            max_tokens: Maximum tokens in response
            top_k: Number of documents to retrieve
        """
        self.vectorstore_manager = vectorstore_manager
        self.graph_store = graph_store
        self.project_id = project_id

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model_name or os.getenv("LLM_MODEL", "gpt-4-turbo-preview"),
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Initialize vector retriever
        self.vector_retriever = PlanningRiskRetriever(
            vectorstore_manager=vectorstore_manager,
            top_k=top_k,
        )

        # Initialize graph retriever if available
        self.graph_retriever = None
        self.graph_query_engine = None
        if graph_store and GRAPH_AVAILABLE:
            self.graph_retriever = GraphRetriever(graph_store, project_id)
            self.graph_query_engine = GraphQueryEngine(graph_store)

        # Create prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNING_RISK_SYSTEM_PROMPT),
            ("human", self.HYBRID_PROMPT_TEMPLATE),
        ])

    def _should_use_graph(self, question: str) -> bool:
        """Determine if the question would benefit from graph traversal."""
        if not self.graph_retriever:
            return False

        # Keywords that indicate graph queries would be helpful
        graph_keywords = [
            "predecessor", "successor", "depends", "dependency",
            "before", "after", "path", "trace", "chain", "impact",
            "downstream", "upstream", "drives", "driving",
            "connected", "relationship", "affects", "affected",
            "leads to", "caused by", "critical path",
        ]

        question_lower = question.lower()
        return any(kw in question_lower for kw in graph_keywords)

    def query(self, question: str) -> str:
        """
        Execute a hybrid query through vector and graph retrieval.

        Args:
            question: User's question

        Returns:
            Generated answer
        """
        # Always get vector context
        vector_docs = self.vector_retriever.invoke(question)
        document_context = format_documents(vector_docs)

        # Get graph context if beneficial
        graph_context = "No graph traversal performed."
        if self._should_use_graph(question):
            graph_docs = self.graph_retriever.retrieve(question)
            if graph_docs:
                graph_context = format_documents(graph_docs)

        # Generate response
        messages = self.prompt.format_messages(
            document_context=document_context,
            graph_context=graph_context,
            question=question,
        )
        response = self.llm.invoke(messages)
        return response.content

    def query_with_sources(self, question: str) -> dict[str, Any]:
        """
        Execute a query and return answer with sources from both retrievers.

        Args:
            question: User's question

        Returns:
            Dictionary with answer and sources
        """
        # Get vector context
        vector_docs = self.vector_retriever.invoke(question)
        document_context = format_documents(vector_docs)

        # Get graph context
        graph_docs = []
        graph_context = "No graph traversal performed."
        graph_query_result = None

        if self._should_use_graph(question):
            graph_docs = self.graph_retriever.retrieve(question)
            if graph_docs:
                graph_context = format_documents(graph_docs)
            # Also get structured query result
            if self.graph_query_engine:
                graph_query_result = self.graph_query_engine.execute_query(
                    question, self.project_id
                )

        # Generate response
        messages = self.prompt.format_messages(
            document_context=document_context,
            graph_context=graph_context,
            question=question,
        )
        response = self.llm.invoke(messages)

        # Format sources
        vector_sources = [
            {
                "type": "vector",
                "doc_type": doc.metadata.get("doc_type"),
                "source": doc.metadata.get("source"),
                "content_preview": doc.page_content[:200] + "..."
                if len(doc.page_content) > 200 else doc.page_content,
            }
            for doc in vector_docs
        ]

        graph_sources = [
            {
                "type": "graph",
                "doc_type": doc.metadata.get("doc_type"),
                "source": doc.metadata.get("source"),
                "content_preview": doc.page_content[:200] + "..."
                if len(doc.page_content) > 200 else doc.page_content,
            }
            for doc in graph_docs
        ]

        return {
            "answer": response.content,
            "vector_sources": vector_sources,
            "graph_sources": graph_sources,
            "graph_query": graph_query_result,
            "num_sources": len(vector_sources) + len(graph_sources),
        }

    def trace_schedule(
        self,
        activity_code: str,
        direction: str = "both",
    ) -> dict[str, Any]:
        """
        Trace schedule dependencies for an activity.

        Args:
            activity_code: Activity code to trace
            direction: 'predecessors', 'successors', or 'both'

        Returns:
            Dictionary with traced activities and analysis
        """
        if not self.graph_query_engine:
            return {"error": "Graph store not available"}

        result = {
            "activity_code": activity_code,
            "predecessors": [],
            "successors": [],
            "analysis": "",
        }

        if direction in ["predecessors", "both"]:
            pred_result = self.graph_query_engine.execute_query(
                f"predecessors of {activity_code}",
                self.project_id,
            )
            result["predecessors"] = pred_result.get("data", [])

        if direction in ["successors", "both"]:
            succ_result = self.graph_query_engine.execute_query(
                f"successors of {activity_code}",
                self.project_id,
            )
            result["successors"] = succ_result.get("data", [])

        # Generate analysis
        question = f"Analyze the schedule dependencies for activity {activity_code}. " \
                   f"It has {len(result['predecessors'])} predecessors and {len(result['successors'])} successors."

        result["analysis"] = self.query(question)
        return result

    def analyze_risk_cascade(self, risk_id: str) -> dict[str, Any]:
        """
        Analyze the cascade effect of a risk through the schedule.

        Args:
            risk_id: Risk ID to analyze

        Returns:
            Dictionary with affected activities and analysis
        """
        if not self.graph_query_engine:
            return {"error": "Graph store not available"}

        # Get directly affected activities
        direct_result = self.graph_query_engine.execute_query(
            f"activities affected by risk {risk_id}",
            self.project_id,
        )

        # Get downstream cascade
        cascade_result = self.graph_query_engine.execute_query(
            f"downstream impact of risk {risk_id}",
            self.project_id,
        )

        result = {
            "risk_id": risk_id,
            "directly_affected": direct_result.get("data", []),
            "cascade_affected": cascade_result.get("data", []),
            "analysis": "",
        }

        # Generate analysis
        direct_count = len(result["directly_affected"])
        cascade_count = len(result["cascade_affected"])
        question = f"Analyze risk {risk_id} which directly affects {direct_count} activities " \
                   f"and could cascade to {cascade_count} downstream activities. " \
                   f"What is the potential impact and what mitigation strategies would you recommend?"

        result["analysis"] = self.query(question)
        return result


class ConversationalRAGChain(PlanningRiskRAGChain):
    """
    RAG chain with conversation history support.
    """

    CONVERSATIONAL_PROMPT = """Based on the conversation history and context, answer the question.

CONVERSATION HISTORY:
{history}

CONTEXT FROM DOCUMENTS:
{context}

CURRENT QUESTION:
{question}

ANSWER:"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_history: list[tuple[str, str]] = []

        # Override prompt for conversational use
        self.conversational_prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNING_RISK_SYSTEM_PROMPT),
            ("human", self.CONVERSATIONAL_PROMPT),
        ])

    def _format_history(self) -> str:
        """Format conversation history."""
        if not self.conversation_history:
            return "No previous conversation."

        formatted = []
        for q, a in self.conversation_history[-5:]:  # Keep last 5 turns
            formatted.append(f"Human: {q}")
            formatted.append(f"Assistant: {a[:500]}...")  # Truncate long answers
        return "\n".join(formatted)

    def query(self, question: str) -> str:
        """
        Execute a query with conversation context.

        Args:
            question: User's question

        Returns:
            Generated answer
        """
        # Get retrieved documents
        docs = self.retriever.invoke(question)
        context = format_documents(docs)
        history = self._format_history()

        # Generate response
        messages = self.conversational_prompt.format_messages(
            history=history,
            context=context,
            question=question,
        )
        response = self.llm.invoke(messages)
        answer = response.content

        # Update history
        self.conversation_history.append((question, answer))

        return answer

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []


# Specialized query functions

def analyze_schedule_health(chain: PlanningRiskRAGChain) -> str:
    """Generate a schedule health analysis."""
    return chain.query(
        "Provide a comprehensive analysis of the schedule health including: "
        "critical path status, delayed activities, overall progress, and any concerns."
    )


def analyze_risk_exposure(chain: PlanningRiskRAGChain) -> str:
    """Generate a risk exposure analysis."""
    return chain.query(
        "Provide a comprehensive risk exposure analysis including: "
        "total EMV, critical risks, risk distribution by category, "
        "and top concerns requiring immediate attention."
    )


def get_project_summary(chain: PlanningRiskRAGChain) -> str:
    """Generate a combined project summary."""
    return chain.query(
        "Provide an executive summary of the project including: "
        "schedule status, key milestones, critical risks, "
        "and overall project health assessment."
    )
