# TransitFlow System Mock Data & Policy Reference

This reference document organizes and structures the mock data and policy specifications found in `train-mock-data/` (excluding `readme.md`) to assist in reviewing and planning upcoming features, such as adding cash payment options to the Metro system.

---
> [!TIP] 
> **可新增政策**
> - 失物招領
> - 禁帶物品 (已初次擴充：刀具、易燃物、化學品)
> - 禁菸 (已初次擴充：大眾運輸法定場所禁菸)
> - 罰款政策
> - 詳情參照英國鐵路規定 National Rail & London Underground
> - 高齡愛心票
---

## 🗺️ System Overview & File Structure

The TransitFlow dual-network transit system comprises two networks:
1. **City Metro** (Stations `MS01` to `MS20`, lines `M1` to `M4`)
2. **National Rail** (Stations `NR01` to `NR10`, lines `NR1` to `NR2`)

There are **three interchange stations** connecting the two networks:
- **Central**: `MS01` / `NR01`
- **Old Town**: `MS07` / `NR03`
- **Ferndale**: `MS15` / `NR07`

The mock files are categorized as follows:

| Category | File Name | Description |
| :--- | :--- | :--- |
| **Business Policies & Rules** | booking_rules.json | Ticketing rules, seat selections, child/group discounts, and accepted payment methods. |
| | refund_policy.json | Cancellation policies (RF001–RF004) and delay compensation guidelines (RF005). |
| | ticket_types.json | Specifications for Single tickets, Return tickets, and Metro Day Passes. |
| | travel_policies.json | Conduct, luggage limits, pet regulations, and bicycle policies. |
| **Network & Timetables** | metro_stations.json | Metro station indices, line mappings, and travel times. |
| | national_rail_stations.json | National Rail station indices, line mappings, and travel times. |
| | metro_schedules.json | Metro train lines, directions, stop orders, and stop-based pricing rates. |
| | national_rail_schedules.json | Rail train service schedules, including Express vs Normal service. |
| | national_rail_seat_layouts.json | Seat layouts for Rail coaches (First class vs Standard class). |
| **Transactional Records** | registered_users.json | Mock accounts for logged-in user profiling. |
| | bookings.json | Existing National Rail booking history. |
| | metro_travel_history.json | Metro tap-in / travel records, including Day Pass activations. |
| | payments.json | Transactional payments tied to bookings and metro trips. |
| | feedback.json | Customer ratings and reviews of completed trips. |
---

## 📜 Business Policies & Rules Deep-Dive

### 1. Booking Rules (`booking_rules.json`)
Defines the parameters under which bookings and payments occur for both networks:

* **National Rail**:
  * **Advance Booking**: Up to 90 days in advance; down to 10 minutes before departure.
  * **Seat Selection**: Included in First Class ($0.00 fee); optional in Standard Class ($0.50 fee).
  * **Ticket Changes**: Allowed for $1.00 fee at least 24 hours before departure. Only date, service, and seat can be changed. Route, fare class, and ticket type cannot be changed. No changes permitted for Express services within 24 hours.
  * **Child Fares**: Under 5 travels free (no ticket). Age 5–15 gets a 50% discount. 16+ pays full fare.
  * **Group Fares**: Groups of 10+ on standard class single/return get a 10% discount.
  * **Payment & Confirmation**: Credit card, debit card, e-wallet. Immediate email and in-app digital ticket (QR code).
* **Metro**:
  * **Advance Booking**: **None**. Single tickets and Day Passes must be purchased on the day of travel only. Day Passes valid from 00:00 to 23:59 on the day of purchase.
  * **Seat Selection**: **None**.
  * **Ticket Changes**: **Not allowed**. Tickets must be refunded and repurchased.
  * **Child Fares**: Under 5 travels free. Age 5–15 gets 50% discount (rounded to nearest $0.10) for single tickets, and Day Passes are available for $2.50. 16+ pays full fare.
  * **Group Fares**: **None**.
  * **Payment & Confirmation**: Credit card, debit card, e-wallet. Immediate in-app confirmation and QR code.

