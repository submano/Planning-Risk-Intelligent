"""
Graph-based Retriever for Planning & Risk Intelligence.

Provides intelligent query routing and graph traversal
for schedule and risk analysis.
"""

import re
from enum import Enum
from typing import Any, Optional

from langchain_core.documents import Document

from src.graph.store import GraphStore


class GraphQueryType(str, Enum):
    """Types of graph queries."""
    # Schedule traversal
    CRITICAL_PATH = "critical_path"
    PREDECESSORS = "predecessors"
    SUCCESSORS = "successors"
    TRACE_PATH = "trace_path"
    DELAY_IMPACT = "delay_impact"
    SCHEDULE_DRIVERS = "schedule_drivers"

    # Risk analysis
    RISK_IMPACT = "risk_impact"
    ACTIVITY_RISKS = "activity_risks"
    DOWNSTREAM_IMPACT = "downstream_impact"
    HIGH_RISK_CRITICAL = "high_risk_critical"

    # Context retrieval
    ACTIVITY_CONTEXT = "activity_context"
    RISK_CONTEXT = "risk_context"
    WBS_HIERARCHY = "wbs_hierarchy"

    # Search
    SEARCH = "search"

    # General
    GENERAL = "general"


class GraphQueryEngine:
    """
    Processes natural language queries and translates them
    to graph traversal operations.
    """

    # Patterns for query classification
    QUERY_PATTERNS = {
        GraphQueryType.CRITICAL_PATH: [
            r"critical path",
            r"critical activities",
            r"zero float",
            r"activities? with no float",
        ],
        GraphQueryType.PREDECESSORS: [
            r"predecessors? (?:of|for)",
            r"what comes before",
            r"depends? on what",
            r"driving (?:activities?|tasks?)",
            r"before (\w+)",
        ],
        GraphQueryType.SUCCESSORS: [
            r"successors? (?:of|for)",
            r"what comes after",
            r"what depends on",
            r"downstream (?:of|from)",
            r"after (\w+)",
        ],
        GraphQueryType.TRACE_PATH: [
            r"path (?:from|between)",
            r"trace (?:from|between)",
            r"how .* connect",
            r"route (?:from|between)",
        ],
        GraphQueryType.DELAY_IMPACT: [
            r"delay impact",
            r"if .* delayed",
            r"impact of delay",
            r"what happens if .* late",
            r"delayed activities?",
        ],
        GraphQueryType.SCHEDULE_DRIVERS: [
            r"schedule drivers?",
            r"what drives",
            r"driving the schedule",
            r"key drivers?",
        ],
        GraphQueryType.RISK_IMPACT: [
            r"risk .* impact",
            r"impact .* risk",
            r"affected by risk",
            r"what .* risk .* affect",
        ],
        GraphQueryType.ACTIVITY_RISKS: [
            r"risks? (?:for|affecting|on) (?:activity|task)",
            r"what risks? (?:affect|impact)",
            r"(?:activity|task) .* risks?",
        ],
        GraphQueryType.DOWNSTREAM_IMPACT: [
            r"downstream impact",
            r"ripple effect",
            r"cascade",
            r"knock-on",
        ],
        GraphQueryType.HIGH_RISK_CRITICAL: [
            r"high risk .* critical",
            r"critical .* high risk",
            r"risky critical",
            r"dangerous activities?",
        ],
        GraphQueryType.ACTIVITY_CONTEXT: [
            r"tell me about (?:activity|task)",
            r"details? (?:for|of|about) (?:activity|task)",
            r"(?:activity|task) (\w+) (?:details?|information|info)",
        ],
        GraphQueryType.RISK_CONTEXT: [
            r"tell me about risk",
            r"details? (?:for|of|about) risk",
            r"risk (\w+) (?:details?|information|info)",
        ],
        GraphQueryType.WBS_HIERARCHY: [
            r"wbs (?:structure|hierarchy)",
            r"work breakdown",
            r"project structure",
        ],
    }

    def __init__(self, graph_store: GraphStore):
        """Initialize the query engine."""
        self.store = graph_store

    def classify_query(self, query: str) -> tuple[GraphQueryType, dict]:
        """
        Classify a natural language query and extract parameters.

        Args:
            query: Natural language query

        Returns:
            Tuple of (query_type, extracted_parameters)
        """
        query_lower = query.lower()
        params = {}

        # Try to extract activity codes (e.g., A1000, A-1000)
        activity_match = re.search(r'\b([A-Z]-?\d{3,})\b', query, re.IGNORECASE)
        if activity_match:
            params["activity_code"] = activity_match.group(1).upper()

        # Try to extract risk IDs (e.g., R001, RISK-001)
        risk_match = re.search(r'\b(R(?:ISK)?-?\d{2,})\b', query, re.IGNORECASE)
        if risk_match:
            params["risk_id"] = risk_match.group(1).upper()

        # Match against patterns
        for query_type, patterns in self.QUERY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return query_type, params

        return GraphQueryType.GENERAL, params

    def execute_query(
        self,
        query: str,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Execute a natural language query against the graph.

        Args:
            query: Natural language query
            project_id: Optional project ID for context

        Returns:
            Dictionary with query results and metadata
        """
        query_type, params = self.classify_query(query)
        params["project_id"] = project_id

        result = {
            "query_type": query_type.value,
            "original_query": query,
            "parameters": params,
            "data": None,
            "summary": "",
        }

        # Execute appropriate query
        if query_type == GraphQueryType.CRITICAL_PATH:
            result["data"] = self._execute_critical_path(params)
            result["summary"] = self._summarize_critical_path(result["data"])

        elif query_type == GraphQueryType.PREDECESSORS:
            result["data"] = self._execute_predecessors(params)
            result["summary"] = self._summarize_predecessors(result["data"], params)

        elif query_type == GraphQueryType.SUCCESSORS:
            result["data"] = self._execute_successors(params)
            result["summary"] = self._summarize_successors(result["data"], params)

        elif query_type == GraphQueryType.TRACE_PATH:
            result["data"] = self._execute_trace_path(params, query)
            result["summary"] = self._summarize_path(result["data"])

        elif query_type == GraphQueryType.DELAY_IMPACT:
            result["data"] = self._execute_delay_impact(params)
            result["summary"] = self._summarize_delay_impact(result["data"], params)

        elif query_type == GraphQueryType.SCHEDULE_DRIVERS:
            result["data"] = self._execute_schedule_drivers(params, query)
            result["summary"] = self._summarize_drivers(result["data"])

        elif query_type == GraphQueryType.RISK_IMPACT:
            result["data"] = self._execute_risk_impact(params)
            result["summary"] = self._summarize_risk_impact(result["data"], params)

        elif query_type == GraphQueryType.ACTIVITY_RISKS:
            result["data"] = self._execute_activity_risks(params)
            result["summary"] = self._summarize_activity_risks(result["data"], params)

        elif query_type == GraphQueryType.DOWNSTREAM_IMPACT:
            result["data"] = self._execute_downstream_impact(params)
            result["summary"] = self._summarize_downstream(result["data"], params)

        elif query_type == GraphQueryType.HIGH_RISK_CRITICAL:
            result["data"] = self._execute_high_risk_critical(params)
            result["summary"] = self._summarize_high_risk_critical(result["data"])

        elif query_type == GraphQueryType.ACTIVITY_CONTEXT:
            result["data"] = self._execute_activity_context(params)
            result["summary"] = self._summarize_activity_context(result["data"])

        elif query_type == GraphQueryType.RISK_CONTEXT:
            result["data"] = self._execute_risk_context(params)
            result["summary"] = self._summarize_risk_context(result["data"])

        elif query_type == GraphQueryType.WBS_HIERARCHY:
            result["data"] = self._execute_wbs_hierarchy(params)
            result["summary"] = self._summarize_wbs(result["data"])

        else:
            # General query - search across nodes
            result["data"] = self._execute_search(query)
            result["summary"] = self._summarize_search(result["data"], query)

        return result

    # Query execution methods

    def _execute_critical_path(self, params: dict) -> list[dict]:
        """Get critical path activities."""
        if params.get("project_id"):
            return self.store.get_critical_path(params["project_id"])
        return self.store.execute_read("""
            MATCH (a:Activity {is_critical: true})
            RETURN a
            ORDER BY a.early_start
        """)

    def _execute_predecessors(self, params: dict) -> list[dict]:
        """Get predecessors of an activity."""
        if params.get("activity_code"):
            # Find by code first
            result = self.store.execute_read("""
                MATCH (a:Activity)
                WHERE a.activity_code = $code OR a.activity_id = $code
                RETURN a.activity_id as activity_id
            """, {"code": params["activity_code"]})
            if result:
                return self.store.get_all_predecessors(result[0]["activity_id"])
        return []

    def _execute_successors(self, params: dict) -> list[dict]:
        """Get successors of an activity."""
        if params.get("activity_code"):
            result = self.store.execute_read("""
                MATCH (a:Activity)
                WHERE a.activity_code = $code OR a.activity_id = $code
                RETURN a.activity_id as activity_id
            """, {"code": params["activity_code"]})
            if result:
                return self.store.get_all_successors(result[0]["activity_id"])
        return []

    def _execute_trace_path(self, params: dict, query: str) -> list[dict]:
        """Trace path between activities."""
        # Extract two activity codes from query
        codes = re.findall(r'\b([A-Z]-?\d{3,})\b', query, re.IGNORECASE)
        if len(codes) >= 2:
            # Get activity IDs
            start_result = self.store.execute_read("""
                MATCH (a:Activity)
                WHERE a.activity_code = $code OR a.activity_id = $code
                RETURN a.activity_id as activity_id
            """, {"code": codes[0].upper()})
            end_result = self.store.execute_read("""
                MATCH (a:Activity)
                WHERE a.activity_code = $code OR a.activity_id = $code
                RETURN a.activity_id as activity_id
            """, {"code": codes[1].upper()})

            if start_result and end_result:
                return self.store.trace_path(
                    start_result[0]["activity_id"],
                    end_result[0]["activity_id"]
                )
        return []

    def _execute_delay_impact(self, params: dict) -> list[dict]:
        """Get delay impact analysis."""
        if params.get("activity_code"):
            result = self.store.execute_read("""
                MATCH (a:Activity)
                WHERE a.activity_code = $code OR a.activity_id = $code
                RETURN a.activity_id as activity_id
            """, {"code": params["activity_code"]})
            if result:
                return self.store.get_delay_impact_chain(result[0]["activity_id"])
        # Return all delayed activities
        return self.store.get_delayed_activities()

    def _execute_schedule_drivers(self, params: dict, query: str) -> list[dict]:
        """Get schedule drivers for a milestone."""
        # Try to find milestone reference
        milestone_match = re.search(r'milestone[s]?\s+(\w+)', query, re.IGNORECASE)
        if milestone_match:
            milestone_code = milestone_match.group(1)
            result = self.store.execute_read("""
                MATCH (m:Milestone)
                WHERE m.activity_code = $code OR m.activity_id = $code
                RETURN m.activity_id as activity_id
            """, {"code": milestone_code})
            if result:
                return self.store.get_schedule_drivers(result[0]["activity_id"])
        return []

    def _execute_risk_impact(self, params: dict) -> list[dict]:
        """Get activities impacted by a risk."""
        if params.get("risk_id"):
            return self.store.get_activities_affected_by_risk(params["risk_id"])
        return []

    def _execute_activity_risks(self, params: dict) -> list[dict]:
        """Get risks affecting an activity."""
        if params.get("activity_code"):
            result = self.store.execute_read("""
                MATCH (a:Activity)
                WHERE a.activity_code = $code OR a.activity_id = $code
                RETURN a.activity_id as activity_id
            """, {"code": params["activity_code"]})
            if result:
                return self.store.get_risks_for_activity(result[0]["activity_id"])
        return []

    def _execute_downstream_impact(self, params: dict) -> list[dict]:
        """Get downstream impact of a risk."""
        if params.get("risk_id"):
            return self.store.get_downstream_impact(params["risk_id"])
        return []

    def _execute_high_risk_critical(self, params: dict) -> list[dict]:
        """Get high-risk critical path activities."""
        return self.store.get_high_risk_critical_activities(risk_threshold=3.0)

    def _execute_activity_context(self, params: dict) -> dict:
        """Get full activity context."""
        if params.get("activity_code"):
            result = self.store.execute_read("""
                MATCH (a:Activity)
                WHERE a.activity_code = $code OR a.activity_id = $code
                RETURN a.activity_id as activity_id
            """, {"code": params["activity_code"]})
            if result:
                return self.store.get_activity_context(result[0]["activity_id"])
        return {}

    def _execute_risk_context(self, params: dict) -> dict:
        """Get full risk context."""
        if params.get("risk_id"):
            return self.store.get_risk_context(params["risk_id"])
        return {}

    def _execute_wbs_hierarchy(self, params: dict) -> list[dict]:
        """Get WBS hierarchy."""
        if params.get("project_id"):
            return self.store.get_wbs_hierarchy(params["project_id"])
        return self.store.execute_read("""
            MATCH (w:WBS)
            RETURN w
            ORDER BY w.level, w.wbs_code
        """)

    def _execute_search(self, query: str) -> list[dict]:
        """Execute general search."""
        # Search activities and risks
        activities = self.store.search_activities(query, limit=5)
        risks = self.store.search_risks(query, limit=5)
        return {"activities": activities, "risks": risks}

    # Summary generation methods

    def _summarize_critical_path(self, data: list[dict]) -> str:
        """Generate summary for critical path."""
        if not data:
            return "No critical path activities found."
        activities = [d.get("a", {}) for d in data]
        codes = [a.get("activity_code", "Unknown") for a in activities if a]
        return f"Critical path contains {len(codes)} activities: {', '.join(codes[:10])}" + \
               ("..." if len(codes) > 10 else "")

    def _summarize_predecessors(self, data: list[dict], params: dict) -> str:
        """Generate summary for predecessors."""
        if not data:
            return f"No predecessors found for {params.get('activity_code', 'activity')}."
        return f"Found {len(data)} predecessor activities in the dependency chain."

    def _summarize_successors(self, data: list[dict], params: dict) -> str:
        """Generate summary for successors."""
        if not data:
            return f"No successors found for {params.get('activity_code', 'activity')}."
        return f"Found {len(data)} downstream activities that depend on this activity."

    def _summarize_path(self, data: list[dict]) -> str:
        """Generate summary for path trace."""
        if not data:
            return "No path found between the specified activities."
        shortest = min(d.get("path_length", 0) for d in data) if data else 0
        return f"Found {len(data)} paths. Shortest path has {shortest} connections."

    def _summarize_delay_impact(self, data: list[dict], params: dict) -> str:
        """Generate summary for delay impact."""
        if not data:
            return "No delay impact analysis available."
        critical_count = sum(1 for d in data if d.get("is_critical"))
        return f"Delay would impact {len(data)} downstream activities, {critical_count} on critical path."

    def _summarize_drivers(self, data: list[dict]) -> str:
        """Generate summary for schedule drivers."""
        if not data:
            return "No schedule drivers found."
        return f"Found {len(data)} activities driving the schedule."

    def _summarize_risk_impact(self, data: list[dict], params: dict) -> str:
        """Generate summary for risk impact."""
        if not data:
            return f"No activities affected by risk {params.get('risk_id', '')}."
        return f"Risk affects {len(data)} activities directly."

    def _summarize_activity_risks(self, data: list[dict], params: dict) -> str:
        """Generate summary for activity risks."""
        if not data:
            return f"No risks found affecting {params.get('activity_code', 'activity')}."
        risks = [d.get("r", {}) for d in data]
        high_risk = sum(1 for r in risks if r.get("risk_score", 0) >= 3)
        return f"Found {len(risks)} risks affecting this activity, {high_risk} high priority."

    def _summarize_downstream(self, data: list[dict], params: dict) -> str:
        """Generate summary for downstream impact."""
        if not data:
            return "No downstream impact found."
        return f"Risk could cascade to {len(data)} downstream activities."

    def _summarize_high_risk_critical(self, data: list[dict]) -> str:
        """Generate summary for high-risk critical activities."""
        if not data:
            return "No high-risk critical path activities found."
        return f"Found {len(data)} critical path activities with high risk exposure."

    def _summarize_activity_context(self, data: dict) -> str:
        """Generate summary for activity context."""
        if not data:
            return "Activity not found."
        activity = data.get("activity", {})
        preds = len(data.get("predecessors", []))
        succs = len(data.get("successors", []))
        risks = len(data.get("risks", []))
        return f"Activity {activity.get('activity_code', '')}: {preds} predecessors, {succs} successors, {risks} risks."

    def _summarize_risk_context(self, data: dict) -> str:
        """Generate summary for risk context."""
        if not data:
            return "Risk not found."
        risk = data.get("risk", {})
        affected = len(data.get("affected_activities", []))
        return f"Risk {risk.get('risk_id', '')}: affects {affected} activities, score {risk.get('risk_score', 'N/A')}."

    def _summarize_wbs(self, data: list[dict]) -> str:
        """Generate summary for WBS hierarchy."""
        if not data:
            return "No WBS structure found."
        return f"WBS contains {len(data)} elements."

    def _summarize_search(self, data: dict, query: str) -> str:
        """Generate summary for search results."""
        activities = data.get("activities", [])
        risks = data.get("risks", [])
        return f"Found {len(activities)} activities and {len(risks)} risks matching '{query}'."


class GraphRetriever:
    """
    Retriever that combines graph queries with document generation
    for use with the RAG chain.
    """

    def __init__(self, graph_store: GraphStore, project_id: Optional[str] = None):
        """Initialize the retriever."""
        self.store = graph_store
        self.query_engine = GraphQueryEngine(graph_store)
        self.project_id = project_id

    def retrieve(self, query: str) -> list[Document]:
        """
        Retrieve relevant information as documents.

        Args:
            query: Natural language query

        Returns:
            List of LangChain Documents with graph data
        """
        result = self.query_engine.execute_query(query, self.project_id)

        documents = []

        # Create main result document
        main_doc = Document(
            page_content=self._format_result(result),
            metadata={
                "source": "neo4j_graph",
                "query_type": result["query_type"],
                "doc_type": f"graph_{result['query_type']}",
            }
        )
        documents.append(main_doc)

        # Add detail documents for specific results
        if result["data"]:
            detail_docs = self._create_detail_documents(result)
            documents.extend(detail_docs)

        return documents

    def _format_result(self, result: dict) -> str:
        """Format query result as document content."""
        content = f"""GRAPH QUERY RESULT
Query Type: {result['query_type']}
Query: {result['original_query']}

SUMMARY:
{result['summary']}

"""
        if result["data"]:
            content += "DETAILED DATA:\n"
            content += self._format_data(result["data"], result["query_type"])

        return content

    def _format_data(self, data: Any, query_type: str) -> str:
        """Format query data based on type."""
        if isinstance(data, dict):
            if "activities" in data and "risks" in data:
                # Search result
                content = "Activities found:\n"
                for item in data.get("activities", [])[:5]:
                    a = item.get("activity", {})
                    content += f"  - {a.get('activity_code')}: {a.get('activity_name')}\n"
                content += "\nRisks found:\n"
                for item in data.get("risks", [])[:5]:
                    r = item.get("risk", {})
                    content += f"  - {r.get('risk_id')}: {r.get('title')}\n"
                return content
            else:
                # Context result
                return self._format_context(data)

        elif isinstance(data, list):
            content = ""
            for i, item in enumerate(data[:20], 1):
                if "a" in item:  # Activity
                    a = item["a"]
                    content += f"{i}. {a.get('activity_code')}: {a.get('activity_name')}\n"
                    content += f"   Status: {a.get('status')} | Float: {a.get('total_float')} | Critical: {a.get('is_critical')}\n"
                elif "pred" in item:  # Predecessor
                    a = item["pred"]
                    content += f"{i}. {a.get('activity_code')}: {a.get('activity_name')} (depth: {item.get('depth', 1)})\n"
                elif "succ" in item:  # Successor
                    a = item["succ"]
                    content += f"{i}. {a.get('activity_code')}: {a.get('activity_name')} (depth: {item.get('depth', 1)})\n"
                elif "r" in item:  # Risk
                    r = item["r"]
                    content += f"{i}. {r.get('risk_id')}: {r.get('title')}\n"
                    content += f"   Score: {r.get('risk_score')} | Priority: {r.get('priority')}\n"
                elif "downstream" in item:
                    a = item["downstream"]
                    content += f"{i}. {a.get('activity_code')}: {a.get('activity_name')}\n"
                    content += f"   Float: {item.get('float')} | Critical: {item.get('is_critical')}\n"

            if len(data) > 20:
                content += f"\n... and {len(data) - 20} more items"
            return content

        return str(data)

    def _format_context(self, data: dict) -> str:
        """Format context data."""
        content = ""

        if "activity" in data:
            a = data["activity"]
            content += f"Activity: {a.get('activity_code')} - {a.get('activity_name')}\n"
            content += f"Status: {a.get('status')} | Type: {a.get('activity_type')}\n"
            content += f"Float: {a.get('total_float')} days | Critical: {a.get('is_critical')}\n"
            content += f"Progress: {a.get('percent_complete')}%\n"

        if "risk" in data:
            r = data["risk"]
            content += f"Risk: {r.get('risk_id')} - {r.get('title')}\n"
            content += f"Score: {r.get('risk_score')} | Priority: {r.get('priority')}\n"
            content += f"Status: {r.get('status')}\n"

        if data.get("predecessors"):
            content += f"\nPredecessors ({len(data['predecessors'])}):\n"
            for p in data["predecessors"][:5]:
                content += f"  - {p.get('activity_code')}: {p.get('activity_name')}\n"

        if data.get("successors"):
            content += f"\nSuccessors ({len(data['successors'])}):\n"
            for s in data["successors"][:5]:
                content += f"  - {s.get('activity_code')}: {s.get('activity_name')}\n"

        if data.get("risks"):
            content += f"\nRisks ({len(data['risks'])}):\n"
            for r in data["risks"][:5]:
                content += f"  - {r.get('risk_id')}: {r.get('title')} (score: {r.get('risk_score')})\n"

        if data.get("affected_activities"):
            content += f"\nAffected Activities ({len(data['affected_activities'])}):\n"
            for a in data["affected_activities"][:5]:
                content += f"  - {a.get('activity_code')}: {a.get('activity_name')}\n"

        return content

    def _create_detail_documents(self, result: dict) -> list[Document]:
        """Create detailed documents from result data."""
        documents = []
        data = result["data"]

        if isinstance(data, list):
            # Group activities for detailed context
            for item in data[:5]:  # Limit detail docs
                if "a" in item:
                    a = item["a"]
                    doc = Document(
                        page_content=f"""Activity: {a.get('activity_code')} - {a.get('activity_name')}
Type: {a.get('activity_type')}
Status: {a.get('status')}
Dates: {a.get('early_start')} to {a.get('early_finish')}
Duration: {a.get('original_duration')} days
Float: {a.get('total_float')} days
Critical: {a.get('is_critical')}
Progress: {a.get('percent_complete')}%""",
                        metadata={
                            "source": "neo4j_graph",
                            "doc_type": "activity_detail",
                            "activity_id": a.get("activity_id"),
                            "activity_code": a.get("activity_code"),
                        }
                    )
                    documents.append(doc)

        return documents
