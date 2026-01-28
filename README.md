# Planning & Risk Intelligence

A RAG (Retrieval-Augmented Generation) system with **Knowledge Graph** capabilities for intelligent analysis of P6 project schedules and risk registers.

## Overview

Planning & Risk Intelligence combines vector-based semantic search with Neo4j knowledge graph traversal to enable project managers to:

- **Query project data** using natural language
- **Trace schedule dependencies** through predecessor/successor relationships
- **Analyze risk cascade effects** through the schedule
- **Understand critical path** and delay impacts

### Key Features

| Feature | Description |
|---------|-------------|
| **P6 Schedule Parsing** | Import Primavera P6 XER files with activities, WBS, relationships, resources |
| **Risk Register Parsing** | Import Excel-based risk registers with flexible column mapping |
| **Vector Store (ChromaDB)** | Semantic search across schedule and risk documents |
| **Knowledge Graph (Neo4j)** | Traverse schedule relationships and trace dependencies |
| **Hybrid RAG** | Combines vector search with graph traversal for comprehensive answers |
| **Schedule Tracing** | Follow predecessor/successor chains to understand impacts |
| **Risk Cascade Analysis** | See how risks propagate through the schedule |

## Architecture

```
┌──────────────────┐     ┌──────────────────┐
│   P6 Schedule    │     │  Risk Register   │
│   (.xer file)    │     │  (.xlsx file)    │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         ▼                        ▼
┌──────────────────────────────────────────┐
│            Data Parsers                   │
│  (P6Parser, RiskRegisterParser)          │
└──────────────────┬───────────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
┌─────────────────┐  ┌─────────────────┐
│  Vector Store   │  │ Knowledge Graph │
│   (ChromaDB)    │  │    (Neo4j)      │
│                 │  │                 │
│ - Documents     │  │ - Nodes:        │
│ - Embeddings    │  │   • Project     │
│ - Semantic      │  │   • Activity    │
│   Search        │  │   • WBS         │
│                 │  │   • Risk        │
│                 │  │   • Resource    │
│                 │  │                 │
│                 │  │ - Relationships:│
│                 │  │   • PRECEDES    │
│                 │  │   • AFFECTS     │
│                 │  │   • CONTAINS    │
└────────┬────────┘  └────────┬────────┘
         │                    │
         └─────────┬──────────┘
                   ▼
         ┌─────────────────────┐
         │   Hybrid RAG Chain  │
         │                     │
         │ - Vector Retrieval  │
         │ - Graph Traversal   │
         │ - LLM Generation    │
         └──────────┬──────────┘
                    ▼
         ┌─────────────────────┐
         │   API / CLI         │
         │   (User Interface)  │
         └─────────────────────┘
```

## Installation

### Prerequisites

- Python 3.10 or higher
- OpenAI API key (for embeddings and LLM)
- Neo4j database (optional, for knowledge graph features)

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
# Edit .env and configure:
# - OPENAI_API_KEY (required)
# - NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD (for graph features)
```

### Neo4j Setup (Optional but Recommended)

For full knowledge graph capabilities, install Neo4j:

**Option 1: Docker**
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest
```

