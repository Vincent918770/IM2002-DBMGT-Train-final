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
"""

from __future__ import annotations

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def _driver():
    """Return a Neo4j driver. Caller is responsible for closing."""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def example_count_nodes() -> int:
    """Example: count all nodes currently in the graph."""
    with _driver() as driver:
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS total")
            return result.single()["total"]


def _format_route(record, origin_id, destination_id, value_key, output_key):
    """Helper to standardize route output format."""
    if record is None:
        return {
            "found": False,
            "origin_id": origin_id,
            "destination_id": destination_id,
            "message": "No route found.",
        }

    return {
        "found": True,
        "origin_id": origin_id,
        "destination_id": destination_id,
        output_key: record[value_key],
        "path": record["stations"],
        "legs": record["legs"],
    }


# ── FASTEST ROUTE (Dijkstra by travel_time_min via APOC) ─────────────────────

def query_shortest_route(origin_id: str, destination_id: str, network: str = "auto") -> dict:
    """
    Find the fastest path between two stations, minimising total travel time.
    Uses apoc.algo.dijkstra for optimized performance.
    """
    cypher = """
    MATCH (start:Station {station_id: $origin_id})
    MATCH (end:Station {station_id: $destination_id})
    
    // 使用 APOC 的 Dijkstra 演算法，指定關係與權重屬性
    CALL apoc.algo.dijkstra(start, end, 'CONNECTS_TO|INTERCHANGES_WITH', 'travel_time_min')
    YIELD path, weight
    
    RETURN
        weight AS total_time_min,
        [n IN nodes(path) | {
            station_id: n.station_id,
            name: n.name,
            network: n.network,
            lines: n.lines
        }] AS stations,
        [r IN relationships(path) | {
            from: startNode(r).station_id,
            to: endNode(r).station_id,
            line: r.line,
            network: r.network,
            travel_time_min: coalesce(r.travel_time_min, 1)
        }] AS legs
    """

    with _driver() as driver:
        with driver.session() as session:
            record = session.run(
                cypher,
                origin_id=origin_id,
                destination_id=destination_id,
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
    Uses apoc.algo.dijkstra based on the 'fare' property.
    """
    fare_multiplier = 1.0
    if fare_class == "first":
        fare_multiplier = 1.8

    cypher = """
    MATCH (start:Station {station_id: $origin_id})
    MATCH (end:Station {station_id: $destination_id})
    
    // 使用 APOC 依照票價尋找最便宜路徑
    CALL apoc.algo.dijkstra(start, end, 'CONNECTS_TO|INTERCHANGES_WITH', 'fare')
    YIELD path, weight
    
    RETURN
        round(weight * $fare_multiplier * 100) / 100 AS total_fare,
        [n IN nodes(path) | {
            station_id: n.station_id,
            name: n.name,
            network: n.network,
            lines: n.lines
        }] AS stations,
        [r IN relationships(path) | {
            from: startNode(r).station_id,
            to: endNode(r).station_id,
            line: r.line,
            network: r.network,
            fare: coalesce(r.fare, 1.0),
            travel_time_min: coalesce(r.travel_time_min, 1)
        }] AS legs
    """

    with _driver() as driver:
        with driver.session() as session:
            record = session.run(
                cypher,
                origin_id=origin_id,
                destination_id=destination_id,
                fare_multiplier=fare_multiplier,
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
    Uses apoc.algo.allSimplePaths for efficient path discovery up to a safe depth limit.
    """
    origin_id = origin_id.upper()
    destination_id = destination_id.upper()
    avoid_station_id = avoid_station_id.upper()

    # Domain Knowledge: 轉乘站會一併封閉
    interchange_counterparts = {
        "NR01": "MS01", "MS01": "NR01",
        "NR03": "MS07", "MS07": "NR03",
        "NR07": "MS15", "MS15": "NR07",
    }

    avoid_ids = [avoid_station_id]
    if avoid_station_id in interchange_counterparts:
        avoid_ids.append(interchange_counterparts[avoid_station_id])

    cypher = """
    MATCH (start:Station {station_id: $origin_id})
    MATCH (end:Station {station_id: $destination_id})
    
    // 尋找深度 8 以內的所有簡單路徑 (APOC)
    CALL apoc.algo.allSimplePaths(start, end, 'CONNECTS_TO|INTERCHANGES_WITH', 8)
    YIELD path
    
    // 過濾掉包含封閉站點的路徑
    WHERE NONE(n IN nodes(path) WHERE n.station_id IN $avoid_ids)
    
    WITH path,
         reduce(total = 0, r IN relationships(path) |
            total + coalesce(r.travel_time_min, 1)
         ) AS total_time

    ORDER BY total_time ASC
    LIMIT $max_routes

    RETURN
        total_time,
        [n IN nodes(path) | {
            station_id: n.station_id,
            name: n.name,
            network: n.network,
            lines: n.lines
        }] AS stations,
        [r IN relationships(path) | {
            from: startNode(r).station_id,
            to: endNode(r).station_id,
            type: type(r),
            line: r.line,
            network: r.network,
            travel_time_min: coalesce(r.travel_time_min, 1)
        }] AS legs
    """

    with _driver() as driver:
        with driver.session() as session:
            records = session.run(
                cypher,
                origin_id=origin_id,
                destination_id=destination_id,
                avoid_ids=avoid_ids,
                max_routes=max_routes,
            )

            routes = []
            for index, record in enumerate(records, start=1):
                routes.append({
                    "route_number": index,
                    "origin_id": origin_id,
                    "destination_id": destination_id,
                    "avoid_station_ids": avoid_ids,
                    "total_time_min": record["total_time"],
                    "stations": record["stations"],
                    "legs": record["legs"],
                })

            return routes


# ── CROSS-NETWORK INTERCHANGE PATH ───────────────────────────────────────────

def query_interchange_path(origin_id: str, destination_id: str) -> dict:
    """
    Find a path between networks crossing an interchange boundary.
    Uses APOC Dijkstra and filters paths containing an INTERCHANGES_WITH relationship.
    """
    cypher = """
    MATCH (start:Station {station_id: $origin_id})
    MATCH (end:Station {station_id: $destination_id})
    
    CALL apoc.algo.dijkstra(start, end, 'CONNECTS_TO|INTERCHANGES_WITH', 'travel_time_min')
    YIELD path, weight
    
    // 確保路徑中必定包含至少一次轉乘
    WHERE ANY(r IN relationships(path) WHERE type(r) = "INTERCHANGES_WITH")
    
    RETURN
        weight AS total_time,
        [n IN nodes(path) | {
            station_id: n.station_id,
            name: n.name,
            network: n.network,
            lines: n.lines
        }] AS stations,
        [n IN nodes(path) WHERE n.is_interchange_metro = true OR n.is_interchange_national_rail = true |
            {
                station_id: n.station_id,
                name: n.name,
                network: n.network
            }
        ] AS interchange_points,
        [r IN relationships(path) | {
            from: startNode(r).station_id,
            to: endNode(r).station_id,
            type: type(r)
        }] AS legs
    """

    with _driver() as driver:
        with driver.session() as session:
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

            return {
                "found": True,
                "origin_id": origin_id,
                "destination_id": destination_id,
                "total_time_min": record["total_time"],
                "stations": record["stations"],
                "interchange_points": record["interchange_points"],
                "legs": record["legs"]
            }


# ── DELAY RIPPLE ANALYSIS (Native Cypher is optimal here) ─────────────────────

def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]:
    """
    Find all stations within N hops of a delayed or disrupted station.
    Native Cypher's variable length path is perfectly suited and efficient for this.
    """
    cypher = """
    MATCH (start:Station {station_id: $delayed_station_id})
    MATCH p = (start)-[:CONNECTS_TO|INTERCHANGES_WITH*1..$hops]-(affected:Station)
    WITH affected, min(length(p)) AS hops_away
    RETURN DISTINCT
        affected.station_id AS station_id,
        affected.name AS name,
        affected.network AS network,
        affected.lines AS lines_affected,
        hops_away
    ORDER BY hops_away ASC, station_id ASC
    """

    with _driver() as driver:
        with driver.session() as session:
            records = session.run(
                cypher,
                delayed_station_id=delayed_station_id,
                hops=int(hops),
            )

            return [
                {
                    "station_id": record["station_id"],
                    "name": record["name"],
                    "network": record["network"],
                    "hops_away": record["hops_away"],
                    "lines_affected": record["lines_affected"],
                }
                for record in records
            ]


# ── STATION CONNECTIONS (Native Cypher is optimal here) ───────────────────────

def query_station_connections(station_id: str) -> list[dict]:
    """List all direct connections from a given station."""
    cypher = """
    MATCH (s:Station {station_id: $station_id})-[r:CONNECTS_TO|INTERCHANGES_WITH]->(target:Station)
    RETURN
        target.station_id AS station_id,
        target.name AS name,
        target.network AS network,
        target.lines AS lines,
        type(r) AS relationship_type,
        r.line AS line,
        r.network AS connection_network,
        coalesce(r.travel_time_min, 1) AS travel_time_min,
        coalesce(r.fare, 0.0) AS fare
    ORDER BY travel_time_min ASC, station_id ASC
    """

    with _driver() as driver:
        with driver.session() as session:
            records = session.run(cypher, station_id=station_id)

            return [
                {
                    "station_id": record["station_id"],
                    "name": record["name"],
                    "network": record["network"],
                    "lines": record["lines"],
                    "relationship_type": record["relationship_type"],
                    "line": record["line"],
                    "connection_network": record["connection_network"],
                    "travel_time_min": record["travel_time_min"],
                    "fare": record["fare"],
                }
                for record in records
            ]