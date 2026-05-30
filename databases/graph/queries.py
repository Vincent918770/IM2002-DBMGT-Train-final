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
from typing import Optional
from neo4j import GraphDatabase

# 讀取骨架專案中的配置
# 自適應引入，若 config 在當前目錄請改為 from config import ...
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


# ── FASTEST ROUTE (Dijkstra by travel_time_min) ───────────────────────────────

def query_shortest_route(
    origin_id: str,
    destination_id: str,
    network: str = "auto",
) -> dict:
    """
    Find the fastest path between two stations, minimising total travel time.
    Uses apoc.algo.dijkstra (APOC required; enabled in docker-compose.yml).

    Args:
        origin_id:       e.g. "MS01" or "NR01"
        destination_id:  e.g. "MS09" or "NR05"
        network:         "metro", "rail", or "auto" (inferred from IDs)

    Returns:
        dict with keys: found, origin_id, destination_id,
                        total_time_min, path (list of station dicts), legs
    """
    with _driver() as driver:
        with driver.session() as session:
            # 使用 apoc.algo.dijkstra 尋找權重最短路徑
            cypher = """
            MATCH (start {id: $origin_id}), (end {id: $destination_id})
            CALL apoc.algo.dijkstra(start, end, 'LINKED_TO|TRANSFER_TO', 'travel_time_min')
            YIELD path, weight
            RETURN weight AS total_time, nodes(path) AS stations
            """
            result = session.run(cypher, origin_id=origin_id, destination_id=destination_id)
            record = result.single()
            
            if not record:
                return {"found": False, "origin_id": origin_id, "destination_id": destination_id}
                
            stations_list = [{"id": n["id"], "name": n["name"], "lines": n["lines"]} for n in record["stations"]]
            return {
                "found": True,
                "origin_id": origin_id,
                "destination_id": destination_id,
                "total_time_min": record["total_time"],
                "path": stations_list,
                "legs": len(stations_list) - 1
            }


# ── CHEAPEST ROUTE (Dijkstra by fare) ────────────────────────────────────────

def query_cheapest_route(
    origin_id: str,
    destination_id: str,
    network: str = "auto",
    fare_class: str = "standard",
) -> dict:
    """
    Find the cheapest path between two stations, minimising total estimated fare.

    Args:
        origin_id:       e.g. "NR01"
        destination_id:  e.g. "NR05"
        network:         "metro", "rail", or "auto"
        fare_class:      "standard" or "first" (national rail only)

    Returns:
        dict with found, total_fare_usd (approximate), stations, legs
    """
    # 依據傳入的艙等選擇對應的關係屬性
    weight_prop = "fare_first" if fare_class == "first" else "fare_standard"
    
    with _driver() as driver:
        with driver.session() as session:
            cypher = f"""
            MATCH (start {{id: $origin_id}}), (end {{id: $destination_id}})
            CALL apoc.algo.dijkstra(start, end, 'LINKED_TO|TRANSFER_TO', '{weight_prop}')
            YIELD path, weight
            RETURN weight AS total_fare, nodes(path) AS stations
            """
            result = session.run(cypher, origin_id=origin_id, destination_id=destination_id)
            record = result.single()
            
            if not record:
                return {"found": False}
                
            stations_list = [{"id": n["id"], "name": n["name"]} for n in record["stations"]]
            return {
                "found": True,
                "total_fare_usd": record["total_fare"],
                "stations": stations_list,
                "legs": len(stations_list) - 1
            }


# ── ALTERNATIVE ROUTES (avoiding a station) ───────────────────────────────────

def query_alternative_routes(
    origin_id: str,
    destination_id: str,
    avoid_station_id: str,
    network: str = "auto",
    max_routes: int = 3,
) -> list[list[dict]]:
    """
    Find paths between two stations that avoid a specific intermediate station.
    Useful for routing around a delayed or closed station.
    (利用 apoc.algo.allSimplePaths 搜尋所有路徑，並在 Cypher 中過濾掉故障站。)

    Args:
        origin_id:         e.g. "NR01"
        destination_id:    e.g. "NR05"
        avoid_station_id:  e.g. "NR03"
        network:           "metro", "rail", or "auto"
        max_routes:        max number of alternatives to return

    Returns:
        List of routes, each route is a list of leg dicts
    """
    with _driver() as driver:
        with driver.session() as session:
            # 尋找所有路徑，並用 NONE(x IN nodes(p) WHERE x.id = ...) 來動態避開故障站
            cypher = """
            MATCH (start {id: $origin_id}), (end {id: $destination_id})
            CALL apoc.algo.allSimplePaths(start, end, 'LINKED_TO|TRANSFER_TO', 15)
            YIELD path
            WHERE NONE(node IN nodes(path) WHERE node.id = $avoid_station_id)
            RETURN [n in nodes(path) | {id: n.id, name: n.name}] AS route_nodes
            LIMIT $max_routes
            """
            result = session.run(cypher, origin_id=origin_id, destination_id=destination_id, 
                                 avoid_station_id=avoid_station_id, max_routes=max_routes)
            
            routes = []
            for record in result:
                routes.append(record["route_nodes"])
            return routes


