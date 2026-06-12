# Peer Review Report

> **Instructions:** Complete this form **individually and independently**.
> Do not discuss your ratings with teammates before submitting.
> Submit via EEClass as a **separate, confidential submission** — not in the shared team repo.
> Your teammates will not see this report.
>
> Reference the team's `WORK_ALLOCATION_TEMPLATE.md` when completing this form.

---

## Your Details

| Field          | Your answer |
| -------------- | ----------- |
| Full Name      | 李加恩      |
| Student ID     | 113403052   |
| Team ID        | 19          |
| Date submitted | 2026/6/12   |

---

## Rating Scale

| Rating | Meaning                                                                                         |
| ------ | ----------------------------------------------------------------------------------------------- |
| **5**  | Exceeded expectations — delivered more than agreed; helped teammates; consistently high quality |
| **4**  | Met expectations fully — delivered exactly what was agreed; on time; good quality               |
| **3**  | Mostly met expectations — minor shortfalls; one or two items completed late or with help        |
| **2**  | Partially met expectations — noticeable gaps; teammates had to cover some tasks                 |
| **1**  | Did not meet expectations — significant tasks left incomplete; very limited contribution        |

---

## Section A — Self-Assessment

### A1. What did you personally implement?

List the specific tasks, functions, files, or document sections that you were the primary author of.
Be specific (e.g., "I designed all 12 tables in schema.sql and implemented query_national_rail_availability and execute_booking").

> _Your answer:_
>
> 工作內容為：系統中的邏輯校對與 Task 6 擴充功能的開發，我實作並整合了以下組件：
>
> **1. 關聯式資料庫查詢與交易安全 (`databases/relational/queries.py`)：**
>
> - 實作訂票工作流程 (`execute_booking`) 與使用者資料查詢。
> - 處理高併發的交易安全性 (ACID 特性)：透過撰寫具備原子性 (Atomic) 的 SQL 更新語法（例如在繳納罰款時強制加入 `AND status = 'unpaid'` 條件），有效防止 Race Condition 導致的重複扣款問題。
>
> **2. Task 6 擴充功能：遺失物與違規罰款系統：**
>
> - **Schema 設計 (`schema.sql`)**：為擴充功能設計了關聯式架構，導入 `lost_items` 與 `penalties` 資料表，並自訂了 ENUM 型別 (`lost_item_status`, `penalty_status`)，在資料庫層級進行嚴格的資料驗證。
> - **查詢實作 (`queries.py`)**：撰寫了擴充系統所需的 7 個 CRUD 操作，包含複雜的狀態過濾與狀態更新邏輯。
> - **專案文件 (`TASK6.md` & `Team19_DESIGN_DOC.md`)**：撰寫了設計文件的第 7 節 (Section 7)，詳細說明設計動機、測試案例與架構決策，並建立了官方要求的 `TASK6.md` 檔案變更目錄。
>
> **3. LLM Agent 整合與安全架構設計 (`skeleton/agent.py`)：**
>
> - 將全新的擴充工具 (`get_lost_item`, `get_user_penalties`) 成功整合進 AI Agent 的 JSON Schema 參數定義與 System Prompt 中。
> - **防幻覺與防誤觸機制 (Anti-Hallucination)**：從參數層級建立防禦，強制設定 `item_id` 為必填欄位 (Required)，確保 LLM 只有在真正具備明確 ID 時才會觸發工具，徹底解決了 Agent 過度觸發 (Over-triggering) 的問題。
> - **Schema 除錯**：成功排查並修復了標準 OpenAPI 巢狀 Schema 格式與專案客製化解析器 (`llm_provider.py`) 之間不相容的嚴重崩潰問題。
>
> 4. RAG 向量資料庫與假資料工程 (Vector DB & Mock Data)
>    處理假資料 JSON（付款、使用者、政策、遺失物、罰款），並撰寫 seed_postgres.py 與 seed_vectors.py。

## 將「動態交易資料」分流至 PostgreSQL，並將「靜態政策文件」向量化送入 pgvector 供 RAG 系統使用。

### A2. What challenges did you face?

Describe any technical or collaboration difficulties you personally encountered and how you resolved them.

