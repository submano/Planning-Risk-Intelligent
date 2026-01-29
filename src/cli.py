"""
Command-line interface for Planning & Risk Intelligence.

Provides CLI commands for:
- Ingesting P6 schedules and risk registers
- Querying the RAG system
- Running analysis
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def ingest_data():
    """CLI command to ingest schedule and risk register data."""
    parser = argparse.ArgumentParser(
        description="Ingest P6 schedules and risk registers into the RAG system"
    )
    parser.add_argument(
        "--schedule",
        "-s",
        type=str,
        help="Path to P6 schedule file (.xer)",
    )
    parser.add_argument(
        "--risk-register",
        "-r",
        type=str,
        help="Path to risk register file (.xlsx or .xls)",
    )
    parser.add_argument(
        "--persist-dir",
        "-d",
        type=str,
        default="./data/chroma_db",
        help="Directory to persist vector store (default: ./data/chroma_db)",
    )
    parser.add_argument(
        "--collection",
        "-c",
        type=str,
        default="planning_risk_intelligence",
        help="Collection name for vector store",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before ingestion",
    )
    parser.add_argument(
        "--graph",
        "-g",
        action="store_true",
        help="Also load data into Neo4j knowledge graph",
    )

    args = parser.parse_args()

    if not args.schedule and not args.risk_register:
        parser.error("At least one of --schedule or --risk-register is required")

    # Import here to avoid slow startup for help messages
    from src.parsers import P6Parser, RiskRegisterParser
    from src.rag import DocumentProcessor, VectorStoreManager

    print("Initializing Planning & Risk Intelligence...")

    # Initialize components
    vectorstore = VectorStoreManager(
        persist_directory=args.persist_dir,
        collection_name=args.collection,
    )
    processor = DocumentProcessor()

    if args.clear:
        print("Clearing existing data...")
        vectorstore.delete_collection()
        vectorstore = VectorStoreManager(
            persist_directory=args.persist_dir,
            collection_name=args.collection,
        )

    all_documents = []

    # Process schedule if provided
    if args.schedule:
        schedule_path = Path(args.schedule)
        if not schedule_path.exists():
            print(f"Error: Schedule file not found: {args.schedule}")
            sys.exit(1)

        print(f"Parsing P6 schedule: {args.schedule}")
        p6_parser = P6Parser()
        schedule = p6_parser.parse(schedule_path)

        print(f"  Project: {schedule.project.project_name}")
        print(f"  Activities: {len(schedule.activities)}")
        print(f"  WBS Elements: {len(schedule.wbs_elements)}")

        documents = processor.process_schedule(schedule, source_file=args.schedule)
        all_documents.extend(documents)
        print(f"  Generated {len(documents)} documents from schedule")

    # Process risk register if provided
    if args.risk_register:
        risk_path = Path(args.risk_register)
        if not risk_path.exists():
            print(f"Error: Risk register file not found: {args.risk_register}")
            sys.exit(1)

        print(f"Parsing risk register: {args.risk_register}")
        risk_parser = RiskRegisterParser()
        risk_register = risk_parser.parse_file(risk_path)

        print(f"  Total Risks: {risk_register.total_risks}")
        print(f"  Open Risks: {len(risk_register.open_risks)}")
        print(f"  Critical Risks: {len(risk_register.critical_risks)}")

        documents = processor.process_risk_register(
            risk_register, source_file=args.risk_register
        )
        all_documents.extend(documents)
        print(f"  Generated {len(documents)} documents from risk register")

    # Add all documents to vector store
    if all_documents:
        print(f"\nIndexing {len(all_documents)} documents to vector store...")
        vectorstore.add_documents(all_documents)
        print("Vector store indexing complete!")

        stats = vectorstore.get_collection_stats()
        print(f"\nVector store statistics:")
        print(f"  Collection: {stats['name']}")
        print(f"  Total documents: {stats['count']}")
        print(f"  Persist directory: {stats['persist_directory']}")
    else:
        print("No documents to index.")

    # Load data into Neo4j knowledge graph if requested
    if args.graph:
        print("\n" + "=" * 50)
        print("Loading data into Neo4j knowledge graph...")
        print("=" * 50)

        try:
            from src.graph.store import GraphStore
            from src.graph.loader import GraphDataLoader

            # Initialize graph store and loader
            graph_store = GraphStore()
            loader = GraphDataLoader(graph_store)

            # Initialize schema
            print("Initializing graph schema...")
            graph_store.initialize_schema()

            project_id = None

            # Load schedule into graph
            if args.schedule:
                print(f"\nLoading schedule into graph...")
                schedule_stats = loader.load_schedule(schedule, clear_existing=args.clear)
                project_id = schedule.project.project_id
                print(f"  Loaded: {schedule_stats}")

            # Load risk register into graph
            if args.risk_register:
                print(f"\nLoading risk register into graph...")
                risk_stats = loader.load_risk_register(risk_register, project_id=project_id)
                print(f"  Loaded: {risk_stats}")

            # Show graph statistics
            print("\nNeo4j graph statistics:")
            node_counts = graph_store.execute_read("""
                MATCH (n)
                RETURN labels(n)[0] AS type, count(n) AS count
                ORDER BY count DESC
            """)
            for record in node_counts:
                print(f"  {record['type']}: {record['count']} nodes")

            print("\nGraph loading complete!")

        except ImportError as e:
            print(f"\nWarning: Could not import graph modules: {e}")
            print("Make sure neo4j is installed: pip install neo4j")
        except Exception as e:
            print(f"\nError loading data into Neo4j: {e}")
            print("Check your Neo4j connection settings in .env file:"
                  "\n  NEO4J_URI=bolt://localhost:7687"
                  "\n  NEO4J_USERNAME=neo4j"
                  "\n  NEO4J_PASSWORD=your-password")


def query():
    """CLI command to query the RAG system."""
    parser = argparse.ArgumentParser(
        description="Query the Planning & Risk Intelligence system"
    )
    parser.add_argument(
        "question",
        type=str,
        nargs="?",
        help="Question to ask (or enter interactive mode if omitted)",
    )
    parser.add_argument(
        "--persist-dir",
        "-d",
        type=str,
        default="./data/chroma_db",
        help="Directory where vector store is persisted",
    )
    parser.add_argument(
        "--collection",
        "-c",
        type=str,
        default="planning_risk_intelligence",
        help="Collection name for vector store",
    )
    parser.add_argument(
        "--sources",
        "-s",
        action="store_true",
        help="Show source documents used for the answer",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Enter interactive query mode",
    )

    args = parser.parse_args()

    # Import here to avoid slow startup
    from src.rag import PlanningRiskRAGChain, VectorStoreManager

    print("Initializing Planning & Risk Intelligence...")

    # Initialize components
    vectorstore = VectorStoreManager(
        persist_directory=args.persist_dir,
        collection_name=args.collection,
    )

    stats = vectorstore.get_collection_stats()
    if stats["count"] == 0:
        print("Error: No data loaded. Please run 'pri-ingest' first to load data.")
        sys.exit(1)

    print(f"Loaded {stats['count']} documents from vector store")

    rag_chain = PlanningRiskRAGChain(vectorstore_manager=vectorstore)

    def process_query(question: str):
        """Process a single query."""
        print(f"\nQuestion: {question}")
        print("-" * 50)

        if args.sources:
            result = rag_chain.query_with_sources(question)
            print(f"\nAnswer:\n{result['answer']}")
            print(f"\n--- Sources ({result['num_sources']}) ---")
            for i, source in enumerate(result["sources"], 1):
                print(f"\n{i}. {source['doc_type']} from {source['source']}")
                print(f"   Preview: {source['content_preview']}")
        else:
            answer = rag_chain.query(question)
            print(f"\nAnswer:\n{answer}")

    # Single query mode
    if args.question and not args.interactive:
        process_query(args.question)
        return

    # Interactive mode
    print("\n" + "=" * 50)
    print("Planning & Risk Intelligence - Interactive Mode")
    print("=" * 50)
    print("Type your questions below. Commands:")
    print("  /quit or /exit - Exit interactive mode")
    print("  /sources - Toggle showing sources")
    print("  /stats - Show vector store statistics")
    print("  /health - Analyze schedule health")
    print("  /risks - Analyze risk exposure")
    print("  /summary - Get executive summary")
    print("=" * 50 + "\n")

    show_sources = args.sources

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["/quit", "/exit", "quit", "exit"]:
                print("Goodbye!")
                break

            if user_input.lower() == "/sources":
                show_sources = not show_sources
                print(f"Source display: {'ON' if show_sources else 'OFF'}")
                continue

            if user_input.lower() == "/stats":
                stats = vectorstore.get_collection_stats()
                print(f"Documents: {stats['count']}")
                print(f"Collection: {stats['name']}")
                continue

            if user_input.lower() == "/health":
                user_input = (
                    "Provide a comprehensive analysis of the schedule health "
                    "including critical path status, delayed activities, "
                    "overall progress, and any concerns."
                )

            if user_input.lower() == "/risks":
                user_input = (
                    "Provide a comprehensive risk exposure analysis including "
                    "total EMV, critical risks, risk distribution by category, "
                    "and top concerns requiring immediate attention."
                )

            if user_input.lower() == "/summary":
                user_input = (
                    "Provide an executive summary of the project including "
                    "schedule status, key milestones, critical risks, "
                    "and overall project health assessment."
                )

            # Store original sources setting and use current one
            original_sources = args.sources
            args.sources = show_sources
            process_query(user_input)
            args.sources = original_sources

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    # Default to query mode if run directly
    query()
