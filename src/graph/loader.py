"""
Graph Data Loader for Planning & Risk Intelligence.

Loads schedule and risk register data into the Neo4j knowledge graph.
"""

from datetime import datetime
from typing import Optional

from src.graph.store import GraphStore
from src.graph.schema import NodeType, RelationshipType
from src.models.schedule import Schedule, Activity, ActivityType
from src.models.risk import RiskRegister, Risk


class GraphDataLoader:
    """
    Loads schedule and risk data into the Neo4j graph.
    """

    def __init__(self, graph_store: GraphStore):
        """
        Initialize the loader.

        Args:
            graph_store: GraphStore instance for database operations
        """
        self.store = graph_store

    def _format_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """Format datetime for Neo4j."""
        if dt is None:
            return None
        return dt.isoformat()

    def load_schedule(self, schedule: Schedule, clear_existing: bool = False) -> dict:
        """
        Load a schedule into the knowledge graph.

        Args:
            schedule: Schedule object to load
            clear_existing: Whether to clear existing data first

        Returns:
            Statistics about loaded data
        """
        if clear_existing:
            self.store.clear_database()
            self.store.initialize_schema()

        stats = {
            "project": 0,
            "wbs": 0,
            "activities": 0,
            "milestones": 0,
            "relationships": 0,
            "resources": 0,
            "calendars": 0,
        }

        # Load project
        self._load_project(schedule)
        stats["project"] = 1

        # Load calendars
        for calendar in schedule.calendars:
            self._load_calendar(calendar, schedule.project.project_id)
        stats["calendars"] = len(schedule.calendars)

        # Load resources
        for resource in schedule.resources:
            self._load_resource(resource, schedule.project.project_id)
        stats["resources"] = len(schedule.resources)

        # Load WBS hierarchy
        for wbs in schedule.wbs_elements:
            self._load_wbs(wbs, schedule.project.project_id)
        stats["wbs"] = len(schedule.wbs_elements)

        # Load activities and milestones
        for activity in schedule.activities:
            if activity.activity_type in [ActivityType.START_MILESTONE, ActivityType.FINISH_MILESTONE]:
                self._load_milestone(activity, schedule.project.project_id)
                stats["milestones"] += 1
            else:
                self._load_activity(activity, schedule.project.project_id)
                stats["activities"] += 1

        # Load relationships (schedule logic)
        for rel in schedule.relationships:
            self._load_relationship(rel)
        stats["relationships"] = len(schedule.relationships)

        # Load resource assignments
        for assignment in schedule.resource_assignments:
            self._load_resource_assignment(assignment)

        # Create analysis relationships
        self._create_critical_path_relationships(schedule.project.project_id)
        self._create_delay_relationships(schedule.project.project_id)

        print(f"Loaded schedule: {stats}")
        return stats

    def load_risk_register(
        self,
        risk_register: RiskRegister,
        project_id: Optional[str] = None,
    ) -> dict:
        """
        Load a risk register into the knowledge graph.

        Args:
            risk_register: RiskRegister object to load
            project_id: Project ID to link risks to

        Returns:
            Statistics about loaded data
        """
        stats = {
            "risks": 0,
            "categories": 0,
            "risk_activity_links": 0,
        }

        # Create risk category nodes
        categories = set()
        for risk in risk_register.risks:
            categories.add(risk.category.value)

        for category in categories:
            self._load_risk_category(category)
        stats["categories"] = len(categories)

        # Load risks
        for risk in risk_register.risks:
            self._load_risk(risk, project_id)
            stats["risks"] += 1

            # Link to activities if specified
            if risk.related_activities:
                for activity_code in risk.related_activities:
                    self._link_risk_to_activity(risk.risk_id, activity_code)
                    stats["risk_activity_links"] += 1

        print(f"Loaded risk register: {stats}")
        return stats

    def _load_project(self, schedule: Schedule) -> None:
        """Load project node."""
        project = schedule.project
        query = """
        MERGE (p:Project {project_id: $project_id})
        SET p.project_code = $project_code,
            p.project_name = $project_name,
            p.description = $description,
            p.planned_start = $planned_start,
            p.planned_finish = $planned_finish,
            p.data_date = $data_date,
            p.total_activities = $total_activities,
            p.completed_activities = $completed_activities,
            p.progress_percent = $progress_percent
        """
        self.store.execute_write(query, {
            "project_id": project.project_id,
            "project_code": project.project_code,
            "project_name": project.project_name,
            "description": project.description,
            "planned_start": self._format_datetime(project.planned_start),
            "planned_finish": self._format_datetime(project.must_finish_by),
            "data_date": self._format_datetime(project.data_date),
            "total_activities": schedule.total_activities,
            "completed_activities": schedule.completed_activities,
            "progress_percent": schedule.schedule_progress,
        })

    def _load_calendar(self, calendar, project_id: str) -> None:
        """Load calendar node."""
        query = """
        MERGE (c:Calendar {calendar_id: $calendar_id})
        SET c.calendar_name = $calendar_name,
            c.calendar_type = $calendar_type,
            c.hours_per_day = $hours_per_day,
            c.hours_per_week = $hours_per_week
        WITH c
        MATCH (p:Project {project_id: $project_id})
        MERGE (p)-[:CONTAINS]->(c)
        """
        self.store.execute_write(query, {
            "calendar_id": calendar.calendar_id,
            "calendar_name": calendar.calendar_name,
            "calendar_type": calendar.calendar_type,
            "hours_per_day": calendar.hours_per_day,
            "hours_per_week": calendar.hours_per_week,
            "project_id": project_id,
        })

    def _load_resource(self, resource, project_id: str) -> None:
        """Load resource node."""
        query = """
        MERGE (r:Resource {resource_id: $resource_id})
        SET r.resource_code = $resource_code,
            r.resource_name = $resource_name,
            r.resource_type = $resource_type,
            r.unit_of_measure = $unit_of_measure,
            r.max_units = $max_units,
            r.standard_rate = $standard_rate
        WITH r
        MATCH (p:Project {project_id: $project_id})
        MERGE (p)-[:CONTAINS]->(r)
        """
        self.store.execute_write(query, {
            "resource_id": resource.resource_id,
            "resource_code": resource.resource_code,
            "resource_name": resource.resource_name,
            "resource_type": resource.resource_type,
            "unit_of_measure": resource.unit_of_measure,
            "max_units": resource.max_units_per_time,
            "standard_rate": resource.standard_rate,
            "project_id": project_id,
        })

    def _load_wbs(self, wbs, project_id: str) -> None:
        """Load WBS node and create hierarchy relationships."""
        query = """
        MERGE (w:WBS {wbs_id: $wbs_id})
        SET w.wbs_code = $wbs_code,
            w.wbs_name = $wbs_name,
            w.level = $level,
            w.project_id = $project_id
        """
        self.store.execute_write(query, {
            "wbs_id": wbs.wbs_id,
            "wbs_code": wbs.wbs_code,
            "wbs_name": wbs.wbs_name,
            "level": wbs.level,
            "project_id": project_id,
        })

        # Create hierarchy relationship
        if wbs.parent_wbs_id:
            self.store.execute_write("""
                MATCH (parent:WBS {wbs_id: $parent_id})
                MATCH (child:WBS {wbs_id: $child_id})
                MERGE (parent)-[:CONTAINS]->(child)
            """, {
                "parent_id": wbs.parent_wbs_id,
                "child_id": wbs.wbs_id,
            })
        else:
            # Link top-level WBS to project
            self.store.execute_write("""
                MATCH (p:Project {project_id: $project_id})
                MATCH (w:WBS {wbs_id: $wbs_id})
                MERGE (p)-[:CONTAINS]->(w)
            """, {
                "project_id": project_id,
                "wbs_id": wbs.wbs_id,
            })

    def _load_activity(self, activity: Activity, project_id: str) -> None:
        """Load activity node."""
        query = """
        MERGE (a:Activity {activity_id: $activity_id})
        SET a.activity_code = $activity_code,
            a.activity_name = $activity_name,
            a.activity_type = $activity_type,
            a.status = $status,
            a.planned_start = $planned_start,
            a.planned_finish = $planned_finish,
            a.actual_start = $actual_start,
            a.actual_finish = $actual_finish,
            a.early_start = $early_start,
            a.early_finish = $early_finish,
            a.late_start = $late_start,
            a.late_finish = $late_finish,
            a.baseline_start = $baseline_start,
            a.baseline_finish = $baseline_finish,
            a.original_duration = $original_duration,
            a.remaining_duration = $remaining_duration,
            a.actual_duration = $actual_duration,
            a.total_float = $total_float,
            a.free_float = $free_float,
            a.percent_complete = $percent_complete,
            a.is_critical = $is_critical,
            a.is_delayed = $is_delayed,
            a.delay_days = $delay_days,
            a.project_id = $project_id
        """
        self.store.execute_write(query, {
            "activity_id": activity.activity_id,
            "activity_code": activity.activity_code,
            "activity_name": activity.activity_name,
            "activity_type": activity.activity_type.value,
            "status": activity.status.value,
            "planned_start": self._format_datetime(activity.planned_start),
            "planned_finish": self._format_datetime(activity.planned_finish),
            "actual_start": self._format_datetime(activity.actual_start),
            "actual_finish": self._format_datetime(activity.actual_finish),
            "early_start": self._format_datetime(activity.early_start),
            "early_finish": self._format_datetime(activity.early_finish),
            "late_start": self._format_datetime(activity.late_start),
            "late_finish": self._format_datetime(activity.late_finish),
            "baseline_start": self._format_datetime(activity.baseline_start),
            "baseline_finish": self._format_datetime(activity.baseline_finish),
            "original_duration": activity.original_duration,
            "remaining_duration": activity.remaining_duration,
            "actual_duration": activity.actual_duration,
            "total_float": activity.total_float,
            "free_float": activity.free_float,
            "percent_complete": activity.percent_complete,
            "is_critical": activity.is_critical,
            "is_delayed": activity.is_delayed,
            "delay_days": activity.delay_days,
            "project_id": project_id,
        })

        # Link to WBS
        if activity.wbs_id:
            self.store.execute_write("""
                MATCH (w:WBS {wbs_id: $wbs_id})
                MATCH (a:Activity {activity_id: $activity_id})
                MERGE (w)-[:CONTAINS]->(a)
            """, {
                "wbs_id": activity.wbs_id,
                "activity_id": activity.activity_id,
            })

        # Link to calendar
        if activity.calendar_id:
            self.store.execute_write("""
                MATCH (c:Calendar {calendar_id: $calendar_id})
                MATCH (a:Activity {activity_id: $activity_id})
                MERGE (a)-[:FOLLOWS]->(c)
            """, {
                "calendar_id": activity.calendar_id,
                "activity_id": activity.activity_id,
            })

    def _load_milestone(self, activity: Activity, project_id: str) -> None:
        """Load milestone node."""
        query = """
        MERGE (m:Milestone {activity_id: $activity_id})
        SET m.activity_code = $activity_code,
            m.activity_name = $activity_name,
            m.milestone_type = $milestone_type,
            m.target_date = $target_date,
            m.actual_date = $actual_date,
            m.status = $status,
            m.is_critical = $is_critical,
            m.project_id = $project_id
        """
        target_date = activity.planned_finish or activity.planned_start
        actual_date = activity.actual_finish or activity.actual_start

        self.store.execute_write(query, {
            "activity_id": activity.activity_id,
            "activity_code": activity.activity_code,
            "activity_name": activity.activity_name,
            "milestone_type": activity.activity_type.value,
            "target_date": self._format_datetime(target_date),
            "actual_date": self._format_datetime(actual_date),
            "status": activity.status.value,
            "is_critical": activity.is_critical,
            "project_id": project_id,
        })

        # Also create as Activity for relationship compatibility
        self._load_activity(activity, project_id)

    def _load_relationship(self, rel) -> None:
        """Load schedule relationship between activities."""
        # Map relationship type to specific relationship
        rel_type_map = {
            "FS": "FINISH_TO_START",
            "FF": "FINISH_TO_FINISH",
            "SS": "START_TO_START",
            "SF": "START_TO_FINISH",
        }
        rel_type = rel_type_map.get(rel.relationship_type.value, "PRECEDES")

        query = f"""
        MATCH (pred:Activity {{activity_id: $pred_id}})
        MATCH (succ:Activity {{activity_id: $succ_id}})
        MERGE (pred)-[r:{rel_type}]->(succ)
        SET r.lag = $lag,
            r.relationship_type = $rel_type_code
        WITH pred, succ
        MERGE (pred)-[:PRECEDES]->(succ)
        """
        self.store.execute_write(query, {
            "pred_id": rel.predecessor_id,
            "succ_id": rel.successor_id,
            "lag": rel.lag,
            "rel_type_code": rel.relationship_type.value,
        })

    def _load_resource_assignment(self, assignment) -> None:
        """Load resource assignment relationship."""
        query = """
        MATCH (a:Activity {activity_id: $activity_id})
        MATCH (r:Resource {resource_id: $resource_id})
        MERGE (a)-[u:USES]->(r)
        SET u.planned_units = $planned_units,
            u.actual_units = $actual_units,
            u.remaining_units = $remaining_units,
            u.planned_cost = $planned_cost,
            u.actual_cost = $actual_cost
        """
        self.store.execute_write(query, {
            "activity_id": assignment.activity_id,
            "resource_id": assignment.resource_id,
            "planned_units": assignment.planned_units,
            "actual_units": assignment.actual_units,
            "remaining_units": assignment.remaining_units,
            "planned_cost": assignment.planned_cost,
            "actual_cost": assignment.actual_cost,
        })

    def _load_risk_category(self, category_name: str) -> None:
        """Load risk category node."""
        query = """
        MERGE (rc:RiskCategory {name: $name})
        SET rc.category_id = $category_id
        """
        self.store.execute_write(query, {
            "name": category_name,
            "category_id": category_name.lower().replace(" ", "_"),
        })

    def _load_risk(self, risk: Risk, project_id: Optional[str]) -> None:
        """Load risk node."""
        query = """
        MERGE (r:Risk {risk_id: $risk_id})
        SET r.risk_code = $risk_code,
            r.title = $title,
            r.description = $description,
            r.category = $category,
            r.subcategory = $subcategory,
            r.status = $status,
            r.priority = $priority,
            r.exposure_type = $exposure_type,
            r.group = $group,
            r.source = $source,
            r.department_category = $department_category,
            r.probability = $probability,
            r.probability_band = $probability_band,
            r.impact_score = $impact_score,
            r.risk_score = $risk_score,
            r.impact_cost = $impact_cost,
            r.impact_schedule = $impact_schedule,
            r.impact_min = $impact_min,
            r.impact_expected = $impact_expected,
            r.impact_max = $impact_max,
            r.pre_mitigation_level = $pre_mitigation_level,
            r.current_score_band = $current_score_band,
            r.simulation_type = $simulation_type,
            r.distribution = $distribution,
            r.emv = $emv,
            r.expected_schedule_impact = $expected_schedule_impact,
            r.residual_probability = $residual_probability,
            r.residual_probability_band = $residual_probability_band,
            r.residual_impact_score = $residual_impact_score,
            r.post_mitigation_level = $post_mitigation_level,
            r.post_distribution = $post_distribution,
            r.post_exposure = $post_exposure,
            r.post_impact_min = $post_impact_min,
            r.post_impact_expected = $post_impact_expected,
            r.post_impact_max = $post_impact_max,
            r.response_type = $response_type,
            r.mitigation_plan = $mitigation_plan,
            r.contingency_plan = $contingency_plan,
            r.consequences = $consequences,
            r.related_mitigation_count = $related_mitigation_count,
            r.risk_owner = $risk_owner,
            r.assigned_to = $assigned_to,
            r.identified_date = $identified_date,
            r.due_date = $due_date,
            r.review_date = $review_date,
            r.last_review_date = $last_review_date,
            r.expiry_date = $expiry_date,
            r.trigger_conditions = $trigger_conditions,
            r.early_warning_signs = $early_warning_signs,
            r.notes = $notes,
            r.last_review_note = $last_review_note,
            r.attributes = $attributes,
            r.scoring_description = $scoring_description,
            r.impact_id = $impact_id,
            r.last_updated = $last_updated,
            r.project_id = $project_id
        """
        self.store.execute_write(query, {
            "risk_id": risk.risk_id,
            "risk_code": risk.risk_code,
            "title": risk.title,
            "description": risk.description,
            "category": risk.category.value,
            "subcategory": risk.subcategory,
            "status": risk.status.value,
            "priority": risk.priority.value,
            "exposure_type": risk.exposure_type.value,
            "group": risk.group,
            "source": risk.source,
            "department_category": risk.department_category,
            "probability": risk.probability,
            "probability_band": risk.probability_band,
            "impact_score": risk.impact_score,
            "risk_score": risk.risk_score,
            "impact_cost": risk.impact_cost,
            "impact_schedule": risk.impact_schedule,
            "impact_min": risk.impact_min,
            "impact_expected": risk.impact_expected,
            "impact_max": risk.impact_max,
            "pre_mitigation_level": risk.pre_mitigation_level,
            "current_score_band": risk.current_score_band,
            "simulation_type": risk.simulation_type,
            "distribution": risk.distribution,
            "emv": risk.expected_monetary_value,
            "expected_schedule_impact": risk.expected_schedule_impact,
            "residual_probability": risk.residual_probability,
            "residual_probability_band": risk.residual_probability_band,
            "residual_impact_score": risk.residual_impact_score,
            "post_mitigation_level": risk.post_mitigation_level,
            "post_distribution": risk.post_distribution,
            "post_exposure": risk.post_exposure,
            "post_impact_min": risk.post_impact_min,
            "post_impact_expected": risk.post_impact_expected,
            "post_impact_max": risk.post_impact_max,
            "response_type": risk.response_type.value,
            "mitigation_plan": risk.mitigation_plan,
            "contingency_plan": risk.contingency_plan,
            "consequences": risk.consequences,
            "related_mitigation_count": risk.related_mitigation_count,
            "risk_owner": risk.risk_owner,
            "assigned_to": risk.assigned_to,
            "identified_date": self._format_datetime(risk.identified_date),
            "due_date": self._format_datetime(risk.due_date),
            "review_date": self._format_datetime(risk.review_date),
            "last_review_date": self._format_datetime(risk.last_review_date),
            "expiry_date": self._format_datetime(risk.expiry_date),
            "trigger_conditions": risk.trigger_conditions,
            "early_warning_signs": risk.early_warning_signs,
            "notes": risk.notes,
            "last_review_note": risk.last_review_note,
            "attributes": risk.attributes,
            "scoring_description": risk.scoring_description,
            "impact_id": risk.impact_id,
            "last_updated": self._format_datetime(risk.last_updated),
            "project_id": project_id,
        })

        # Link to category
        self.store.execute_write("""
            MATCH (r:Risk {risk_id: $risk_id})
            MATCH (rc:RiskCategory {name: $category})
            MERGE (r)-[:BELONGS_TO]->(rc)
        """, {
            "risk_id": risk.risk_id,
            "category": risk.category.value,
        })

        # Link to project
        if project_id:
            self.store.execute_write("""
                MATCH (r:Risk {risk_id: $risk_id})
                MATCH (p:Project {project_id: $project_id})
                MERGE (p)-[:CONTAINS]->(r)
            """, {
                "risk_id": risk.risk_id,
                "project_id": project_id,
            })

        # Link to owner resource if exists
        if risk.risk_owner:
            self.store.execute_write("""
                MATCH (r:Risk {risk_id: $risk_id})
                MATCH (res:Resource)
                WHERE res.resource_name = $owner OR res.resource_code = $owner
                MERGE (r)-[:OWNED_BY]->(res)
            """, {
                "risk_id": risk.risk_id,
                "owner": risk.risk_owner,
            })

    def _link_risk_to_activity(self, risk_id: str, activity_code: str) -> None:
        """Create AFFECTS relationship between risk and activity."""
        query = """
        MATCH (r:Risk {risk_id: $risk_id})
        MATCH (a:Activity)
        WHERE a.activity_code = $activity_code OR a.activity_id = $activity_code
        MERGE (r)-[:AFFECTS]->(a)
        """
        self.store.execute_write(query, {
            "risk_id": risk_id,
            "activity_code": activity_code.strip(),
        })

    def _create_critical_path_relationships(self, project_id: str) -> None:
        """Create ON_CRITICAL_PATH relationships for critical activities."""
        query = """
        MATCH (a:Activity {project_id: $project_id})
        WHERE a.is_critical = true
        MATCH (p:Project {project_id: $project_id})
        MERGE (a)-[r:ON_CRITICAL_PATH]->(p)
        SET r.float = a.total_float
        """
        self.store.execute_write(query, {"project_id": project_id})

    def _create_delay_relationships(self, project_id: str) -> None:
        """Create DELAYED_FROM_BASELINE relationships for delayed activities."""
        query = """
        MATCH (a:Activity {project_id: $project_id})
        WHERE a.is_delayed = true
        MATCH (p:Project {project_id: $project_id})
        MERGE (a)-[r:DELAYED_FROM_BASELINE]->(p)
        SET r.delay_days = a.delay_days
        """
        self.store.execute_write(query, {"project_id": project_id})
