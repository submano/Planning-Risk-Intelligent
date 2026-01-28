"""
FastAPI application for Planning & Risk Intelligence.

Provides REST API endpoints for:
- Uploading and processing P6 schedules and risk registers
- Querying the RAG system (vector and graph-based)
- Getting project insights and analysis
- Tracing schedule dependencies via knowledge graph
"""

import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.parsers import P6Parser, RiskRegisterParser
from src.rag import DocumentProcessor, PlanningRiskRAGChain, HybridRAGChain, VectorStoreManager

# Optional graph imports
try:
    from src.graph import GraphStore, GraphDataLoader, GraphRetriever, GraphQueryEngine
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False

load_dotenv()


# Global state
class AppState:
    vectorstore_manager: Optional[VectorStoreManager] = None
    rag_chain: Optional[PlanningRiskRAGChain] = None
    hybrid_chain: Optional[HybridRAGChain] = None
    document_processor: Optional[DocumentProcessor] = None
    graph_store: Optional[Any] = None  # GraphStore
    graph_loader: Optional[Any] = None  # GraphDataLoader
    graph_query_engine: Optional[Any] = None  # GraphQueryEngine
    current_project_id: Optional[str] = None


state = AppState()


def init_graph_store() -> bool:
    """Initialize the graph store connection."""
    if not GRAPH_AVAILABLE:
        return False

    try:
        state.graph_store = GraphStore()
        if state.graph_store.verify_connectivity():
            state.graph_loader = GraphDataLoader(state.graph_store)
            state.graph_query_engine = GraphQueryEngine(state.graph_store)
            state.graph_store.initialize_schema()
            print("Neo4j graph store connected and initialized")
            return True
        else:
            print("Could not connect to Neo4j")
            state.graph_store = None
            return False
    except Exception as e:
        print(f"Neo4j initialization failed: {e}")
        state.graph_store = None
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Initialize vector store components
    state.vectorstore_manager = VectorStoreManager()
    state.document_processor = DocumentProcessor()

    # Try to initialize graph store
    graph_available = init_graph_store()

    # Try to initialize RAG chain if vector store has documents
    try:
        stats = state.vectorstore_manager.get_collection_stats()
        if stats["count"] > 0:
            # Initialize hybrid chain if graph is available
            if graph_available:
                state.hybrid_chain = HybridRAGChain(
                    vectorstore_manager=state.vectorstore_manager,
                    graph_store=state.graph_store,
                    project_id=state.current_project_id,
                )
                state.rag_chain = state.hybrid_chain
                print(f"Loaded hybrid RAG with {stats['count']} documents and graph store")
            else:
                state.rag_chain = PlanningRiskRAGChain(
                    vectorstore_manager=state.vectorstore_manager
                )
                print(f"Loaded vector RAG with {stats['count']} documents")
    except Exception as e:
        print(f"Could not initialize RAG chain: {e}")

    yield

    # Cleanup on shutdown
    state.vectorstore_manager = None
    state.rag_chain = None
    state.hybrid_chain = None
    if state.graph_store:
        state.graph_store.close()
        state.graph_store = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Planning & Risk Intelligence API",
        description="RAG and Knowledge Graph API for analyzing P6 schedules and risk registers",
        version="0.2.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()


# Request/Response Models
class QueryRequest(BaseModel):
    """Request model for queries."""
    question: str = Field(..., description="Question to ask about the project")
    include_sources: bool = Field(
        default=False, description="Include source documents in response"
    )
    use_graph: bool = Field(
        default=True, description="Use knowledge graph for traversal queries"
    )


class QueryResponse(BaseModel):
    """Response model for queries."""
    answer: str = Field(..., description="Generated answer")
    sources: Optional[list[dict]] = Field(
        None, description="Source documents used for answer"
    )
    graph_sources: Optional[list[dict]] = Field(
        None, description="Graph-based sources"
    )
    num_sources: Optional[int] = Field(None, description="Number of sources used")


class UploadResponse(BaseModel):
    """Response model for file uploads."""
    success: bool
    message: str
    documents_added: int
    graph_nodes_created: Optional[int] = None
    file_type: str


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    vector_store_count: int
    rag_chain_ready: bool
    graph_available: bool
    graph_node_count: Optional[int] = None


class AnalysisResponse(BaseModel):
    """Response model for analysis endpoints."""
    analysis: str
    type: str


class GraphQueryRequest(BaseModel):
    """Request model for graph-specific queries."""
    query_type: str = Field(..., description="Type of graph query")
    activity_code: Optional[str] = Field(None, description="Activity code for queries")
    risk_id: Optional[str] = Field(None, description="Risk ID for queries")
    parameters: Optional[dict] = Field(None, description="Additional parameters")