> [!WARNING]
> **Impact of Adding Cash Payment to Metro:**
> Currently, the booking rules show:
> `accepted_methods: ["credit_card", "debit_card", "ewallet"]`
> If cash is supported, we must add `"cash"` to `accepted_methods` in `booking_rules.json` under `metro`, and update `where_to_buy` to reflect ticket counters/cash-enabled kiosks (e.g. "Tickets can be purchased via the app, station ticket machines, or staffed ticket counters").

---

### 2. Refund Policies (`refund_policy.json`)
Refund rules dictate how cancellations are processed:

* **RF001 (National Rail – Normal Service)**:
  * $\ge 48$ hours before departure: **100% refund**, $0 admin fee.
  * $24$ to $48$ hours: **75% refund**, $0.50 admin fee.
  * $2$ to $24$ hours: **50% refund**, $0.50 admin fee.
  * $< 2$ hours or after departure: **0% refund**.
* **RF002 (National Rail – Express Service)**:
  * $\ge 48$ hours before departure: **100% refund**, $1.00 admin fee.
  * $24$ to $48$ hours: **50% refund**, $1.00 admin fee.
  * $< 24$ hours: **0% refund**.
* **RF003 (Metro – Single Ticket)**:
  * Refundable for **100% refund** before tapping in at the origin station (status 'confirmed').
  * **0% refund** once tapped in (status 'completed' / 'travelled_at' is set).
* **RF004 (Metro – Day Pass)**:
  * Refundable for **100% refund** before the first tap-in on the travel date.
  * **0% refund** once activated.
* **RF005 (Delay Compensation)**:
  * 30–59 mins delay: **50% refund** of the leg's fare.
  * 60–119 mins delay: **100% refund** of the leg's fare.
  * $\ge 120$ mins delay: **100% refund** + alternative transport costs up to $10.00.
  * Exclusions apply to third-party events (weather, force majeure).

> [!IMPORTANT]
> **Impact of Cash Payments on Refund Policy:**
> For credit card, debit card, or e-wallet transactions, refunds are processed electronically. For cash payments made at a staffed counter or terminal:
> 1. Refunds cannot be pushed back to a bank card. They must either be refunded **in cash at a staffed ticket counter** or as **in-app credit/voucher**.
> 2. RF003/RF004 should mention cash refund guidelines (e.g. "Cash purchases must be refunded at staffed ticket counters within 24 hours of travel date, prior to tap-in").

---

### 3. Ticket Types (`ticket_types.json`)
Defines the technical properties of ticket categories:

* **Single Ticket**:
  * Available on: Metro, National Rail.
  * Metro: Stops-based pricing ($0.80 base + $0.30 per stop). Validity: travel date only (expires at midnight). No advance purchase. Refundable under RF003.
  * National Rail: Stops-based with fare class (standard/first) & service type (normal/express). Seat assigned. Validity: selected service only. Refundable under RF001/RF002.
* **Return Ticket**:
  * Available on: National Rail only.
  * Comprises two legs priced and treated independently. Validity: Outbound on selected service; Return on any service on same route within 30 days.
* **Metro Day Pass**:
  * Flat rate: **$5.00** (Standard) / **$2.50** (Child discount).
  * Unlimited journeys on all metro lines (M1-M4) for one calendar day. Refundable under RF004 if completely unused.

---

### 4. Travel Policies (`travel_policies.json`)
Specifies conditions of carriage (luggage, pets, bikes, conduct, prohibited items, and smoking policy). Key elements:


* **Metro**:
  * **Bicycles**: Foldable bikes are permitted *outside* peak hours (Peak: 07:00-09:30 and 17:00-20:00 weekdays). Standard non-foldable bikes are **prohibited at all times**. E-scooters are prohibited due to battery fire safety.
  * **Luggage**: Max 2 items per passenger, max size 70x50x30 cm.
  * **Pets**: Permitted only in enclosed carriers (max 50x35x25 cm). Assistance dogs exempt.
  * **Food/Drink**: Sealed drinks permitted. Hot/smelling food and alcohol are strictly prohibited. Priority seats must be vacated for seniors/pregnant/disabled/children.
  * **Prohibited Items**: Weapons, foldable/non-foldable standard bikes/e-scooters (as per restrictions), smelly items, and key restricted categories:
  * *Knives and sharp items*: Various knives, scissors, utility knives (exposed blades due to improper packaging are violations).
  * *Flammable and explosive materials*: Gasoline, paint, turpentine/rosin water, pressurized gases, explosives, etc.   * *Chemical and hazardous items*: Corrosive liquids, highly toxic chemicals, etc.
  * **Smoking Policy**: Strictly prohibited by law. Under statutory rules, all public transport vehicles and areas including indoor waiting rooms, platforms, and carriage interiors are strictly non-smoking.

