"""
TransitFlow — Neo4j Seeder
Run once after starting Docker:
    python skeleton/seed_neo4j.py

Loads station and network data from train-mock-data/:
  - metro_stations.json         — city metro stations and adjacencies
  - national_rail_stations.json — national rail stations and adjacencies

This script implements the graph schema (node labels, relationship types, properties)
based on the data in these files.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, ".")

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train-mock-data")
)


def _load(filename: str):
    with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


# ==========================================
# 輔助函式 (Helper Functions) 來自程式碼二
# ==========================================

def _create_constraints(session):
    session.run(
        """
        CREATE CONSTRAINT station_id_unique IF NOT EXISTS
        FOR (s:Station)
        REQUIRE s.station_id IS UNIQUE
        """
    )


def _merge_metro_station(session, station: dict):
    session.run(
        """
        MERGE (s:Station {station_id: $station_id})
        SET s:MetroStation,
            s.name = $name,
            s.network = "metro",
            s.lines = $lines,
            s.is_interchange_metro = $is_interchange_metro,
            s.interchange_metro_lines = $interchange_metro_lines,
            s.is_interchange_national_rail = $is_interchange_national_rail,
            s.interchange_national_rail_station_id = $interchange_national_rail_station_id
        """,
        station_id=station["station_id"],
        name=station.get("name", station["station_id"]),
        lines=station.get("lines", []),
        is_interchange_metro=station.get("is_interchange_metro", False),
        interchange_metro_lines=station.get("interchange_metro_lines", []),
        is_interchange_national_rail=station.get("is_interchange_national_rail", False),
        interchange_national_rail_station_id=(
            station.get("interchange_national_rail_station_id")
            or station.get("national_rail_station_id")
            or station.get("interchange_station_id")
        ),
    )


def _merge_rail_station(session, station: dict):
    session.run(
        """
        MERGE (s:Station {station_id: $station_id})
        SET s:NationalRailStation,
            s.name = $name,
            s.network = "national_rail",
            s.lines = $lines,
            s.is_interchange_national_rail = $is_interchange_national_rail,
            s.interchange_national_rail_lines = $interchange_national_rail_lines,
            s.is_interchange_metro = $is_interchange_metro,
            s.interchange_metro_station_id = $interchange_metro_station_id
        """,
        station_id=station["station_id"],
        name=station.get("name", station["station_id"]),
        lines=station.get("lines", []),
        is_interchange_national_rail=station.get("is_interchange_national_rail", False),
        interchange_national_rail_lines=station.get("interchange_national_rail_lines", []),
        is_interchange_metro=station.get("is_interchange_metro", False),
        interchange_metro_station_id=(
            station.get("interchange_metro_station_id")
            or station.get("metro_station_id")
            or station.get("interchange_station_id")
        ),
    )


def _merge_connection(session, from_id: str, to_id: str, line: str, travel_time_min: int, network: str):
    session.run(
        """
        MATCH (a:Station {station_id: $from_id})
        MATCH (b:Station {station_id: $to_id})
        MERGE (a)-[r:CONNECTS_TO {line: $line, network: $network}]->(b)
        SET r.travel_time_min = $travel_time_min,
            r.fare = CASE
                WHEN $network = "metro" THEN 1.0
                ELSE toFloat($travel_time_min) * 0.35
            END
        """,
        from_id=from_id,
        to_id=to_id,
        line=line,
        travel_time_min=int(travel_time_min),
        network=network,
    )


def _merge_interchange(session, metro_id: str, rail_id: str) -> bool:
    result = session.run(
        """
        MATCH (m:Station {station_id: $metro_id})
        MATCH (r:Station {station_id: $rail_id})

        MERGE (m)-[a:INTERCHANGES_WITH]->(r)
        SET a.travel_time_min = 5, a.fare = 0.0, a.network = "interchange", a.line = "INTERCHANGE"

        MERGE (r)-[b:INTERCHANGES_WITH]->(m)
        SET b.travel_time_min = 5, b.fare = 0.0, b.network = "interchange", b.line = "INTERCHANGE"

        RETURN count(a) + count(b) AS created_count
        """,
        metro_id=metro_id,
        rail_id=rail_id,
    ).single()

    return bool(result and result["created_count"] > 0)


def _extract_interchange_pairs_from_data(metro_stations: list[dict], rail_stations: list[dict]):
    pairs: list[tuple[str, str]] = []

    for station in metro_stations:
        metro_id = station.get("station_id")
        rail_id = station.get("interchange_national_rail_station_id") or station.get("national_rail_station_id") or station.get("interchange_station_id")
        if metro_id and rail_id and str(metro_id).upper().startswith("MS") and str(rail_id).upper().startswith("NR"):
            pairs.append((str(metro_id).upper(), str(rail_id).upper()))

    for station in rail_stations:
        rail_id = station.get("station_id")
        metro_id = station.get("interchange_metro_station_id") or station.get("metro_station_id") or station.get("interchange_station_id")
        if metro_id and rail_id and str(metro_id).upper().startswith("MS") and str(rail_id).upper().startswith("NR"):
            pairs.append((str(metro_id).upper(), str(rail_id).upper()))

    fallback_pairs = [("MS01", "NR01"), ("MS07", "NR03"), ("MS15", "NR07")]
    for pair in fallback_pairs:
        if pair not in pairs:
            pairs.append(pair)

    unique_pairs = []
    for pair in pairs:
        if pair not in unique_pairs:
            unique_pairs.append(pair)

    return unique_pairs


# ==========================================
# 主程式：以骨架為基礎，實作 TODO 內容
# ==========================================

def seed():
    metro_stations = _load("metro_stations.json")
    rail_stations  = _load("national_rail_stations.json")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("  Cleared existing graph data")
            
            # 建立約束以保證效能及資料正確性
            _create_constraints(session)

            # TODO: Design your node labels and create metro station nodes.
            # Each station has: station_id, name, lines, and interchange info.
            for station in metro_stations:
                _merge_metro_station(session, station)
            print(f"  Created {len(metro_stations)} metro stations")

            # TODO: Design your node labels and create national rail station nodes.
            for station in rail_stations:
                _merge_rail_station(session, station)
            print(f"  Created {len(rail_stations)} national rail stations")

            # TODO: Design your relationship types and create metro links.
            # Each station lists its adjacent_stations with line and travel_time_min.
            metro_links_count = 0
            for station in metro_stations:
                for adj in station.get("adjacent_stations", []):
                    to_id = adj.get("station_id")
                    if to_id:
                        _merge_connection(session, station["station_id"], to_id, adj.get("line", "UNKNOWN"), adj.get("travel_time_min", 1), "metro")
                        metro_links_count += 1
            print(f"  Created {metro_links_count} metro links")

            # TODO: Design your relationship types and create national rail links.
            rail_links_count = 0
            for station in rail_stations:
                for adj in station.get("adjacent_stations", []):
                    to_id = adj.get("station_id")
                    if to_id:
                        _merge_connection(session, station["station_id"], to_id, adj.get("line", "UNKNOWN"), adj.get("travel_time_min", 1), "national_rail")
                        rail_links_count += 1
            print(f"  Created {rail_links_count} national rail links")

            # TODO: Create interchange relationships between metro and rail stations.
            # Interchange info is in the is_interchange_national_rail field of metro_stations.json.
            interchange_pairs = _extract_interchange_pairs_from_data(metro_stations, rail_stations)
            interchange_count = 0
            for metro_id, rail_id in interchange_pairs:
                if _merge_interchange(session, metro_id, rail_id):
                    interchange_count += 1
            print(f"  Created {interchange_count} metro-national rail interchange pairs")
            
    finally:
        # 使用 try-finally 確保連線一定會關閉
        driver.close()

    print("\nNeo4j graph seeded successfully.")
    print("   Open http://localhost:7475 to explore the graph.")


if __name__ == "__main__":
    print("Connecting to Neo4j...")
    seed()