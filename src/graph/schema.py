"""
Neo4j Graph Schema for Planning & Risk Intelligence.

Defines the knowledge graph structure including:
- Node types (Project, WBS, Activity, Risk, Resource, etc.)
- Relationship types (CONTAINS, PRECEDES, AFFECTS, etc.)
- Constraints and indexes for performance

Graph Model:
============

Nodes:
------
(:Project)          - Project container
(:WBS)              - Work Breakdown Structure element
(:Activity)         - Schedule activity/task
(:Milestone)        - Project milestone
(:Resource)         - Project resource
(:Calendar)         - Work calendar
(:Risk)             - Risk register entry
(:RiskCategory)     - Risk category grouping

Relationships:
--------------
(Project)-[:CONTAINS]->(WBS)
(WBS)-[:CONTAINS]->(WBS)           - WBS hierarchy
(WBS)-[:CONTAINS]->(Activity)
(Activity)-[:PRECEDES]->(Activity) - Schedule logic (FS, FF, SS, SF)
(Activity)-[:USES]->(Resource)
(Activity)-[:FOLLOWS]->(Calendar)
(Risk)-[:AFFECTS]->(Activity)
(Risk)-[:AFFECTS]->(WBS)
(Risk)-[:BELONGS_TO]->(RiskCategory)
(Risk)-[:OWNED_BY]->(Resource)
(Activity)-[:ON_CRITICAL_PATH]->(Project)
(Activity)-[:DELAYED_FROM_BASELINE]->(Project)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class NodeType(str, Enum):
    """Node types in the knowledge graph."""
    PROJECT = "Project"
    WBS = "WBS"
    ACTIVITY = "Activity"
    MILESTONE = "Milestone"
    RESOURCE = "Resource"
    CALENDAR = "Calendar"
    RISK = "Risk"
    RISK_CATEGORY = "RiskCategory"


class RelationshipType(str, Enum):
    """Relationship types in the knowledge graph."""
    # Structural relationships
    CONTAINS = "CONTAINS"
    BELONGS_TO = "BELONGS_TO"

    # Schedule logic relationships
    PRECEDES = "PRECEDES"  # Generic predecessor
    FINISH_TO_START = "FINISH_TO_START"
    FINISH_TO_FINISH = "FINISH_TO_FINISH"
    START_TO_START = "START_TO_START"
    START_TO_FINISH = "START_TO_FINISH"

    # Resource relationships
    USES = "USES"
    ASSIGNED_TO = "ASSIGNED_TO"
    OWNED_BY = "OWNED_BY"

    # Calendar relationships
    FOLLOWS = "FOLLOWS"

    # Risk relationships
    AFFECTS = "AFFECTS"
    MITIGATES = "MITIGATES"
    RELATED_TO = "RELATED_TO"

    # Analysis relationships
    ON_CRITICAL_PATH = "ON_CRITICAL_PATH"
    DELAYED_FROM_BASELINE = "DELAYED_FROM_BASELINE"
    DRIVES = "DRIVES"  # Schedule driver


@dataclass
class GraphSchema:
    """
    Graph schema definition with node and relationship structures.
    """

    # Node property definitions
    NODE_PROPERTIES = {
        NodeType.PROJECT: [
            "project_id", "project_code", "project_name", "description",
            "planned_start", "planned_finish", "data_date",
            "total_activities", "completed_activities", "progress_percent"
        ],
        NodeType.WBS: [
            "wbs_id", "wbs_code", "wbs_name", "level", "parent_wbs_id"
        ],
        NodeType.ACTIVITY: [
            "activity_id", "activity_code", "activity_name", "activity_type",
            "status", "planned_start", "planned_finish",
            "actual_start", "actual_finish", "early_start", "early_finish",
            "late_start", "late_finish", "baseline_start", "baseline_finish",
            "original_duration", "remaining_duration", "actual_duration",
            "total_float", "free_float", "percent_complete",
            "is_critical", "is_delayed", "delay_days"
        ],
        NodeType.MILESTONE: [
            "activity_id", "activity_code", "activity_name", "milestone_type",
            "target_date", "actual_date", "status", "is_critical"
        ],
        NodeType.RESOURCE: [
            "resource_id", "resource_code", "resource_name", "resource_type",
            "unit_of_measure", "max_units", "standard_rate"
        ],
        NodeType.CALENDAR: [
            "calendar_id", "calendar_name", "calendar_type",
            "hours_per_day", "hours_per_week"
        ],
        NodeType.RISK: [
            "risk_id", "risk_code", "title", "description",
            "category", "subcategory", "status", "priority",
            "probability", "impact_score", "risk_score",
            "impact_cost", "impact_schedule",
            "emv", "expected_schedule_impact",
            "residual_probability", "residual_impact_score",
            "response_type", "mitigation_plan", "contingency_plan",
            "risk_owner", "assigned_to",
            "identified_date", "due_date", "review_date",
            "trigger_conditions", "early_warning_signs"
        ],
        NodeType.RISK_CATEGORY: [
            "category_id", "name", "description"
        ],
    }

    # Relationship property definitions
    RELATIONSHIP_PROPERTIES = {
        RelationshipType.PRECEDES: ["lag", "relationship_type"],
        RelationshipType.FINISH_TO_START: ["lag"],
        RelationshipType.FINISH_TO_FINISH: ["lag"],
        RelationshipType.START_TO_START: ["lag"],
        RelationshipType.START_TO_FINISH: ["lag"],
        RelationshipType.USES: ["planned_units", "actual_units", "remaining_units", "cost"],
        RelationshipType.AFFECTS: ["impact_type", "impact_severity", "notes"],
        RelationshipType.ON_CRITICAL_PATH: ["path_order", "float"],
        RelationshipType.DELAYED_FROM_BASELINE: ["delay_days", "variance_type"],
    }


# Cypher statements for schema constraints
SCHEMA_CONSTRAINTS = [
    # Unique constraints
    "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.project_id IS UNIQUE",
    "CREATE CONSTRAINT wbs_id IF NOT EXISTS FOR (w:WBS) REQUIRE w.wbs_id IS UNIQUE",
    "CREATE CONSTRAINT activity_id IF NOT EXISTS FOR (a:Activity) REQUIRE a.activity_id IS UNIQUE",
    "CREATE CONSTRAINT milestone_id IF NOT EXISTS FOR (m:Milestone) REQUIRE m.activity_id IS UNIQUE",
    "CREATE CONSTRAINT resource_id IF NOT EXISTS FOR (r:Resource) REQUIRE r.resource_id IS UNIQUE",
    "CREATE CONSTRAINT calendar_id IF NOT EXISTS FOR (c:Calendar) REQUIRE c.calendar_id IS UNIQUE",
    "CREATE CONSTRAINT risk_id IF NOT EXISTS FOR (r:Risk) REQUIRE r.risk_id IS UNIQUE",
    "CREATE CONSTRAINT risk_category_name IF NOT EXISTS FOR (rc:RiskCategory) REQUIRE rc.name IS UNIQUE",
]

# Cypher statements for indexes
SCHEMA_INDEXES = [
    # Activity indexes for common queries
    "CREATE INDEX activity_code IF NOT EXISTS FOR (a:Activity) ON (a.activity_code)",
    "CREATE INDEX activity_status IF NOT EXISTS FOR (a:Activity) ON (a.status)",
    "CREATE INDEX activity_critical IF NOT EXISTS FOR (a:Activity) ON (a.is_critical)",
    "CREATE INDEX activity_delayed IF NOT EXISTS FOR (a:Activity) ON (a.is_delayed)",
    "CREATE INDEX activity_float IF NOT EXISTS FOR (a:Activity) ON (a.total_float)",

    # WBS indexes
    "CREATE INDEX wbs_code IF NOT EXISTS FOR (w:WBS) ON (w.wbs_code)",
    "CREATE INDEX wbs_level IF NOT EXISTS FOR (w:WBS) ON (w.level)",

    # Risk indexes
    "CREATE INDEX risk_code IF NOT EXISTS FOR (r:Risk) ON (r.risk_code)",
    "CREATE INDEX risk_status IF NOT EXISTS FOR (r:Risk) ON (r.status)",
    "CREATE INDEX risk_priority IF NOT EXISTS FOR (r:Risk) ON (r.priority)",
    "CREATE INDEX risk_category IF NOT EXISTS FOR (r:Risk) ON (r.category)",
    "CREATE INDEX risk_score IF NOT EXISTS FOR (r:Risk) ON (r.risk_score)",

    # Resource indexes
    "CREATE INDEX resource_code IF NOT EXISTS FOR (r:Resource) ON (r.resource_code)",
    "CREATE INDEX resource_type IF NOT EXISTS FOR (r:Resource) ON (r.resource_type)",

    # Full-text search indexes
    "CREATE FULLTEXT INDEX activity_search IF NOT EXISTS FOR (a:Activity) ON EACH [a.activity_name, a.activity_code]",
    "CREATE FULLTEXT INDEX risk_search IF NOT EXISTS FOR (r:Risk) ON EACH [r.title, r.description, r.mitigation_plan]",
    "CREATE FULLTEXT INDEX wbs_search IF NOT EXISTS FOR (w:WBS) ON EACH [w.wbs_name, w.wbs_code]",
]


# Pre-built Cypher query templates
class CypherTemplates:
    """Pre-built Cypher query templates for common operations."""

    # Critical path queries
    GET_CRITICAL_PATH = """
    MATCH (p:Project {project_id: $project_id})<-[:ON_CRITICAL_PATH]-(a:Activity)
    RETURN a
    ORDER BY a.early_start
    """

    TRACE_CRITICAL_PATH = """
    MATCH path = (start:Activity {is_critical: true})-[:PRECEDES*]->(end:Activity {is_critical: true})
    WHERE start.activity_id = $start_activity_id
    RETURN path
    """

    # Predecessor/Successor queries
    GET_PREDECESSORS = """
    MATCH (a:Activity {activity_id: $activity_id})<-[r:PRECEDES|FINISH_TO_START|FINISH_TO_FINISH|START_TO_START|START_TO_FINISH]-(pred:Activity)
    RETURN pred, type(r) as relationship_type, r.lag as lag
    """

    GET_SUCCESSORS = """
    MATCH (a:Activity {activity_id: $activity_id})-[r:PRECEDES|FINISH_TO_START|FINISH_TO_FINISH|START_TO_START|START_TO_FINISH]->(succ:Activity)
    RETURN succ, type(r) as relationship_type, r.lag as lag
    """

    GET_ALL_PREDECESSORS = """
    MATCH path = (a:Activity {activity_id: $activity_id})<-[:PRECEDES*]-(pred:Activity)
    RETURN pred, length(path) as depth
    ORDER BY depth
    """

    GET_ALL_SUCCESSORS = """
    MATCH path = (a:Activity {activity_id: $activity_id})-[:PRECEDES*]->(succ:Activity)
    RETURN succ, length(path) as depth
    ORDER BY depth
    """

    # Risk impact analysis
    GET_RISKS_FOR_ACTIVITY = """
    MATCH (a:Activity {activity_id: $activity_id})<-[:AFFECTS]-(r:Risk)
    RETURN r
    ORDER BY r.risk_score DESC
    """

    GET_ACTIVITIES_AFFECTED_BY_RISK = """
    MATCH (r:Risk {risk_id: $risk_id})-[:AFFECTS]->(a:Activity)
    RETURN a
    ORDER BY a.early_start
    """

    GET_DOWNSTREAM_IMPACT = """
    MATCH (r:Risk {risk_id: $risk_id})-[:AFFECTS]->(a:Activity)-[:PRECEDES*0..]->(downstream:Activity)
    RETURN DISTINCT downstream
    ORDER BY downstream.early_start
    """

    # WBS hierarchy queries
    GET_WBS_HIERARCHY = """
    MATCH path = (root:WBS {level: 1})-[:CONTAINS*]->(child:WBS)
    WHERE root.project_id = $project_id
    RETURN path
    """

    GET_ACTIVITIES_IN_WBS = """
    MATCH (w:WBS {wbs_id: $wbs_id})-[:CONTAINS*0..]->(child)-[:CONTAINS]->(a:Activity)
    RETURN a
    """

    # Delay analysis
    GET_DELAYED_ACTIVITIES = """
    MATCH (a:Activity {is_delayed: true})
    RETURN a
    ORDER BY a.delay_days DESC
    """

    GET_DELAY_IMPACT_CHAIN = """
    MATCH (a:Activity {activity_id: $activity_id})-[:PRECEDES*]->(downstream:Activity)
    WHERE a.is_delayed = true
    RETURN downstream,
           downstream.total_float as float,
           downstream.is_critical as is_critical
    ORDER BY downstream.early_start
    """

    # Schedule analysis
    GET_NEAR_CRITICAL_ACTIVITIES = """
    MATCH (a:Activity)
    WHERE a.total_float <= $threshold AND a.total_float > 0
    RETURN a
    ORDER BY a.total_float
    """

    GET_SCHEDULE_DRIVERS = """
    MATCH (a:Activity)-[:PRECEDES*]->(end:Milestone)
    WHERE end.activity_id = $milestone_id
    WITH a, count(*) as path_count
    RETURN a
    ORDER BY a.total_float, path_count DESC
    LIMIT $limit
    """

    # Resource analysis
    GET_RESOURCE_ASSIGNMENTS = """
    MATCH (r:Resource {resource_id: $resource_id})<-[:USES]-(a:Activity)
    RETURN a
    ORDER BY a.early_start
    """

    GET_RESOURCE_CONFLICTS = """
    MATCH (a1:Activity)-[:USES]->(r:Resource)<-[:USES]-(a2:Activity)
    WHERE a1.activity_id < a2.activity_id
      AND a1.early_start < a2.early_finish
      AND a2.early_start < a1.early_finish
    RETURN a1, a2, r
    """

    # Combined schedule-risk analysis
    GET_HIGH_RISK_CRITICAL_ACTIVITIES = """
    MATCH (a:Activity {is_critical: true})<-[:AFFECTS]-(r:Risk)
    WHERE r.risk_score >= $risk_threshold
    RETURN a, collect(r) as risks
    ORDER BY a.early_start
    """

    GET_RISK_EXPOSURE_BY_PATH = """
    MATCH path = (start:Activity)-[:PRECEDES*]->(end:Milestone {activity_id: $milestone_id})
    WITH nodes(path) as activities
    UNWIND activities as a
    MATCH (a)<-[:AFFECTS]-(r:Risk)
    RETURN a.activity_code as activity,
           collect(r.title) as risks,
           sum(r.emv) as total_emv
    ORDER BY total_emv DESC
    """

    # Full-text search
    SEARCH_ACTIVITIES = """
    CALL db.index.fulltext.queryNodes('activity_search', $search_term)
    YIELD node, score
    RETURN node as activity, score
    ORDER BY score DESC
    LIMIT $limit
    """

    SEARCH_RISKS = """
    CALL db.index.fulltext.queryNodes('risk_search', $search_term)
    YIELD node, score
    RETURN node as risk, score
    ORDER BY score DESC
    LIMIT $limit
    """
