"""
Parser for Excel Risk Register files.

Supports various Excel formats (.xlsx, .xls) and flexible column mapping
to handle different risk register templates.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.models.risk import (
    Risk,
    RiskCategory,
    RiskRegister,
    RiskResponseType,
    RiskStatus,
)


class RiskRegisterParser:
    """Parser for Excel risk register files."""

    # Default column mappings (can be customized)
    DEFAULT_COLUMN_MAP = {
        # Core fields
        "risk_id": ["risk_id", "id", "risk id", "risk #", "risk number", "no", "no."],
        "risk_code": ["risk_code", "code", "risk code", "reference", "ref"],
        "title": ["title", "risk title", "name", "risk name", "risk", "short description"],
        "description": [
            "description",
            "risk description",
            "desc",
            "details",
            "full description",
            "narrative",
        ],
        # Classification
        "category": ["category", "risk category", "type", "risk type", "area"],
        "subcategory": ["subcategory", "sub-category", "sub category"],
        "status": ["status", "risk status", "state", "current status"],
        # Probability and Impact
        "probability": [
            "probability",
            "prob",
            "likelihood",
            "prob.",
            "probability score",
            "p",
            "likelihood score",
        ],
        "impact_score": [
            "impact",
            "impact score",
            "severity",
            "consequence",
            "i",
            "impact rating",
        ],
        "impact_cost": [
            "cost impact",
            "cost_impact",
            "impact cost",
            "$ impact",
            "financial impact",
            "cost ($)",
        ],
        "impact_schedule": [
            "schedule impact",
            "schedule_impact",
            "time impact",
            "days impact",
            "schedule (days)",
            "delay (days)",
        ],
        # Residual
        "residual_probability": [
            "residual probability",
            "residual prob",
            "post-mitigation probability",
            "mitigated probability",
        ],
        "residual_impact_score": [
            "residual impact",
            "residual severity",
            "post-mitigation impact",
            "mitigated impact",
        ],
        # Response
        "response_type": [
            "response",
            "response type",
            "strategy",
            "risk response",
            "treatment",
        ],
        "mitigation_plan": [
            "mitigation",
            "mitigation plan",
            "mitigation actions",
            "treatment plan",
            "response plan",
            "actions",
        ],
        "contingency_plan": [
            "contingency",
            "contingency plan",
            "fallback",
            "backup plan",
        ],
        # Assignment
        "risk_owner": ["owner", "risk owner", "responsible", "accountable"],
        "assigned_to": ["assigned to", "assigned", "assignee", "action owner"],
        # Dates
        "identified_date": [
            "identified",
            "identified date",
            "date identified",
            "raised date",
            "creation date",
        ],
        "due_date": ["due date", "due", "target date", "action due date"],
        "review_date": ["review date", "next review", "review"],
        "closed_date": ["closed date", "closure date", "date closed"],
        # Related items
        "related_activities": [
            "related activities",
            "activities",
            "linked activities",
            "affected activities",
        ],
        "related_wbs": ["wbs", "related wbs", "wbs element", "work package"],
        # Additional
        "trigger_conditions": ["trigger", "triggers", "trigger conditions", "cause"],
        "early_warning_signs": [
            "early warning",
            "warning signs",
            "indicators",
            "early indicators",
        ],
        "notes": ["notes", "comments", "remarks", "additional notes"],
    }

    # Category mappings
    CATEGORY_MAP = {
        "technical": RiskCategory.TECHNICAL,
        "tech": RiskCategory.TECHNICAL,
        "schedule": RiskCategory.SCHEDULE,
        "time": RiskCategory.SCHEDULE,
        "cost": RiskCategory.COST,
        "budget": RiskCategory.COST,
        "financial": RiskCategory.COST,
        "resource": RiskCategory.RESOURCE,
        "resources": RiskCategory.RESOURCE,
        "staffing": RiskCategory.RESOURCE,
        "external": RiskCategory.EXTERNAL,
        "organizational": RiskCategory.ORGANIZATIONAL,
        "organisation": RiskCategory.ORGANIZATIONAL,
        "organization": RiskCategory.ORGANIZATIONAL,
        "management": RiskCategory.MANAGEMENT,
        "quality": RiskCategory.QUALITY,
        "safety": RiskCategory.SAFETY,
        "hse": RiskCategory.SAFETY,
        "environmental": RiskCategory.ENVIRONMENTAL,
        "environment": RiskCategory.ENVIRONMENTAL,
        "legal": RiskCategory.LEGAL,
        "contractual": RiskCategory.LEGAL,
        "regulatory": RiskCategory.REGULATORY,
        "compliance": RiskCategory.REGULATORY,
    }

    # Status mappings
    STATUS_MAP = {
        "open": RiskStatus.OPEN,
        "active": RiskStatus.OPEN,
        "new": RiskStatus.OPEN,
        "mitigating": RiskStatus.MITIGATING,
        "in progress": RiskStatus.MITIGATING,
        "treating": RiskStatus.MITIGATING,
        "monitoring": RiskStatus.MONITORING,
        "watch": RiskStatus.MONITORING,
        "closed": RiskStatus.CLOSED,
        "resolved": RiskStatus.CLOSED,
        "retired": RiskStatus.RETIRED,
        "occurred": RiskStatus.OCCURRED,
        "realized": RiskStatus.OCCURRED,
    }

    # Response type mappings
    RESPONSE_MAP = {
        "avoid": RiskResponseType.AVOID,
        "mitigate": RiskResponseType.MITIGATE,
        "reduce": RiskResponseType.MITIGATE,
        "transfer": RiskResponseType.TRANSFER,
        "share": RiskResponseType.SHARE,
        "accept": RiskResponseType.ACCEPT,
        "exploit": RiskResponseType.EXPLOIT,
        "enhance": RiskResponseType.ENHANCE,
    }

    def __init__(self, column_map: Optional[dict] = None):
        """
        Initialize parser with optional custom column mapping.

        Args:
            column_map: Custom mapping of field names to possible column headers
        """
        self.column_map = column_map or self.DEFAULT_COLUMN_MAP

    def parse_file(
        self,
        file_path: str | Path,
        sheet_name: str | int = 0,
        header_row: int = 0,
    ) -> RiskRegister:
        """
        Parse an Excel risk register file.

        Args:
            file_path: Path to the Excel file
            sheet_name: Sheet name or index (default: first sheet)
            header_row: Row number containing headers (0-indexed)

        Returns:
            RiskRegister object with all parsed risks
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Risk register file not found: {file_path}")

        # Read Excel file
        df = pd.read_excel(
            file_path,
            sheet_name=sheet_name,
            header=header_row,
        )

        return self._parse_dataframe(df, file_path.stem)

    def parse_dataframe(self, df: pd.DataFrame, project_name: str = "") -> RiskRegister:
        """
        Parse a pandas DataFrame containing risk register data.

        Args:
            df: DataFrame with risk register data
            project_name: Optional project name

        Returns:
            RiskRegister object
        """
        return self._parse_dataframe(df, project_name)

    def _parse_dataframe(self, df: pd.DataFrame, project_name: str = "") -> RiskRegister:
        """Internal method to parse DataFrame to RiskRegister."""
        # Normalize column names
        df.columns = df.columns.str.lower().str.strip()

        # Build column mapping for this specific file
        field_to_column = self._map_columns(df.columns.tolist())

        risks = []
        for idx, row in df.iterrows():
            try:
                risk = self._parse_row(row, field_to_column, idx)
                if risk:
                    risks.append(risk)
            except Exception as e:
                # Log warning but continue parsing
                print(f"Warning: Failed to parse row {idx}: {e}")
                continue

        return RiskRegister(
            project_name=project_name,
            risks=risks,
            last_updated=datetime.now(),
        )

    def _map_columns(self, columns: list[str]) -> dict[str, str]:
        """Map field names to actual column names in the DataFrame."""
        field_to_column = {}

        for field, possible_names in self.column_map.items():
            for name in possible_names:
                if name in columns:
                    field_to_column[field] = name
                    break

        return field_to_column

    def _parse_row(
        self, row: pd.Series, field_map: dict[str, str], row_idx: int
    ) -> Optional[Risk]:
        """Parse a single row into a Risk object."""

        def get_value(field: str, default: Any = None) -> Any:
            """Get value from row using field mapping."""
            if field in field_map:
                val = row.get(field_map[field])
                if pd.isna(val):
                    return default
                return val
            return default

        def get_str(field: str, default: str = "") -> str:
            """Get string value."""
            val = get_value(field, default)
            return str(val).strip() if val else default

        def get_float(field: str, default: Optional[float] = None) -> Optional[float]:
            """Get float value."""
            val = get_value(field)
            if val is None:
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        def get_date(field: str) -> Optional[datetime]:
            """Get datetime value."""
            val = get_value(field)
            if val is None:
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, pd.Timestamp):
                return val.to_pydatetime()
            try:
                return pd.to_datetime(val).to_pydatetime()
            except (ValueError, TypeError):
                return None

        def get_list(field: str) -> list[str]:
            """Get list value from comma-separated string."""
            val = get_str(field)
            if not val:
                return []
            return [item.strip() for item in val.split(",") if item.strip()]

        # Get required fields
        risk_id = get_str("risk_id") or str(row_idx + 1)
        title = get_str("title")
        description = get_str("description")

        # Skip rows without title/description (likely empty or header rows)
        if not title and not description:
            return None

        # Parse probability (handle percentage or decimal)
        probability = get_float("probability", 0.5)
        if probability and probability > 1:
            probability = probability / 100.0  # Convert percentage to decimal
        probability = max(0.0, min(1.0, probability or 0.5))

        # Parse impact score (handle different scales)
        impact_score = get_float("impact_score", 3.0)
        if impact_score and impact_score > 5:
            impact_score = impact_score / 20.0  # Normalize to 1-5 scale
        impact_score = max(1.0, min(5.0, impact_score or 3.0))

        # Parse category
        category_str = get_str("category").lower()
        category = self.CATEGORY_MAP.get(category_str, RiskCategory.OTHER)

        # Parse status
        status_str = get_str("status").lower()
        status = self.STATUS_MAP.get(status_str, RiskStatus.OPEN)

        # Parse response type
        response_str = get_str("response_type").lower()
        response_type = self.RESPONSE_MAP.get(response_str, RiskResponseType.MITIGATE)

        # Parse residual values
        residual_prob = get_float("residual_probability")
        if residual_prob and residual_prob > 1:
            residual_prob = residual_prob / 100.0
        residual_impact = get_float("residual_impact_score")
        if residual_impact and residual_impact > 5:
            residual_impact = residual_impact / 20.0

        return Risk(
            risk_id=risk_id,
            risk_code=get_str("risk_code") or None,
            title=title or f"Risk {risk_id}",
            description=description or title or f"Risk {risk_id}",
            category=category,
            subcategory=get_str("subcategory") or None,
            status=status,
            probability=probability,
            impact_score=impact_score,
            impact_cost=get_float("impact_cost"),
            impact_schedule=get_float("impact_schedule"),
            residual_probability=residual_prob,
            residual_impact_score=residual_impact,
            response_type=response_type,
            mitigation_plan=get_str("mitigation_plan") or None,
            contingency_plan=get_str("contingency_plan") or None,
            risk_owner=get_str("risk_owner") or None,
            assigned_to=get_str("assigned_to") or None,
            identified_date=get_date("identified_date"),
            due_date=get_date("due_date"),
            review_date=get_date("review_date"),
            closed_date=get_date("closed_date"),
            related_activities=get_list("related_activities"),
            related_wbs=get_str("related_wbs") or None,
            trigger_conditions=get_str("trigger_conditions") or None,
            early_warning_signs=get_str("early_warning_signs") or None,
            notes=get_str("notes") or None,
            last_updated=datetime.now(),
        )