**Option 2: Neo4j Desktop**
Download from [neo4j.com](https://neo4j.com/download/) and create a local database.

Update your `.env`:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
```

## Quick Start

### 1. Ingest Data

```bash
# Ingest a P6 schedule (loads to both vector store and graph)
pri-ingest --schedule path/to/schedule.xer

# Ingest a risk register
pri-ingest --risk-register path/to/risks.xlsx

# Ingest both
pri-ingest --schedule schedule.xer --risk-register risks.xlsx
```

### 2. Query via CLI

```bash
# Basic query
pri-query "What activities are on the critical path?"

# Schedule tracing queries (uses knowledge graph)
pri-query "What are the predecessors of activity A3000?"
pri-query "What is the downstream impact if A2000 is delayed?"

# Risk queries
pri-query "What risks affect the critical path?"
pri-query "What is the cascade effect of risk R001?"

# Interactive mode
pri-query --interactive
```

### 3. Run the API Server

```bash
pri-server
# Or
uvicorn src.api.main:app --reload
```

Visit `http://localhost:8000/docs` for the interactive API documentation.

## Knowledge Graph Schema

The Neo4j knowledge graph models project data as:

### Nodes

| Node Type | Description |
|-----------|-------------|
| `Project` | Project container with dates and progress |
| `WBS` | Work Breakdown Structure elements |
| `Activity` | Schedule activities/tasks |
| `Milestone` | Project milestones |
| `Risk` | Risk register entries |
| `RiskCategory` | Risk category groupings |
| `Resource` | Project resources |
| `Calendar` | Work calendars |

### Relationships

| Relationship | Description |
|--------------|-------------|
| `CONTAINS` | Hierarchical containment (Project→WBS→Activity) |
| `PRECEDES` | Schedule logic (Activity→Activity) |
| `FINISH_TO_START` | FS relationship with lag |
| `FINISH_TO_FINISH` | FF relationship |
| `START_TO_START` | SS relationship |
| `AFFECTS` | Risk impacts activity |
| `ON_CRITICAL_PATH` | Activity is on critical path |
| `DELAYED_FROM_BASELINE` | Activity is delayed |
| `USES` | Activity uses resource |
| `BELONGS_TO` | Risk belongs to category |

## API Endpoints

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload/schedule` | Upload P6 schedule (XER) |
| POST | `/upload/risk-register` | Upload risk register (Excel) |
| POST | `/query` | Query with hybrid RAG |
| GET | `/health` | Health check with graph status |

### Knowledge Graph Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/graph/query` | Execute graph-specific query |
| GET | `/graph/trace/{activity_code}` | Trace activity dependencies |
| GET | `/graph/risk-cascade/{risk_id}` | Analyze risk cascade effect |
| GET | `/graph/critical-path` | Get critical path from graph |
| GET | `/graph/stats` | Get graph statistics |

### Analysis Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analysis/schedule-health` | Schedule health analysis |
| GET | `/analysis/risk-exposure` | Risk exposure analysis |
| GET | `/analysis/executive-summary` | Executive summary |

## Usage Examples

### Trace Schedule Dependencies

```python
import requests

# Trace predecessors and successors
response = requests.get(
    "http://localhost:8000/graph/trace/A3000",
    params={"direction": "both"}
)
result = response.json()
print(f"Predecessors: {len(result['predecessors'])}")
print(f"Successors: {len(result['successors'])}")
print(f"Analysis: {result['analysis']}")
```

### Analyze Risk Cascade

```python
# See how a risk cascades through the schedule
response = requests.get("http://localhost:8000/graph/risk-cascade/R001")
result = response.json()
print(f"Directly affected: {len(result['directly_affected'])} activities")
print(f"Cascade affected: {len(result['cascade_affected'])} activities")
```

### Query with Graph Traversal

```python
response = requests.post(
    "http://localhost:8000/query",
    json={
        "question": "What is the impact chain if activity A2000 is delayed by 2 weeks?",
        "include_sources": True,
        "use_graph": True
    }
)
result = response.json()
print(result["answer"])
```

### Python API with Graph

```python
from src.parsers import P6Parser, RiskRegisterParser
from src.rag import DocumentProcessor, VectorStoreManager, HybridRAGChain
from src.graph import GraphStore, GraphDataLoader

# Parse data
schedule = P6Parser().parse("schedule.xer")
risk_register = RiskRegisterParser().parse_file("risks.xlsx")

# Load to vector store
processor = DocumentProcessor()
vectorstore = VectorStoreManager()
docs = processor.process_schedule(schedule, "schedule.xer")
docs += processor.process_risk_register(risk_register, "risks.xlsx")
vectorstore.add_documents(docs)

# Load to knowledge graph
graph_store = GraphStore()
graph_store.initialize_schema()
loader = GraphDataLoader(graph_store)
loader.load_schedule(schedule)
loader.load_risk_register(risk_register, schedule.project.project_id)

# Create hybrid chain
chain = HybridRAGChain(
    vectorstore_manager=vectorstore,
    graph_store=graph_store,
    project_id=schedule.project.project_id,
)

# Query with graph traversal
answer = chain.query("What is the downstream impact if A2000 is delayed?")
print(answer)

# Trace schedule
trace = chain.trace_schedule("A3000", direction="both")
print(f"Predecessors: {len(trace['predecessors'])}")
print(f"Analysis: {trace['analysis']}")

# Analyze risk cascade
cascade = chain.analyze_risk_cascade("R001")
print(f"Cascade impact: {len(cascade['cascade_affected'])} activities")
```

## Project Structure

```
Planning-Risk-Intelligent/
├── src/
│   ├── models/           # Data models
│   │   ├── schedule.py   # P6 schedule models
│   │   └── risk.py       # Risk register models
│   ├── parsers/          # Data parsers
│   │   ├── p6_parser.py  # P6/XER file parser
│   │   └── risk_register.py
│   ├── graph/            # Knowledge graph components
│   │   ├── schema.py     # Neo4j schema & Cypher templates
│   │   ├── store.py      # Graph store manager
│   │   ├── loader.py     # Data loader for graph
│   │   └── retriever.py  # Graph-based retrieval
│   ├── rag/              # RAG components
│   │   ├── document_processor.py
│   │   ├── vectorstore.py
│   │   ├── retriever.py
│   │   └── chain.py      # Includes HybridRAGChain
│   ├── api/main.py       # FastAPI application
│   └── cli.py            # Command-line interface
├── data/sample/          # Sample data files
├── tests/                # Test files
└── README.md
```

## Configuration

Environment variables (set in `.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USERNAME` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | Required for graph |
| `NEO4J_DATABASE` | Neo4j database name | `neo4j` |
| `CHROMA_PERSIST_DIRECTORY` | Vector store location | `./data/chroma_db` |
| `LLM_MODEL` | OpenAI model | `gpt-4-turbo-preview` |
| `EMBEDDING_MODEL` | Embedding model | `text-embedding-3-small` |

## Graph Query Types

The system understands various query patterns:

| Query Pattern | Example |
|--------------|---------|
| Critical Path | "What activities are on the critical path?" |
| Predecessors | "What are the predecessors of A3000?" |
| Successors | "What activities come after A2000?" |
| Trace Path | "Trace the path from A1000 to A4000" |
| Delay Impact | "What is impacted if A2000 is delayed?" |
| Risk Impact | "What activities are affected by risk R001?" |
| Downstream | "What is the downstream impact of R002?" |
| High-Risk Critical | "Which critical activities have high risk?" |

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

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting a pull request.
