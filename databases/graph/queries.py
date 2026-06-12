"""
TransitFlow — Neo4j Graph Database Layer
=========================================
This module handles all queries to Neo4j.

GRAPH ROLE:
  - Model the dual transit network (city metro M1–M4 + national rail NR1–NR2)
  - Find fastest routes (Dijkstra by travel_time_min via APOC)
  - Find cheapest routes (Dijkstra by fare via APOC)
  - Find alternative routes avoiding a given station
  - Find cross-network interchange paths (metro → rail or rail → metro)
  - Show delay ripple: which stations are affected within N hops

STUDENT TASK
------------
Design your graph schema (node labels, relationship types, properties)
based on the data in train-mock-data/, seed it with skeleton/seed_neo4j.py,
then implement the query_ functions below.

Functions prefixed with `query_` are called by the agent (skeleton/agent.py).

TransitFlow — Neo4j Graph Database Layer (Refactored)
=========================================
This module handles all queries to Neo4j.

This module is responsible for Neo4j query logic, including fastest routes, cheapest routes, avoid-station paths, interchange routes, delay ripple analysis, and direct station connection queries.
"""

from __future__ import annotations

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# Global driver instance for Neo4j connection (singleton pattern)
_driver_instance = None

def _get_driver():
    """Initialize and return the Neo4j driver instance. Creates connection on first call and reuses it thereafter."""
    global _driver_instance
    if _driver_instance is None:
        _driver_instance = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver_instance

def close_driver():
    """Close the Neo4j driver connection and reset the global instance."""
    global _driver_instance
    if _driver_instance is not None:
        _driver_instance.close()
        _driver_instance = None


def example_count_nodes() -> int:
    """Example: count all nodes currently in the graph."""
    # Example function: show how to use a Neo4j session for a simple query
    driver = _get_driver()
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) AS total")
        return result.single()["total"]


def _format_route(record, origin_id, destination_id, value_key, output_key):
    """Helper to standardize route output format."""
    # Convert Cypher query results into a route format readable by the agent
    if record is None:
        return {
            "found": False,
            "origin_id": origin_id,
            "destination_id": destination_id,
            "message": "No route found.",
        }

    # Format successful route result with metric and path information
    return {
        "found": True,
        "origin_id": origin_id,
        "destination_id": destination_id,
        output_key: record[value_key],  # Insert the calculated metric (time/fare)
        "path": record["stations"],     # List of stations traversed
        "legs": record["legs"],         # List of individual route segments
    }


# ── FASTEST ROUTE (Dijkstra by travel_time_min via APOC) ─────────────────────

def query_shortest_route(origin_id: str, destination_id: str, network: str = "auto") -> dict:
    """
    Find the fastest path between two stations, minimising total travel time.
    """
    # When network is 'auto' allow metro, rail, and interchange links; otherwise restrict to a single network
    rel_type = "METRO_LINK|RAIL_LINK" if network != "auto" else "METRO_LINK|RAIL_LINK|INTERCHANGE_TO"

    cypher = f"""
    MATCH (start:Station {{station_id: $origin_id}})
    MATCH (end:Station {{station_id: $destination_id}})
    
    CALL apoc.algo.dijkstra(start, end, '{rel_type}', 'travel_time_min')
    YIELD path, weight
    
    // Ensure network consistency: in auto mode any mix is allowed; otherwise all edges must match network param
    WHERE $network = 'auto' OR ALL(r IN relationships(path) WHERE r.network = $network)
    
    RETURN
        weight AS total_time_min,                           // Dijkstra's weight: total travel time in minutes
        [n IN nodes(path) | {{                              // Build station list from path nodes
            station_id: n.station_id,
            name: n.name,
            network: n.network,
            lines: n.lines
        }}] AS stations,
        [i IN range(0, length(path)-1) | {{               // Build leg list from path edges
            from: nodes(path)[i].station_id,
            to: nodes(path)[i+1].station_id,
            line: relationships(path)[i].line,
            network: relationships(path)[i].network,
            travel_time_min: coalesce(relationships(path)[i].travel_time_min, 1)  // Default 1 min if missing
        }}] AS legs
    """

    driver = _get_driver()
    with driver.session() as session:
        record = session.run(
            cypher,
            origin_id=origin_id,
            destination_id=destination_id,
            network=network
        ).single()

        return _format_route(
            record=record,
            origin_id=origin_id,
            destination_id=destination_id,
            value_key="total_time_min",
            output_key="total_time_min",
        )