def create_sample_risk_register() -> pd.DataFrame:
    """Create a sample risk register DataFrame for testing/demo."""
    data = {
        "Risk ID": ["R001", "R002", "R003", "R004", "R005"],
        "Title": [
            "Resource Availability Risk",
            "Technical Integration Failure",
            "Schedule Delay - Permitting",
            "Cost Overrun - Materials",
            "Weather Impact on Construction",
        ],
        "Description": [
            "Key resources may not be available during critical project phases due to competing priorities",
            "Integration between legacy systems and new platform may fail or require significant rework",
            "Permit approval process may take longer than planned due to regulatory requirements",
            "Material costs may increase significantly due to market volatility and supply chain issues",
            "Adverse weather conditions may delay outdoor construction activities during winter months",
        ],
        "Category": ["Resource", "Technical", "Schedule", "Cost", "External"],
        "Status": ["Open", "Mitigating", "Monitoring", "Open", "Open"],
        "Probability": [0.6, 0.4, 0.7, 0.5, 0.3],
        "Impact Score": [4, 5, 3, 4, 3],
        "Cost Impact": [50000, 200000, 30000, 150000, 75000],
        "Schedule Impact": [15, 30, 45, 10, 20],
        "Response Type": ["Mitigate", "Avoid", "Accept", "Transfer", "Mitigate"],
        "Mitigation Plan": [
            "Cross-train team members and identify backup resources",
            "Conduct proof of concept early and have fallback architecture",
            "Start permit application early and maintain regulatory relationships",
            "Lock in material prices with suppliers through contracts",
            "Build weather contingency into schedule and plan indoor work alternatives",
        ],
        "Owner": ["PM", "Tech Lead", "PM", "Procurement", "Site Manager"],
        "Due Date": [
            "2024-03-15",
            "2024-02-28",
            "2024-04-01",
            "2024-02-15",
            "2024-01-31",
        ],
    }
    return pd.DataFrame(data)
