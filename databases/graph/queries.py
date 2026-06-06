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

"""
TransitFlow — Neo4j Graph Database Layer (Refactored)
=========================================
This module handles all queries to Neo4j.

本模組負責 Neo4j 的查詢邏輯，包含最短時間、最低車資、避站路線、換乘路徑、延誤影響範圍、
以及直接站點連線查詢。
"""

from __future__ import annotations

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def _driver():
    """Return a Neo4j driver. Caller is responsible for closing."""
    # 建立 Neo4j 連線驅動，後續查詢皆使用此驅動物件
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def example_count_nodes() -> int:
    """Example: count all nodes currently in the graph."""
    # 範例函式：示範如何使用 Neo4j session 進行簡單查詢
    with _driver() as driver:
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS total")
            return result.single()["total"]


def _format_route(record, origin_id, destination_id, value_key, output_key):
    """Helper to standardize route output format."""
    # 將 Cypher 查詢結果統一轉換成 agent 可讀的路徑格式
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
    """
    # network = 'auto' 時允許經過地鐵、國鐵與換乘連線；否則限制在單一路網內
    rel_type = "METRO_LINK|RAIL_LINK" if network != "auto" else "METRO_LINK|RAIL_LINK|INTERCHANGE_TO"

    cypher = f"""
    MATCH (start:Station {{station_id: $origin_id}})
    MATCH (end:Station {{station_id: $destination_id}})
    
    CALL apoc.algo.dijkstra(start, end, '{rel_type}', 'travel_time_min')
    YIELD path, weight
    
    // Fix: Explicit network isolation check to prevent traversing wrong networks
    WHERE $network = 'auto' OR ALL(r IN relationships(path) WHERE r.network = $network)
    
    RETURN
        weight AS total_time_min,
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
            travel_time_min: coalesce(relationships(path)[i].travel_time_min, 1)
        }}] AS legs
    """

    with _driver() as driver:
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
    # network = 'auto' 時允許所有路線種類，否則只搜尋指定網路
    rel_type = "METRO_LINK|RAIL_LINK" if network != "auto" else "METRO_LINK|RAIL_LINK|INTERCHANGE_TO"
    
    # 根據票種選擇不同的權重屬性：first class 使用 fare_first，其他使用 fare
    weight_property = "fare_first" if fare_class == "first" else "fare"

    cypher = f"""
    MATCH (start:Station {{station_id: $origin_id}})
    MATCH (end:Station {{station_id: $destination_id}})
    
    CALL apoc.algo.dijkstra(start, end, '{rel_type}', $weight_property)
    YIELD path, weight AS total_fare
    
    WHERE $network = 'auto' OR ALL(r IN relationships(path) WHERE r.network = $network)
    
    RETURN
        round(total_fare * 100) / 100 AS total_fare,
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
            fare: coalesce(relationships(path)[i][$weight_property], 1.0),
            travel_time_min: coalesce(relationships(path)[i].travel_time_min, 1)
        }}] AS legs
    """

    with _driver() as driver:
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
) -> list[list[dict]]:
    """
    Find alternative routes while avoiding a closed station and its interchange counterpart.
    """
    # 站號轉成大寫，保證比對一致性
    origin_id = origin_id.upper()
    destination_id = destination_id.upper()
    avoid_station_id = avoid_station_id.upper()

    # 針對已知換乘站，避免同一座站的對應換乘站也被走到
    interchange_counterparts = {
        "NR01": "MS01", "MS01": "NR01",
        "NR03": "MS07", "MS07": "NR03",
        "NR07": "MS15", "MS15": "NR07",
    }

    avoid_ids = [avoid_station_id]
    if avoid_station_id in interchange_counterparts:
        avoid_ids.append(interchange_counterparts[avoid_station_id])

    rel_type = "METRO_LINK|RAIL_LINK" if network != "auto" else "METRO_LINK|RAIL_LINK|INTERCHANGE_TO"

    cypher = f"""
    MATCH (start:Station {{station_id: $origin_id}})
    MATCH (end:Station {{station_id: $destination_id}})
    
    CALL apoc.algo.allSimplePaths(start, end, '{rel_type}', 8)
    YIELD path
    
    WHERE NONE(n IN nodes(path) WHERE n.station_id IN $avoid_ids)
      AND ($network = 'auto' OR ALL(r IN relationships(path) WHERE r.network = $network))
    
    WITH path,
         reduce(total = 0, r IN relationships(path) |
            total + coalesce(r.travel_time_min, 1)
         ) AS total_time

    ORDER BY total_time ASC
    LIMIT $max_routes

    RETURN
        [i IN range(0, length(path)-1) | {{
            from: nodes(path)[i].station_id,
            to: nodes(path)[i+1].station_id,
            type: type(relationships(path)[i]),
            line: relationships(path)[i].line,
            network: relationships(path)[i].network,
            travel_time_min: coalesce(relationships(path)[i].travel_time_min, 1)
        }}] AS legs
    """

    with _driver() as driver:
        with driver.session() as session:
            records = session.run(
                cypher,
                origin_id=origin_id,
                destination_id=destination_id,
                avoid_ids=avoid_ids,
                network=network,
                max_routes=max_routes,
            )
            return [record["legs"] for record in records]


# ── CROSS-NETWORK INTERCHANGE PATH ───────────────────────────────────────────

def query_interchange_path(origin_id: str, destination_id: str) -> dict:
    """
    Find a path between networks crossing an interchange boundary.
    """
    # 查找必須包含 INTERCHANGE_TO 的跨網路路徑，而不是僅找最短路徑
    cypher = """
    MATCH (start:Station {station_id: $origin_id})
    MATCH (end:Station {station_id: $destination_id})
    
    MATCH path = (start)-[:METRO_LINK|RAIL_LINK|INTERCHANGE_TO*1..15]-(end)
    WHERE ANY(r IN relationships(path) WHERE type(r) = 'INTERCHANGE_TO')
    
    WITH path, reduce(t = 0, r IN relationships(path) | t + coalesce(r.travel_time_min, 1)) AS total_time
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


# ── DELAY RIPPLE ANALYSIS (Using APOC Expand Config) ─────────────────────────

def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]:
    """
    Find all stations within N hops of a delayed or disrupted station.
    """
    # 使用 APOC path.expandConfig 來收集指定 hop 範圍內受影響的車站
    cypher = """
    MATCH (start:Station {station_id: $delayed_station_id})
    CALL apoc.path.expandConfig(start, {
        relationshipFilter: "METRO_LINK|RAIL_LINK|INTERCHANGE_TO",
        minLevel: 1,
        maxLevel: $hops,
        uniqueness: "NODE_GLOBAL"
    })
    YIELD path
    
    WITH last(nodes(path)) AS affected, length(path) AS hops_away
    
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
                hops=int(hops)
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
    # 查詢目標車站直接可達的鄰站連線
    cypher = """
    MATCH (s:Station {station_id: $station_id})-[r:METRO_LINK|RAIL_LINK|INTERCHANGE_TO]->(target:Station)
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