# ── CHEAPEST ROUTE (Dijkstra by fare via APOC) ───────────────────────────────

def query_cheapest_route(
    origin_id: str,
    destination_id: str,
    network: str = "auto",
    fare_class: str = "standard",
) -> dict:
    """
    Find the cheapest path between two stations, minimising total estimated fare.
    Note: Requires 'fare' and 'fare_first' properties to exist in the database.
    """
    # When network is 'auto' allow all route types; otherwise only search the specified network
    rel_type = "METRO_LINK|RAIL_LINK" if network != "auto" else "METRO_LINK|RAIL_LINK|INTERCHANGE_TO"
    
    # Select weight property: first-class uses fare_first, standard uses fare
    weight_property = "fare_first" if fare_class == "first" else "fare"

    cypher = f"""
    MATCH (start:Station {{station_id: $origin_id}})
    MATCH (end:Station {{station_id: $destination_id}})
    
    // Use Dijkstra to find minimum-cost path
    CALL apoc.algo.dijkstra(start, end, '{rel_type}', $weight_property)
    YIELD path, weight AS total_fare
    
    // Ensure network consistency when specified
    WHERE $network = 'auto' OR ALL(r IN relationships(path) WHERE r.network = $network)
    
    // Check which networks are traversed in the path
    WITH path, total_fare,
         ANY(r IN relationships(path) WHERE toLower(r.network) = 'metro') AS has_metro,
         ANY(r IN relationships(path) WHERE toLower(r.network) = 'national_rail') AS has_rail
    // Add network-specific base fees to the path fare
    WITH path, total_fare,
         (CASE WHEN has_metro THEN 0.80 ELSE 0.0 END + 
          CASE WHEN has_rail THEN 2.50 ELSE 0.0 END) AS base_fare
    RETURN
        round((total_fare + base_fare) * 100) / 100 AS total_fare,    // Round to 2 decimal places
        [n IN nodes(path) | {{
            station_id: n.station_id,
            name: n.name,
            network: n.network,
            lines: n.lines
        }}] AS stations,
        [i IN range(0, length(path)-1) | {{
            from: nodes(path)[i].station_id,
            to: nodes(path)[i+1].station_id,
            line: relationships(path)[i].line,
            network: relationships(path)[i].network,
            fare: coalesce(relationships(path)[i][$weight_property], 1.0),          // Default fare if missing
            travel_time_min: coalesce(relationships(path)[i].travel_time_min, 1)   // Default time if missing
        }}] AS legs
    """

    driver = _get_driver()
    with driver.session() as session:
        record = session.run(
            cypher,
            origin_id=origin_id,
            destination_id=destination_id,
            network=network,
            weight_property=weight_property
        ).single()

        return _format_route(
            record=record,
            origin_id=origin_id,
            destination_id=destination_id,
            value_key="total_fare",
            output_key="total_fare_usd",
        )


# ── ALTERNATIVE ROUTES (Avoid station via APOC allSimplePaths) ───────────────

