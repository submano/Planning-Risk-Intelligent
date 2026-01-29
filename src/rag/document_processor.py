"""
Document processor for converting schedule and risk data into LangChain documents.

This module handles the transformation of structured P6 schedule data and risk register
data into text documents suitable for embedding and retrieval.
"""

from datetime import datetime
from typing import Optional

from langchain_core.documents import Document

from src.models.risk import ExposureType, Risk, RiskRegister, RiskPriority
from src.models.schedule import Activity, Schedule, WBSElement


class DocumentProcessor:
    """Converts schedule and risk data into documents for RAG."""

    def __init__(
        self,
        chunk_size: int = 1000,
        include_metadata: bool = True,
    ):
        """
        Initialize document processor.

        Args:
            chunk_size: Target size for document chunks (approximate)
            include_metadata: Whether to include detailed metadata
        """
        self.chunk_size = chunk_size
        self.include_metadata = include_metadata

    def process_schedule(self, schedule: Schedule, source_file: str = "") -> list[Document]:
        """
        Process a schedule into documents.

        Args:
            schedule: Schedule object to process
            source_file: Source file path for metadata

        Returns:
            List of Document objects
        """
        documents = []

        # Project overview document
        documents.append(self._create_project_overview_doc(schedule, source_file))

        # Schedule summary document
        documents.append(self._create_schedule_summary_doc(schedule, source_file))

        # Critical path document
        if schedule.critical_path_activities:
            documents.append(self._create_critical_path_doc(schedule, source_file))

        # WBS hierarchy documents
        documents.extend(self._create_wbs_documents(schedule, source_file))

        # Activity documents (grouped by WBS)
        documents.extend(self._create_activity_documents(schedule, source_file))

        # Delayed activities document
        if schedule.delayed_activities:
            documents.append(self._create_delayed_activities_doc(schedule, source_file))

        # Milestone documents
        documents.extend(self._create_milestone_documents(schedule, source_file))

        return documents

    def process_risk_register(
        self, risk_register: RiskRegister, source_file: str = ""
    ) -> list[Document]:
        """
        Process a risk register into documents.

        Args:
            risk_register: RiskRegister object to process
            source_file: Source file path for metadata

        Returns:
            List of Document objects
        """
        documents = []

        # Risk register overview
        documents.append(self._create_risk_overview_doc(risk_register, source_file))

        # Risk summary by category
        documents.append(self._create_risk_category_summary_doc(risk_register, source_file))

        # Critical and high risks document
        documents.append(self._create_high_priority_risks_doc(risk_register, source_file))

        # Individual risk documents
        documents.extend(self._create_individual_risk_documents(risk_register, source_file))

        # Risk mitigation summary
        documents.append(self._create_mitigation_summary_doc(risk_register, source_file))

        return documents

    # Schedule document creation methods

    def _create_project_overview_doc(
        self, schedule: Schedule, source_file: str
    ) -> Document:
        """Create project overview document."""
        project = schedule.project

        content = f"""PROJECT OVERVIEW: {project.project_name}

Project Code: {project.project_code}
Project ID: {project.project_id}
Description: {project.description or 'No description provided'}

Key Dates:
- Planned Start: {self._format_date(project.planned_start)}
- Must Finish By: {self._format_date(project.must_finish_by)}
- Data Date (Status Date): {self._format_date(project.data_date)}

Schedule Statistics:
- Total Activities: {schedule.total_activities}
- Completed Activities: {schedule.completed_activities}
- Overall Progress: {schedule.schedule_progress:.1f}%
- Critical Path Activities: {len(schedule.critical_path_activities)}
- Delayed Activities: {len(schedule.delayed_activities)}
- WBS Elements: {len(schedule.wbs_elements)}
- Resources: {len(schedule.resources)}
"""

        return Document(
            page_content=content,
            metadata={
                "source": source_file,
                "doc_type": "project_overview",
                "project_id": project.project_id,
                "project_name": project.project_name,
            },
        )

    def _create_schedule_summary_doc(
        self, schedule: Schedule, source_file: str
    ) -> Document:
        """Create schedule summary document."""
        project = schedule.project

        # Calculate status breakdown
        status_counts = {}
        for activity in schedule.activities:
            status = activity.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        # Calculate float statistics
        float_values = [a.total_float for a in schedule.activities if a.total_float is not None]
        avg_float = sum(float_values) / len(float_values) if float_values else 0

        content = f"""SCHEDULE SUMMARY: {project.project_name}

Activity Status Breakdown:
{self._format_dict(status_counts)}

Float Analysis:
- Activities with Zero or Negative Float (Critical): {len(schedule.critical_path_activities)}
- Average Total Float: {avg_float:.1f} days
- Activities with float data: {len(float_values)} of {schedule.total_activities}

Progress Summary:
- Schedule Progress: {schedule.schedule_progress:.1f}%
- Completed: {schedule.completed_activities} activities
- Remaining: {schedule.total_activities - schedule.completed_activities} activities

Schedule Health Indicators:
- Critical Path Length: {len(schedule.critical_path_activities)} activities
- Delayed Activities: {len(schedule.delayed_activities)}
- Schedule Performance: {'On Track' if len(schedule.delayed_activities) == 0 else 'Delayed'}
"""

        return Document(
            page_content=content,
            metadata={
                "source": source_file,
                "doc_type": "schedule_summary",
                "project_id": project.project_id,
            },
        )

    def _create_critical_path_doc(
        self, schedule: Schedule, source_file: str
    ) -> Document:
        """Create critical path activities document."""
        critical_activities = schedule.critical_path_activities

        content = f"""CRITICAL PATH ACTIVITIES: {schedule.project.project_name}

The following {len(critical_activities)} activities are on the critical path (zero or negative float):

"""
        for activity in critical_activities[:50]:  # Limit to prevent overly long documents
            content += f"""
Activity: {activity.activity_code} - {activity.activity_name}
- Status: {activity.status.value}
- Planned: {self._format_date(activity.planned_start)} to {self._format_date(activity.planned_finish)}
- Total Float: {activity.total_float or 0:.1f} days
- Progress: {activity.percent_complete:.1f}%
"""

        if len(critical_activities) > 50:
            content += f"\n... and {len(critical_activities) - 50} more critical activities"

        return Document(
            page_content=content,
            metadata={
                "source": source_file,
                "doc_type": "critical_path",
                "project_id": schedule.project.project_id,
                "activity_count": len(critical_activities),
            },
        )

    def _create_wbs_documents(
        self, schedule: Schedule, source_file: str
    ) -> list[Document]:
        """Create documents for WBS hierarchy."""
        documents = []

        if not schedule.wbs_elements:
            return documents

        # Create WBS hierarchy document
        content = f"""WORK BREAKDOWN STRUCTURE: {schedule.project.project_name}

WBS Hierarchy:
"""
        for wbs in schedule.wbs_elements:
            indent = "  " * (wbs.level - 1)
            content += f"{indent}- {wbs.wbs_code}: {wbs.wbs_name}\n"

        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source": source_file,
                    "doc_type": "wbs_hierarchy",
                    "project_id": schedule.project.project_id,
                },
            )
        )

        return documents

    def _create_activity_documents(
        self, schedule: Schedule, source_file: str
    ) -> list[Document]:
        """Create documents for activities, grouped by WBS."""
        documents = []

        # Group activities by WBS
        wbs_activities: dict[str, list[Activity]] = {}
        for activity in schedule.activities:
            wbs_id = activity.wbs_id or "No WBS"
            if wbs_id not in wbs_activities:
                wbs_activities[wbs_id] = []
            wbs_activities[wbs_id].append(activity)

        # Create document for each WBS group
        wbs_lookup = {wbs.wbs_id: wbs for wbs in schedule.wbs_elements}

        for wbs_id, activities in wbs_activities.items():
            wbs = wbs_lookup.get(wbs_id)
            wbs_name = f"{wbs.wbs_code}: {wbs.wbs_name}" if wbs else wbs_id

            content = f"""ACTIVITIES FOR WBS: {wbs_name}

Number of activities: {len(activities)}

Activities:
"""
            for activity in activities:
                content += f"""
{activity.activity_code}: {activity.activity_name}
  Type: {activity.activity_type.value}
  Status: {activity.status.value}
  Dates: {self._format_date(activity.planned_start)} to {self._format_date(activity.planned_finish)}
  Duration: {activity.original_duration or 'N/A'} days
  Progress: {activity.percent_complete:.1f}%
  Float: {activity.total_float or 'N/A'} days
  Critical: {'Yes' if activity.is_critical else 'No'}
"""

            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": source_file,
                        "doc_type": "wbs_activities",
                        "wbs_id": wbs_id,
                        "wbs_name": wbs_name,
                        "project_id": schedule.project.project_id,
                        "activity_count": len(activities),
                    },
                )
            )

        return documents

    def _create_delayed_activities_doc(
        self, schedule: Schedule, source_file: str
    ) -> Document:
        """Create document for delayed activities."""
        delayed = schedule.delayed_activities

        content = f"""DELAYED ACTIVITIES: {schedule.project.project_name}

The following {len(delayed)} activities are delayed from their baseline:

"""
        for activity in delayed[:30]:
            delay = activity.delay_days or 0
            content += f"""
{activity.activity_code}: {activity.activity_name}
  Delay: {delay:.0f} days
  Baseline Finish: {self._format_date(activity.baseline_finish)}
  Current Forecast: {self._format_date(activity.early_finish)}
  Status: {activity.status.value}
  Progress: {activity.percent_complete:.1f}%
"""

        return Document(
            page_content=content,
            metadata={
                "source": source_file,
                "doc_type": "delayed_activities",
                "project_id": schedule.project.project_id,
                "delay_count": len(delayed),
            },
        )

    def _create_milestone_documents(
        self, schedule: Schedule, source_file: str
    ) -> list[Document]:
        """Create documents for milestones."""
        from src.models.schedule import ActivityType

        milestones = [
            a
            for a in schedule.activities
            if a.activity_type
            in [ActivityType.START_MILESTONE, ActivityType.FINISH_MILESTONE]
        ]

        if not milestones:
            return []

        content = f"""PROJECT MILESTONES: {schedule.project.project_name}

Key Milestones ({len(milestones)} total):

"""
        for milestone in milestones:
            content += f"""
{milestone.activity_code}: {milestone.activity_name}
  Type: {milestone.activity_type.value}
  Target Date: {self._format_date(milestone.planned_finish or milestone.planned_start)}
  Status: {milestone.status.value}
  Baseline: {self._format_date(milestone.baseline_finish or milestone.baseline_start)}
"""

        return [
            Document(
                page_content=content,
                metadata={
                    "source": source_file,
                    "doc_type": "milestones",
                    "project_id": schedule.project.project_id,
                    "milestone_count": len(milestones),
                },
            )
        ]

    # Risk document creation methods

    def _create_risk_overview_doc(
        self, risk_register: RiskRegister, source_file: str
    ) -> Document:
        """Create risk register overview document."""
        content = f"""RISK REGISTER OVERVIEW: {risk_register.project_name or 'Project Risk Register'}

Risk Statistics:
- Total Risks: {risk_register.total_risks}
- Open Risks: {len(risk_register.open_risks)}
- Critical Risks: {len(risk_register.critical_risks)}
- High Priority Risks: {len(risk_register.high_risks)}

Financial Impact Summary:
- Total Expected Monetary Value (EMV): ${risk_register.total_emv:,.2f}
- Total Expected Schedule Impact: {risk_register.total_expected_schedule_impact:.1f} days

Risk Exposure Type Distribution:
"""
        exposure_counts = {}
        for risk in risk_register.risks:
            exposure = risk.exposure_type.value
            exposure_counts[exposure] = exposure_counts.get(exposure, 0) + 1
        content += self._format_dict(exposure_counts)

        content += "\n\nRisk Status Distribution:\n"
        status_counts = {}
        for risk in risk_register.risks:
            status = risk.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        content += self._format_dict(status_counts)

        content += "\n\nRisk Priority Distribution:\n"
        priority_counts = {}
        for risk in risk_register.risks:
            priority = risk.priority.value
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        content += self._format_dict(priority_counts)

        return Document(
            page_content=content,
            metadata={
                "source": source_file,
                "doc_type": "risk_overview",
                "project_name": risk_register.project_name,
                "total_risks": risk_register.total_risks,
            },
        )

    def _create_risk_category_summary_doc(
        self, risk_register: RiskRegister, source_file: str
    ) -> Document:
        """Create risk summary by category."""
        content = f"""RISK ANALYSIS BY CATEGORY: {risk_register.project_name or 'Project'}

"""
        for category, risks in risk_register.risks_by_category().items():
            total_emv = sum(r.expected_monetary_value or 0 for r in risks)
            total_schedule = sum(r.expected_schedule_impact or 0 for r in risks)
            avg_score = sum(r.risk_score for r in risks) / len(risks) if risks else 0

            content += f"""
{category.value} Risks ({len(risks)} risks):
  Average Risk Score: {avg_score:.2f}
  Total EMV: ${total_emv:,.2f}
  Total Schedule Impact: {total_schedule:.1f} days
  Key Risks:
"""
            for risk in sorted(risks, key=lambda r: r.risk_score, reverse=True)[:3]:
                content += f"    - {risk.title} (Score: {risk.risk_score:.2f})\n"

        return Document(
            page_content=content,
            metadata={
                "source": source_file,
                "doc_type": "risk_category_summary",
                "project_name": risk_register.project_name,
            },
        )

    def _create_high_priority_risks_doc(
        self, risk_register: RiskRegister, source_file: str
    ) -> Document:
        """Create document for critical and high priority risks."""
        critical = risk_register.critical_risks
        high = risk_register.high_risks

        content = f"""HIGH PRIORITY RISKS: {risk_register.project_name or 'Project'}

CRITICAL RISKS ({len(critical)}):
"""
        for risk in critical:
            content += self._format_risk_summary(risk)

        content += f"\n\nHIGH PRIORITY RISKS ({len(high)}):\n"
        for risk in high:
            content += self._format_risk_summary(risk)

        return Document(
            page_content=content,
            metadata={
                "source": source_file,
                "doc_type": "high_priority_risks",
                "project_name": risk_register.project_name,
                "critical_count": len(critical),
                "high_count": len(high),
            },
        )

    def _create_individual_risk_documents(
        self, risk_register: RiskRegister, source_file: str
    ) -> list[Document]:
        """Create detailed documents for each risk."""
        documents = []

        for risk in risk_register.risks:
            # Build three-point estimate section if available
            three_point_pre = ""
            if risk.impact_min is not None or risk.impact_expected is not None or risk.impact_max is not None:
                three_point_pre = f"""
Three-Point Estimate (Pre-Mitigation):
  - Minimum: {risk.impact_min if risk.impact_min is not None else 'N/A'}
  - Expected: {risk.impact_expected if risk.impact_expected is not None else 'N/A'}
  - Maximum: {risk.impact_max if risk.impact_max is not None else 'N/A'}
"""

            three_point_post = ""
            if risk.post_impact_min is not None or risk.post_impact_expected is not None or risk.post_impact_max is not None:
                three_point_post = f"""
Three-Point Estimate (Post-Mitigation):
  - Minimum: {risk.post_impact_min if risk.post_impact_min is not None else 'N/A'}
  - Expected: {risk.post_impact_expected if risk.post_impact_expected is not None else 'N/A'}
  - Maximum: {risk.post_impact_max if risk.post_impact_max is not None else 'N/A'}
"""

            # Build residual assessment section
            residual_section = ""
            if risk.residual_probability is not None or risk.residual_impact_score is not None:
                residual_section = f"""
POST-MITIGATION (RESIDUAL) ASSESSMENT:
- Residual Probability: {self._format_percent(risk.residual_probability, 'Not assessed')}
- Residual Probability Band: {risk.residual_probability_band or 'N/A'}
- Residual Impact Score: {risk.residual_impact_score or 'Not assessed'}
- Post-Mitigation Level: {risk.post_mitigation_level or 'N/A'}
- Residual Risk Score: {self._format_float(risk.residual_risk_score, 2, 'N/A')}
{three_point_post}"""

            content = f"""RISK DETAIL: {risk.title}

Risk ID: {risk.risk_id}
Code: {risk.risk_code or 'N/A'}
Exposure Type: {risk.exposure_type.value}
Category: {risk.category.value}
Subcategory/Phase: {risk.subcategory or 'N/A'}
Status: {risk.status.value}
Priority: {risk.priority.value}
Group: {risk.group or 'N/A'}
Source: {risk.source or 'N/A'}
Department Category: {risk.department_category or 'N/A'}

DESCRIPTION:
{risk.description}

CONSEQUENCES:
{risk.consequences or 'Not specified'}

PRE-MITIGATION ASSESSMENT:
- Probability: {risk.probability:.0%}
- Probability Band: {risk.probability_band or 'N/A'}
- Impact Score: {risk.impact_score}/5
- Risk Score: {risk.risk_score:.2f}
- Pre-Mitigation Level: {risk.pre_mitigation_level or 'N/A'}
- Current Score Band: {risk.current_score_band or 'N/A'}
- Cost Impact: {self._format_currency(risk.impact_cost)}
- Schedule Impact: {risk.impact_schedule or 'Not quantified'} days
- Expected Monetary Value: {self._format_currency(risk.expected_monetary_value, 'N/A')}
- Expected Schedule Impact: {self._format_float(risk.expected_schedule_impact, 1, 'N/A')} days
- Distribution Type: {risk.distribution or 'N/A'}
- Simulation Type: {risk.simulation_type or 'N/A'}
{three_point_pre}
{residual_section}

RESPONSE STRATEGY:
- Response Type: {risk.response_type.value}
- Mitigation Plan: {risk.mitigation_plan or 'Not defined'}
- Contingency Plan: {risk.contingency_plan or 'Not defined'}
- Related Mitigation Actions: {risk.related_mitigation_count or 'N/A'}

OWNERSHIP:
- Risk Owner: {risk.risk_owner or 'Unassigned'}
- Assigned To: {risk.assigned_to or 'Unassigned'}

DATES:
- Identified/Created: {self._format_date(risk.identified_date)}
- Due Date: {self._format_date(risk.due_date)}
- Next Review Date: {self._format_date(risk.review_date)}
- Last Review Date: {self._format_date(risk.last_review_date)}
- Expiry Date: {self._format_date(risk.expiry_date)}
- Last Updated: {self._format_date(risk.last_updated)}

RELATED ITEMS:
- Related Activities: {', '.join(risk.related_activities) if risk.related_activities else 'None'}
- Related WBS: {risk.related_wbs or 'None'}
- Impact ID: {risk.impact_id or 'N/A'}

TRIGGERS AND WARNINGS:
- Cause/Trigger Conditions: {risk.trigger_conditions or 'Not defined'}
- Early Warning Signs: {risk.early_warning_signs or 'Not defined'}

ADDITIONAL INFORMATION:
- Scoring Description: {risk.scoring_description or 'N/A'}
- Attributes: {risk.attributes or 'N/A'}
- Last Review Note: {risk.last_review_note or 'N/A'}

NOTES/REMARKS:
{risk.notes or 'No additional notes'}
"""

            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": source_file,
                        "doc_type": "risk_detail",
                        "risk_id": risk.risk_id,
                        "risk_title": risk.title,
                        "exposure_type": risk.exposure_type.value,
                        "category": risk.category.value,
                        "status": risk.status.value,
                        "priority": risk.priority.value,
                        "risk_score": risk.risk_score,
                        "pre_mitigation_level": risk.pre_mitigation_level,
                        "post_mitigation_level": risk.post_mitigation_level,
                        "project_name": risk_register.project_name,
                    },
                )
            )

        return documents

    def _create_mitigation_summary_doc(
        self, risk_register: RiskRegister, source_file: str
    ) -> Document:
        """Create summary of all mitigation plans."""
        content = f"""RISK MITIGATION SUMMARY: {risk_register.project_name or 'Project'}

This document summarizes all mitigation and contingency plans for identified risks.

"""
        for risk in risk_register.risks:
            if risk.mitigation_plan or risk.contingency_plan:
                content += f"""
{risk.risk_id}: {risk.title}
Priority: {risk.priority.value} | Owner: {risk.risk_owner or 'Unassigned'}

Mitigation Plan:
{risk.mitigation_plan or 'Not defined'}

Contingency Plan:
{risk.contingency_plan or 'Not defined'}

---
"""

        return Document(
            page_content=content,
            metadata={
                "source": source_file,
                "doc_type": "mitigation_summary",
                "project_name": risk_register.project_name,
            },
        )

    # Helper methods

    def _format_date(self, dt: Optional[datetime]) -> str:
        """Format datetime to string."""
        if dt is None:
            return "Not set"
        return dt.strftime("%Y-%m-%d")

    def _format_dict(self, d: dict) -> str:
        """Format dictionary as indented list."""
        return "\n".join(f"  - {k}: {v}" for k, v in d.items())

    def _format_currency(self, value: Optional[float], default: str = "Not quantified") -> str:
        """Format currency value."""
        if value is None:
            return default
        return f"${value:,.2f}"

    def _format_float(self, value: Optional[float], decimals: int = 1, default: str = "N/A") -> str:
        """Format float value."""
        if value is None:
            return default
        return f"{value:.{decimals}f}"

    def _format_percent(self, value: Optional[float], default: str = "N/A") -> str:
        """Format percentage value."""
        if value is None:
            return default
        return f"{value:.0%}"

    def _format_risk_summary(self, risk: Risk) -> str:
        """Format risk as brief summary."""
        return f"""
{risk.risk_id}: {risk.title}
  Type: {risk.exposure_type.value} | Score: {risk.risk_score:.2f} | Probability: {risk.probability:.0%} | Impact: {risk.impact_score}/5
  Category: {risk.category.value} | Status: {risk.status.value}
  Pre-Mitigation Level: {risk.pre_mitigation_level or 'N/A'} | Post-Mitigation Level: {risk.post_mitigation_level or 'N/A'}
  Owner: {risk.risk_owner or 'Unassigned'}
  EMV: {self._format_currency(risk.expected_monetary_value, 'N/A')}
"""
