"""
FastAPI application for Planning & Risk Intelligence.

Provides REST API endpoints for:
- Uploading and processing P6 schedules and risk registers
- Querying the RAG system
- Getting project insights and analysis
"""

import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.parsers import P6Parser, RiskRegisterParser
from src.rag import DocumentProcessor, PlanningRiskRAGChain, VectorStoreManager

load_dotenv()


# Global state
class AppState:
    vectorstore_manager: Optional[VectorStoreManager] = None
    rag_chain: Optional[PlanningRiskRAGChain] = None
    document_processor: Optional[DocumentProcessor] = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Initialize components on startup
    state.vectorstore_manager = VectorStoreManager()
    state.document_processor = DocumentProcessor()

    # Try to initialize RAG chain if vector store has documents
    try:
        stats = state.vectorstore_manager.get_collection_stats()
        if stats["count"] > 0:
            state.rag_chain = PlanningRiskRAGChain(
                vectorstore_manager=state.vectorstore_manager
            )
            print(f"Loaded existing vector store with {stats['count']} documents")
    except Exception as e:
        print(f"Could not load existing vector store: {e}")

    yield

    # Cleanup on shutdown
    state.vectorstore_manager = None
    state.rag_chain = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Planning & Risk Intelligence API",
        description="RAG-based API for analyzing P6 schedules and risk registers",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
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


class QueryResponse(BaseModel):
    """Response model for queries."""
    answer: str = Field(..., description="Generated answer")
    sources: Optional[list[dict]] = Field(
        None, description="Source documents used for answer"
    )
    num_sources: Optional[int] = Field(None, description="Number of sources used")


class UploadResponse(BaseModel):
    """Response model for file uploads."""
    success: bool
    message: str
    documents_added: int
    file_type: str


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    vector_store_count: int
    rag_chain_ready: bool


class AnalysisResponse(BaseModel):
    """Response model for analysis endpoints."""
    analysis: str
    type: str


# Endpoints

@app.get("/", tags=["General"])
async def root():
    """Root endpoint."""
    return {
        "name": "Planning & Risk Intelligence API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Check API health status."""
    count = 0
    if state.vectorstore_manager:
        try:
            stats = state.vectorstore_manager.get_collection_stats()
            count = stats["count"]
        except Exception:
            pass

    return HealthResponse(
        status="healthy",
        vector_store_count=count,
        rag_chain_ready=state.rag_chain is not None,
    )


@app.post("/upload/schedule", response_model=UploadResponse, tags=["Data Ingestion"])
async def upload_schedule(file: UploadFile = File(...)):
    """
    Upload a P6 schedule file (XER format).

    The file will be parsed and indexed for RAG queries.
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

        # Process into documents
        documents = state.document_processor.process_schedule(
            schedule, source_file=file.filename
        )

        # Add to vector store
        state.vectorstore_manager.add_documents(documents)

        # Initialize/reinitialize RAG chain
        state.rag_chain = PlanningRiskRAGChain(
            vectorstore_manager=state.vectorstore_manager
        )

        # Cleanup
        os.unlink(tmp_path)

        return UploadResponse(
            success=True,
            message=f"Successfully processed schedule: {schedule.project.project_name}",
            documents_added=len(documents),
            file_type="P6 Schedule (XER)",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.post("/upload/risk-register", response_model=UploadResponse, tags=["Data Ingestion"])
async def upload_risk_register(file: UploadFile = File(...)):
    """
    Upload a risk register file (Excel format).

    The file will be parsed and indexed for RAG queries.
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

        # Process into documents
        documents = state.document_processor.process_risk_register(
            risk_register, source_file=file.filename
        )

        # Add to vector store
        state.vectorstore_manager.add_documents(documents)

        # Initialize/reinitialize RAG chain
        state.rag_chain = PlanningRiskRAGChain(
            vectorstore_manager=state.vectorstore_manager
        )

        # Cleanup
        os.unlink(tmp_path)

        return UploadResponse(
            success=True,
            message=f"Successfully processed risk register with {risk_register.total_risks} risks",
            documents_added=len(documents),
            file_type="Risk Register (Excel)",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.post("/query", response_model=QueryResponse, tags=["Query"])
async def query(request: QueryRequest):
    """
    Query the Planning & Risk Intelligence system.

    Ask questions about the project schedule, risks, or get combined insights.
    """
    if not state.rag_chain:
        raise HTTPException(
            status_code=400,
            detail="No data loaded. Please upload a schedule or risk register first.",
        )

    try:
        if request.include_sources:
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


@app.get("/analysis/schedule-health", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_schedule():
    """Get a comprehensive schedule health analysis."""
    if not state.rag_chain:
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        analysis = state.rag_chain.query(
            "Provide a comprehensive analysis of the schedule health including: "
            "critical path status, delayed activities, overall progress, and any concerns."
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
            "schedule status, key milestones, critical risks, "
            "and overall project health assessment."
        )
        return AnalysisResponse(analysis=analysis, type="executive_summary")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/data", tags=["Data Management"])
async def clear_data():
    """Clear all indexed data and reset the system."""
    try:
        if state.vectorstore_manager:
            state.vectorstore_manager.delete_collection()

        # Reinitialize
        state.vectorstore_manager = VectorStoreManager()
        state.rag_chain = None

        return {"success": True, "message": "All data cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", tags=["Data Management"])
async def get_stats():
    """Get statistics about the indexed data."""
    if not state.vectorstore_manager:
        return {"documents": 0, "rag_ready": False}

    try:
        stats = state.vectorstore_manager.get_collection_stats()
        return {
            "documents": stats["count"],
            "collection_name": stats["name"],
            "rag_ready": state.rag_chain is not None,
        }
    except Exception as e:
        return {"documents": 0, "rag_ready": False, "error": str(e)}


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