def query_alternative_routes(
    origin_id: str,
    destination_id: str,
    avoid_station_id: str,
    network: str = "auto",
    max_routes: int = 3,
) -> list[dict]:
    """
    Find alternative routes while avoiding a closed station and its interchange counterpart.
    """
    # Convert station IDs to uppercase to ensure consistent matching
    origin_id = origin_id.upper()
    destination_id = destination_id.upper()
    avoid_station_id = avoid_station_id.upper()

    # Mapping of interchange station pairs to avoid both when one is closed
    interchange_counterparts = {
        "NR01": "MS01", "MS01": "NR01",
        "NR03": "MS07", "MS07": "NR03",
        "NR07": "MS15", "MS15": "NR07",
    }

    # Build list of stations to avoid: the main station plus its interchange pair if it exists
    avoid_ids = [avoid_station_id]
    if avoid_station_id in interchange_counterparts:
        avoid_ids.append(interchange_counterparts[avoid_station_id])

    cypher = """
    MATCH (start:Station {station_id: $origin_id})
    MATCH (end:Station {station_id: $destination_id})

    // Find all simple paths (no cycles) up to 8 hops with any combination of link types
    MATCH p = (start)-[:METRO_LINK|RAIL_LINK|INTERCHANGE_TO*1..8]-(end)

    // Filter out paths containing avoided stations and ensure no node appears twice
    WHERE NONE(n IN nodes(p) WHERE n.station_id IN $avoid_ids)
      AND ALL(n IN nodes(p) WHERE single(m IN nodes(p) WHERE m = n))

    // Calculate total travel time for the path
    WITH p,
         reduce(total = 0, r IN relationships(p) |
             total + coalesce(r.travel_time_min, 1)       // Sum edge times with default 1 minute
         ) AS total_time

    // Sort by efficiency: shortest time first, then fewest hops
    ORDER BY total_time ASC, length(p) ASC
    LIMIT $max_routes

    RETURN
        total_time,
        [n IN nodes(p) | {
            station_id: n.station_id,
            name: n.name,
            network: n.network,
            lines: n.lines
        }] AS stations,
        [r IN relationships(p) | {
            from: startNode(r).station_id,
            to: endNode(r).station_id,
            type: type(r),
            line: r.line,
            network: r.network,
            travel_time_min: coalesce(r.travel_time_min, 1)
        }] AS legs
    """

    driver = _get_driver() 
    with driver.session() as session:
        # Execute Cypher query with parameters
        records = session.run(
            cypher,
            origin_id=origin_id,
            destination_id=destination_id,
            avoid_ids=avoid_ids,
            max_routes=max_routes,
        )

        # Convert query results into standardized route dictionaries
        routes = []
        for index, record in enumerate(records, start=1):
            routes.append(
                {
                    "route_number": index,                          # Sequential number for display
                    "origin_id": origin_id,
                    "destination_id": destination_id,
                    "avoid_station_ids": avoid_ids,                 # Stations excluded from this route
                    "total_time_min": record["total_time"],
                    "path": record["stations"],
                    "stations": record["stations"],
                    "legs": record["legs"],
                }
            )
        return routes


# ── CROSS-NETWORK INTERCHANGE PATH ───────────────────────────────────────────

def query_interchange_path(origin_id: str, destination_id: str) -> dict:
    """
    Find a path between networks crossing an interchange boundary.
    """
    # Find a cross-network path that MUST include INTERCHANGE_TO relationship
    cypher = """
    MATCH (start:Station {station_id: $origin_id})
    MATCH (end:Station {station_id: $destination_id})
    
    // Find paths allowing any combination of link types, up to 15 hops
    MATCH path = (start)-[:METRO_LINK|RAIL_LINK|INTERCHANGE_TO*1..15]-(end)
    // Filter: only keep paths that have at least one INTERCHANGE_TO relationship
    WHERE ANY(r IN relationships(path) WHERE type(r) = 'INTERCHANGE_TO')
    
    // Calculate total travel time by summing edge weights
    WITH path, reduce(t = 0, r IN relationships(path) | t + coalesce(r.travel_time_min, 1)) AS total_time
    // Get the fastest interchange path
    ORDER BY total_time ASC
    LIMIT 1
    
    RETURN
        total_time,
        [n IN nodes(path) | {
            station_id: n.station_id,
            name: n.name,
            network: n.network,
            lines: n.lines
        }] AS stations,

        // Extract stations that are endpoints of INTERCHANGE_TO edges
        [n IN nodes(path) WHERE ANY(r IN relationships(path) WHERE type(r) = 'INTERCHANGE_TO' AND (startNode(r) = n OR endNode(r) = n)) | {
                station_id: n.station_id,
                name: n.name,
                network: n.network
            }
        ] AS interchange_points,
        [i IN range(0, length(path)-1) | {
            from: nodes(path)[i].station_id,
            to: nodes(path)[i+1].station_id,
            type: type(relationships(path)[i])
        }] AS legs
    """

    driver = _get_driver()
    with driver.session() as session:
        # Execute query and get single result (or None)
        record = session.run(
            cypher,
            origin_id=origin_id,
            destination_id=destination_id,
        ).single()

        if record is None:
            return {
                "found": False,
                "origin_id": origin_id,
                "destination_id": destination_id,
                "message": "No interchange path found.",
            }

        # Return successful result with detailed route and interchange info
        return {
            "found": True,
            "origin_id": origin_id,
            "destination_id": destination_id,
            "total_time_min": record["total_time"],
            "stations": record["stations"],
            "interchange_points": record["interchange_points"],      # Stations where network transfer occurs
            "legs": record["legs"]
        }


