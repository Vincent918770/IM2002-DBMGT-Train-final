# Contribution Summary: `train-mock-data` Directory 
**(Lucas / 10LJN09)**

This document outlines all modifications, creations, and architectural decisions made by Lucas (10LJN09) within the `train-mock-data` directory since the initial repository fork. 

這份文件總結了自從 Fork 專案之後，由 Lucas (10LJN09) 在 `train-mock-data` 資料夾中所進行的所有修改、新增內容以及架構決策。

---

## 1. Mock Data Creation (假資料建立)
**Files Modified/Created (影響檔案):** 
- `lost_items.json` [NEW]
- `penalties.json` [NEW]

**English:**
Designed and generated entirely new mock datasets to support the newly introduced schemas.
- Created `lost_items.json` containing comprehensive mock data for lost and found items, tracking statuses such as 'reported', 'found', and 'claimed', along with station IDs and dates.
- Created `penalties.json` containing detailed mock data for user penalties (e.g., fare evasion, carrying prohibited items), tracking fine amounts and payment lifecycles.

**中文 (Chinese):**
為了支援全新設計的資料庫架構，親自設計並生成了全新的假資料集。
- 建立了 `lost_items.json`，包含完整的遺失物假資料，追蹤包含「已通報」、「已尋獲」、「已領取」等狀態，以及對應的車站與日期。
- 建立了 `penalties.json`，包含使用者罰單（如逃票、攜帶違禁品等）的詳細假資料，並追蹤罰款金額與繳費生命週期。

---

## 2. Policy & Rule Definitions (政策與規則定義)
**Files Modified/Created (影響檔案):** 
- `booking_rules.json` [MODIFIED]
- `penalty_fares.json` [NEW]
- `travel_policies.json` [MODIFIED]
- `taipei_metro_lost&found.pdf` [NEW]

**English:**
Significantly expanded the business logic and rules engine for the TransitFlow system.
- Refined `booking_rules.json` to include explicit constraints on payment binding (restricting it to App or physical counters only) and verified concession statuses.
- Updated `booking_rules.json` to refine `app_credit` policies, setting a maximum balance of $250 USD and restricting top-ups to ticket refunds, delay compensation, or staffed ticket counters (electronic payments strictly prohibited).
- Authored `penalty_fares.json` to explicitly define the penalty rules, fine amounts, and conditions for fare evasion and rule-breaking.
- Uploaded real-world reference documents (`taipei_metro_lost&found.pdf`) to enrich the RAG vector database.

**中文 (Chinese):**
大幅度擴充了 TransitFlow 系統的商業邏輯與規則引擎。
- 完善了 `booking_rules.json`，加入對付款方式綁定的嚴格限制（規定只能於 App 或臨櫃綁定），並定義了優惠票的驗證狀態。
- 更新了 `booking_rules.json` 以完善 `app_credit` (App 錢包) 政策，設定最高儲值上限為 $250 美金，並嚴格規定僅能透過退票、延誤補償或於人工櫃檯儲值 (全面禁止使用電子支付儲值)。
- 撰寫了 `penalty_fares.json`，明確定義了逃票及違規的罰款規則、罰金級距與條件。
- 上傳了真實世界參考文件 (`taipei_metro_lost&found.pdf`)，以豐富 RAG 向量資料庫的政策知識。

---

## 3. Architecture & Setup Documentation (架構與環境設定文件)
**Files Modified/Created (影響檔案):** 
- `schema_LJN_temp.md` [NEW]
- `setup_guide.md` [NEW]
- `train_mock_data_reference.md` [NEW]

**English:**
Authored comprehensive documentation to guide team development, ensure schema consistency, and simplify onboarding.
- Created `schema_LJN_temp.md` as the authoritative design document outlining the extraction of `users_confidential`, pessimistic locking strategies, polymorphic associations, and the design of the lost items / penalties tables.
- Wrote the `setup_guide.md` to provide the team with clear, step-by-step instructions on initializing PostgreSQL, generating dummy data, and seeding the Vector database for the RAG system.
- Created `train_mock_data_reference.md` as a central dictionary explaining the relationships and constraints within the mock JSON files.

**中文 (Chinese):**
撰寫了詳盡的開發文件，以引導團隊開發、確保 Schema 一致性，並簡化環境架設流程。
- 建立了 `schema_LJN_temp.md` 作為權威設計文件，其中詳細記錄了分離 `users_confidential` 機密表、悲觀鎖 (Pessimistic Locking) 策略、多型關聯 (Polymorphic associations)，以及遺失物與罰單資料表的設計。
- 撰寫了 `setup_guide.md`，為團隊提供清晰、循序漸進的環境架設指南，包含初始化 PostgreSQL、生成假資料，以及寫入 RAG 向量資料庫的步驟。
- 建立了 `train_mock_data_reference.md`，作為統一的資料字典，解釋各個 JSON 假資料檔之間的關聯與限制。
