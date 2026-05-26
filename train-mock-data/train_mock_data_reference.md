# TransitFlow System Mock Data & Policy Reference

This reference document organizes and structures the mock data and policy specifications found in `train-mock-data/` (excluding `readme.md`) to assist in reviewing and planning upcoming features, such as adding cash payment options to the Metro system.

---
> [!TIP] 
**可新增政策**
> - 失物招領
> - 禁帶物品
> - 禁菸
> - 罰款政策
> - 詳情參照英國鐵路規定 National Rail & London Underground
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
| **Business Policies & Rules** | [booking_rules.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/booking_rules.json) | Ticketing rules, seat selections, child/group discounts, and accepted payment methods. |
| | [refund_policy.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/refund_policy.json) | Cancellation policies (RF001–RF004) and delay compensation guidelines (RF005). |
| | [ticket_types.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/ticket_types.json) | Specifications for Single tickets, Return tickets, and Metro Day Passes. |
| | [travel_policies.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/travel_policies.json) | Conduct, luggage limits, pet regulations, and bicycle policies. |
| **Network & Timetables** | [metro_stations.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/metro_stations.json) | Metro station indices, line mappings, and travel times. |
| | [national_rail_stations.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/national_rail_stations.json) | National Rail station indices, line mappings, and travel times. |
| | [metro_schedules.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/metro_schedules.json) | Metro train lines, directions, stop orders, and stop-based pricing rates. |
| | [national_rail_schedules.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/national_rail_schedules.json) | Rail train service schedules, including Express vs Normal service. |
| | [national_rail_seat_layouts.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/national_rail_seat_layouts.json) | Seat layouts for Rail coaches (First class vs Standard class). |
| **Transactional Records** | [registered_users.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/registered_users.json) | Mock accounts for logged-in user profiling. |
| | [bookings.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/bookings.json) | Existing National Rail booking history. |
| | [metro_travel_history.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/metro_travel_history.json) | Metro tap-in / travel records, including Day Pass activations. |
| | [payments.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/payments.json) | Transactional payments tied to bookings and metro trips. |
| | [feedback.json](file:///c:/Users/ACER/Desktop/大學/IM2002-DBMGT-Train-final/train-mock-data/feedback.json) | Customer ratings and reviews of completed trips. |

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
Specifies conditions of carriage (luggage, pets, bikes, conduct). Key elements:

* **Metro**:
  * **Bicycles**: Foldable bikes are permitted *outside* peak hours (Peak: 07:00-09:30 and 17:00-20:00 weekdays). Standard non-foldable bikes are **prohibited at all times**. E-scooters are prohibited due to battery fire safety.
  * **Luggage**: Max 2 items per passenger, max size 70x50x30 cm.
  * **Pets**: Permitted only in enclosed carriers (max 50x35x25 cm). Assistance dogs exempt.
  * **Food/Drink**: Sealed drinks permitted. Hot/smelling food and alcohol are strictly prohibited. Priority seats must be vacated for seniors/pregnant/disabled/children.
* **National Rail**:
  * **Bicycles**: Foldable permitted free. Standard bikes permitted in designated bays (max 2 per train) with a **$2.00 fee** paid at the platform bay gate. Prohibited during peak hours (07:00-09:30, 16:30-19:00).
  * **Pets**: Dogs permitted on a lead in standard class coaches only (no seat occupancy, $0 fee).
  * **Quiet Zones**: Designated standard carriages where calls and loud noises are prohibited.

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
```

> [!TIP]
> **Database Cash Integration Considerations:**
> When integrating cash payments, the `payments` table and `payments.json` data will need to support `"cash"` as a valid `"method"`. 
> Unlike bank card payments, cash transactions cannot fail due to network gateways, but their status may require a state representation like `"paid_at_counter"`.

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