# ── CROSS-NETWORK INTERCHANGE PATH ───────────────────────────────────────────

def query_interchange_path(origin_id: str, destination_id: str) -> dict:
    """
    Find a path between a metro station and a national rail station (or vice versa)
    crossing the network boundary via interchange relationships.

    Args:
        origin_id:       e.g. "MS03" (metro) or "NR05" (national rail)
        destination_id:  e.g. "NR05" (national rail) or "MS09" (metro)

    Returns:
        dict with found, stations list, interchange points, total_time_min
    """
    with _driver() as driver:
        with driver.session() as session:
            # 尋找包含 TRANSFER_TO 關係的跨網路最短路徑
            cypher = """
            MATCH (start {id: $origin_id}), (end {id: $destination_id})
            CALL apoc.algo.dijkstra(start, end, 'LINKED_TO|TRANSFER_TO', 'travel_time_min')
            YIELD path, weight
            RETURN weight AS total_time, nodes(path) AS s_nodes, relationships(path) AS r_rels
            """
            result = session.run(cypher, origin_id=origin_id, destination_id=destination_id)
            record = result.single()
            
            if not record:
                return {"found": False}
                
            stations = [{"id": n["id"], "name": n["name"]} for n in record["s_nodes"]]
            
            # 篩選出路徑中哪些點是進行「跨網轉乘」的交會點
            interchanges = []
            for rel in record["r_rels"]:
                if rel.type == "TRANSFER_TO":
                    # 抓取該關係的起點站 ID
                    interchanges.append(rel.start_node.id if hasattr(rel.start_node, 'id') else "Interchange Station")

            return {
                "found": True,
                "stations": stations,
                "interchange_points": interchanges,
                "total_time_min": record["total_time"]
            }


# ── DELAY RIPPLE ANALYSIS ─────────────────────────────────────────────────────

def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]:
    """
    Find all stations within N hops of a delayed or disrupted station.
    Works on both metro and national rail networks.

    Args:
        delayed_station_id: e.g. "NR03" or "MS01"
        hops:               how many connections out to search (default 2)

    Returns:
        List of dicts: {station_id, name, hops_away, lines_affected}
    """
    with _driver() as driver:
        with driver.session() as session:
            # 運用 Cypher 變長路徑 *1..hops 計算特定步數內影響的車站
            cypher = f"""
            MATCH p = (start {{id: $delayed_station_id}})-[*1..{hops}]-(affected)
            WHERE start <> affected
            WITH affected, min(length(p)) AS hops_away
            RETURN affected.id AS station_id, 
                   affected.name AS name, 
                   hops_away, 
                   affected.lines AS lines_affected
            ORDER BY hops_away, station_id
            """
            result = session.run(cypher, delayed_station_id=delayed_station_id)
            
            ripple_list = []
            for record in result:
                ripple_list.append({
                    "station_id": record["station_id"],
                    "name": record["name"],
                    "hops_away": record["hops_away"],
                    "lines_affected": record["lines_affected"]
                })
            return ripple_list


# ── STATION CONNECTIONS ───────────────────────────────────────────────────────

def query_station_connections(station_id: str) -> list[dict]:
    """
    List all direct connections from a given station.

    Args:
        station_id: e.g. "MS01" or "NR01"
    """
    with _driver() as driver:
        with driver.session() as session:
            cypher = """
            MATCH (start {id: $station_id})-[r:LINKED_TO|TRANSFER_TO]->(next)
            RETURN next.id AS to_id, 
                   next.name AS to_name, 
                   type(r) AS connection_type,
                   r.line AS line, 
                   r.travel_time_min AS time
            """
            result = session.run(cypher, station_id=station_id)
            return [dict(record) for record in result]