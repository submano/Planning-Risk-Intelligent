# Planning & Risk Intelligence - Usage Guide

This guide provides step-by-step instructions for using the Planning & Risk Intelligence system to analyze P6 schedules and risk registers.

---

## Table of Contents

1. [Installation & Setup](#1-installation--setup)
2. [Starting the Services](#2-starting-the-services)
3. [Loading Data](#3-loading-data)
4. [Querying the System](#4-querying-the-system)
5. [Using the Knowledge Graph](#5-using-the-knowledge-graph)
6. [API Reference](#6-api-reference)
7. [Common Use Cases](#7-common-use-cases)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Installation & Setup

### 1.1 Prerequisites

- Python 3.10 or higher
- OpenAI API key
- Neo4j database (optional, for graph features)

### 1.2 Install the Package

```bash
# Clone the repository
git clone https://github.com/yourusername/Planning-Risk-Intelligent.git
cd Planning-Risk-Intelligent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows

# Install the package
pip install -e .
```

### 1.3 Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

**Required settings in `.env`:**
```
OPENAI_API_KEY=sk-your-api-key-here
```

**Optional Neo4j settings (for graph features):**
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
```

### 1.4 Set Up Neo4j (Optional but Recommended)

**Option A: Using Docker**
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password123 \
  neo4j:latest
```

**Option B: Using Neo4j Desktop**
1. Download from https://neo4j.com/download/
2. Create a new project and database
3. Start the database
4. Note the bolt URL and credentials

---

## 2. Starting the Services

### 2.1 Start the API Server

```bash
# Start the server
pri-server

# Or with custom host/port
API_HOST=0.0.0.0 API_PORT=8080 pri-server
```

The API will be available at:
- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 2.2 Verify the Setup

```bash
# Check health status
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "vector_store_count": 0,
  "rag_chain_ready": false,
  "graph_available": true,
  "graph_node_count": 0
}
```

---

## 3. Loading Data

### 3.1 Using the CLI

**Load a P6 Schedule:**
```bash
pri-ingest --schedule /path/to/schedule.xer
```

**Load a Risk Register:**
```bash
pri-ingest --risk-register /path/to/risks.xlsx
```

**Load Both:**
```bash
pri-ingest --schedule schedule.xer --risk-register risks.xlsx
```

**Options:**
```bash
# Clear existing data before loading
pri-ingest --schedule schedule.xer --clear

# Specify custom storage directory
pri-ingest --schedule schedule.xer --persist-dir ./my_data
```

### 3.2 Using the API

**Upload Schedule:**
```bash
curl -X POST "http://localhost:8000/upload/schedule" \
  -F "file=@schedule.xer"
```

**Upload Risk Register:**
```bash
curl -X POST "http://localhost:8000/upload/risk-register" \
  -F "file=@risks.xlsx"
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully processed schedule: My Project",
  "documents_added": 15,
  "graph_nodes_created": 45,
  "file_type": "P6 Schedule (XER)"
}
```

### 3.3 Using Python

```python
from src.parsers import P6Parser, RiskRegisterParser
from src.rag import DocumentProcessor, VectorStoreManager
from src.graph import GraphStore, GraphDataLoader

# Parse files
schedule = P6Parser().parse("schedule.xer")
risks = RiskRegisterParser().parse_file("risks.xlsx")

# Load to vector store
processor = DocumentProcessor()
vectorstore = VectorStoreManager()

docs = processor.process_schedule(schedule, "schedule.xer")
docs += processor.process_risk_register(risks, "risks.xlsx")
vectorstore.add_documents(docs)

# Load to graph (optional)
graph = GraphStore()
graph.initialize_schema()
loader = GraphDataLoader(graph)
loader.load_schedule(schedule)
loader.load_risk_register(risks, schedule.project.project_id)
```

---

## 4. Querying the System

### 4.1 CLI Interactive Mode

```bash
# Start interactive mode
pri-query --interactive
```

**Available Commands:**
```
You: What is the project status?
You: /critical       # Show critical path
You: /risks          # Show risk analysis
You: /health         # Show schedule health
You: /summary        # Show executive summary
You: /sources        # Toggle source display
You: /quit           # Exit
```

### 4.2 Single Queries via CLI

```bash
# Basic query
pri-query "What activities are on the critical path?"

# Query with sources
pri-query --sources "What are the top risks?"

# Query about specific items
pri-query "Tell me about activity A3000"
pri-query "What is risk R001?"
```

### 4.3 API Queries

**Basic Query:**
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the project status?"}'
```

**Query with Sources:**
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the critical risks?",
    "include_sources": true,
    "use_graph": true
  }'
```

### 4.4 Python Queries

```python
from src.rag import HybridRAGChain, VectorStoreManager
from src.graph import GraphStore

# Initialize
vectorstore = VectorStoreManager()
graph = GraphStore()

chain = HybridRAGChain(
    vectorstore_manager=vectorstore,
    graph_store=graph,
    project_id="1"
)

# Simple query
answer = chain.query("What is the project status?")
print(answer)

# Query with sources
result = chain.query_with_sources("What are the top risks?")
print(result["answer"])
print(f"Sources: {result['num_sources']}")
```

---

## 5. Using the Knowledge Graph

### 5.1 Trace Schedule Dependencies

**CLI:**
```bash
pri-query "What are the predecessors of A3000?"
pri-query "What activities come after A2000?"
pri-query "Trace the path from A1000 to A4000"
```

**API:**
```bash
# Trace activity dependencies
curl "http://localhost:8000/graph/trace/A3000?direction=both"
```

**Response:**
```json
{
  "activity_code": "A3000",
  "predecessors": [
    {"activity_code": "A2040", "activity_name": "Planning Complete", "depth": 1},
    {"activity_code": "A2020", "activity_name": "Schedule Development", "depth": 2}
  ],
  "successors": [
    {"activity_code": "A3010", "activity_name": "Development Phase 1", "depth": 1}
  ],
  "analysis": "Activity A3000 (Procurement) has 5 predecessors..."
}
```

### 5.2 Analyze Risk Cascade

**CLI:**
```bash
pri-query "What is the cascade effect of risk R001?"
pri-query "What downstream activities are affected by R002?"
```

**API:**
```bash
# Analyze risk cascade
curl "http://localhost:8000/graph/risk-cascade/R001"
```

**Response:**
```json
{
  "risk_id": "R001",
  "directly_affected": [
    {"activity_code": "A2000", "activity_name": "Develop Project Plan"}
  ],
  "cascade_affected": [
    {"activity_code": "A2020", "activity_name": "Schedule Development"},
    {"activity_code": "A3000", "activity_name": "Procurement"}
  ],
  "analysis": "Risk R001 directly affects 1 activity and could cascade to 8 downstream activities..."
}
```

### 5.3 Critical Path from Graph

**API:**
```bash
curl "http://localhost:8000/graph/critical-path"
```

### 5.4 Graph Statistics

**API:**
```bash
curl "http://localhost:8000/graph/stats"
```

**Response:**
```json
{
  "available": true,
  "nodes": {
    "Project": 1,
    "Activity": 20,
    "WBS": 5,
    "Risk": 10
  },
  "relationships": {
    "PRECEDES": 25,
    "AFFECTS": 15,
    "CONTAINS": 26
  },
  "total_nodes": 40,
  "total_relationships": 66
}
```

---

## 6. API Reference

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check |
| GET | `/stats` | Data statistics |
| POST | `/query` | Query the system |
| DELETE | `/data` | Clear all data |

### Data Upload

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload/schedule` | Upload P6 XER file |
| POST | `/upload/risk-register` | Upload Excel risk register |

### Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analysis/schedule-health` | Schedule health analysis |
| GET | `/analysis/risk-exposure` | Risk exposure analysis |
| GET | `/analysis/executive-summary` | Executive summary |

### Knowledge Graph

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/graph/query` | Execute graph query |
| GET | `/graph/trace/{code}` | Trace activity dependencies |
| GET | `/graph/risk-cascade/{id}` | Analyze risk cascade |
| GET | `/graph/critical-path` | Get critical path |
| GET | `/graph/stats` | Graph statistics |

---

## 7. Common Use Cases

### 7.1 Schedule Analysis

```bash
# Overall status
pri-query "What is the current schedule status?"

# Critical path
pri-query "What activities are on the critical path?"

# Delays
pri-query "Which activities are delayed from baseline?"

# Float analysis
pri-query "Which activities have less than 5 days of float?"

# Milestone status
pri-query "What is the status of upcoming milestones?"
```

### 7.2 Risk Analysis

```bash
# Top risks
pri-query "What are the top 5 risks by score?"

# Category analysis
pri-query "What risks are in the Technical category?"

# EMV analysis
pri-query "What is the total expected monetary value of open risks?"

# Mitigation status
pri-query "Which risks need mitigation plans?"

# Owner workload
pri-query "Which risk owner has the most assigned risks?"
```

### 7.3 Combined Schedule-Risk Analysis

```bash
# Risk impact on schedule
pri-query "Which risks affect the critical path?"

# High-risk activities
pri-query "Which critical activities have high risk exposure?"

# Delay analysis
pri-query "If activity A2000 is delayed, what is the downstream impact?"

# Risk cascade
pri-query "If risk R001 occurs, what activities would be affected?"
```

### 7.4 Executive Reporting

```bash
# Executive summary
pri-query "Provide an executive summary of the project"

# Health dashboard
curl "http://localhost:8000/analysis/schedule-health"
curl "http://localhost:8000/analysis/risk-exposure"
curl "http://localhost:8000/analysis/executive-summary"
```

---

## 8. Troubleshooting

### 8.1 Common Issues

**Issue: "No data loaded" error**
```bash
# Solution: Load data first
pri-ingest --schedule schedule.xer
```

**Issue: Neo4j connection failed**
```bash
# Check Neo4j is running
docker ps | grep neo4j

# Check credentials in .env
cat .env | grep NEO4J

# Test connection
curl http://localhost:7474
```

**Issue: OpenAI API errors**
```bash
# Verify API key
echo $OPENAI_API_KEY

# Check key in .env
cat .env | grep OPENAI
```

### 8.2 Reset the System

```bash
# Clear all data via CLI
pri-ingest --schedule schedule.xer --clear

# Or via API
curl -X DELETE "http://localhost:8000/data"
```

### 8.3 Check System Status

```bash
# Health check
curl "http://localhost:8000/health"

# Data statistics
curl "http://localhost:8000/stats"

# Graph status
curl "http://localhost:8000/graph/stats"
```

### 8.4 Logs

```bash
# Run server with debug output
LOG_LEVEL=DEBUG pri-server

# Check for errors in output
pri-query "test query" 2>&1 | grep -i error
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                PLANNING & RISK INTELLIGENCE                  │
├─────────────────────────────────────────────────────────────┤
│ SETUP                                                        │
│   pip install -e .                                          │
│   cp .env.example .env   # Add OPENAI_API_KEY               │
│                                                             │
│ LOAD DATA                                                   │
│   pri-ingest --schedule file.xer                            │
│   pri-ingest --risk-register file.xlsx                      │
│                                                             │
│ QUERY                                                       │
│   pri-query "your question"                                 │
│   pri-query --interactive                                   │
│                                                             │
│ API                                                         │
│   pri-server                    # Start server              │
│   http://localhost:8000/docs    # API documentation         │
│                                                             │
│ COMMON QUERIES                                              │
│   "What is the project status?"                             │
│   "What are the critical risks?"                            │
│   "What are the predecessors of A1000?"                     │
│   "What is the cascade effect of risk R001?"                │
└─────────────────────────────────────────────────────────────┘
```
