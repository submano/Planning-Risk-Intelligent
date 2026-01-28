"""
Neo4j Graph Store for Planning & Risk Intelligence.

Manages connections to Neo4j and provides methods for
creating, querying, and managing the knowledge graph.
"""

import os
from contextlib import contextmanager
from typing import Any, Generator, Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver, Session, Result

from src.graph.schema import SCHEMA_CONSTRAINTS, SCHEMA_INDEXES, CypherTemplates

load_dotenv()


class GraphStore:
    """
    Neo4j graph store manager.

    Handles database connections, schema initialization,
    and provides query execution methods.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        """
        Initialize the graph store.

        Args:
            uri: Neo4j connection URI (bolt://localhost:7687)
            username: Neo4j username
            password: Neo4j password
            database: Neo4j database name
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")

        self._driver: Optional[Driver] = None

    @property
    def driver(self) -> Driver:
        """Get or create the Neo4j driver."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
            )
        return self._driver

    def close(self) -> None:
        """Close the database connection."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def verify_connectivity(self) -> bool:
        """Verify connection to Neo4j."""
        try:
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            print(f"Failed to connect to Neo4j: {e}")
            return False

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Get a database session context manager."""
        session = self.driver.session(database=self.database)
        try:
            yield session
        finally:
            session.close()

    def execute_query(
        self,
        query: str,
        parameters: Optional[dict] = None,
        write: bool = False,
    ) -> list[dict]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters
            write: Whether this is a write transaction

        Returns:
            List of result records as dictionaries
        """
        with self.session() as session:
            if write:
                result = session.execute_write(
                    lambda tx: list(tx.run(query, parameters or {}))
                )
            else:
                result = session.execute_read(
                    lambda tx: list(tx.run(query, parameters or {}))
                )
            return [dict(record) for record in result]

    def execute_write(self, query: str, parameters: Optional[dict] = None) -> list[dict]:
        """Execute a write query."""
        return self.execute_query(query, parameters, write=True)

    def execute_read(self, query: str, parameters: Optional[dict] = None) -> list[dict]:
        """Execute a read query."""
        return self.execute_query(query, parameters, write=False)

    def initialize_schema(self) -> None:
        """
        Initialize the graph schema with constraints and indexes.

        This should be called once when setting up the database.
        """
        print("Initializing Neo4j schema...")

        # Create constraints
        for constraint in SCHEMA_CONSTRAINTS:
            try:
                self.execute_write(constraint)
                print(f"  Created constraint: {constraint[:60]}...")
            except Exception as e:
                # Constraint may already exist
                if "already exists" not in str(e).lower():
                    print(f"  Warning: {e}")

        # Create indexes
        for index in SCHEMA_INDEXES:
            try:
                self.execute_write(index)
                print(f"  Created index: {index[:60]}...")
            except Exception as e:
                # Index may already exist
                if "already exists" not in str(e).lower():
                    print(f"  Warning: {e}")

        print("Schema initialization complete.")

    def clear_database(self) -> None:
        """
        Clear all nodes and relationships from the database.

        WARNING: This will delete all data!
        """
        self.execute_write("MATCH (n) DETACH DELETE n")
        print("Database cleared.")

    def get_stats(self) -> dict:
        """Get database statistics."""
        node_counts = self.execute_read("""
            MATCH (n)
            RETURN labels(n)[0] as label, count(*) as count
            ORDER BY count DESC
        """)

        rel_counts = self.execute_read("""
            MATCH ()-[r]->()
            RETURN type(r) as type, count(*) as count
            ORDER BY count DESC
        """)

        return {
            "nodes": {r["label"]: r["count"] for r in node_counts},
            "relationships": {r["type"]: r["count"] for r in rel_counts},
            "total_nodes": sum(r["count"] for r in node_counts),
            "total_relationships": sum(r["count"] for r in rel_counts),
        }

    # Pre-built query methods using CypherTemplates

    def get_critical_path(self, project_id: str) -> list[dict]:
        """Get all activities on the critical path."""
        return self.execute_read(
            CypherTemplates.GET_CRITICAL_PATH,
            {"project_id": project_id}
        )

    def get_predecessors(self, activity_id: str) -> list[dict]:
        """Get immediate predecessors of an activity."""
        return self.execute_read(
            CypherTemplates.GET_PREDECESSORS,
            {"activity_id": activity_id}
        )

    def get_successors(self, activity_id: str) -> list[dict]:
        """Get immediate successors of an activity."""
        return self.execute_read(
            CypherTemplates.GET_SUCCESSORS,
            {"activity_id": activity_id}
        )

    def get_all_predecessors(self, activity_id: str) -> list[dict]:
        """Get all predecessors (full chain) of an activity."""
        return self.execute_read(
            CypherTemplates.GET_ALL_PREDECESSORS,
            {"activity_id": activity_id}
        )

    def get_all_successors(self, activity_id: str) -> list[dict]:
        """Get all successors (full chain) of an activity."""
        return self.execute_read(
            CypherTemplates.GET_ALL_SUCCESSORS,
            {"activity_id": activity_id}
        )

    def get_risks_for_activity(self, activity_id: str) -> list[dict]:
        """Get all risks affecting an activity."""
        return self.execute_read(
            CypherTemplates.GET_RISKS_FOR_ACTIVITY,
            {"activity_id": activity_id}
        )

    def get_activities_affected_by_risk(self, risk_id: str) -> list[dict]:
        """Get all activities affected by a risk."""
        return self.execute_read(
            CypherTemplates.GET_ACTIVITIES_AFFECTED_BY_RISK,
            {"risk_id": risk_id}
        )

    def get_downstream_impact(self, risk_id: str) -> list[dict]:
        """Get all downstream activities that could be impacted by a risk."""
        return self.execute_read(
            CypherTemplates.GET_DOWNSTREAM_IMPACT,
            {"risk_id": risk_id}
        )

    def get_delayed_activities(self) -> list[dict]:
        """Get all delayed activities."""
        return self.execute_read(CypherTemplates.GET_DELAYED_ACTIVITIES)

    def get_delay_impact_chain(self, activity_id: str) -> list[dict]:
        """Get the chain of activities impacted by a delay."""
        return self.execute_read(
            CypherTemplates.GET_DELAY_IMPACT_CHAIN,
            {"activity_id": activity_id}
        )

    def get_near_critical_activities(self, threshold: float = 5.0) -> list[dict]:
        """Get activities with float below threshold but not critical."""
        return self.execute_read(
            CypherTemplates.GET_NEAR_CRITICAL_ACTIVITIES,
            {"threshold": threshold}
        )

    def get_high_risk_critical_activities(self, risk_threshold: float = 3.0) -> list[dict]:
        """Get critical path activities with high-risk exposure."""
        return self.execute_read(
            CypherTemplates.GET_HIGH_RISK_CRITICAL_ACTIVITIES,
            {"risk_threshold": risk_threshold}
        )

    def search_activities(self, search_term: str, limit: int = 10) -> list[dict]:
        """Full-text search for activities."""
        return self.execute_read(
            CypherTemplates.SEARCH_ACTIVITIES,
            {"search_term": search_term, "limit": limit}
        )

    def search_risks(self, search_term: str, limit: int = 10) -> list[dict]:
        """Full-text search for risks."""
        return self.execute_read(
            CypherTemplates.SEARCH_RISKS,
            {"search_term": search_term, "limit": limit}
        )

    def get_wbs_hierarchy(self, project_id: str) -> list[dict]:
        """Get the complete WBS hierarchy for a project."""
        return self.execute_read(
            CypherTemplates.GET_WBS_HIERARCHY,
            {"project_id": project_id}
        )

    def get_schedule_drivers(self, milestone_id: str, limit: int = 10) -> list[dict]:
        """Get activities that drive a milestone date."""
        return self.execute_read(
            CypherTemplates.GET_SCHEDULE_DRIVERS,
            {"milestone_id": milestone_id, "limit": limit}
        )

    def trace_path(
        self,
        start_activity_id: str,
        end_activity_id: str,
    ) -> list[dict]:
        """
        Trace the path between two activities.

        Returns all paths between start and end activities.
        """
        query = """
        MATCH path = (start:Activity {activity_id: $start_id})-[:PRECEDES*]->(end:Activity {activity_id: $end_id})
        RETURN path,
               length(path) as path_length,
               [n in nodes(path) | n.activity_code] as activity_codes
        ORDER BY path_length
        LIMIT 10
        """
        return self.execute_read(
            query,
            {"start_id": start_activity_id, "end_id": end_activity_id}
        )

    def get_activity_context(self, activity_id: str) -> dict:
        """
        Get full context for an activity including predecessors,
        successors, risks, WBS, and resources.
        """
        query = """
        MATCH (a:Activity {activity_id: $activity_id})
        OPTIONAL MATCH (a)<-[:PRECEDES]-(pred:Activity)
        OPTIONAL MATCH (a)-[:PRECEDES]->(succ:Activity)
        OPTIONAL MATCH (a)<-[:AFFECTS]-(risk:Risk)
        OPTIONAL MATCH (wbs:WBS)-[:CONTAINS]->(a)
        OPTIONAL MATCH (a)-[:USES]->(res:Resource)
        RETURN a as activity,
               collect(DISTINCT pred) as predecessors,
               collect(DISTINCT succ) as successors,
               collect(DISTINCT risk) as risks,
               wbs,
               collect(DISTINCT res) as resources
        """
        results = self.execute_read(query, {"activity_id": activity_id})
        return results[0] if results else {}

    def get_risk_context(self, risk_id: str) -> dict:
        """
        Get full context for a risk including affected activities,
        related risks, and owner.
        """
        query = """
        MATCH (r:Risk {risk_id: $risk_id})
        OPTIONAL MATCH (r)-[:AFFECTS]->(a:Activity)
        OPTIONAL MATCH (r)-[:RELATED_TO]-(related:Risk)
        OPTIONAL MATCH (r)-[:OWNED_BY]->(owner:Resource)
        OPTIONAL MATCH (r)-[:BELONGS_TO]->(cat:RiskCategory)
        RETURN r as risk,
               collect(DISTINCT a) as affected_activities,
               collect(DISTINCT related) as related_risks,
               owner,
               cat as category
        """
        results = self.execute_read(query, {"risk_id": risk_id})
        return results[0] if results else {}
