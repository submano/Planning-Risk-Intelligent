"""
RAG Chain for Planning & Risk Intelligence.

Implements the complete RAG pipeline combining retrieval and generation
for answering questions about project schedules and risks.
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


# System prompts for different query types
PLANNING_RISK_SYSTEM_PROMPT = """You are an expert Project Planning and Risk Intelligence Assistant.
You have deep knowledge of project management, scheduling (particularly Primavera P6), and risk management.

Your role is to:
1. Analyze project schedule data and identify potential issues
2. Evaluate risks and their impacts on the project
3. Provide actionable insights and recommendations
4. Answer questions accurately based on the provided context

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

When discussing risks:
- Reference risks by their IDs and titles
- Consider probability, impact, and overall risk score
- Discuss mitigation strategies when relevant
- Consider the expected monetary value (EMV) and schedule impacts
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