> _Your answer:_
>
> 在整個專案過程中，我遇到並克服了幾個關鍵的技術與架構挑戰：
>
> **1. AI 代理幻覺與工具誤觸 (Hallucination & Over-triggering)：**
>
> - _挑戰：_ 在測試 AI 代理時，它經常產生幻覺或在使用者未提供具體資訊的情況下，錯誤觸發後端工具（例如亂跑 `find_route` 或 `get_lost_item`）。
> - _解決方案：_ 我透過重新設計 `agent.py` 中的 JSON Schema 解決了這個問題。藉由將特定參數（如 `item_id`）嚴格設定為必填 (`required`)，我建立了一道天然防線，確保 LLM 只有在使用者提供確切必要資料時才能執行該工具。我也同步優化了 System Prompt 來嚴格規範工具的使用時機。
>
> **2. 預防 LLM 工具呼叫的 IDOR 資安漏洞：**
>
> - _挑戰：_ 起初，`get_user_penalties` 工具要求 LLM 傳入 `user_id` 作為參數。我意識到這是一個巨大的不安全直接物件參考 (IDOR) 漏洞，因為 LLM 可能會被誘導去查詢其他使用者的私人罰款資料。
> - _解決方案：_ 我將 `user_id` 參數從 LLM 的可見範圍中徹底移除。取而代之的是，我修改了後端的 `_execute_tool` 邏輯，安全且自動地將當前登入使用者的身分 (Session) 注入到資料庫查詢中。這確保了 100% 的資料隱私及絕對準確的資料庫命中。
>
> **3. 解析器不相容問題 (AttributeError 系統崩潰)：**
>
> - _挑戰：_ 在加入 Task 6 擴充工具後，Gradio UI 發生了嚴重的 `AttributeError: 'str' object has no attribute 'items'` 崩潰錯誤。
> - _解決方案：_ 我一路追蹤 Bug 到了 `llm_provider.py`。問題出在格式不相容：我最初使用了標準的 OpenAPI 巢狀 JSON Schema (`"type": "object", "properties": {...}`)，但我們本地的客製化解析器預期的卻是「扁平化」的字典格式。我成功逆向工程了解析器的邏輯，並將 `agent.py` 中的工具定義扁平化，成功修復了 UI 崩潰問題。
>
> 4. 測試資料管理與系統架構抉擇 (Mock Data vs DB Source of Truth)

挑戰： 在開發 app_credit 錢包功能與註冊系統時，遇到了「是否該讓後端系統直接去覆寫初始 JSON 測試檔案」的架構兩難。
解決方案： 我堅守正統的資料庫管理原則，推動「將 JSON 嚴格視為唯讀種子資料 (Read-only Seed Data)」的團隊決策。所有交易寫入全數交由 PostgreSQL 管理，成功避免了 Anti-pattern 設計與高併發寫入造成的檔案毀損風險。

---

### A3. Self-rating

| Criterion                                                   | Rating (1–5) | Justification (1–2 sentences)                                          |
| ----------------------------------------------------------- | ------------ | ---------------------------------------------------------------------- |
| I delivered the tasks assigned to me in the work allocation | 5            | 我準時並完整地完成了指派的後端邏輯校對與 Task 6 擴充功能開發任務。     |
| The quality of my work was satisfactory                     | 5            | 我盡力確保程式碼的品質。                                               |
| I communicated well and kept the team informed              | 5            | 我積極與團隊成員溝通，確保大家了解我的進度。                           |
| I met deadlines agreed within the team                      | 5            | 我在項目期間按時完成所有承諾的任務，沒有拖延。                         |
| **Overall self-rating**                                     | 5            | 我認為爆肝的程度超出了預期，因為開發加分題時也協助隊友開發關聯式資料庫 |

---

### A4. Estimated contribution percentage

What percentage of the total team effort do you estimate you personally contributed?

> My estimated contribution: **35%**

---

## Section B — Peer Assessments

Complete one subsection per teammate. Add or remove subsections to match your team size.
If your team has 2 members, complete B1 only. If 3 members, complete B1 and B2.

---

### B1. Assessment of Teammate 1

| Field                 | Your answer |
| --------------------- | ----------- |
| Teammate's full name  | 賴韋衡      |
| Teammate's student ID | 113403017   |

#### What did this teammate deliver?

List the tasks, functions, files, or document sections that this teammate was the primary author of,
based on what you observed during the project (compare against the work allocation).

> *Your answer:*主要負責關聯式資料庫 (PostgreSQL) 的基礎架構開發與完善(schema+seed+queries)，也負責密碼雜湊與分密碼和使用者的table。此外，他負責繪製專案的 Entity-Relationship (ER) 圖，並花費許多心力協助撰寫與排版 Team19_DESIGN_DOC.md 系統設計文件。

#### Did their actual contribution match the agreed work allocation?

> *Your answer (Yes / Mostly / Partially / No — with explanation):*是

#### Peer rating for this teammate

