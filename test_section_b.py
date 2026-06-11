import sys
import traceback

# 將專案根目錄加入 sys.path，以便能正確 import
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from databases.relational.queries import (
    query_national_rail_availability,
    query_metro_schedules,
    query_national_rail_fare,
    query_metro_fare,
    query_available_seats
)

def run_test(test_name, func, *args):
    print(f"\n[{test_name}]")
    print(f"呼叫: {func.__name__}{args}")
    try:
        result = func(*args)
        print("回傳結果:")
        print(result)
        return result
    except NotImplementedError as e:
        print(f"❌ 尚未實作: {e}")
    except Exception as e:
        print("❌ 執行發生錯誤:")
        traceback.print_exc()

def main():
    print("========== Section B 測試腳本 ==========")
    
    # B1: query_national_rail_availability
    run_test("B1-1 (有車情境)", query_national_rail_availability, "NR01", "NR05", "2025-06-01")
    run_test("B1-2 (無車情境/逆向)", query_national_rail_availability, "NR05", "NR10", "2025-06-01")

    # B2: query_metro_schedules
    run_test("B2-1 (有共同地鐵線 - M1線)", query_metro_schedules, "MS20", "MS17")
    run_test("B2-2 (無共同地鐵線 - 需轉乘)", query_metro_schedules, "MS20", "MS09")

    # B3: query_national_rail_fare
    run_test("B3-1 (經濟艙 Standard)", query_national_rail_fare, "NR_SCH01", "standard", 4)
    run_test("B3-2 (頭等艙 First)", query_national_rail_fare, "NR_SCH01", "first", 4)

    # B4: query_metro_fare
    run_test("B4 (地鐵費用計算)", query_metro_fare, "MS_SCH01", 6)

    # B5: query_available_seats
    run_test("B5 (查詢頭等艙空位)", query_available_seats, "NR_SCH01", "2025-06-01", "first")

    print("\n========== 測試結束 ==========")
    print("請核對以上輸出的 '回傳結果' 是否符合評分標準！")

if __name__ == "__main__":
    main()