* **National Rail**:
  * **Bicycles**: Foldable permitted free. Standard bikes permitted in designated bays (max 2 per train) with a **$2.00 fee** paid at the platform bay gate. Prohibited during peak hours (07:00-09:30, 16:30-19:00).
  * **Pets**: Dogs permitted on a lead in standard class coaches only (no seat occupancy, $0 fee).
  * **Quiet Zones**: Designated standard carriages where calls and loud noises are prohibited.
  * **Prohibited Items**: Same key restricted categories as Metro (Knives and sharp items, Flammable and explosive materials, Chemical and hazardous items) as well as weapons, e-scooters, and smelly items.
  * **Smoking Policy**: Strictly prohibited by law. All train carriages and station platforms, including indoor waiting rooms, are statutory non-smoking areas.
---

## 📈 Network & Timetable Master Data

### 1. Stations & Layouts
* **Metro Stations (`metro_stations.json`)**: List of 20 stations (`MS01` to `MS20`). Each record lists lines served, interchange attributes, and adjacent stations with travel times.
* **Rail Stations (`national_rail_stations.json`)**: List of 10 stations (`NR01` to `NR10`).
* **Rail Seat Layouts (`national_rail_seat_layouts.json`)**: Schedules map to a seat layout (e.g. `SL01` for `NR_SCH01`). Coach A is First Class (seats A01–A06), Coach B is Standard Class (seats B01–B12).

### 2. Timetables & Schedules
* **Metro Schedules (`metro_schedules.json`)**:
  * `MS_SCH01`/`MS_SCH02` (M1 line northbound/southbound)
  * `MS_SCH03`/`MS_SCH04` (M2 line eastbound/westbound)
  * `MS_SCH05`/`MS_SCH06` (M3 line northbound/southbound)
  * `MS_SCH07`/`MS_SCH08` (M4 line eastbound/westbound)
  * Every schedule specifies a base fare of **$0.80** and per stop rate of **$0.30**.
* **National Rail Schedules (`national_rail_schedules.json`)**:
  * `NR_SCH01`/`NR_SCH02` (NR1 line northbound/southbound - Normal service)
    * Fare standard: $2.50 base, $1.50 per stop. First: $4.00 base, $2.50 per stop.
  * `NR_SCH03`/`NR_SCH04` (NR2 line eastbound/westbound - Normal service)
  * `NR_SCH05`/`NR_SCH06` (NR1 line - Express service: skips NR02, NR04)
    * Fare standard: $6.60 base, $1.80 per stop. First: $10.80 base, $3.00 per stop.
  * `NR_SCH07`/`NR_SCH08` (NR2 line - Express service: skips NR06, NR08)

---

## 💾 Transactional & User Mock Data

### 1. Registered Users (`registered_users.json`)
Contains 20 mock users (`RU01` to `RU20`). Includes plaintext passwords, secret questions, registered dates, and active flags.
**Example Schema:**
```json
{
  "user_id": "RU01",
  "full_name": "Alice Tan",
  "email": "alice.tan@email.com",
  "password": "alice1990",
  "phone": "07912340101",
  "date_of_birth": "1990-03-14",
  "secret_question": "What was the name of your first pet?",
  "secret_answer": "Biscuit",
  "registered_at": "2023-01-10T09:00:00Z",
  "is_active": true
}
```

### 2. National Rail Bookings (`bookings.json`)
Records representing reservations made by registered users on National Rail.
**Example Schema:**
```json
{
  "booking_id": "BK001",
  "user_id": "RU01",
  "schedule_id": "NR_SCH01",
  "origin_station_id": "NR01",
  "destination_station_id": "NR05",
  "travel_date": "2026-04-02",
  "departure_time": "07:00",
  "ticket_type": "single",
  "fare_class": "standard",
  "coach": "B",
  "seat_id": "B05",
  "stops_travelled": 4,
  "amount_usd": 8.50,
  "status": "completed",
  "booked_at": "2026-04-01T10:15:00Z",
  "travelled_at": "2026-04-02T07:00:00Z"
}
```

