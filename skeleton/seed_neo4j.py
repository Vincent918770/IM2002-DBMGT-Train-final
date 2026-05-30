"""
TransitFlow — Neo4j Seeder
Run once after starting Docker:
    python skeleton/seed_neo4j.py

Loads station and network data from train-mock-data/:
  - metro_stations.json         — city metro stations and adjacencies
  - national_rail_stations.json — national rail stations and adjacencies
"""

import json
import os
import sys

sys.path.insert(0, ".")

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train-mock-data")
)


def _load(filename):
    with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def seed():
    # 1. 讀取 mock 資料
    metro_stations = _load("metro_stations.json")
    rail_stations  = _load("national_rail_stations.json")

    # 2. 建立資料庫連線驅動（自動帶入 config 的連線資訊）
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        # 使用 execute_write 封裝交易邏輯，確保寫入安全性
        def _execute_seeding(tx):
            print("正在清空舊資料庫...")
            tx.run("MATCH (n) DETACH DELETE n")

            # ---- (A) 建立捷運站節點 ----
            print("正在建立捷運站節點...")
            tx.run("""
                UNWIND $data AS m
                MERGE (s:MetroStation {id: m.station_id})
                SET s.name = m.name, s.lines = m.lines
            """, data=metro_stations)

            # ---- (B) 建立國鐵站節點 ----
            print("正在建立國鐵站節點...")
            tx.run("""
                UNWIND $data AS r
                MERGE (s:RailStation {id: r.station_id})
                SET s.name = r.name, s.lines = r.lines
            """, data=rail_stations)

            # ---- (C) 建立捷運路線連線 (LINKED_TO) ----
            print("正在建立捷運路線軌道連線...")
            tx.run("""
                UNWIND $data AS m
                MATCH (f:MetroStation {id: m.station_id})
                UNWIND m.adjacent_stations AS adj
                MATCH (t:MetroStation {id: adj.station_id})
                WHERE adj.line IN m.lines
                MERGE (f)-[rel_m:LINKED_TO {line: adj.line}]->(t)
                SET rel_m.travel_time_min = adj.travel_time_min
            """, data=metro_stations)

            # ---- (D) 建立國鐵路線連線 (LINKED_TO) ----
            print("正在建立國鐵路線軌道連線...")
            tx.run("""
                UNWIND $data AS r
                MATCH (f:RailStation {id: r.station_id})
                UNWIND r.adjacent_stations AS adj
                MATCH (t:RailStation {id: adj.station_id})
                WHERE adj.line IN r.lines
                MERGE (f)-[rel_r:LINKED_TO {line: adj.line}]->(t)
                SET rel_r.travel_time_min = adj.travel_time_min
            """, data=rail_stations)

            # ---- (E) 動態建立跨系統轉乘關係 (TRANSFER_TO) ----
            print("正在動態建立捷運與國鐵間的轉乘通道...")
            tx.run("""
                UNWIND $data AS m
                WITH m WHERE m.is_interchange_national_rail = true AND m.interchange_national_rail_station_id IS NOT NULL
                MATCH (metro:MetroStation {id: m.station_id})
                MATCH (rail:RailStation {id: m.interchange_national_rail_station_id})
                MERGE (metro)-[:TRANSFER_TO]->(rail)
                MERGE (rail)-[:TRANSFER_TO]->(metro)
            """, data=metro_stations)

        # 執行寫入交易
        session.execute_write(_execute_seeding)

    driver.close()
    print("\nNeo4j graph seeded successfully.")
    print("   Open http://localhost:7475 to explore the graph.")


if __name__ == "__main__":
    print("Connecting to Neo4j...")
    seed()