"""Data models for P6 schedule data."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ActivityType(str, Enum):
    """Activity types in P6."""
    TASK_DEPENDENT = "Task Dependent"
    RESOURCE_DEPENDENT = "Resource Dependent"
    LEVEL_OF_EFFORT = "Level of Effort"
    START_MILESTONE = "Start Milestone"
    FINISH_MILESTONE = "Finish Milestone"
    WBS_SUMMARY = "WBS Summary"


class ActivityStatus(str, Enum):
    """Activity status in P6."""
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


class RelationshipType(str, Enum):
    """Relationship types between activities."""
    FINISH_TO_START = "FS"
    FINISH_TO_FINISH = "FF"
    START_TO_START = "SS"
    START_TO_FINISH = "SF"


class WBSElement(BaseModel):
    """Work Breakdown Structure element."""
    wbs_id: str = Field(..., description="WBS unique identifier")
    wbs_code: str = Field(..., description="WBS code")
    wbs_name: str = Field(..., description="WBS name")
    parent_wbs_id: Optional[str] = Field(None, description="Parent WBS ID")
    level: int = Field(1, description="WBS hierarchy level")
    project_id: Optional[str] = Field(None, description="Associated project ID")


class Activity(BaseModel):
    """Schedule activity from P6."""
    activity_id: str = Field(..., description="Activity unique identifier")
    activity_code: str = Field(..., description="Activity code/ID")
    activity_name: str = Field(..., description="Activity name/description")
    activity_type: ActivityType = Field(
        ActivityType.TASK_DEPENDENT, description="Type of activity"
    )
    status: ActivityStatus = Field(
        ActivityStatus.NOT_STARTED, description="Current status"
    )
    wbs_id: Optional[str] = Field(None, description="Associated WBS ID")
    wbs_code: Optional[str] = Field(None, description="WBS code path")

    # Dates
    planned_start: Optional[datetime] = Field(None, description="Planned start date")
    planned_finish: Optional[datetime] = Field(None, description="Planned finish date")
    actual_start: Optional[datetime] = Field(None, description="Actual start date")
    actual_finish: Optional[datetime] = Field(None, description="Actual finish date")
    early_start: Optional[datetime] = Field(None, description="Early start date")
    early_finish: Optional[datetime] = Field(None, description="Early finish date")
    late_start: Optional[datetime] = Field(None, description="Late start date")
    late_finish: Optional[datetime] = Field(None, description="Late finish date")
    baseline_start: Optional[datetime] = Field(None, description="Baseline start date")
    baseline_finish: Optional[datetime] = Field(None, description="Baseline finish date")

    # Duration
    original_duration: Optional[float] = Field(None, description="Original duration (days)")
    remaining_duration: Optional[float] = Field(None, description="Remaining duration (days)")
    actual_duration: Optional[float] = Field(None, description="Actual duration (days)")

    # Float
    total_float: Optional[float] = Field(None, description="Total float (days)")
    free_float: Optional[float] = Field(None, description="Free float (days)")

    # Progress
    percent_complete: float = Field(0.0, description="Percent complete (0-100)")
    physical_percent_complete: Optional[float] = Field(
        None, description="Physical percent complete"
    )

    # Additional fields
    calendar_id: Optional[str] = Field(None, description="Calendar ID")
    primary_constraint_type: Optional[str] = Field(None, description="Primary constraint")
    primary_constraint_date: Optional[datetime] = Field(None, description="Constraint date")
    notes: Optional[str] = Field(None, description="Activity notes")

    @property
    def is_critical(self) -> bool:
        """Check if activity is on critical path."""
        return self.total_float is not None and self.total_float <= 0

    @property
    def is_delayed(self) -> bool:
        """Check if activity is delayed from baseline."""
        if self.baseline_finish and self.early_finish:
            return self.early_finish > self.baseline_finish
        return False

    @property
    def delay_days(self) -> Optional[float]:
        """Calculate delay in days from baseline."""
        if self.baseline_finish and self.early_finish:
            delta = self.early_finish - self.baseline_finish
            return delta.days if delta.days > 0 else 0
        return None


class Relationship(BaseModel):
    """Relationship/dependency between activities."""
    relationship_id: str = Field(..., description="Relationship unique identifier")
    predecessor_id: str = Field(..., description="Predecessor activity ID")
    successor_id: str = Field(..., description="Successor activity ID")
    relationship_type: RelationshipType = Field(
        RelationshipType.FINISH_TO_START, description="Type of relationship"
    )
    lag: float = Field(0.0, description="Lag time in days")


class Resource(BaseModel):
    """Resource definition."""
    resource_id: str = Field(..., description="Resource unique identifier")
    resource_code: str = Field(..., description="Resource code")
    resource_name: str = Field(..., description="Resource name")
    resource_type: str = Field("Labor", description="Resource type (Labor/Non-Labor/Material)")
    unit_of_measure: Optional[str] = Field(None, description="Unit of measure")
    max_units_per_time: Optional[float] = Field(None, description="Max units available")
    standard_rate: Optional[float] = Field(None, description="Standard cost rate")


class ResourceAssignment(BaseModel):
    """Resource assignment to activity."""
    assignment_id: str = Field(..., description="Assignment unique identifier")
    activity_id: str = Field(..., description="Activity ID")
    resource_id: str = Field(..., description="Resource ID")
    planned_units: Optional[float] = Field(None, description="Planned units")
    actual_units: Optional[float] = Field(None, description="Actual units")
    remaining_units: Optional[float] = Field(None, description="Remaining units")
    planned_cost: Optional[float] = Field(None, description="Planned cost")
    actual_cost: Optional[float] = Field(None, description="Actual cost")


class Calendar(BaseModel):
    """Calendar definition."""
    calendar_id: str = Field(..., description="Calendar unique identifier")
    calendar_name: str = Field(..., description="Calendar name")
    calendar_type: str = Field("Project", description="Calendar type")
    hours_per_day: float = Field(8.0, description="Working hours per day")
    hours_per_week: float = Field(40.0, description="Working hours per week")


class Project(BaseModel):
    """Project information."""
    project_id: str = Field(..., description="Project unique identifier")
    project_code: str = Field(..., description="Project code")
    project_name: str = Field(..., description="Project name")
    planned_start: Optional[datetime] = Field(None, description="Project planned start")
    must_finish_by: Optional[datetime] = Field(None, description="Project must finish by date")
    data_date: Optional[datetime] = Field(None, description="Data date / status date")
    description: Optional[str] = Field(None, description="Project description")


class Schedule(BaseModel):
    """Complete schedule data container."""
    project: Project
    activities: list[Activity] = Field(default_factory=list)
    wbs_elements: list[WBSElement] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    resource_assignments: list[ResourceAssignment] = Field(default_factory=list)
    calendars: list[Calendar] = Field(default_factory=list)

    @property
    def critical_path_activities(self) -> list[Activity]:
        """Get all activities on critical path."""
        return [a for a in self.activities if a.is_critical]

    @property
    def delayed_activities(self) -> list[Activity]:
        """Get all delayed activities."""
        return [a for a in self.activities if a.is_delayed]

    @property
    def total_activities(self) -> int:
        """Total number of activities."""
        return len(self.activities)

    @property
    def completed_activities(self) -> int:
        """Number of completed activities."""
        return len([a for a in self.activities if a.status == ActivityStatus.COMPLETED])

    @property
    def schedule_progress(self) -> float:
        """Overall schedule progress percentage."""
        if not self.activities:
            return 0.0
        return sum(a.percent_complete for a in self.activities) / len(self.activities)