# ── DELAY RIPPLE ANALYSIS (Using APOC Expand Config) ─────────────────────────

def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]:
    """
    Find all stations within N hops of a delayed or disrupted station.
    """
    # Use APOC path.expandConfig to collect stations affected within the specified hop range
    cypher = """
    MATCH (start:Station {station_id: $delayed_station_id})
    // Expand from start station to all reachable stations within hop range
    CALL apoc.path.expandConfig(start, {
        relationshipFilter: "METRO_LINK|RAIL_LINK|INTERCHANGE_TO",  // Allow any link type
        minLevel: 1,                                                  // At least 1 hop
        maxLevel: $hops,                                              // At most N hops
        uniqueness: "NODE_GLOBAL"                                     // Visit each node only once
    })
    YIELD path
    
    // Extract the last (farthest) node in each path and count hops
    WITH last(nodes(path)) AS affected, length(path) AS hops_away
    
    // Return distinct affected stations sorted by distance
    RETURN DISTINCT
        affected.station_id AS station_id,
        affected.name AS name,
        affected.network AS network,
        affected.lines AS lines_affected,
        hops_away                                                      // Distance from disruption
    ORDER BY hops_away ASC, station_id ASC
    """

    driver = _get_driver()
    with driver.session() as session:
        # Execute ripple expansion query
        records = session.run(
            cypher,
            delayed_station_id=delayed_station_id,
            hops=int(hops)
        )

        # Convert results to standardized affected station format
        return [
            {
                "station_id": record["station_id"],
                "name": record["name"],
                "network": record["network"],
                "hops_away": record["hops_away"],                    # Distance from disruption
                "lines_affected": record["lines_affected"],
            }
            for record in records
        ]


# ── STATION CONNECTIONS (Native Cypher is optimal here) ───────────────────────

def query_station_connections(station_id: str, max_hops: int = 1) -> list[dict]:
    """List all direct connections from a given station."""
    # Query direct neighbor connections from the target station
    cypher = """
    MATCH (s:Station {station_id: $station_id})-[r:METRO_LINK|RAIL_LINK|INTERCHANGE_TO]->(target:Station)
    RETURN
        target.station_id AS station_id,
        target.name AS name,
        target.network AS network,
        target.lines AS lines,
        type(r) AS relationship_type,                                 // METRO_LINK, RAIL_LINK, or INTERCHANGE_TO
        r.line AS line,                                              // Line identifier (e.g., 'M1', 'NR1')
        r.network AS connection_network,                             // Network of the edge
        coalesce(r.travel_time_min, 1) AS travel_time_min,          // Travel time with default fallback
        coalesce(r.fare, 0.0) AS fare                               // Fare with default fallback
    ORDER BY travel_time_min ASC, station_id ASC
    """

    driver = _get_driver()
    with driver.session() as session:
        # Execute connection query
        records = session.run(cypher, station_id=station_id)

        # Convert results to standardized connection format
        return [
            {
                "station_id": record["station_id"],
                "name": record["name"],
                "network": record["network"],
                "lines": record["lines"],
                "relationship_type": record["relationship_type"],   # Type of link to neighbor
                "line": record["line"],                             # Specific line identifier
                "connection_network": record["connection_network"],
                "travel_time_min": record["travel_time_min"],
                "fare": record["fare"],
            }
            for record in records
        ]