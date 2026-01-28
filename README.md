# Planning & Risk Intelligence

A RAG (Retrieval-Augmented Generation) system for intelligent analysis of P6 project schedules and risk registers.

## Overview

Planning & Risk Intelligence enables project managers and teams to query their project data using natural language. The system:

- **Parses P6 Schedules**: Imports Primavera P6 XER files including activities, WBS, relationships, resources, and calendars
- **Parses Risk Registers**: Imports Excel-based risk registers with flexible column mapping
- **Intelligent Retrieval**: Uses semantic search to find relevant information across schedule and risk data
- **AI-Powered Analysis**: Generates insights, answers questions, and provides recommendations

## Features

- **Natural Language Queries**: Ask questions like "What activities are on the critical path?" or "What are the top risks affecting the schedule?"
- **Schedule Analysis**: Critical path identification, delay detection, progress tracking
- **Risk Analysis**: Risk scoring, EMV calculation, mitigation plan tracking
- **Combined Intelligence**: Understand how risks relate to schedule activities
- **REST API**: FastAPI-based API for integration with other tools
- **CLI Interface**: Command-line tools for data ingestion and queries

## Installation

### Prerequisites

- Python 3.10 or higher
- OpenAI API key (for embeddings and LLM)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Planning-Risk-Intelligent.git
cd Planning-Risk-Intelligent
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
# Or for development:
pip install -e ".[dev]"
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

## Quick Start

### 1. Ingest Data

```bash
# Ingest a P6 schedule
pri-ingest --schedule path/to/schedule.xer

# Ingest a risk register
pri-ingest --risk-register path/to/risks.xlsx

# Ingest both
pri-ingest --schedule schedule.xer --risk-register risks.xlsx
```

### 2. Query via CLI

```bash
# Single query
pri-query "What activities are on the critical path?"

# Interactive mode
pri-query --interactive

# Show source documents
pri-query --sources "What are the top 5 risks?"
```

### 3. Run the API Server

```bash
pri-server
# Or
uvicorn src.api.main:app --reload
```

Then visit `http://localhost:8000/docs` for the interactive API documentation.

## Usage Examples

### CLI Queries

```bash
# Schedule queries
pri-query "What is the overall project status?"
pri-query "Which activities are delayed?"
pri-query "What are the key milestones?"

# Risk queries
pri-query "What are the critical risks?"
pri-query "What is the total expected monetary value of risks?"
pri-query "Show me the mitigation plan for resource risks"

# Combined queries
pri-query "What risks could affect the critical path?"
pri-query "Give me an executive summary of the project"
```

### API Usage

```python
import requests

# Upload a schedule
with open("schedule.xer", "rb") as f:
    response = requests.post(
        "http://localhost:8000/upload/schedule",
        files={"file": f}
    )

# Query the system
response = requests.post(
    "http://localhost:8000/query",
    json={
        "question": "What are the top risks?",
        "include_sources": True
    }
)
print(response.json()["answer"])
```

### Python API

```python
from src.parsers import P6Parser, RiskRegisterParser
from src.rag import DocumentProcessor, VectorStoreManager, PlanningRiskRAGChain

# Parse data
schedule = P6Parser().parse("schedule.xer")
risk_register = RiskRegisterParser().parse_file("risks.xlsx")

# Process into documents
processor = DocumentProcessor()
docs = processor.process_schedule(schedule, "schedule.xer")
docs += processor.process_risk_register(risk_register, "risks.xlsx")

# Create vector store
vectorstore = VectorStoreManager()
vectorstore.add_documents(docs)

# Query
chain = PlanningRiskRAGChain(vectorstore_manager=vectorstore)
answer = chain.query("What is the project status?")
print(answer)
```

## Project Structure

```
Planning-Risk-Intelligent/
├── src/
│   ├── models/           # Data models for schedule and risk
│   │   ├── schedule.py   # P6 schedule models
│   │   └── risk.py       # Risk register models
│   ├── parsers/          # Data parsers
│   │   ├── p6_parser.py  # P6/XER file parser
│   │   └── risk_register.py  # Excel risk register parser
│   ├── rag/              # RAG components
│   │   ├── document_processor.py  # Convert data to documents
│   │   ├── vectorstore.py  # Vector store management
│   │   ├── retriever.py    # Custom retrieval logic
│   │   └── chain.py        # RAG chain implementation
│   ├── api/              # FastAPI application
│   │   └── main.py       # API endpoints
│   └── cli.py            # Command-line interface
├── data/
│   └── sample/           # Sample data files
├── tests/                # Test files
├── scripts/              # Utility scripts
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project configuration
└── README.md
```

## Configuration

Environment variables (set in `.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `CHROMA_PERSIST_DIRECTORY` | Vector store location | `./data/chroma_db` |
| `COLLECTION_NAME` | Vector store collection name | `planning_risk_intelligence` |
| `EMBEDDING_MODEL` | OpenAI embedding model | `text-embedding-3-small` |
| `LLM_MODEL` | OpenAI LLM model | `gpt-4-turbo-preview` |
| `LLM_TEMPERATURE` | LLM temperature | `0.1` |
| `TOP_K_RESULTS` | Number of documents to retrieve | `5` |
| `API_HOST` | API server host | `0.0.0.0` |
| `API_PORT` | API server port | `8000` |

## Supported File Formats

### P6 Schedule
- `.xer` - Primavera P6 XER export format

### Risk Register
- `.xlsx` - Excel workbook
- `.xls` - Legacy Excel format

The risk register parser supports flexible column mapping. Common column names are automatically detected:
- Risk ID: `risk_id`, `id`, `risk #`, etc.
- Title: `title`, `risk title`, `name`, etc.
- Description: `description`, `details`, etc.
- Category: `category`, `risk category`, `type`, etc.
- And many more (see `src/parsers/risk_register.py` for full mapping)

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

```bash
black src/ tests/
ruff check src/ tests/
```

### Type Checking

```bash
mypy src/
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| POST | `/upload/schedule` | Upload P6 schedule |
| POST | `/upload/risk-register` | Upload risk register |
| POST | `/query` | Query the RAG system |
| GET | `/analysis/schedule-health` | Get schedule health analysis |
| GET | `/analysis/risk-exposure` | Get risk exposure analysis |
| GET | `/analysis/executive-summary` | Get executive summary |
| DELETE | `/data` | Clear all indexed data |
| GET | `/stats` | Get vector store statistics |

## Architecture

```
┌──────────────────┐     ┌──────────────────┐
│   P6 Schedule    │     │  Risk Register   │
│   (.xer file)    │     │  (.xlsx file)    │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐     ┌──────────────────┐
│   P6 Parser      │     │ Risk Parser      │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         └───────────┬────────────┘
                     ▼
         ┌──────────────────────┐
         │  Document Processor  │
         │  (Text Documents)    │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │   Vector Store       │
         │   (ChromaDB)         │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │   RAG Chain          │
         │   (LangChain + GPT)  │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │   API / CLI          │
         │   (User Interface)   │
         └──────────────────────┘
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting a pull request.
