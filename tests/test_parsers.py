"""Tests for P6 and Risk Register parsers."""

from pathlib import Path

import pandas as pd
import pytest

from src.models.schedule import ActivityStatus, ActivityType, Schedule
from src.models.risk import RiskCategory, RiskStatus, RiskRegister
from src.parsers.p6_parser import P6Parser, XERParser
from src.parsers.risk_register import RiskRegisterParser, create_sample_risk_register


class TestXERParser:
    """Tests for XER file parsing."""

    @pytest.fixture
    def sample_xer_content(self):
        """Sample XER content for testing."""
        return """ERMHDR	20.12	2024-01-15	Project	admin	Test	USD	Test Schedule
%T	PROJECT
%F	proj_id	proj_short_name	proj_name	plan_start_date	scd_end_date
%R	1	TEST	Test Project	2024-01-01 08:00	2024-12-31 17:00
%T	PROJWBS
%F	wbs_id	proj_id	wbs_short_name	wbs_name	parent_wbs_id	seq_num
%R	1	1	TEST	Test Project	 	1
%R	2	1	1.0	Phase 1	1	2
%T	TASK
%F	task_id	proj_id	wbs_id	task_code	task_name	task_type	status_code	target_start_date	target_end_date	total_float_hr_cnt	phys_complete_pct
%R	100	1	2	A1000	Task 1	TT_Task	TK_Complete	2024-01-01 08:00	2024-01-05 17:00	0	100
%R	101	1	2	A1010	Task 2	TT_Task	TK_Active	2024-01-08 08:00	2024-01-12 17:00	-8	50
%R	102	1	2	A1020	Milestone 1	TT_FinMile	TK_NotStart	2024-01-15 17:00	2024-01-15 17:00	0	0
%T	TASKPRED
%F	task_pred_id	task_id	pred_task_id	pred_type	lag_hr_cnt
%R	1	101	100	PR_FS	0
%R	2	102	101	PR_FS	0
%E
"""

    def test_parse_content(self, sample_xer_content):
        """Test parsing XER content."""
        parser = XERParser()
        schedule = parser.parse_content(sample_xer_content)

        assert isinstance(schedule, Schedule)
        assert schedule.project.project_name == "Test Project"
        assert schedule.project.project_code == "TEST"

    def test_parse_activities(self, sample_xer_content):
        """Test activity parsing."""
        parser = XERParser()
        schedule = parser.parse_content(sample_xer_content)

        assert len(schedule.activities) == 3

        # Check first activity
        task1 = next(a for a in schedule.activities if a.activity_code == "A1000")
        assert task1.activity_name == "Task 1"
        assert task1.status == ActivityStatus.COMPLETED
        assert task1.percent_complete == 100

        # Check in-progress activity
        task2 = next(a for a in schedule.activities if a.activity_code == "A1010")
        assert task2.status == ActivityStatus.IN_PROGRESS
        assert task2.percent_complete == 50

        # Check milestone
        milestone = next(a for a in schedule.activities if a.activity_code == "A1020")
        assert milestone.activity_type == ActivityType.FINISH_MILESTONE

    def test_parse_relationships(self, sample_xer_content):
        """Test relationship parsing."""
        parser = XERParser()
        schedule = parser.parse_content(sample_xer_content)

        assert len(schedule.relationships) == 2

    def test_parse_wbs(self, sample_xer_content):
        """Test WBS parsing."""
        parser = XERParser()
        schedule = parser.parse_content(sample_xer_content)

        assert len(schedule.wbs_elements) == 2

    def test_critical_path_detection(self, sample_xer_content):
        """Test critical path activity detection."""
        parser = XERParser()
        schedule = parser.parse_content(sample_xer_content)

        critical = schedule.critical_path_activities
        # Activities with 0 or negative float
        assert len(critical) >= 2