| Criterion                                           | Rating (1–5) | Justification (1–2 sentences)                          |
| --------------------------------------------------- | ------------ | ------------------------------------------------------ |
| Delivered the tasks assigned in the work allocation | 5            | 完整地完成關聯式資料庫與 ER圖                          |
| Quality of their work was satisfactory              | 4            | 盡力確保程式碼的品質和正確性，但用AI沒看懂也不太懂 Git |
| Communicated well and kept the team informed        | 4            | 搞到我的時候沒說，我自己發現的                         |
| Met deadlines agreed within the team                | 5            | 在項目期間按時完成所有承諾的任務，沒有拖延             |
| **Overall rating for this teammate**                | 5            | 雖然搞到我了，但他很努力在做事                         |

#### Estimated contribution percentage for this teammate

> My estimate of their contribution: **33%**

---

### B2. Assessment of Teammate 2

| Field                 | Your answer |
| --------------------- | ----------- |
| Teammate's full name  | 陳品丞      |
| Teammate's student ID | 113403026   |

#### What did this teammate deliver?

> *Your answer:*主要負責圖形資料庫 (Neo4j) 的架構開發，完成了地鐵與國鐵車站節點 (Nodes) 及連線 (Relationships) 的建構，並參與了路徑最佳化查詢腳本的開發，同時也協助完成了負責區域的設計文件撰寫。

#### Did their actual contribution match the agreed work allocation?

> *Your answer (Yes / Mostly / Partially / No — with explanation):*是

#### Peer rating for this teammate

| Criterion                                           | Rating (1–5) | Justification (1–2 sentences)                    |
| --------------------------------------------------- | ------------ | ------------------------------------------------ |
| Delivered the tasks assigned in the work allocation | 5            | 完整地完成圖資料庫與演算法                       |
| Quality of their work was satisfactory              | 5            | 他寫的code品質蠻好的，尤其是link-state algorithm |
| Communicated well and kept the team informed        | 5            | 積極與團隊成員溝通，確保大家了解他的進度         |
| Met deadlines agreed within the team                | 5            | 在項目期間按時完成所有承諾的任務，沒有拖延       |
| **Overall rating for this teammate**                | 5            |                                                  |

#### Estimated contribution percentage for this teammate

> My estimate of their contribution: **32%**

---

## Section C — Contribution Percentage Summary

All members (including yourself) must sum to 100%.

| Member     | Your estimated % | Notes                                                                  |
| ---------- | ---------------- | ---------------------------------------------------------------------- |
| Yourself   | 35%              | 測試+task6加分+校對系統中邏輯+額外的政策(非task6)+協助開發關聯式資料庫 |
| Teammate 1 | 33%              | 開發並完善關聯式資料庫+撰寫設計文件+處理ER圖                           |
| Teammate 2 | 32%              | 開發並完善圖資料庫+撰寫設計文件                                        |
| **Total**  | **100%**         | 大家都很努力的做事                                                     |

---

## Section D — Overall Team Reflection

### D1. What went well in the team's collaboration?

> *Your answer (2–4 sentences):*團隊的技術分工明確拆解為三大資料庫 (PostgreSQL, Neo4j, pgvector) 並分頭進行開發和協助。團隊成員展現出高度的向心力、配合度及責任感，各自努力完善負責的模組。

---

### D2. What would you do differently if you did this project again?

> *Your answer (2–4 sentences):*本次專案由於部分成員對 Git 協作不夠熟悉，曾發生直接覆蓋掉其他成員重要架構設計與程式碼的狀況。所以若重來一次，會更加嚴格地建立並遵守 Git 版本控制與分支合併 (Branch Merging) 的標準作業流程 (SOP)，以避免類似的版本衝突與做白工的情況再次發生。

---

### D3. Is there anything else the markers should know about team dynamics or individual contributions?

This is optional. Use it only if there is important context that the ratings above do not capture
(e.g., a member had a documented personal emergency, or a member was unresponsive for a significant period).

> *Your answer (or "Nothing to add"):*關於個人貢獻的 Git 歷史紀錄，有一點想向評分者補充說明： 專案中期，我針對關聯式資料庫構思了較為複雜的設計（例如 1:1 Auth Split、Polymorphic Constraints 與防禦性約束），並將其放置於暫存分支 (schema-ex)。然而，有隊友因不熟悉 Git 操作，不慎直接 Merge 了該分支並上傳覆蓋了整個 schema.sql。這導致這部分的高階架構設計在 Git 歷史紀錄上錯誤歸屬到了隊友的名下。事發後，我額外花費了大量時間進行除錯、重新建立 Schema 關聯並修復被破壞的約束條件，這部分的心力較難從表面的 Git Commit 數量上直接看出來，特此說明。

---

## Declaration

I confirm that this peer review reflects my honest and independent assessment.
I understand it will be kept confidential from my teammates.

**Signed:** 李加恩 **Date:** 2026-06-12
