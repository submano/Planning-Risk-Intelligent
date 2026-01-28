"""Tests for RAG components."""

import pytest

from src.models.schedule import (
    Activity,
    ActivityStatus,
    ActivityType,
    Project,
    Schedule,
    WBSElement,
)
from src.models.risk import Risk, RiskCategory, RiskRegister, RiskStatus
from src.rag.document_processor import DocumentProcessor
from src.rag.retriever import PlanningRiskRetriever, QueryType


class TestDocumentProcessor:
    """Tests for document processor."""

    @pytest.fixture
    def sample_schedule(self):
        """Create a sample schedule for testing."""
        project = Project(
            project_id="1",
            project_code="TEST",
            project_name="Test Project",
        )

        activities = [
            Activity(
                activity_id="1",
                activity_code="A1000",
                activity_name="Task 1",
                activity_type=ActivityType.TASK_DEPENDENT,
                status=ActivityStatus.COMPLETED,
                percent_complete=100,
                total_float=0,
            ),
            Activity(
                activity_id="2",
                activity_code="A1010",
                activity_name="Task 2",
                activity_type=ActivityType.TASK_DEPENDENT,
                status=ActivityStatus.IN_PROGRESS,
                percent_complete=50,
                total_float=-8,
            ),
            Activity(
                activity_id="3",
                activity_code="M1000",
                activity_name="Milestone 1",
                activity_type=ActivityType.FINISH_MILESTONE,
                status=ActivityStatus.NOT_STARTED,
                percent_complete=0,
                total_float=0,
            ),
        ]

        wbs = [
            WBSElement(
                wbs_id="1",
                wbs_code="TEST",
                wbs_name="Test Project",
                level=1,
            ),
        ]

        return Schedule(
            project=project,
            activities=activities,
            wbs_elements=wbs,
        )

    @pytest.fixture
    def sample_risk_register(self):
        """Create a sample risk register for testing."""
        risks = [
            Risk(
                risk_id="R001",
                title="Test Risk 1",
                description="Description of test risk 1",
                category=RiskCategory.TECHNICAL,
                status=RiskStatus.OPEN,
                probability=0.8,
                impact_score=4,
                impact_cost=100000,
                impact_schedule=20,
                mitigation_plan="Mitigation plan for risk 1",
            ),
            Risk(
                risk_id="R002",
                title="Test Risk 2",
                description="Description of test risk 2",
                category=RiskCategory.SCHEDULE,
                status=RiskStatus.MITIGATING,
                probability=0.5,
                impact_score=3,
                impact_cost=50000,
                impact_schedule=10,
            ),
        ]

        return RiskRegister(
            project_name="Test Project",
            risks=risks,
        )

    def test_process_schedule(self, sample_schedule):
        """Test processing schedule into documents."""
        processor = DocumentProcessor()
        documents = processor.process_schedule(sample_schedule, "test.xer")

        assert len(documents) > 0

        # Check document types
        doc_types = [doc.metadata.get("doc_type") for doc in documents]
        assert "project_overview" in doc_types
        assert "schedule_summary" in doc_types

    def test_process_risk_register(self, sample_risk_register):
        """Test processing risk register into documents."""
        processor = DocumentProcessor()
        documents = processor.process_risk_register(sample_risk_register, "risks.xlsx")

        assert len(documents) > 0

        # Check document types
        doc_types = [doc.metadata.get("doc_type") for doc in documents]
        assert "risk_overview" in doc_types
        assert "risk_detail" in doc_types

    def test_document_metadata(self, sample_schedule):
        """Test document metadata is properly set."""
        processor = DocumentProcessor()
        documents = processor.process_schedule(sample_schedule, "test.xer")

        for doc in documents:
            assert "source" in doc.metadata
            assert "doc_type" in doc.metadata
            assert doc.metadata["source"] == "test.xer"

    def test_critical_path_document(self, sample_schedule):
        """Test critical path document creation."""
        processor = DocumentProcessor()
        documents = processor.process_schedule(sample_schedule, "test.xer")

        critical_docs = [
            doc for doc in documents if doc.metadata.get("doc_type") == "critical_path"
        ]

        # Should have critical path doc since we have activities with 0 or negative float
        assert len(critical_docs) > 0

    def test_risk_detail_documents(self, sample_risk_register):
        """Test individual risk detail documents."""
        processor = DocumentProcessor()
        documents = processor.process_risk_register(sample_risk_register, "risks.xlsx")

        risk_details = [
            doc for doc in documents if doc.metadata.get("doc_type") == "risk_detail"
        ]

        # Should have one detail doc per risk
        assert len(risk_details) == 2


class TestQueryClassification:
    """Tests for query classification."""

    def test_classify_schedule_query(self):
        """Test classification of schedule-related queries."""
        # Create a mock retriever for testing classification
        from unittest.mock import MagicMock

        retriever = PlanningRiskRetriever(
            vectorstore_manager=MagicMock()
        )

        assert retriever._classify_query("What is the schedule status?") == QueryType.SCHEDULE
        assert retriever._classify_query("Show me all activities") == QueryType.SCHEDULE
        assert retriever._classify_query("What milestones are coming up?") == QueryType.SCHEDULE

    def test_classify_risk_query(self):
        """Test classification of risk-related queries."""
        from unittest.mock import MagicMock

        retriever = PlanningRiskRetriever(
            vectorstore_manager=MagicMock()
        )

        assert retriever._classify_query("What are the top risks?") == QueryType.RISK
        assert retriever._classify_query("Show risk mitigation plans") == QueryType.RISK
        assert retriever._classify_query("What is the total EMV?") == QueryType.RISK

    def test_classify_critical_path_query(self):
        """Test classification of critical path queries."""
        from unittest.mock import MagicMock

        retriever = PlanningRiskRetriever(
            vectorstore_manager=MagicMock()
        )

        assert retriever._classify_query("What is on the critical path?") == QueryType.CRITICAL_PATH
        assert retriever._classify_query("Show delayed activities") == QueryType.CRITICAL_PATH

    def test_classify_combined_query(self):
        """Test classification of combined queries."""
        from unittest.mock import MagicMock

        retriever = PlanningRiskRetriever(
            vectorstore_manager=MagicMock()
        )

        result = retriever._classify_query("What risks affect the schedule?")
        assert result == QueryType.COMBINED

    def test_classify_general_query(self):
        """Test classification of general queries."""
        from unittest.mock import MagicMock

        retriever = PlanningRiskRetriever(
            vectorstore_manager=MagicMock()
        )

        assert retriever._classify_query("Give me a project summary") == QueryType.GENERAL