class GraphQueryResponse(BaseModel):
    """Response model for graph queries."""
    query_type: str
    summary: str
    data: Optional[Any] = None
    analysis: Optional[str] = None


class TraceResponse(BaseModel):
    """Response for schedule trace queries."""
    activity_code: str
    predecessors: list[dict]
    successors: list[dict]
    analysis: str


class RiskCascadeResponse(BaseModel):
    """Response for risk cascade analysis."""
    risk_id: str
    directly_affected: list[dict]
    cascade_affected: list[dict]
    analysis: str


# Endpoints

@app.get("/", tags=["General"])
async def root():
    """Root endpoint."""
    return {
        "name": "Planning & Risk Intelligence API",
        "version": "0.2.0",
        "features": {
            "vector_store": True,
            "knowledge_graph": GRAPH_AVAILABLE and state.graph_store is not None,
        },
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Check API health status."""
    vector_count = 0
    graph_count = None

    if state.vectorstore_manager:
        try:
            stats = state.vectorstore_manager.get_collection_stats()
            vector_count = stats["count"]
        except Exception:
            pass

    if state.graph_store:
        try:
            graph_stats = state.graph_store.get_stats()
            graph_count = graph_stats.get("total_nodes", 0)
        except Exception:
            pass

    return HealthResponse(
        status="healthy",
        vector_store_count=vector_count,
        rag_chain_ready=state.rag_chain is not None,
        graph_available=state.graph_store is not None,
        graph_node_count=graph_count,
    )


@app.post("/upload/schedule", response_model=UploadResponse, tags=["Data Ingestion"])
async def upload_schedule(
    file: UploadFile = File(...),
    load_to_graph: bool = Query(True, description="Also load data into knowledge graph"),
):
    """
    Upload a P6 schedule file (XER format).

    The file will be parsed and indexed for both vector and graph-based queries.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    if not file.filename.lower().endswith(".xer"):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Please upload a .xer file"
        )

    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xer") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Parse the schedule
        parser = P6Parser()
        schedule = parser.parse(tmp_path)

        # Store project ID
        state.current_project_id = schedule.project.project_id

        # Process into documents for vector store
        documents = state.document_processor.process_schedule(
            schedule, source_file=file.filename
        )
        state.vectorstore_manager.add_documents(documents)

        # Load into graph if available and requested
        graph_nodes = None
        if load_to_graph and state.graph_loader:
            try:
                graph_stats = state.graph_loader.load_schedule(schedule)
                graph_nodes = sum(graph_stats.values())
            except Exception as e:
                print(f"Warning: Could not load to graph: {e}")

        # Initialize/reinitialize RAG chain
        if state.graph_store:
            state.hybrid_chain = HybridRAGChain(
                vectorstore_manager=state.vectorstore_manager,
                graph_store=state.graph_store,
                project_id=state.current_project_id,
            )
            state.rag_chain = state.hybrid_chain
        else:
            state.rag_chain = PlanningRiskRAGChain(
                vectorstore_manager=state.vectorstore_manager
            )

        # Cleanup
        os.unlink(tmp_path)

        return UploadResponse(
            success=True,
            message=f"Successfully processed schedule: {schedule.project.project_name}",
            documents_added=len(documents),
            graph_nodes_created=graph_nodes,
            file_type="P6 Schedule (XER)",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.post("/upload/risk-register", response_model=UploadResponse, tags=["Data Ingestion"])
async def upload_risk_register(
    file: UploadFile = File(...),
    load_to_graph: bool = Query(True, description="Also load data into knowledge graph"),
):
    """
    Upload a risk register file (Excel format).

    The file will be parsed and indexed for both vector and graph-based queries.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    valid_extensions = [".xlsx", ".xls"]
    if not any(file.filename.lower().endswith(ext) for ext in valid_extensions):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an Excel file (.xlsx or .xls)",
        )

    try:
        # Save uploaded file temporarily
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Parse the risk register
        parser = RiskRegisterParser()
        risk_register = parser.parse_file(tmp_path)

        # Process into documents for vector store
        documents = state.document_processor.process_risk_register(
            risk_register, source_file=file.filename
        )
        state.vectorstore_manager.add_documents(documents)

        # Load into graph if available and requested
        graph_nodes = None
        if load_to_graph and state.graph_loader:
            try:
                graph_stats = state.graph_loader.load_risk_register(
                    risk_register,
                    project_id=state.current_project_id,
                )
                graph_nodes = sum(graph_stats.values())
            except Exception as e:
                print(f"Warning: Could not load to graph: {e}")

        # Initialize/reinitialize RAG chain
        if state.graph_store:
            state.hybrid_chain = HybridRAGChain(
                vectorstore_manager=state.vectorstore_manager,
                graph_store=state.graph_store,
                project_id=state.current_project_id,
            )
            state.rag_chain = state.hybrid_chain
        else:
            state.rag_chain = PlanningRiskRAGChain(
                vectorstore_manager=state.vectorstore_manager
            )

        # Cleanup
        os.unlink(tmp_path)

        return UploadResponse(
            success=True,
            message=f"Successfully processed risk register with {risk_register.total_risks} risks",
            documents_added=len(documents),
            graph_nodes_created=graph_nodes,
            file_type="Risk Register (Excel)",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.post("/query", response_model=QueryResponse, tags=["Query"])
async def query(request: QueryRequest):
    """
    Query the Planning & Risk Intelligence system.

    Uses both vector store and knowledge graph for comprehensive answers.
    """
    if not state.rag_chain:
        raise HTTPException(
            status_code=400,
            detail="No data loaded. Please upload a schedule or risk register first.",
        )

    try:
        if request.include_sources and isinstance(state.rag_chain, HybridRAGChain):
            result = state.rag_chain.query_with_sources(request.question)
            return QueryResponse(
                answer=result["answer"],
                sources=result.get("vector_sources"),
                graph_sources=result.get("graph_sources"),
                num_sources=result["num_sources"],
            )
        elif request.include_sources:
            result = state.rag_chain.query_with_sources(request.question)
            return QueryResponse(
                answer=result["answer"],
                sources=result["sources"],
                num_sources=result["num_sources"],
            )
        else:
            answer = state.rag_chain.query(request.question)
            return QueryResponse(answer=answer)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


# Graph-specific endpoints

@app.post("/graph/query", response_model=GraphQueryResponse, tags=["Knowledge Graph"])
async def graph_query(request: GraphQueryRequest):
    """
    Execute a graph-specific query for schedule traversal.

    Supported query types:
    - critical_path: Get all critical path activities
    - predecessors: Get predecessors of an activity
    - successors: Get successors of an activity
    - risks_for_activity: Get risks affecting an activity
    - activities_for_risk: Get activities affected by a risk
    - delay_impact: Analyze delay impact chain
    """
    if not state.graph_query_engine:
        raise HTTPException(
            status_code=400,
            detail="Knowledge graph not available. Please ensure Neo4j is configured.",
        )

    try:
        # Build query based on type
        query_map = {
            "critical_path": "critical path activities",
            "predecessors": f"predecessors of {request.activity_code}",
            "successors": f"successors of {request.activity_code}",
            "risks_for_activity": f"risks affecting activity {request.activity_code}",
            "activities_for_risk": f"activities affected by risk {request.risk_id}",
            "delay_impact": f"delay impact of {request.activity_code}",
            "downstream_impact": f"downstream impact of risk {request.risk_id}",
        }

        query_text = query_map.get(request.query_type, request.query_type)
        result = state.graph_query_engine.execute_query(
            query_text,
            state.current_project_id,
        )

        # Generate analysis if we have a hybrid chain
        analysis = None
        if state.hybrid_chain and result.get("data"):
            analysis = state.hybrid_chain.query(
                f"Based on the graph query result showing {result['summary']}, "
                f"provide analysis and recommendations."
            )

        return GraphQueryResponse(
            query_type=result["query_type"],
            summary=result["summary"],
            data=result["data"],
            analysis=analysis,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph query error: {str(e)}")


@app.get("/graph/trace/{activity_code}", response_model=TraceResponse, tags=["Knowledge Graph"])
async def trace_activity(
    activity_code: str,
    direction: str = Query("both", description="Direction: predecessors, successors, or both"),
):
    """
    Trace schedule dependencies for an activity.

    Returns predecessor and successor chains with AI analysis.
    """
    if not state.hybrid_chain:
        raise HTTPException(
            status_code=400,
            detail="Hybrid RAG chain not available.",
        )

    try:
        result = state.hybrid_chain.trace_schedule(activity_code, direction)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return TraceResponse(
            activity_code=activity_code,
            predecessors=result.get("predecessors", []),
            successors=result.get("successors", []),
            analysis=result.get("analysis", ""),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trace error: {str(e)}")


@app.get("/graph/risk-cascade/{risk_id}", response_model=RiskCascadeResponse, tags=["Knowledge Graph"])
async def analyze_risk_cascade(risk_id: str):
    """
    Analyze the cascade effect of a risk through the schedule.

    Shows directly affected activities and downstream cascade impact.
    """
    if not state.hybrid_chain:
        raise HTTPException(
            status_code=400,
            detail="Hybrid RAG chain not available.",
        )

    try:
        result = state.hybrid_chain.analyze_risk_cascade(risk_id)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return RiskCascadeResponse(
            risk_id=risk_id,
            directly_affected=result.get("directly_affected", []),
            cascade_affected=result.get("cascade_affected", []),
            analysis=result.get("analysis", ""),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk cascade analysis error: {str(e)}")


@app.get("/graph/critical-path", tags=["Knowledge Graph"])
async def get_critical_path():
    """Get all activities on the critical path from the knowledge graph."""
    if not state.graph_store:
        raise HTTPException(status_code=400, detail="Knowledge graph not available")

    try:
        result = state.graph_store.get_critical_path(state.current_project_id or "")
        return {
            "count": len(result),
            "activities": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/stats", tags=["Knowledge Graph"])
async def get_graph_stats():
    """Get knowledge graph statistics."""
    if not state.graph_store:
        return {
            "available": False,
            "message": "Knowledge graph not configured",
        }

    try:
        stats = state.graph_store.get_stats()
        return {
            "available": True,
            "nodes": stats.get("nodes", {}),
            "relationships": stats.get("relationships", {}),
            "total_nodes": stats.get("total_nodes", 0),
            "total_relationships": stats.get("total_relationships", 0),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


# Analysis endpoints

@app.get("/analysis/schedule-health", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_schedule():
    """Get a comprehensive schedule health analysis."""
    if not state.rag_chain:
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        analysis = state.rag_chain.query(
            "Provide a comprehensive analysis of the schedule health including: "
            "critical path status, delayed activities, overall progress, "
            "predecessor/successor relationships, and any concerns."
        )
        return AnalysisResponse(analysis=analysis, type="schedule_health")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/risk-exposure", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_risks():
    """Get a comprehensive risk exposure analysis."""
    if not state.rag_chain:
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        analysis = state.rag_chain.query(
            "Provide a comprehensive risk exposure analysis including: "
            "total EMV, critical risks, risk distribution by category, "
            "which activities are affected by risks, "
            "and top concerns requiring immediate attention."
        )
        return AnalysisResponse(analysis=analysis, type="risk_exposure")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/executive-summary", response_model=AnalysisResponse, tags=["Analysis"])
async def executive_summary():
    """Get an executive summary of the project."""
    if not state.rag_chain:
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        analysis = state.rag_chain.query(
            "Provide an executive summary of the project including: "
            "schedule status, critical path, key milestones, critical risks, "
            "risk-schedule interactions, and overall project health assessment."
        )
        return AnalysisResponse(analysis=analysis, type="executive_summary")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Data management endpoints

@app.delete("/data", tags=["Data Management"])
async def clear_data():
    """Clear all indexed data from both vector store and graph."""
    try:
        if state.vectorstore_manager:
            state.vectorstore_manager.delete_collection()

        if state.graph_store:
            state.graph_store.clear_database()
            state.graph_store.initialize_schema()

        # Reinitialize
        state.vectorstore_manager = VectorStoreManager()
        state.rag_chain = None
        state.hybrid_chain = None
        state.current_project_id = None

        return {"success": True, "message": "All data cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", tags=["Data Management"])
async def get_stats():
    """Get statistics about all indexed data."""
    result = {
        "vector_store": {"documents": 0},
        "graph_store": {"available": False},
        "rag_ready": state.rag_chain is not None,
        "hybrid_mode": state.hybrid_chain is not None,
    }

    if state.vectorstore_manager:
        try:
            stats = state.vectorstore_manager.get_collection_stats()
            result["vector_store"] = {
                "documents": stats["count"],
                "collection_name": stats["name"],
            }
        except Exception as e:
            result["vector_store"]["error"] = str(e)

    if state.graph_store:
        try:
            graph_stats = state.graph_store.get_stats()
            result["graph_store"] = {
                "available": True,
                "total_nodes": graph_stats.get("total_nodes", 0),
                "total_relationships": graph_stats.get("total_relationships", 0),
                "nodes_by_type": graph_stats.get("nodes", {}),
            }
        except Exception as e:
            result["graph_store"] = {"available": False, "error": str(e)}

    return result


def run_server():
    """Run the FastAPI server."""
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=True,
    )


if __name__ == "__main__":
    run_server()
