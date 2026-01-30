"""
Streamlit Web Interface for Planning & Risk Intelligence.

Provides a user-friendly chat interface for querying project
schedules and risk registers using RAG.
"""

import os
import sys
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Planning & Risk Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .stChat message {
        padding: 1rem;
    }
    .status-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .status-success {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
    }
    .status-warning {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
    }
    .status-info {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "vectorstore" not in st.session_state:
        st.session_state.vectorstore = None
    if "graph_store" not in st.session_state:
        st.session_state.graph_store = None
    if "rag_chain" not in st.session_state:
        st.session_state.rag_chain = None
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False
    if "use_hybrid" not in st.session_state:
        st.session_state.use_hybrid = False
    if "schedule_info" not in st.session_state:
        st.session_state.schedule_info = None
    if "risk_info" not in st.session_state:
        st.session_state.risk_info = None


def load_existing_data():
    """Load existing data from vector store."""
    try:
        from src.rag import VectorStoreManager

        vectorstore = VectorStoreManager(
            persist_directory="./data/chroma_db",
            collection_name="planning_risk_intelligence",
        )
        stats = vectorstore.get_collection_stats()

        if stats["count"] > 0:
            st.session_state.vectorstore = vectorstore
            st.session_state.data_loaded = True
            return stats
        return None
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None


def connect_neo4j():
    """Try to connect to Neo4j."""
    try:
        from src.graph.store import GraphStore

        graph_store = GraphStore()
        # Test connection
        result = graph_store.execute_read("MATCH (n) RETURN count(n) as count")
        if result and result[0]["count"] > 0:
            st.session_state.graph_store = graph_store
            return result[0]["count"]
        return 0
    except Exception as e:
        return None


def init_rag_chain():
    """Initialize the RAG chain with current settings."""
    if st.session_state.vectorstore is None:
        return False

    try:
        from src.rag import PlanningRiskRAGChain

        if st.session_state.use_hybrid and st.session_state.graph_store:
            from src.rag.hybrid_retriever import HybridRetriever

            retriever = HybridRetriever(
                vectorstore_manager=st.session_state.vectorstore,
                graph_store=st.session_state.graph_store,
                top_k=5,
                use_graph=True,
            )
            st.session_state.rag_chain = PlanningRiskRAGChain(
                vectorstore_manager=st.session_state.vectorstore,
                retriever=retriever,
            )
        else:
            st.session_state.rag_chain = PlanningRiskRAGChain(
                vectorstore_manager=st.session_state.vectorstore,
            )
        return True
    except Exception as e:
        st.error(f"Error initializing RAG chain: {e}")
        return False


def process_uploaded_files(schedule_file, risk_file, load_to_graph=False):
    """Process uploaded files and load into vector store."""
    from src.parsers import P6Parser, RiskRegisterParser
    from src.rag import DocumentProcessor, VectorStoreManager

    progress = st.progress(0, text="Initializing...")

    try:
        # Initialize components
        vectorstore = VectorStoreManager(
            persist_directory="./data/chroma_db",
            collection_name="planning_risk_intelligence",
        )
        processor = DocumentProcessor()
        all_documents = []
        schedule = None
        risk_register = None

        progress.progress(10, text="Processing files...")

        # Process schedule
        if schedule_file is not None:
            progress.progress(20, text="Parsing P6 schedule...")

            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xer") as tmp:
                tmp.write(schedule_file.getvalue())
                tmp_path = tmp.name

            p6_parser = P6Parser()
            schedule = p6_parser.parse(Path(tmp_path))

            st.session_state.schedule_info = {
                "project_name": schedule.project.project_name,
                "activities": len(schedule.activities),
                "wbs_elements": len(schedule.wbs_elements),
            }

            progress.progress(40, text="Converting schedule to documents...")
            docs = processor.process_schedule(schedule, source_file=schedule_file.name)
            all_documents.extend(docs)

            os.unlink(tmp_path)

        # Process risk register
        if risk_file is not None:
            progress.progress(50, text="Parsing risk register...")

            suffix = ".xlsx" if risk_file.name.endswith(".xlsx") else ".xls"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(risk_file.getvalue())
                tmp_path = tmp.name

            risk_parser = RiskRegisterParser()
            risk_register = risk_parser.parse_file(Path(tmp_path))

            st.session_state.risk_info = {
                "total_risks": risk_register.total_risks,
                "open_risks": len(risk_register.open_risks),
                "critical_risks": len(risk_register.critical_risks),
            }

            progress.progress(60, text="Converting risks to documents...")
            docs = processor.process_risk_register(risk_register, source_file=risk_file.name)
            all_documents.extend(docs)

            os.unlink(tmp_path)

        # Add to vector store
        if all_documents:
            progress.progress(70, text=f"Indexing {len(all_documents)} documents...")
            vectorstore.add_documents(all_documents)
            st.session_state.vectorstore = vectorstore
            st.session_state.data_loaded = True

        # Load to Neo4j if requested
        if load_to_graph and (schedule or risk_register):
            progress.progress(80, text="Loading to Neo4j...")
            try:
                from src.graph.store import GraphStore
                from src.graph.loader import GraphDataLoader

                graph_store = GraphStore()
                loader = GraphDataLoader(graph_store)
                graph_store.initialize_schema()

                project_id = None
                if schedule:
                    loader.load_schedule(schedule, clear_existing=True)
                    project_id = schedule.project.project_id

                if risk_register:
                    loader.load_risk_register(risk_register, project_id=project_id)

                st.session_state.graph_store = graph_store
            except Exception as e:
                st.warning(f"Could not load to Neo4j: {e}")

        progress.progress(100, text="Complete!")
        return True

    except Exception as e:
        st.error(f"Error processing files: {e}")
        return False


def display_sidebar():
    """Display the sidebar with settings and data info."""
    with st.sidebar:
        st.title("📊 P&R Intelligence")
        st.markdown("---")

        # Data loading section
        st.subheader("📁 Data Management")

        # Check for existing data
        if not st.session_state.data_loaded:
            stats = load_existing_data()
            if stats:
                st.success(f"Loaded {stats['count']} documents")

        # File uploaders
        with st.expander("Upload New Data", expanded=not st.session_state.data_loaded):
            schedule_file = st.file_uploader(
                "P6 Schedule (.xer)",
                type=["xer"],
                help="Upload a Primavera P6 XER export file"
            )

            risk_file = st.file_uploader(
                "Risk Register (.xlsx)",
                type=["xlsx", "xls"],
                help="Upload a risk register Excel file"
            )

            load_to_graph = st.checkbox(
                "Also load to Neo4j",
                value=False,
                help="Load data into Neo4j for relationship queries"
            )

            if st.button("📥 Load Data", type="primary", disabled=(schedule_file is None and risk_file is None)):
                with st.spinner("Processing files..."):
                    if process_uploaded_files(schedule_file, risk_file, load_to_graph):
                        st.success("Data loaded successfully!")
                        st.rerun()

        st.markdown("---")

        # Data status
        st.subheader("📈 Data Status")

        if st.session_state.vectorstore:
            stats = st.session_state.vectorstore.get_collection_stats()
            st.metric("Documents in Vector Store", stats["count"])
        else:
            st.warning("No data loaded")

        # Neo4j status
        neo4j_count = connect_neo4j()
        if neo4j_count is not None and neo4j_count > 0:
            st.metric("Nodes in Neo4j", neo4j_count)

            # Hybrid mode toggle
            st.session_state.use_hybrid = st.toggle(
                "🔗 Hybrid Mode (Neo4j + Vector)",
                value=st.session_state.use_hybrid,
                help="Enable graph traversal for relationship queries"
            )
        elif neo4j_count == 0:
            st.info("Neo4j is empty. Upload data with 'Load to Neo4j' enabled.")
        else:
            st.info("Neo4j not connected")

        # Schedule info
        if st.session_state.schedule_info:
            with st.expander("📅 Schedule Info"):
                info = st.session_state.schedule_info
                st.write(f"**Project:** {info['project_name']}")
                st.write(f"**Activities:** {info['activities']}")
                st.write(f"**WBS Elements:** {info['wbs_elements']}")

        # Risk info
        if st.session_state.risk_info:
            with st.expander("⚠️ Risk Register Info"):
                info = st.session_state.risk_info
                st.write(f"**Total Risks:** {info['total_risks']}")
                st.write(f"**Open Risks:** {info['open_risks']}")
                st.write(f"**Critical Risks:** {info['critical_risks']}")

        st.markdown("---")

        # Quick actions
        st.subheader("⚡ Quick Actions")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Summary"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "Provide an executive summary of the project status."
                })
                st.rerun()

        with col2:
            if st.button("🎯 Critical"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "What activities are on the critical path?"
                })
                st.rerun()

        col3, col4 = st.columns(2)
        with col3:
            if st.button("⚠️ Risks"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "What are the top high-priority risks?"
                })
                st.rerun()

        with col4:
            if st.button("📊 Health"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "Analyze the schedule health and any concerns."
                })
                st.rerun()

        st.markdown("---")

        # Clear chat
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()


def display_chat():
    """Display the main chat interface."""
    st.title("💬 Planning & Risk Intelligence")

    # Mode indicator
    if st.session_state.use_hybrid and st.session_state.graph_store:
        st.caption("🔗 Hybrid Mode: Using ChromaDB + Neo4j for comprehensive answers")
    else:
        st.caption("📚 Vector Mode: Using ChromaDB for semantic search")

    # Check if data is loaded
    if not st.session_state.data_loaded:
        st.info("👈 Please upload data files using the sidebar to get started.")

        # Example questions
        st.markdown("### Example Questions")
        st.markdown("""
        Once you load your data, you can ask questions like:
        - "What activities are on the critical path?"
        - "What are the high-priority risks?"
        - "Show me delayed activities"
        - "What happens if activity X is delayed?"
        - "Summarize the project status"
        """)
        return

    # Initialize RAG chain if needed
    if st.session_state.rag_chain is None:
        init_rag_chain()

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask about your project schedule or risks..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Re-init RAG chain if hybrid mode changed
                    init_rag_chain()

                    response = st.session_state.rag_chain.query(prompt)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})


def main():
    """Main application entry point."""
    init_session_state()
    display_sidebar()
    display_chat()


if __name__ == "__main__":
    main()