class TestP6Parser:
    """Tests for unified P6 parser."""

    def test_parse_xer_file(self, tmp_path):
        """Test parsing XER file from path."""
        xer_content = """ERMHDR	20.12	2024-01-15	Project	admin	Test	USD
%T	PROJECT
%F	proj_id	proj_short_name	proj_name
%R	1	TEST	Test Project
%T	TASK
%F	task_id	proj_id	wbs_id	task_code	task_name	task_type	status_code
%R	100	1		A1000	Test Task	TT_Task	TK_NotStart
%E
"""
        xer_file = tmp_path / "test.xer"
        xer_file.write_text(xer_content)

        parser = P6Parser()
        schedule = parser.parse(xer_file)

        assert schedule.project.project_name == "Test Project"
        assert len(schedule.activities) == 1

    def test_unsupported_format(self, tmp_path):
        """Test handling of unsupported file format."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("<project></project>")

        parser = P6Parser()
        with pytest.raises(ValueError, match="Unsupported file format"):
            parser.parse(xml_file)


class TestRiskRegisterParser:
    """Tests for risk register parsing."""

    @pytest.fixture
    def sample_risk_df(self):
        """Create sample risk register DataFrame."""
        return create_sample_risk_register()

    def test_parse_dataframe(self, sample_risk_df):
        """Test parsing DataFrame to RiskRegister."""
        parser = RiskRegisterParser()
        register = parser.parse_dataframe(sample_risk_df, "Test Project")

        assert isinstance(register, RiskRegister)
        assert register.total_risks == 5
        assert register.project_name == "Test Project"

    def test_parse_risk_fields(self, sample_risk_df):
        """Test individual risk field parsing."""
        parser = RiskRegisterParser()
        register = parser.parse_dataframe(sample_risk_df)

        # Find a specific risk
        risk = next(r for r in register.risks if r.risk_id == "R001")

        assert risk.title == "Resource Availability Risk"
        assert risk.category == RiskCategory.RESOURCE
        assert risk.status == RiskStatus.OPEN
        assert risk.probability == 0.6
        assert risk.impact_score == 4

    def test_risk_score_calculation(self, sample_risk_df):
        """Test risk score calculation."""
        parser = RiskRegisterParser()
        register = parser.parse_dataframe(sample_risk_df)

        risk = next(r for r in register.risks if r.risk_id == "R001")
        expected_score = 0.6 * 4  # probability * impact
        assert risk.risk_score == expected_score

    def test_parse_excel_file(self, tmp_path, sample_risk_df):
        """Test parsing Excel file."""
        excel_path = tmp_path / "risk_register.xlsx"
        sample_risk_df.to_excel(excel_path, index=False)

        parser = RiskRegisterParser()
        register = parser.parse_file(excel_path)

        assert register.total_risks == 5

    def test_category_mapping(self):
        """Test category string mapping."""
        parser = RiskRegisterParser()

        # Test various category strings
        assert parser.CATEGORY_MAP.get("technical") == RiskCategory.TECHNICAL
        assert parser.CATEGORY_MAP.get("cost") == RiskCategory.COST
        assert parser.CATEGORY_MAP.get("schedule") == RiskCategory.SCHEDULE

    def test_status_mapping(self):
        """Test status string mapping."""
        parser = RiskRegisterParser()

        assert parser.STATUS_MAP.get("open") == RiskStatus.OPEN
        assert parser.STATUS_MAP.get("mitigating") == RiskStatus.MITIGATING
        assert parser.STATUS_MAP.get("closed") == RiskStatus.CLOSED

    def test_risk_register_properties(self, sample_risk_df):
        """Test RiskRegister computed properties."""
        parser = RiskRegisterParser()
        register = parser.parse_dataframe(sample_risk_df)

        # Test aggregations
        assert len(register.open_risks) > 0
        assert register.total_emv > 0
        assert register.total_expected_schedule_impact > 0

        # Test groupings
        by_category = register.risks_by_category()
        assert len(by_category) > 0

        by_owner = register.risks_by_owner()
        assert len(by_owner) > 0