### 3. Metro Travel History (`metro_travel_history.json`)
Represents actual trips taken on the Metro.
* **Single Tickets**: Record has its own `purchased_at` timestamp and fare `amount_usd` (e.g. $1.40, $2.00).
* **Day Passes**: 
  * The *first* tap of the day has `ticket_type: "day_pass"`, `day_pass_ref: null`, and `amount_usd: 5.00` (original purchase).
  * Subsequent taps on that day have `day_pass_ref: "MTXXX"` (pointing to the first trip's ID) and `amount_usd: 0.00`.

**Example Schemas:**
```json
// Single Ticket Metro Journey
{
  "trip_id": "MT001",
  "user_id": "RU02",
  "schedule_id": "MS_SCH01",
  "origin_station_id": "MS20",
  "destination_station_id": "MS01",
  "travel_date": "2026-04-03",
  "ticket_type": "single",
  "stops_travelled": 2,
  "amount_usd": 1.40,
  "status": "completed",
  "purchased_at": "2026-04-03T05:50:00Z",
  "travelled_at": "2026-04-03T06:05:00Z"
}

// Day Pass Second Activation (Free Tap)
{
  "trip_id": "MT021",
  "user_id": "RU04",
  "schedule_id": "MS_SCH04",
  "origin_station_id": "MS08",
  "destination_station_id": "MS14",
  "travel_date": "2026-04-06",
  "ticket_type": "day_pass",
  "day_pass_ref": "MT002",
  "stops_travelled": null,
  "amount_usd": 0.00,
  "status": "completed",
  "purchased_at": null,
  "travelled_at": "2026-04-06T12:35:00Z"
}
```

### 4. Payments (`payments.json`)
Payments mapping to a National Rail booking or Metro trip. Statuses include `"paid"` and `"refunded"`.
**Example Schema:**
```json
{
  "payment_id": "PM001",
  "booking_id": "BK001", // Or MT001 for Metro
  "amount_usd": 8.50,
  "method": "credit_card",
  "status": "paid",
  "paid_at": "2026-04-01T10:16:00Z"
}

> [!TIP]
> **Database Cash Integration Considerations:**
> When integrating cash payments, the `payments` table and `payments.json` data will need to support `"cash"` as a valid `"method"`. 
> Unlike bank card payments, cash transactions cannot fail due to network gateways, but their status may require a state representation like `"paid_at_counter"`.
```
---

## 🛠️ Cash Payment Extension Checklist

To implement cash payments at the counter/terminal on the Metro network, the following files will require modifications:

### 1. Policy & Rules (`train-mock-data/` JSON files)
- [ ] **`booking_rules.json`**:
  - Add `"cash"` to `metro.payment.accepted_methods`.
  - Update `metro.booking_confirmation.method` to include cash receipts ("In-app confirmation or physical printed receipt issued immediately upon cash purchase").
  - Update `metro.advance_booking.where_to_buy` to mention staffed ticket counters ("Tickets can be purchased via the app, station ticket machines, or staffed ticket counters").
- [ ] **`refund_policy.json`**:
  - Add a note in `RF003` (Metro Single Ticket) and `RF004` (Metro Day Pass) describing how cash payments are refunded:
    > "Cash payments are non-refundable electronically. To receive a refund, passengers must present their unused QR ticket or printed receipt at a staffed ticket counter on the date of purchase, prior to any tap-in."

### 2. Transactional Schemas (`databases/` SQL files & codebase queries)
- [ ] **PostgreSQL Schema (`schema.sql`)**:
  - Ensure the payment method column/enum supports `'cash'`.
  - Check if booking or transaction status needs a physical-ticket counter flag or kiosk ID.
- [ ] **Seeding Scripts (`seed_postgres.py`)**:
  - Insert mock payment entries representing cash purchases at physical counters (e.g. using `method: "cash"`).
- [ ] **Vector Seeder (`seed_vectors.py`)**:
  - After modifying policy files, rerun `python skeleton/seed_vectors.py` to refresh the vector embeddings in the `policy_documents` database so TransitFlow's LLM assistant is aware of the new cash payment rules and counter buying options.


---

# 中文翻譯

# TransitFlow 系統模擬數據與政策參考

本參考文件整理並建構了位於 `train-mock-data/`（不含 `readme.md`）中的模擬數據與政策規範，以協助審查和規劃即將推出的功能，例如在捷運（Metro）系統中新增現金支付選項。

---
> [!TIP]
> **可新增政策**
> - 失物招領
> - 禁帶物品 (已初次擴充：刀具、易燃物、化學品)
> - 禁菸 (已初次擴充：大眾運輸法定場所禁菸)
> - 罰款政策
> - 詳情參照英國鐵路規定 National Rail & London Underground
> - 高齡愛心票
---

## 🗺️ 系統概述與檔案結構

TransitFlow 雙網絡大眾運輸系統包含兩個網絡：
1. **城市捷運 (City Metro)**（車站 `MS01` 至 `MS20`，路線 `M1` 至 `M4`）
2. **國家鐵路 (National Rail)**（車站 `NR01` 至 `NR10`，路線 `NR1` 至 `NR2`）

共有 **三個轉乘站** 連接這兩個網絡：
- **Central**：`MS01` / `NR01`
- **Old Town**：`MS07` / `NR03`
- **Ferndale**：`MS15` / `NR07`

模擬檔案分類如下：

| 分類 | 檔案名稱 | 說明 |
| :--- | :--- | :--- |
| **業務政策與規則** | booking_rules.json | 票務規則、座位選擇、兒童/團體折扣以及接受的支付方式。 |
| | refund_policy.json | 退票政策（RF001–RF004）和延誤補償指南（RF005）。 |
| | ticket_types.json | 單程票、來回票和捷運一日票的規範。 |
| | travel_policies.json | 行為守則、行李限制、寵物規定和自行車政策。 |
| **路網與時刻表** | metro_stations.json | 捷運車站索引、路線對照和行車時間。 |
| | national_rail_stations.json | 國家鐵路車站索引、路線對照和行車時間。 |
| | metro_schedules.json | 捷運列車路線、行車方向、停靠順序和按站計費費率。 |
| | national_rail_schedules.json | 鐵路列車班次时刻表，包含快速與普通服務。 |
| | national_rail_seat_layouts.json | 鐵路車廂座位配置（頭等艙 vs 標準艙）。 |
| **交易紀錄** | registered_users.json | 已註冊用戶設定檔的模擬帳戶。 |
| | bookings.json | 現有的國家鐵路訂票歷史紀錄。 |
| | metro_travel_history.json | 捷運刷卡進站/乘車紀錄，包含一日票啟用紀錄。 |
| | payments.json | 與訂票和捷運乘車關聯的交易支付紀錄。 |
| | feedback.json | 客戶對已完成行程的評分與評論。 |

---

## 📜 業務政策與規則深入解析

### 1. 訂票規則 (`booking_rules.json`)
定義兩個網絡中進行預訂與付款的參數：

* **國家鐵路 (National Rail)**：
  * **預付款預訂**：最多可提前 90 天；最晚至出發前 10 分鐘。
  * **座位選擇**：頭等艙已包含（$0.00 費用）；標準艙為選購（$0.50 費用）。
  * **車票變更**：允許在出發前至少 24 小時變更，手續費為 $1.00。僅限變更日期、班次和座位。不可變更路線、票價等級和車票類型。快速列車（Express services）在出發前 24 小時內不允許任何變更。
  * **兒童票價**：5 歲以下免費乘車（無需購票）。5–15 歲享有 50% 折扣。16 歲及以上支付全額票價。
  * **團體票價**：標準艙單程/來回票 10 人（含）以上團體享有 10% 折扣。
  * **付款與確認**：信用卡、金融卡、電子錢包。立即發送電子郵件並提供 App 內數位車票（QR Code）。
* **城市捷運 (Metro)**：
  * **預付款預訂**：**無**。單程票和一日票僅限乘車當天購買。一日票有效時間為購買當天 00:00 至 23:59。
  * **座位選擇**：**無**。
  * **車票變更**：**不允許**。車票必須退票後重新購買。
  * **兒童票價**：5 歲以下免費乘車。5–15 歲單程票享有 50% 折扣（四捨五入至最近的 $0.10），一日票售價為 $2.50。16 歲及以上支付全額票價。
  * **團體票價**：**無**。
  * **付款與確認**：信用卡、金融卡、電子錢包。立即於 App 內確認並提供 QR Code。

> [!WARNING]
> **在捷運系統新增現金支付的影響：**
> 目前訂票規則顯示：
> `accepted_methods: ["credit_card", "debit_card", "ewallet"]`
> 若要支援現金，我們必須在 `booking_rules.json` 中的 `metro` 下將 `"cash"` 加入至 `accepted_methods`，並更新 `where_to_buy` 以反映售票窗口/支援現金的售票機（例如：「車票可透過 App、車站售票機或人工售票窗口購買」）。

---

### 2. 退票政策 (`refund_policy.json`)
退票規則規定了如何處理取消預訂：

* **RF001（國家鐵路 – 普通服務）**：
  * 出發前 $\ge 48$ 小時：**100% 退款**，$0 行政費。
  * 出發前 $24$ 至 $48$ 小時：**75% 退款**，$0.50 行政費。
  * 出發前 $2$ 至 $24$ 小時：**50% 退款**，$0.50 行政費。
  * 出發前 $< 2$ 小時或出發後：**0% 退款**。
* **RF002（國家鐵路 – 快速服務）**：
  * 出發前 $\ge 48$ 小時：**100% 退款**，$1.00 行政費。
  * 出發前 $24$ 至 $48$ 小時：**50% 退款**，$1.00 行政費.
  * 出發前 $< 24$ 小時：**0% 退款**。
* **RF003（捷運 – 單程票）**：
  * 在起點站刷卡進站前（狀態為「已確認 confirmed」）可退還 **100% 退款**。
  * 一旦刷卡進站（狀態為「已完成 completed」/ 已設定「乘車時間 travelled_at」）則 **0% 退款**。
* **RF004（捷運 – 一日票）**：
  * 在乘車當天首次刷卡進站前可退還 **100% 退款**。
  * 一旦啟用則 **0% 退款**。
* **RF005（延誤補償）**：
  * 延誤 30–59 分鐘：退還該單程票價的 **50%**。
  * 延誤 60–119 分鐘：退還該單程票價的 **100%**。
  * 延誤 $\ge 120$ 分鐘：**100% 退款** + 補償最高 $10.00 的替代交通費用。
  * 第三方事件（天氣、不可抗力）適用排除條款。

> [!IMPORTANT]
> **現金支付對退票政策的影響：**
> 對於信用卡、金融卡或電子錢包交易，退款會以電子方式處理。對於在人工窗口或終端機進行的現金支付：
> 1. 退款無法退回至銀行卡。必須在**人工售票窗口以現金退款**，或作為 **App 內點數/抵用券**退還。
> 2. RF003/RF004 應提及現金退款指引（例如：「現金購買的車票必須在乘車日期 24 小時內且刷卡進站前，於人工售票窗口辦理退款」）。

---

### 3. 車票類型 (`ticket_types.json`)
定義車票分類的技術屬性：

* **單程票 (Single Ticket)**：
  * 適用於：捷運、國家鐵路。
  * 捷運：按站計費（$0.80 基本費 + 每站 $0.30）。有效期：僅限乘車當天（午夜失效）。不提供提前購買。適用 RF003 退票規定。
  * 國家鐵路：按站計費，並區分艙等（標準艙/頭等艙）與服務類型（普通/快速）。已分配座位。有效期：僅限所選班次。適用 RF001/RF002 退票規定。
* **來回票 (Return Ticket)**：
  * 適用於：僅限國家鐵路。
  * 包含去程與回程兩段，獨立定價與處理。有效期：去程僅限所選班次；回程可在 30 天內乘坐同一路線的任何班次。
* **捷運一日票 (Metro Day Pass)**：
  * 單一票價：**$5.00**（標準）/ **$2.50**（兒童折扣）。
  * 在一個日曆天內無限次搭乘所有捷運路線（M1-M4）。若完全未使用，適用 RF004 退票規定。

---

### 4. 乘車政策 (`travel_policies.json`)
規定運送條件（行李、寵物、自行車、行為守則、禁帶物品、禁菸政策）。關鍵要素：

* **城市捷運 (Metro)**：
  * **自行車**：折疊式自行車允許在*非尖峰時段*攜帶（尖峰時段：工作日 07:00-09:30 與 17:00-20:00）。標準非折疊式自行車**任何時候均禁止攜帶**。由於電池起火安全疑慮，禁止攜帶電動滑板車。
  * **行李**：每位乘客最多 2 件，最大尺寸為 70x50x30 公分。
  * **寵物**：僅限裝於封閉式寵物箱籠中（最大 50x35x25 公分）。導盲犬/服務犬除外。
  * **餐飲**：允許攜帶密封飲料。嚴禁攜帶熱食/有異味的食物以及酒精飲料。博愛座必須讓位給年長者/孕婦/身心障礙者/孩童。
  * **禁帶物品**：武器、隨身折疊/標準自行車及滑板車（依限制）、異味物品，以及新增之三大管制類別：
    * *刀具與尖銳物品*：如各類刀具、剪刀、美工刀（未妥善包裝致刀刃外露者屬違規）。
    * *易燃物與易爆物*：汽油、油漆、松香水、高壓氣體、炸藥等。
    * *化學與有害物品*：具腐蝕性液體、具強烈毒性化學物質等。
  * **禁菸政策**：依據法律規定，所有大眾運輸工具皆全面禁止吸菸。從室內候車室、月台到車廂內部，均屬於法定禁菸場所。
* **國家鐵路 (National Rail)**：
  * **自行車**：折疊式自行車可免費攜帶。標準自行車允許置於指定車廂（每列列車最多 2 輛），並須在月台閘門支付 **$2.00 費用**。尖峰時段（07:00-09:30，16:30-19:00）禁止攜帶。
  * **寵物**：僅限標準艙車廂允許牽繩犬隻（不得佔用座位，$0 費用）。
  * **靜音區**：指定的標準艙車廂，禁止通話與大聲喧嘩。
  * **禁帶物品**：禁帶項目與城市捷運相同（包含刀具與尖銳物品、易燃易爆物、化學有害物品、武器、電動滑板車及異味物品）。
  * **禁菸政策**：全面禁菸。所有火車車廂、車站月台及室內候車室均屬於法定禁菸場所。

---

## 🛠️ 現金支付擴充清單

要在捷運網絡的售票處/終端機實施現金支付，需要修改以下檔案：

### 1. 政策與規則（`train-mock-data/` JSON 檔案）
- [ ] **`booking_rules.json`**：
  - 將 `"cash"` 新增至 `metro.payment.accepted_methods`。
  - 更新 `metro.booking_confirmation.method` 以包含現金收據（「現金購買後立即提供 App 內確認或印製實體紙本收據」）。
  - 更新 `metro.advance_booking.where_to_buy` 以提及人工售票窗口（「車票可透過 App、車站售票機或人工售票窗口購買」）。
- [ ] **`refund_policy.json`**：
  - 在 `RF003`（捷運單程票）與 `RF004`（捷運一日票）中新增關於現金支付如何退款的說明：
    > 「現金付款無法以電子方式退款。若要辦理退款，乘客必須在購買當天且刷卡進站前，持未使用的 QR 碼車票或列印的紙本收據至人工售票窗口辦理。」

### 2. 交易結構（`databases/` SQL 檔案與程式碼查詢）
- [ ] **PostgreSQL 結構 (`schema.sql`)**：
  - 確保支付方式欄位/列舉支援 `'cash'`。
  - 檢查訂票或交易狀態是否需要實體票務窗口標記或售票機 ID。
- [ ] **資料植入腳本 (`seed_postgres.py`)**：
  - 插入代表在實體窗口進行現金購買的模擬支付項目（例如使用 `method: "cash"`）。
- [ ] **向量植入器 (`seed_vectors.py`)**：
  - 修改政策檔案後，重新執行 `python skeleton/seed_vectors.py` 以更新 `policy_documents` 資料庫中的向量嵌入，使 TransitFlow 的 LLM 助手能得知新的現金支付規則與窗口購買選項。

