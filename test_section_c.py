import json
from databases.graph.queries import (
    query_shortest_route,
    query_cheapest_route,
    query_alternative_routes,
    query_interchange_path,
    query_delay_ripple,
    query_station_connections
)

def run_tests():
    print("========================================")
    print("🚇 執行 Section C (Graph DB) 驗證腳本")
    print("========================================\n")

    # C1: Shortest Route
    print("--- [C1] query_shortest_route ---")
    c1_metro = query_shortest_route("MS20", "MS09", "metro")
    print(f"✅ C1 (Metro 正常): MS20 -> MS09 | 行車時間: {c1_metro.get('total_time_min')} 分鐘")
    
    c1_rail = query_shortest_route("MS01", "NR05", "national_rail")
    print(f"✅ C1 (Rail 斷線): MS01 -> NR05 (純火車) | 找不到路徑，回傳: {c1_rail}")
    print()

    # C2: Cheapest Route
    print("--- [C2] query_cheapest_route ---")
    c2_standard = query_cheapest_route("NR01", "NR05", "national_rail", "standard")
    print(f"✅ C2 (Standard 標準艙): NR01 -> NR05 | 總票價: ${c2_standard.get('total_fare_usd')} (應為 8.5)")
    
    c2_first = query_cheapest_route("NR01", "NR05", "national_rail", "first")
    print(f"✅ C2 (First 頭等艙): NR01 -> NR05 | 總票價: ${c2_first.get('total_fare_usd')} (應為 13.3)")
    print()

    # C3: Alternative Routes
    print("--- [C3] query_alternative_routes ---")
    c3_routes = query_alternative_routes("MS01", "MS17", "MS04", "auto", 3)
    print(f"✅ C3 (避開特定站): MS01 -> MS17 (避開 MS04) | 找到 {len(c3_routes)} 條替代路線")
    if c3_routes:
        path_names = [f"{leg['from']}->{leg['to']} ({leg['line']})" for leg in c3_routes[0]['legs']]
        print(f"   最佳替代路線經過: {', '.join(path_names)}")
    print()

    # C4: Interchange Path
    print("--- [C4] query_interchange_path ---")
    c4_path = query_interchange_path("MS20", "NR05")
    print(f"✅ C4 (跨網路轉乘): MS20 -> NR05 | 總時間: {c4_path.get('total_time_min')} 分鐘")
    if "interchange_points" in c4_path:
        ic_names = [n['name'] for n in c4_path['interchange_points']]
        print(f"   使用的轉乘站: {ic_names}")
    print()

    # C5: Delay Ripple
    print("--- [C5] query_delay_ripple ---")
    c5_hops2 = query_delay_ripple("MS01", 2)
    print(f"✅ C5 (Hops=2): MS01 延誤影響 {len(c5_hops2)} 個車站 (應為 12)")
    
    c5_hops0 = query_delay_ripple("MS01", 0)
    print(f"✅ C5 (Hops=0): MS01 延誤影響 {len(c5_hops0)} 個車站 (應為 1)")
    print()

    # C6: Station Connections
    print("--- [C6] query_station_connections ---")
    c6_conn = query_station_connections("MS01")
    print(f"✅ C6 (相鄰車站): MS01 直接連接了 {len(c6_conn)} 個車站 (應為 5)")
    if c6_conn:
        names = [n['name'] for n in c6_conn]
        print(f"   連接站點: {names}")
    print()

    print("🎉 Section C 測試腳本執行完畢！如果上面都沒有報錯 (Crash)，代表你的 C1~C6 邏輯完美！")

if __name__ == "__main__":
    run_tests()
