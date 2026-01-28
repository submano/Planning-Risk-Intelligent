"""Data models for risk register data."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class RiskCategory(str, Enum):
    """Risk categories."""
    TECHNICAL = "Technical"
    SCHEDULE = "Schedule"
    COST = "Cost"
    RESOURCE = "Resource"
    EXTERNAL = "External"
    ORGANIZATIONAL = "Organizational"
    MANAGEMENT = "Management"
    QUALITY = "Quality"
    SAFETY = "Safety"
    ENVIRONMENTAL = "Environmental"
    LEGAL = "Legal"
    REGULATORY = "Regulatory"
    OTHER = "Other"


class RiskStatus(str, Enum):
    """Risk status."""
    OPEN = "Open"
    MITIGATING = "Mitigating"
    MONITORING = "Monitoring"
    CLOSED = "Closed"
    RETIRED = "Retired"
    OCCURRED = "Occurred"


class RiskPriority(str, Enum):
    """Risk priority levels."""
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    VERY_LOW = "Very Low"


class RiskResponseType(str, Enum):
    """Risk response strategies."""
    AVOID = "Avoid"
    MITIGATE = "Mitigate"
    TRANSFER = "Transfer"
    ACCEPT = "Accept"
    EXPLOIT = "Exploit"  # For opportunities
    ENHANCE = "Enhance"  # For opportunities
    SHARE = "Share"  # For opportunities


class Risk(BaseModel):
    """Individual risk entry."""
    risk_id: str = Field(..., description="Risk unique identifier")
    risk_code: Optional[str] = Field(None, description="Risk code/number")
    title: str = Field(..., description="Risk title")
    description: str = Field(..., description="Detailed risk description")

    # Classification
    category: RiskCategory = Field(RiskCategory.OTHER, description="Risk category")
    subcategory: Optional[str] = Field(None, description="Risk subcategory")
    status: RiskStatus = Field(RiskStatus.OPEN, description="Current risk status")

    # Assessment - Pre-mitigation
    probability: float = Field(
        ..., ge=0.0, le=1.0, description="Probability of occurrence (0-1)"
    )
    impact_cost: Optional[float] = Field(None, description="Cost impact if occurs ($)")
    impact_schedule: Optional[float] = Field(
        None, description="Schedule impact if occurs (days)"
    )
    impact_score: float = Field(
        ..., ge=1, le=5, description="Impact severity score (1-5)"
    )

    # Assessment - Post-mitigation (residual)
    residual_probability: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Residual probability after mitigation"
    )
    residual_impact_score: Optional[float] = Field(
        None, ge=1, le=5, description="Residual impact score after mitigation"
    )

    # Response
    response_type: RiskResponseType = Field(
        RiskResponseType.MITIGATE, description="Risk response strategy"
    )
    mitigation_plan: Optional[str] = Field(None, description="Mitigation plan description")
    contingency_plan: Optional[str] = Field(None, description="Contingency plan if risk occurs")

    # Assignment
    risk_owner: Optional[str] = Field(None, description="Person responsible for managing risk")
    assigned_to: Optional[str] = Field(None, description="Person assigned for mitigation")

    # Dates
    identified_date: Optional[datetime] = Field(None, description="Date risk was identified")
    due_date: Optional[datetime] = Field(None, description="Due date for mitigation")
    review_date: Optional[datetime] = Field(None, description="Next review date")
    closed_date: Optional[datetime] = Field(None, description="Date risk was closed")

    # Related items
    related_activities: list[str] = Field(
        default_factory=list, description="Related activity IDs from schedule"
    )
    related_wbs: Optional[str] = Field(None, description="Related WBS element")
    related_risks: list[str] = Field(
        default_factory=list, description="Related risk IDs"
    )

    # Additional
    trigger_conditions: Optional[str] = Field(
        None, description="Conditions that trigger the risk"
    )
    early_warning_signs: Optional[str] = Field(
        None, description="Early warning indicators"
    )
    notes: Optional[str] = Field(None, description="Additional notes")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")

    @computed_field
    @property
    def risk_score(self) -> float:
        """Calculate risk score (probability * impact)."""
        return self.probability * self.impact_score

    @computed_field
    @property
    def residual_risk_score(self) -> Optional[float]:
        """Calculate residual risk score after mitigation."""
        if self.residual_probability is not None and self.residual_impact_score is not None:
            return self.residual_probability * self.residual_impact_score
        return None

    @computed_field
    @property
    def priority(self) -> RiskPriority:
        """Determine risk priority based on risk score."""
        score = self.risk_score
        if score >= 4.0:
            return RiskPriority.CRITICAL
        elif score >= 3.0:
            return RiskPriority.HIGH
        elif score >= 2.0:
            return RiskPriority.MEDIUM
        elif score >= 1.0:
            return RiskPriority.LOW
        else:
            return RiskPriority.VERY_LOW

    @computed_field
    @property
    def expected_monetary_value(self) -> Optional[float]:
        """Calculate Expected Monetary Value (EMV) for cost impact."""
        if self.impact_cost is not None:
            return self.probability * self.impact_cost
        return None

    @computed_field
    @property
    def expected_schedule_impact(self) -> Optional[float]:
        """Calculate expected schedule impact in days."""
        if self.impact_schedule is not None:
            return self.probability * self.impact_schedule
        return None


class RiskRegister(BaseModel):
    """Complete risk register container."""
    project_id: Optional[str] = Field(None, description="Associated project ID")
    project_name: Optional[str] = Field(None, description="Project name")
    risks: list[Risk] = Field(default_factory=list)
    last_updated: Optional[datetime] = Field(None, description="Register last updated")
    version: Optional[str] = Field(None, description="Register version")

    @property
    def open_risks(self) -> list[Risk]:
        """Get all open risks."""
        return [r for r in self.risks if r.status in [RiskStatus.OPEN, RiskStatus.MITIGATING]]

    @property
    def critical_risks(self) -> list[Risk]:
        """Get all critical priority risks."""
        return [r for r in self.risks if r.priority == RiskPriority.CRITICAL]

    @property
    def high_risks(self) -> list[Risk]:
        """Get high priority risks."""
        return [r for r in self.risks if r.priority == RiskPriority.HIGH]

    @property
    def total_risks(self) -> int:
        """Total number of risks."""
        return len(self.risks)

    @property
    def total_emv(self) -> float:
        """Total Expected Monetary Value of all open risks."""
        return sum(
            r.expected_monetary_value or 0.0
            for r in self.risks
            if r.status in [RiskStatus.OPEN, RiskStatus.MITIGATING]
        )

    @property
    def total_expected_schedule_impact(self) -> float:
        """Total expected schedule impact in days."""
        return sum(
            r.expected_schedule_impact or 0.0
            for r in self.risks
            if r.status in [RiskStatus.OPEN, RiskStatus.MITIGATING]
        )

    def risks_by_category(self) -> dict[RiskCategory, list[Risk]]:
        """Group risks by category."""
        result: dict[RiskCategory, list[Risk]] = {}
        for risk in self.risks:
            if risk.category not in result:
                result[risk.category] = []
            result[risk.category].append(risk)
        return result

    def risks_by_owner(self) -> dict[str, list[Risk]]:
        """Group risks by owner."""
        result: dict[str, list[Risk]] = {}
        for risk in self.risks:
            owner = risk.risk_owner or "Unassigned"
            if owner not in result:
                result[owner] = []
            result[owner].append(risk)
        return result
