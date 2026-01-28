"""
Parser for Primavera P6 XER files.

XER files are tab-delimited text files exported from Oracle Primavera P6.
The format consists of table definitions followed by data rows.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.schedule import (
    Activity,
    ActivityStatus,
    ActivityType,
    Calendar,
    Project,
    Relationship,
    RelationshipType,
    Resource,
    ResourceAssignment,
    Schedule,
    WBSElement,
)


class XERParser:
    """Parser for P6 XER export files."""

    # Mapping of P6 activity types to our enum
    ACTIVITY_TYPE_MAP = {
        "TT_Task": ActivityType.TASK_DEPENDENT,
        "TT_Rsrc": ActivityType.RESOURCE_DEPENDENT,
        "TT_LOE": ActivityType.LEVEL_OF_EFFORT,
        "TT_Mile": ActivityType.START_MILESTONE,
        "TT_FinMile": ActivityType.FINISH_MILESTONE,
        "TT_WBS": ActivityType.WBS_SUMMARY,
    }

    # Mapping of P6 activity status to our enum
    STATUS_MAP = {
        "TK_NotStart": ActivityStatus.NOT_STARTED,
        "TK_Active": ActivityStatus.IN_PROGRESS,
        "TK_Complete": ActivityStatus.COMPLETED,
    }

    # Mapping of relationship types
    RELATIONSHIP_MAP = {
        "PR_FS": RelationshipType.FINISH_TO_START,
        "PR_FF": RelationshipType.FINISH_TO_FINISH,
        "PR_SS": RelationshipType.START_TO_START,
        "PR_SF": RelationshipType.START_TO_FINISH,
    }

    def __init__(self):
        self.tables: dict[str, list[dict]] = {}
        self.table_columns: dict[str, list[str]] = {}

    def parse_file(self, file_path: str | Path) -> Schedule:
        """Parse an XER file and return a Schedule object."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"XER file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return self.parse_content(content)

    def parse_content(self, content: str) -> Schedule:
        """Parse XER content string and return a Schedule object."""
        self._parse_tables(content)

        # Parse project info
        project = self._parse_project()

        # Parse all components
        wbs_elements = self._parse_wbs()
        activities = self._parse_activities()
        relationships = self._parse_relationships()
        resources = self._parse_resources()
        assignments = self._parse_assignments()
        calendars = self._parse_calendars()

        return Schedule(
            project=project,
            activities=activities,
            wbs_elements=wbs_elements,
            relationships=relationships,
            resources=resources,
            resource_assignments=assignments,
            calendars=calendars,
        )

    def _parse_tables(self, content: str) -> None:
        """Parse XER content into tables dictionary."""
        lines = content.split("\n")
        current_table = None
        current_columns: list[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            record_type = parts[0] if parts else ""

            if record_type == "%T":
                # Table definition
                current_table = parts[1] if len(parts) > 1 else None
                if current_table:
                    self.tables[current_table] = []
                    self.table_columns[current_table] = []

            elif record_type == "%F":
                # Field definitions
                if current_table:
                    current_columns = parts[1:]
                    self.table_columns[current_table] = current_columns

            elif record_type == "%R":
                # Data row
                if current_table and current_columns:
                    row_data = parts[1:]
                    row_dict = {}
                    for i, col in enumerate(current_columns):
                        row_dict[col] = row_data[i] if i < len(row_data) else ""
                    self.tables[current_table].append(row_dict)

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse P6 date string to datetime."""
        if not date_str or date_str.strip() == "":
            return None

        # P6 date formats
        formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d-%b-%y %H:%M",
            "%d-%b-%y",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def _parse_float(self, value: str) -> Optional[float]:
        """Parse string to float, handling empty strings."""
        if not value or value.strip() == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _parse_project(self) -> Project:
        """Parse PROJECT table to get project info."""
        projects = self.tables.get("PROJECT", [])
        if not projects:
            # Return a default project if none found
            return Project(
                project_id="default",
                project_code="DEFAULT",
                project_name="Imported Schedule",
            )

        proj = projects[0]  # Use first project
        return Project(
            project_id=proj.get("proj_id", ""),
            project_code=proj.get("proj_short_name", ""),
            project_name=proj.get("proj_name", proj.get("proj_short_name", "")),
            planned_start=self._parse_date(proj.get("plan_start_date", "")),
            must_finish_by=self._parse_date(proj.get("scd_end_date", "")),
            data_date=self._parse_date(proj.get("last_recalc_date", "")),
            description=proj.get("proj_desc", ""),
        )

    def _parse_wbs(self) -> list[WBSElement]:
        """Parse PROJWBS table for WBS elements."""
        wbs_data = self.tables.get("PROJWBS", [])
        wbs_elements = []

        for wbs in wbs_data:
            wbs_elements.append(
                WBSElement(
                    wbs_id=wbs.get("wbs_id", ""),
                    wbs_code=wbs.get("wbs_short_name", ""),
                    wbs_name=wbs.get("wbs_name", ""),
                    parent_wbs_id=wbs.get("parent_wbs_id", None) or None,
                    level=int(wbs.get("seq_num", "1") or "1"),
                    project_id=wbs.get("proj_id", None),
                )
            )

        return wbs_elements

    def _parse_activities(self) -> list[Activity]:
        """Parse TASK table for activities."""
        tasks = self.tables.get("TASK", [])
        activities = []

        for task in tasks:
            activity_type_code = task.get("task_type", "TT_Task")
            status_code = task.get("status_code", "TK_NotStart")

            activities.append(
                Activity(
                    activity_id=task.get("task_id", ""),
                    activity_code=task.get("task_code", ""),
                    activity_name=task.get("task_name", ""),
                    activity_type=self.ACTIVITY_TYPE_MAP.get(
                        activity_type_code, ActivityType.TASK_DEPENDENT
                    ),
                    status=self.STATUS_MAP.get(status_code, ActivityStatus.NOT_STARTED),
                    wbs_id=task.get("wbs_id", None) or None,
                    # Dates
                    planned_start=self._parse_date(task.get("target_start_date", "")),
                    planned_finish=self._parse_date(task.get("target_end_date", "")),
                    actual_start=self._parse_date(task.get("act_start_date", "")),
                    actual_finish=self._parse_date(task.get("act_end_date", "")),
                    early_start=self._parse_date(task.get("early_start_date", "")),
                    early_finish=self._parse_date(task.get("early_end_date", "")),
                    late_start=self._parse_date(task.get("late_start_date", "")),
                    late_finish=self._parse_date(task.get("late_end_date", "")),
                    # Duration
                    original_duration=self._parse_float(task.get("target_drtn_hr_cnt", "")),
                    remaining_duration=self._parse_float(task.get("remain_drtn_hr_cnt", "")),
                    actual_duration=self._parse_float(task.get("act_drtn_hr_cnt", "")),
                    # Float
                    total_float=self._parse_float(task.get("total_float_hr_cnt", "")),
                    free_float=self._parse_float(task.get("free_float_hr_cnt", "")),
                    # Progress
                    percent_complete=self._parse_float(task.get("phys_complete_pct", "")) or 0.0,
                    physical_percent_complete=self._parse_float(
                        task.get("phys_complete_pct", "")
                    ),
                    # Additional
                    calendar_id=task.get("clndr_id", None) or None,
                    notes=task.get("task_memo", None) or None,
                )
            )

        return activities

    def _parse_relationships(self) -> list[Relationship]:
        """Parse TASKPRED table for relationships."""
        preds = self.tables.get("TASKPRED", [])
        relationships = []

        for pred in preds:
            rel_type = pred.get("pred_type", "PR_FS")
            relationships.append(
                Relationship(
                    relationship_id=pred.get("task_pred_id", ""),
                    predecessor_id=pred.get("pred_task_id", ""),
                    successor_id=pred.get("task_id", ""),
                    relationship_type=self.RELATIONSHIP_MAP.get(
                        rel_type, RelationshipType.FINISH_TO_START
                    ),
                    lag=self._parse_float(pred.get("lag_hr_cnt", "")) or 0.0,
                )
            )

        return relationships

    def _parse_resources(self) -> list[Resource]:
        """Parse RSRC table for resources."""
        rsrcs = self.tables.get("RSRC", [])
        resources = []

        for rsrc in rsrcs:
            resources.append(
                Resource(
                    resource_id=rsrc.get("rsrc_id", ""),
                    resource_code=rsrc.get("rsrc_short_name", ""),
                    resource_name=rsrc.get("rsrc_name", ""),
                    resource_type=rsrc.get("rsrc_type", "Labor"),
                    unit_of_measure=rsrc.get("unit_of_measure", None) or None,
                    max_units_per_time=self._parse_float(rsrc.get("max_qty_per_hr", "")),
                    standard_rate=self._parse_float(rsrc.get("cost_qty_link_flag", "")),
                )
            )

        return resources

    def _parse_assignments(self) -> list[ResourceAssignment]:
        """Parse TASKRSRC table for resource assignments."""
        assigns = self.tables.get("TASKRSRC", [])
        assignments = []

        for assign in assigns:
            assignments.append(
                ResourceAssignment(
                    assignment_id=assign.get("taskrsrc_id", ""),
                    activity_id=assign.get("task_id", ""),
                    resource_id=assign.get("rsrc_id", ""),
                    planned_units=self._parse_float(assign.get("target_qty", "")),
                    actual_units=self._parse_float(assign.get("act_qty", "")),
                    remaining_units=self._parse_float(assign.get("remain_qty", "")),
                    planned_cost=self._parse_float(assign.get("target_cost", "")),
                    actual_cost=self._parse_float(assign.get("act_cost", "")),
                )
            )

        return assignments

    def _parse_calendars(self) -> list[Calendar]:
        """Parse CALENDAR table for calendars."""
        cals = self.tables.get("CALENDAR", [])
        calendars = []

        for cal in cals:
            calendars.append(
                Calendar(
                    calendar_id=cal.get("clndr_id", ""),
                    calendar_name=cal.get("clndr_name", ""),
                    calendar_type=cal.get("clndr_type", "Project"),
                    hours_per_day=self._parse_float(cal.get("day_hr_cnt", "")) or 8.0,
                    hours_per_week=self._parse_float(cal.get("week_hr_cnt", "")) or 40.0,
                )
            )

        return calendars


class P6Parser:
    """
    Unified parser that can handle different P6 export formats.
    Currently supports XER format.
    """

    def __init__(self):
        self.xer_parser = XERParser()

    def parse(self, file_path: str | Path) -> Schedule:
        """
        Parse a P6 export file.

        Args:
            file_path: Path to the P6 export file (XER format)

        Returns:
            Schedule object with all parsed data
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        if suffix == ".xer":
            return self.xer_parser.parse_file(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}. Supported formats: .xer")

    def parse_content(self, content: str, format: str = "xer") -> Schedule:
        """
        Parse P6 content from string.

        Args:
            content: File content as string
            format: Format type ('xer')

        Returns:
            Schedule object with all parsed data
        """
        if format.lower() == "xer":
            return self.xer_parser.parse_content(content)
        else:
            raise ValueError(f"Unsupported format: {format}")
