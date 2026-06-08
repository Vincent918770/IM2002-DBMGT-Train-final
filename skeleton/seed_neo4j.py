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

# Add the project root to the module search path so skeleton.config can be imported correctly
sys.path.insert(0, ".")

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# Data directory path pointing to train-mock-data
_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train-mock-data")
)


def _load(filename: str):
    """Load the specified JSON file and return its data."""
    with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def _create_constraints(session):
    """Create a uniqueness constraint on station_id in Neo4j to prevent duplicate nodes."""
    session.run(
        """
        CREATE CONSTRAINT station_id_unique IF NOT EXISTS
        FOR (s:Station)
        REQUIRE s.station_id IS UNIQUE
        """
    )


def _merge_metro_station(session, station: dict):
    """Create or merge a metro station node and set its properties."""
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
    """Create or merge a national rail station node and set its properties."""
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


def _merge_metro_link(session, from_id: str, to_id: str, line: str, travel_time_min: int):
    """Create or merge a METRO_LINK relationship between metro stations."""
    session.run(
        """
        MATCH (a:Station {station_id: $from_id})
        MATCH (b:Station {station_id: $to_id})
        MERGE (a)-[r:METRO_LINK {line: $line}]->(b)
        SET r.travel_time_min = $travel_time_min,
            r.network = "metro",
            r.fare = 1.0,
            r.fare_first = 1.0
        """,
        from_id=from_id,
        to_id=to_id,
        line=line,
        travel_time_min=int(travel_time_min),
    )

def _merge_rail_link(session, from_id: str, to_id: str, line: str, travel_time_min: int):
    """Create or merge a RAIL_LINK relationship between national rail stations."""
    session.run(
        """
        MATCH (a:Station {station_id: $from_id})
        MATCH (b:Station {station_id: $to_id})
        MERGE (a)-[r:RAIL_LINK {line: $line}]->(b)
        SET r.travel_time_min = $travel_time_min,
            r.network = "national_rail",
            r.fare = toFloat($travel_time_min) * 0.35,
            r.fare_first = toFloat($travel_time_min) * 0.35 * 1.8
        """,
        from_id=from_id,
        to_id=to_id,
        line=line,
        travel_time_min=int(travel_time_min),
    )


def _merge_interchange(session, metro_id: str, rail_id: str) -> bool:
    """Create bidirectional INTERCHANGE_TO transfer relationships between metro and national rail stations."""
    result = session.run(
        """
        MATCH (m:MetroStation {station_id: $metro_id})
        MATCH (r:NationalRailStation {station_id: $rail_id})

        /* 修正為 INTERCHANGE_TO */
        MERGE (m)-[a:INTERCHANGE_TO]->(r)
        SET a.travel_time_min = 5, a.fare = 0.0, a.fare_first = 0.0, a.network = "interchange", a.line = "INTERCHANGE"

        /* 修正為 INTERCHANGE_TO */
        MERGE (r)-[b:INTERCHANGE_TO]->(m)
        SET b.travel_time_min = 5, b.fare = 0.0, b.fare_first = 0.0, b.network = "interchange", b.line = "INTERCHANGE"

        RETURN count(a) + count(b) AS created_count
        """,
        metro_id=metro_id,
        rail_id=rail_id,
    ).single()

    return bool(result and result["created_count"] > 0)


def _extract_interchange_pairs_from_data(metro_stations: list[dict], rail_stations: list[dict]):
    """Extract matching metro/national rail interchange station pairs from station data."""
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

    unique_pairs = []
    for pair in pairs:
        if pair not in unique_pairs:
            unique_pairs.append(pair)

    return unique_pairs


# ==========================================
# Main program: implement the TODO logic based on the skeleton
# ==========================================

def seed():
    # Load raw JSON data for both transit networks
    metro_stations = _load("metro_stations.json")
    rail_stations  = _load("national_rail_stations.json")

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with driver.session() as session:
            # Clear existing graph data to avoid duplicate nodes or relationships
            session.run("MATCH (n) DETACH DELETE n")
            print("  Cleared existing graph data")
            
            # Create constraints to ensure performance and data correctness
            _create_constraints(session)

            # Create metro station nodes with IDs, names, lines, and interchange info
            for station in metro_stations:
                _merge_metro_station(session, station)
            print(f"  Created {len(metro_stations)} metro stations")

            # Create national rail station nodes with IDs, names, lines, and interchange info
            for station in rail_stations:
                _merge_rail_station(session, station)
            print(f"  Created {len(rail_stations)} national rail stations")

            # Create adjacent links between metro stations
            # Each station record includes adjacent_stations, which can generate the route relationships
            metro_links_count = 0
            for station in metro_stations:
                for adj in station.get("adjacent_stations", []):
                    to_id = adj.get("station_id")
                    if to_id:
                        _merge_metro_link(session, station["station_id"], to_id, adj.get("line", "UNKNOWN"), adj.get("travel_time_min", 1))
                        metro_links_count += 1
            print(f"  Created {metro_links_count} metro links")

            # Create adjacent links between national rail stations
            rail_links_count = 0
            for station in rail_stations:
                for adj in station.get("adjacent_stations", []):
                    to_id = adj.get("station_id")
                    if to_id:
                        _merge_rail_link(session, station["station_id"], to_id, adj.get("line", "UNKNOWN"), adj.get("travel_time_min", 1))
                        rail_links_count += 1
            print(f"  Created {rail_links_count} national rail links")

            # Create interchange relationships between metro and national rail
            # Interchange info is provided by related fields in metro_stations.json
            interchange_pairs = _extract_interchange_pairs_from_data(metro_stations, rail_stations)
            interchange_count = 0
            for metro_id, rail_id in interchange_pairs:
                if _merge_interchange(session, metro_id, rail_id):
                    interchange_count += 1
            print(f"  Created {interchange_count} metro-national rail interchange pairs")
            
    finally:
        # Use try-finally to ensure the connection is always closed
        driver.close()

    print("\nNeo4j graph seeded successfully.")
    print("   Open http://localhost:7475 to explore the graph.")


if __name__ == "__main__":
    print("Connecting to Neo4j...")
    seed()