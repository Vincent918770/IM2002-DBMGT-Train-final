# Team AI Workflow Guide — TransitFlow

A practical guide for three students working together on TransitFlow using any AI coding assistant (Claude Code, GitHub Copilot, Cursor, Gemini Code Assist, etc.).

**Read this before you write a single line of code.**

---

## Table of Contents

- [Part 0: Before Anyone Writes Code — The Schema-First Rule](#part-0-before-anyone-writes-code--the-schema-first-rule)
- [Part 1: Team Coordination with AI](#part-1-team-coordination-with-ai)
- [Part 2: The AI-Integrated Workflow Loop](#part-2-the-ai-integrated-workflow-loop)
- [Part 3: Small Working Examples](#part-3-small-working-examples)
- [Part 4: Prompts That Work](#part-4-prompts-that-work)
- [Appendix: Pre-Session Checklist](#appendix-pre-session-checklist)

---

## Part 0: Before Anyone Writes Code — The Schema-First Rule

> **Critical:** Every query function in `databases/relational/queries.py` and `databases/graph/queries.py` runs SQL or Cypher against your database. That SQL references table names and column names that **you** design. If one person's AI generates `SELECT * FROM stations` and another person's generates `SELECT * FROM metro_stations`, nothing will work together.
>
> **The rule: agree on `databases/relational/schema.sql` as a team before anyone implements a single query function.**

### Step 0.1 — Run the Schema Design Workshop Together

Do this once as a team, before splitting work. It takes about 90 minutes.

**Preparation (each person, before the meeting):**
1. Read `train-mock-data/metro_stations.json` and `train-mock-data/bookings.json`
2. Read the stub function signatures in `databases/relational/queries.py` — the function names and their docstrings tell you exactly what data the queries need to return
3. Skim `train-mock-data/national_rail_schedules.json`, `train-mock-data/registered_users.json`, `train-mock-data/payments.json`

**During the workshop:**
1. Each person asks their AI assistant: *"Given this JSON data [paste 10–20 lines], what SQL tables would you design?"*
2. Compare the three AI outputs as a team — they will differ
3. Discuss and decide together (AI proposes options; humans decide)
4. Write the agreed schema into `databases/relational/schema.sql`

See [Example 1](#example-1-schema-design-workshop) in Part 3 for a concrete walkthrough.

### Step 0.2 — Commit and Lock the Schema

Once your team agrees on the schema, one person commits it:

```bash
git checkout -b feature/schema-design
git add databases/relational/schema.sql
git commit -m "Add agreed relational schema - team reviewed"
```

Open a Pull Request and have all three teammates approve it before merging to main. After it merges, **do not rename tables or columns without telling the whole team** — it will break everyone else's queries.

### Step 0.3 — Do the Same for the Graph Schema

The graph queries in `databases/graph/queries.py` (e.g., `query_shortest_route`, `query_station_connections`) need a Neo4j node/relationship schema. Read `train-mock-data/metro_stations.json` and `train-mock-data/national_rail_stations.json`, decide on node labels (`Station`, `MetroStation`, etc.) and relationship types (`CONNECTS_TO`, `INTERCHANGE`, etc.) as a team before implementing graph queries.

---

## Part 1: Team Coordination with AI

### 1.1 — Who Owns What

Use this as a starting point. Adjust it to your team.

| Area | Files to implement | Shared dependency |
|---|---|---|
| Relational schema | `databases/relational/schema.sql` | **Whole team — agree together** |
| Relational queries | `databases/relational/queries.py` | Schema must be finalized first |
| Graph schema + queries | `databases/graph/queries.py` | Station IDs from relational schema |
| Seeding & testing | `skeleton/seed_postgres.py`, `skeleton/seed_neo4j.py` | Both schemas |

**Document your assignments.** Create a `TEAM.md` file at the project root:

```markdown
# Team Assignments

| Name  | Primary responsibility                          |
|-------|-------------------------------------------------|
| Alice | Relational schema + relational query functions  |
| Bob   | Graph schema + graph query functions            |
| Carol | Seeding scripts + integration testing           |
```

### 1.2 — Git Basics (Step by Step)

If you are new to Git, follow this pattern every time you start working:

**One-time setup:**
```bash
# Clone the shared repo (do this once)
git clone <your-repo-url>
cd transitflow-demo
```

**Every time you start a work session:**
```bash
# 1. Make sure you have the latest code from your teammates
git checkout main
git pull origin main

# 2. Create a branch for what you're about to do
git checkout -b feature/alice/metro-schedules-query
```

**While working:**
```bash
# Save your progress frequently
git add databases/relational/queries.py
git commit -m "Implement query_metro_schedules - returns schedules by origin/destination"
```

**When you're done with a feature:**
```bash
# Push your branch to GitHub
git push origin feature/alice/metro-schedules-query
# Then open a Pull Request on GitHub and ask a teammate to review
```

**Branch naming convention:** `feature/<your-name>/<what-youre-doing>`

Examples:
- `feature/alice/relational-schema`
- `feature/bob/graph-shortest-route`
- `feature/carol/seed-postgres`

### 1.3 — The Shared AI Context File

> **The single most impactful thing you can do for consistency.**

Create `AI_SESSION_CONTEXT.md` in the repo root (a template is provided — see [AI_SESSION_CONTEXT.md](AI_SESSION_CONTEXT.md)). Every time someone opens an AI chat session, they **paste the contents of this file as the first message**.

This file contains:
- The project's agreed coding conventions
- Your finalized schema (once decided)
- The function signatures you're implementing
- Your team's decisions log

The AI will then know your table names, column names, return types, and style — and will generate code that fits your codebase instead of inventing its own conventions.

**Who updates it:** Whoever merges a schema change or makes an architectural decision updates `AI_SESSION_CONTEXT.md` in the same commit. Treat it like a living document.

### 1.4 — The Before-You-Start Ritual

Before opening your AI assistant each session:

1. `git pull origin main` — get your teammates' latest merged work
2. Check GitHub for open Pull Requests — is anything waiting for your review?
3. Tell your teammates (via your team chat) what you're about to work on: *"Working on query_metro_schedules today"*
4. Paste `AI_SESSION_CONTEXT.md` into your AI chat as the first message

This takes two minutes and prevents three people asking AI to solve the same problem three different ways.

### 1.5 — Agree on a Definition of Done Per Stub

Before implementing any stub function, answer these questions as a team:

- What input does it receive? (already documented in the docstring)
- What should it return? (already documented — look at the `Returns:` section)
- What does a correct output look like for a known input?

Write this down. For example, for `query_metro_schedules("MS01", "MS09")`:
- *"Should return at least one schedule. Each dict must have keys `schedule_id`, `line`, `departure_time`, `stops_list`."*

This is your acceptance criterion. When your AI generates code, test it against this criterion before marking the task done.

---

## Part 2: The AI-Integrated Workflow Loop

For every feature or function you implement, follow this five-stage loop. Never skip straight to Implementation.

```
Analysis & Planning → Options Evaluation → Minimal Implementation → Testing → Merging
         ↑                                                                        |
         └────────────────────────────────────────────────────────────────────────┘
                            (loop back if tests fail or reveal new requirements)
```

### Stage 1 — Analysis & Planning

**What you do:** Understand the problem before asking AI to solve it.

1. Read the stub function's docstring — it tells you exactly what the function must do
2. Look at the mock data that the function will query
3. Trace which table(s) you'll need (from your agreed schema)

**AI's role at this stage:** Ask AI to *explain*, not generate. Example:

> *"I need to implement `query_metro_schedules(origin_id, destination_id)`. It should return schedules that serve both stations in the correct order. My schema has a `metro_schedules` table with columns: `schedule_id, line, direction, stops (JSONB array)`. Can you explain what SQL approach I'd use to find schedules where both station IDs appear in the stops array in the right order?"*

**Human decision point:** Do you understand the approach before proceeding? If not, ask AI to explain further — don't ask it to generate code yet.

### Stage 2 — Options Evaluation

**What you do:** Ask AI for 2–3 approaches and compare them with your teammate.

Example prompt:

> *"Give me two different SQL approaches to find metro schedules where MS01 comes before MS09 in a JSONB array of stop IDs. Show the tradeoffs."*

AI might propose:
- Option A: Use `jsonb_array_elements` with position tracking
- Option B: Use `@>` containment operator + position comparison

Compare with your teammate. Pick the one that matches your schema and your team's SQL comfort level. Document the decision in `AI_SESSION_CONTEXT.md`:
> *"Metro schedule stop-order checking: using jsonb_array_elements approach (Option A) — clearer to read, easier to debug"*

### Stage 3 — Minimal Implementation

**What you do:** Implement one function at a time. Get it working before moving to the next.

**Before generating code, prepare your prompt:**
1. Paste your `AI_SESSION_CONTEXT.md` contents (if you haven't already)
2. Paste the exact stub function signature and docstring
3. Paste the relevant table definition from your schema

Example prompt structure (see [Part 4](#part-4-prompts-that-work) for templates):

> *[paste AI_SESSION_CONTEXT.md]*
>
> *Now implement this function. Match the signature exactly — do not change parameter names or return types:*
> *[paste stub function]*
>
> *My schema for the relevant tables:*
> *[paste CREATE TABLE statements]*

**Review the AI output before using it:**
- Does it use the table names from your schema? (not invented ones)
- Does it match the return type described in the docstring?
- Does it follow the `_connect()` / `RealDictCursor` pattern from `example_query()`?

See [Example 2](#example-2-implementing-a-relational-query-stub) in Part 3 for a full walkthrough.

### Stage 4 — Testing

**What you do:** Manually run the function and verify it returns what you expect.

You do not need a formal test framework. Open a Python shell:

```python
# From the project root, with your virtual environment active
python

>>> from databases.relational.queries import query_metro_schedules
>>> result = query_metro_schedules("MS01", "MS09")
>>> print(result)
>>> # Does it return a list? Does each item have the expected keys?
>>> # Is the result non-empty for a route that exists in your seed data?
```

**What to check:**
- Does it return a list (not None, not an error)?
- Does each dict have the keys the agent expects?
- For a station pair you know exists, does it return sensible results?
- For a station pair that doesn't exist, does it return an empty list (not crash)?

If the function raises an error, paste the error and your code back into the AI chat and ask it to fix the issue.

### Stage 5 — Merging

**What you do:** Get your work reviewed by a teammate and merge it.

1. Push your branch: `git push origin feature/alice/metro-schedules-query`
2. Open a Pull Request on GitHub
3. Ask a teammate to review — see [Example 4](#example-4-pr-review-and-merging) in Part 3
4. Address any feedback
5. Merge once approved
6. Update `AI_SESSION_CONTEXT.md` if any architectural decisions changed

**Update the main branch after merging:**
```bash
git checkout main
git pull origin main
```

---

## Part 3: Small Working Examples

### Example 1: Schema Design Workshop

**Scenario:** Your team is designing the `metro_stations` table from the mock data.

**Step 1 — Look at the mock data** (`train-mock-data/metro_stations.json`):

```json
{
  "station_id": "MS01",
  "name": "Central Square",
  "lines": ["M1", "M2"],
  "is_interchange_metro": true,
  "interchange_metro_lines": ["M1", "M2"],
  "is_interchange_national_rail": true,
  "interchange_national_rail_station_id": "NR01",
  "adjacent_stations": [
    { "station_id": "MS05", "line": "M1", "travel_time_min": 3 },
    { "station_id": "MS02", "line": "M1", "travel_time_min": 3 }
  ]
}
```

**Step 2 — Ask AI to propose a schema:**

> *"Here is one entry from our metro station data: [paste the JSON above]. Design a PostgreSQL schema to store this data. Note that `adjacent_stations` represents graph relationships — we have a separate Neo4j database for those, so you do not need to store them in SQL. Focus on what the relational database needs."*

**Step 3 — AI might produce something like:**

```sql
CREATE TABLE metro_stations (
    station_id          VARCHAR(10) PRIMARY KEY,
    name                TEXT NOT NULL,
    is_interchange_metro         BOOLEAN DEFAULT FALSE,
    is_interchange_national_rail BOOLEAN DEFAULT FALSE,
    interchange_nr_station_id    VARCHAR(10) REFERENCES national_rail_stations(station_id)
);

CREATE TABLE metro_station_lines (
    station_id  VARCHAR(10) REFERENCES metro_stations(station_id),
    line        VARCHAR(5) NOT NULL,
    PRIMARY KEY (station_id, line)
);
```

**Step 4 — Team discussion questions:**
- Do we need `metro_station_lines` as a separate table, or can we store lines as a simple array? (Hint: look at what queries will need to filter by line)
- Should `interchange_nr_station_id` be a foreign key constraint now, or added after both tables exist?
- What will `query_metro_schedules` need from this table?

**Human decision:** The team decides — AI proposes options. Normalization choices affect everyone's query functions, so everyone must agree.

---

### Example 2: Implementing a Relational Query Stub

**Scenario:** Alice is implementing `query_metro_schedules`.

**Step 1 — Alice reads the stub** (`databases/relational/queries.py`, lines 110–118):

```python
def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:
    """
    Return metro schedules that serve both origin and destination in the correct order.

    Args:
        origin_id:       e.g. "MS01"
        destination_id:  e.g. "MS09"
    """
    raise NotImplementedError("TODO: implement after designing your schema")
```

**Step 2 — Alice prepares her prompt:**

```
[paste AI_SESSION_CONTEXT.md first]

Now implement this Python function. Rules:
- Use the _connect() helper and psycopg2.extras.RealDictCursor pattern shown in example_query()
- Match the stub's signature exactly — do not change parameter names or return types
- Use only table/column names from the schema below

Stub to implement:
[paste the stub above]

My schema (relevant tables):
CREATE TABLE metro_schedules (
    schedule_id  VARCHAR(20) PRIMARY KEY,
    line         VARCHAR(5) NOT NULL,
    direction    VARCHAR(10),
    stops        JSONB NOT NULL   -- ordered list of station_ids, e.g. ["MS01","MS02","MS09"]
);
```

**Step 3 — AI generates code. Alice checks:**
- Does it use `_connect()` from the module? ✓ or ✗
- Does it use `RealDictCursor`? ✓ or ✗
- Does it return `list[dict]`, not a single row? ✓ or ✗
- Does it reference `metro_schedules` (not an invented table name)? ✓ or ✗

**Step 4 — Alice tests it:**

```python
python

>>> from databases.relational.queries import query_metro_schedules
>>> result = query_metro_schedules("MS01", "MS09")
>>> print(type(result))      # should be <class 'list'>
>>> print(result)            # should show schedule dicts
>>> print(result[0].keys())  # check key names
```

---

### Example 3: Implementing a Graph Query Stub

**Scenario:** Bob is implementing `query_station_connections`.

**The stub** (`databases/graph/queries.py`, lines 159–166):

```python
def query_station_connections(station_id: str) -> list[dict]:
    """
    List all direct connections from a given station.

    Args:
        station_id: e.g. "MS01" or "NR01"
    """
    raise NotImplementedError("TODO: implement after designing your graph schema")
```

**Bob's prompt:**

```
[paste AI_SESSION_CONTEXT.md first]

Implement this Neo4j query function. Rules:
- Use the _driver() helper and the session pattern shown in example_count_nodes()
- Match the stub's signature exactly
- Use the node labels and relationship types from our agreed graph schema below

Stub to implement:
[paste stub above]

Our graph schema:
- Node label: Station, properties: {station_id, name, network}
- Relationship: CONNECTS_TO, properties: {line, travel_time_min}
```

**Bob checks the AI output:**
- Does it use `_driver()` from the module? ✓ or ✗
- Does it use `with driver.session() as session:`? ✓ or ✗
- Does the Cypher use `Station` as the node label (not `Node` or `stop`)? ✓ or ✗
- Does it return `list[dict]`? ✓ or ✗

**Bob tests it:**

```python
python

>>> from databases.graph.queries import query_station_connections
>>> result = query_station_connections("MS01")
>>> print(result)
>>> # MS01 (Central Square) connects to MS05, MS02, MS06, MS07 per the mock data
>>> # Check that your results match
```

---

### Example 4: PR Review and Merging

**Scenario:** Alice has pushed `feature/alice/metro-schedules-query` and opened a PR.

**Bob reviews the PR. He checks:**

1. Does the function match the stub's signature? (no extra or changed parameters)
2. Does it use table/column names from the agreed schema?
3. Does it follow the `_connect()` / `RealDictCursor` pattern?
4. Does it handle the empty-result case (no schedules found)?

**If Bob spots an issue**, he leaves a comment on GitHub:
> *"Line 45: your query uses `stations` but our schema calls this table `metro_stations`. Also the return dict is missing the `departure_time` key that `query_metro_fare` expects."*

**Alice fixes it**, pushes a new commit, and replies to the comment.

**After Bob approves**, Alice merges the PR:
- Click "Merge Pull Request" on GitHub
- Then locally: `git checkout main && git pull origin main`

---

### Example 5: Catching an AI Inconsistency

**Scenario:** Carol asks her AI to implement `query_national_rail_fare`. The AI generates:

```python
cur.execute("SELECT * FROM fares WHERE route_id = %s", (schedule_id,))
```

But the agreed schema has no `fares` table — the fare is calculated from `national_rail_schedules.base_fare_usd` and `national_rail_schedules.per_stop_rate_usd`.

**How to catch it:**
- The code runs, but returns `[]` or throws a `psycopg2.errors.UndefinedTable` error
- Carol compares the table name in the AI output against her schema — mismatch found

**Fix:** Carol updates her prompt to paste the exact `CREATE TABLE` statements and says:
> *"Do not invent table or column names. Use only what appears in the schema below."*

**Lesson:** Always paste your schema into the AI prompt. AI will make up plausible-sounding names if you don't give it the real ones.

---

## Part 4: Prompts That Work

These are tool-agnostic templates. Paste them into any AI assistant (Claude, Copilot, Cursor, Gemini, etc.).

### Template A: Schema Design

```
I'm a student working on a database project. Here is one sample entry from our
raw data file [filename]:

[paste 1–3 JSON objects from the mock data]

Design a PostgreSQL schema to store this data. Constraints:
- Use snake_case for all table and column names
- Use VARCHAR for IDs (they look like "MS01", "NR_SCH01")
- Avoid storing graph/network relationships (those go in Neo4j)
- Include PRIMARY KEY and NOT NULL where appropriate
- Show the CREATE TABLE statement only, no explanation

Note: this schema will be shared with two teammates. Table names must be agreed
before anyone writes query functions.
```

### Template B: Query Function Implementation

```
I'm implementing a Python function for a PostgreSQL database project.
Follow these rules strictly:
- Use only the table and column names in the schema below — do not invent names
- Use the _connect() helper function already defined in the module
- Use psycopg2.extras.RealDictCursor (so rows come back as dicts)
- Match the stub signature exactly — do not change parameter names or return type
- Return an empty list [] (not None) when no rows are found
- Do not add try/except unless the docstring specifically asks for error handling

[paste AI_SESSION_CONTEXT.md here]

Stub to implement:
[paste the stub function with its docstring]

Schema (relevant tables only):
[paste the CREATE TABLE statements your function will query]
```

### Template C: Code Review

```
Review this Python database function against the stub contract and schema below.
Check for:
1. Does it use only table/column names from the schema?
2. Does it match the stub's return type and key names?
3. Does it follow the _connect() / RealDictCursor pattern?
4. Does it handle the empty-result case gracefully?
5. Any SQL injection risk (are all user inputs parameterised with %s)?

Report only real issues — no style suggestions.

Stub (the contract):
[paste the original stub]

Implementation to review:
[paste your code]

Schema:
[paste relevant CREATE TABLE statements]
```

### Template D: Debugging

```
This Python function is raising an error. Help me fix it.

Error:
[paste the full traceback]

Function:
[paste your code]

Schema:
[paste relevant CREATE TABLE statements]

What I expected it to do:
[one sentence]
```

### How to Share Prompts That Worked

When you find a prompt that produces good output, add it to the **Prompts log** section of `AI_SESSION_CONTEXT.md`. Your teammates can reuse it instead of spending time writing their own.

---

## Appendix: Pre-Session Checklist

Run through this before every AI-assisted work session.

```
[ ] git checkout main && git pull origin main
[ ] Check GitHub for open Pull Requests — anything needing your review?
[ ] Confirm Docker containers are running: docker compose ps
    (should show postgres, neo4j, pgadmin as "Up")
[ ] Confirm your virtual environment is active: python -c "import psycopg2; print('ok')"
[ ] Open AI_SESSION_CONTEXT.md and paste its contents into your AI chat
[ ] Tell your teammates what you're about to work on
```

If Docker isn't running: `docker compose up -d` from the project root.

If your venv is missing: see the [Python Virtual Environments](README.md#python-virtual-environments) section of README.md.

---

## Quick Reference

| Question | Where to look |
|---|---|
| What functions do I need to implement? | `databases/relational/queries.py`, `databases/graph/queries.py` — read the stubs and docstrings |
| What data do I have to work with? | `train-mock-data/` — JSON files for every entity |
| What does the agent call my function with? | `skeleton/agent.py` — the `TOOLS` list shows the exact parameters |
| Where do I design the schema? | `databases/relational/schema.sql` — currently empty, you fill it in |
| What do I paste into AI at the start? | `AI_SESSION_CONTEXT.md` — the shared context file |
| Generic team practices and checklists | `TEAM_PROJECT_GUIDE.md` |

---

# 團隊 AI 協作開發指南 — TransitFlow (中文版)

這是一份實用的指南，專為三位合作開發 TransitFlow 的同學設計，旨在指導如何使用任何 AI 程式助理（Claude Code、GitHub Copilot、Cursor、Gemini Code Assist 等）進行高效協作。

**在撰寫任何一行程式碼之前，請務必先閱讀本指南。**

---

## 目錄

- [Part 0：動工開發前 — Schema 優先原則](#part-0動工開發前--schema-優先原則)
- [Part 1：團隊與 AI 協作的分工與協調](#part-1團隊與-ai-協作的分工與協調)
- [Part 2：AI 整合開發工作流程循環](#part-2ai-整合開發工作流程循環)
- [Part 3：具體工作範例與示範](#part-3具體工作範例與示範)
- [Part 4：實測有效的 AI 提示詞模板](#part-4實測有效的-ai-提示詞模板)
- [附錄：每次開始開發前的自我檢查清單](#附錄每次開始開發前的自我檢查清單)

---

## Part 0：動工開發前 — Schema 優先原則

> **重要提示：** `databases/relational/queries.py` 和 `databases/graph/queries.py` 中的每個查詢函式，都會對你的資料庫執行 SQL 或 Cypher 查詢。這些查詢所引用的資料表名稱與欄位名稱都必須由**你們**親自設計。如果其中一位隊員的 AI 生成了 `SELECT * FROM stations`，而另一位隊員的 AI 生成了 `SELECT * FROM metro_stations`，整套系統將完全無法整合。
>
> **核心原則：在實作任何查詢函式之前，團隊 must 先對 `databases/relational/schema.sql` 達成共識。**

### 步驟 0.1 — 共同進行 Schema 設計討論會

在團隊分工開始前，共同進行這項設計（約需 90 分鐘）。

**會前準備（每位隊員在開會前完成）：**
1. 閱讀 `train-mock-data/metro_stations.json` 和 `train-mock-data/bookings.json`
2. 閱讀 `databases/relational/queries.py` 中的 stub（未實作的函式定義）— 函式名稱與其 docstring 會明確告訴你該查詢需要回傳什麼資料
3. 概覽 `train-mock-data/national_rail_schedules.json`、`train-mock-data/registered_users.json`、`train-mock-data/payments.json`

**會議期間：**
1. 每個人向自己的 AI 助理提問：*"給定這份 JSON 資料 [貼上 10-20 行範例]，你會如何設計 PostgreSQL 的資料表結構？"*
2. 在團隊中比較三份 AI 的輸出 — 它們一定會有所不同
3. 共同討論並做決定（由 AI 提案，人類做最終決策）
4. 將達成共識的 Schema 寫入 `databases/relational/schema.sql`

請參閱 Part 3 的 [範例 1](#範例-1schema-設計討論會) 以了解具體的進行流程。

### 步驟 0.2 — 提交並鎖定 Schema

當團隊對 Schema 達成共識後，由一人進行提交：

```bash
git checkout -b feature/schema-design
git add databases/relational/schema.sql
git commit -m "Add agreed relational schema - team reviewed"
```

在 GitHub 上發起 Pull Request (PR)，並由另外兩位隊友審查批准，然後合併到 `main` 分支。合併後，**在未通知全體隊員的情況下，切勿隨意重新命名資料表或欄位** — 這會直接破壞其他人的查詢程式碼。

### 步驟 0.3 — 圖形資料庫 Schema 也依循此原則

`databases/graph/queries.py` 中的圖形查詢（例如 `query_shortest_route`、`query_station_connections`）需要一個 Neo4j 的節點/關係（node/relationship）結構。請先閱讀 `train-mock-data/metro_stations.json` 和 `train-mock-data/national_rail_stations.json`，在開始實作圖形查詢之前，先共同決定節點標籤（`Station`、`MetroStation` 等）以及關係類型（`CONNECTS_TO`、`INTERCHANGE` 等）。

---

## Part 1：團隊與 AI 協作的分工與協調

### 1.1 — 角色與職責分配

這是一個推薦的起點，你們可以根據團隊情況進行調整：

| 負責領域 | 需實作的檔案 | 共享依賴 |
|---|---|---|
| 關聯式資料庫 Schema | `databases/relational/schema.sql` | **全體隊員 — 共同討論決定** |
| 關聯式資料庫查詢 | `databases/relational/queries.py` | 必須先確定關聯式 Schema |
| 圖形 Schema 與查詢 | `databases/graph/queries.py` | 依賴關聯式 Schema 訂定的車站 ID |
| 資料導入與測試 | `skeleton/seed_postgres.py`, `skeleton/seed_neo4j.py` | 雙資料庫 Schema |

**記錄你們的分配。** 在專案根目錄下建立一個 `TEAM.md` 檔案：

```markdown
# 團隊任務分配

| 姓名  | 主要職責 |
|-------|-------------------------------------------------|
| Alice | 關聯式資料庫 Schema + 關聯式查詢功能實作 |
| Bob   | 圖形資料庫 Schema + 圖形查詢功能實作 |
| Carol | 資料導入 (Seeding) 腳本 + 整合測試 |
```

### 1.2 — Git 基礎協作（逐步指南）

如果你對 Git 還不熟悉，請在每次開始撰寫程式碼前，遵循以下模式：

**一次性設定：**
```bash
# 複製共享的專案庫 (只須做一次)
git clone <你的專案庫URL>
cd transitflow-demo
```

**每次開始開發的儀式：**
```bash
# 1. 確保你拿到了隊友們最新的程式碼
git checkout main
git pull origin main

# 2. 為你接下來要做的事情建立一個新分支
git checkout -b feature/alice/metro-schedules-query
```

**開發期間：**
```bash
# 頻繁保存你的開發進度
git add databases/relational/queries.py
git commit -m "Implement query_metro_schedules - returns schedules by origin/destination"
```

**當完成功能開發後：**
```bash
# 將你的分支推送至 GitHub
git push origin feature/alice/metro-schedules-query
# 接著在 GitHub 上發起一個 Pull Request (PR)，並邀請隊友審查
```

**分支命名規範：** `feature/<你的英文名字>/<你正在做的事情>`

例如：
- `feature/alice/relational-schema`
- `feature/bob/graph-shortest-route`
- `feature/carol/seed-postgres`

### 1.3 — 共享的 AI 上下文檔案 (AI_SESSION_CONTEXT.md)

> **這對維持程式碼一致性最為關鍵。**

在專案根目錄建立 `AI_SESSION_CONTEXT.md` 檔案（已提供模板 — 參見 [AI_SESSION_CONTEXT.md](AI_SESSION_CONTEXT.md)）。每次開啟新的 AI 對話工作階段時，**請先將此檔案的內容複製並貼上，作為對 AI 說的第一句話**。

這個檔案包含：
- 專案約定的編碼規範
- 你們最終討論通過的資料庫 Schema (一旦確定)
- 準備要實作的函式定義與規格
- 團隊決策紀錄

有了這些資訊，AI 就會知道你的資料表名稱、欄位名稱、回傳型態以及程式碼風格，進而生成符合你們專案架構的程式碼，而不會自己胡亂發明命名約定。

**誰負責更新它：** 誰合併了 Schema 變更或做出了架構決策，就由誰在同一個提交 (commit) 中負責更新 `AI_SESSION_CONTEXT.md`。請將它視為活的文件。

### 1.4 — 開始開發前的「準備儀式」

在每次打開 AI 助理開始寫程式前：

1. `git pull origin main` — 獲取隊友最新合併的成果
2. 檢查 GitHub 上的 Pull Requests — 是否有任何需要你協助審查的 PR？
3. 在團隊通訊軟體通知隊友你正要開始的工作：*"我今天準備實作 query_metro_schedules"*
4. 將 `AI_SESSION_CONTEXT.md` 內容貼到你的 AI 對話框中作為第一段輸入

這只需要花費兩分鐘，卻能有效防止三個人用三種完全不同且互不相容的方式來解同一個問題。

### 1.5 — 對每個 Stub 達成「完成定義 (Definition of Done)」共識

在實作任何 stub 函式前，團隊先確認好這些問題：

- 該函式會接收什麼輸入參數？（已記錄在 docstring 的參數說明中）
- 它應該回傳什麼資料結構？（已記錄在 docstring 的 `Returns:` 部分）
- 針對已知的輸入，正確的輸出結果應當長怎樣？

例如，對於 `query_metro_schedules("MS01", "MS09")`：
- *"必須回傳至少一個時刻表。每個 dict 都必須包含 `schedule_id`、`line`、`departure_time`、`stops_list` 這些 key。"*

這是你們的驗收準則。在 AI 生成程式碼後，在將任務標記為完成前，務必對照此準則進行驗證。

---

## Part 2：AI 整合開發工作流程循環

對於你要實作的每個功能或函式，請遵循這個「五階段循環」。千萬不要直接跳到實作階段。

```
分析與規劃 (Analysis & Planning) → 評估不同選項 (Options Evaluation) → 極簡實作 (Minimal Implementation) → 測試 (Testing) → 合併 (Merging)
          ↑                                                                                                                 |
          └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                (若測試失敗或發現新需求，則返回重新循環)
```

### 階段 1 — 分析與規劃

**你要做的事：** 在要求 AI 解題前，先搞懂問題的來龍去脈。

1. 仔細閱讀 stub 函式的 docstring — 它會告訴你這個函式必須達成的目的
2. 查看該功能需要查詢的 raw 模擬數據（模擬 JSON 資料）
3. 對照你們已達共識的 Schema，理清需要查詢哪些資料表

**AI 在此階段的角色：** 讓 AI 來*解釋*思路，而不是直接寫程式。範例：

> *"我需要實作 `query_metro_schedules(origin_id, destination_id)`。它需要以正確的順序回傳同時服務這兩個站點的時刻表。我的 Schema 裡有一個 `metro_schedules` 資料表，欄位有：`schedule_id, line, direction, stops (JSONB array)`。你能向我解釋，在 SQL 中要如何篩選出 stops 陣列中同時包含這兩個站點 ID，且起點 ID 出現在終點 ID 之前的時刻表嗎？"*

**人類決策點：** 在開始下一步前，你是否已經理解了這個解法思路？如果還不清楚，請進一步讓 AI 解釋 — 先不要急著叫它寫程式。

### 階段 2 — 評估不同選項

**你要做的事：** 讓 AI 提供 2 到 3 種不同的做法，並與隊友一同比較。

提示詞範例：

> *"請提供兩種不同的 SQL 方法，來檢查 stops (JSONB 陣列) 中 MS01 是否出現在 MS09 之前。並說明這兩種方法的優缺點與 Tradeoffs。"*

AI 可能會給出：
- 方法 A：使用 `jsonb_array_elements` 進行位置追蹤
- 方法 B：使用 `@>` 包含運算子搭配位置索引比較

與隊友討論，選擇一個最符合你們 Schema 設計與團隊 SQL 掌握度的方案。將此決策記錄到 `AI_SESSION_CONTEXT.md` 中：
> *"地鐵時刻表停靠順序檢查：使用 jsonb_array_elements 方法 (方法 A) — 易於閱讀且易於偵錯"*

### 階段 3 — 極簡實作

**你要做的事：** 一次只實作一個函式。確保它能跑了，再進行下一個。

**在讓 AI 生成程式碼前，準備好你的提示詞：**
1. 貼上你的 `AI_SESSION_CONTEXT.md` 內容（如果你在該對話中還沒貼過的話）
2. 貼上該 stub 函式的完整定義與 docstring
3. 貼上關聯資料表的 CREATE TABLE 語句

提示詞結構範例（請參考 Part 4 的模板）：

> *[貼上 AI_SESSION_CONTEXT.md]*
>
> *現在請實作這個 Python 函式。請嚴格遵守原有的函式簽章，請勿修改任何參數名稱或回傳類型：*
> *[貼上 stub 函式程式碼]*
>
> *以下是此查詢涉及的資料表 Schema：*
> *[貼上 CREATE TABLE 語句]*

**使用 AI 生成的程式碼前的檢查要點：**
- 它是否使用了你們 Schema 的資料表名稱？（而非 AI 自己發明的名字）
- 它的回傳格式是否完全符合 docstring 中描述的資料型態？
- 它是否遵循了 `example_query()` 中展示的 `_connect()` 與 `RealDictCursor` 連線與游標模式？

請參閱 Part 3 的 [範例 2](#範例-2實作關聯式資料庫查詢-stub) 了解完整的操作細節。

### 階段 4 — 測試

**你要做的事：** 手動呼叫該函式，驗證回傳的資料是否符合預期。

不需要寫複雜的測試框架。直接打開 Python 互動式視窗：

```python
# 在專案根目錄，啟用虛擬環境後輸入
python

>>> from databases.relational.queries import query_metro_schedules
>>> result = query_metro_schedules("MS01", "MS09")
>>> print(result)
>>> # 是否回傳了 list？裡面的每個元素是否包含預期的 dict 欄位？
>>> # 對於種子資料中確實存在的站點，是否能正常查到非空的結果？
```

**測試檢查清單：**
- 函式是否正常回傳一個 list (而不是 None，也沒有丟出程式 crash 報錯)？
- list 中的每個 dict 是否包含 Agent 預期要用的 keys？
- 輸入一對你已知存在的站點，結果是否合理？
- 輸入一對不存在的站點，它是否能優雅地回傳空列表 `[]` (而不是丟出 exception 崩潰)？

如果函式拋出了錯誤，將 traceback 報錯訊息與你的程式碼貼回給 AI，要求它進行排查與修正。

### 階段 5 — 合併

**你要做的事：** 讓隊友審查你的程式碼，並合併回主分支。

1. 推送你的開發分支：`git push origin feature/alice/metro-schedules-query`
2. 在 GitHub 上針對 `main` 發起 Pull Request
3. 邀請隊友進行 Code Review — 參閱 [範例 4](#範例-4pr-審查與合併)
4. 根據回饋意見進行修改
5. 核准後進行合併
6. 若有任何架構性決策變更，更新 `AI_SESSION_CONTEXT.md`

**合併後更新你本地的 main 分支：**
```bash
git checkout main
git pull origin main
```

---

## Part 3：具體工作範例與示範

### 範例 1：Schema 設計討論會

**場景：** 團隊正在合作設計 `metro_stations` 的資料表結構。

**第一步 — 查看原始模擬數據** (`train-mock-data/metro_stations.json`)：

```json
{
  "station_id": "MS01",
  "name": "Central Square",
  "lines": ["M1", "M2"],
  "is_interchange_metro": true,
  "interchange_metro_lines": ["M1", "M2"],
  "is_interchange_national_rail": true,
  "interchange_national_rail_station_id": "NR01",
  "adjacent_stations": [
    { "station_id": "MS05", "line": "M1", "travel_time_min": 3 },
    { "station_id": "MS02", "line": "M1", "travel_time_min": 3 }
  ]
}
```

**第二步 — 要求 AI 提供 Schema 設計提案：**

> *"這是我們地鐵車站資料中的一筆範例：[貼上方的 JSON 內容]。請為我們設計一個 PostgreSQL 的 Schema 來儲存這些資料。請注意，`adjacent_stations` 代表圖形關係 — 我們會把這些連接關係存放在 Neo4j 圖形資料庫中，所以你在 SQL 設計中不需要儲存鄰近車站關係。請專注在關聯式資料庫需要的欄位即可。"*

**第三步 — AI 給出的提案可能長這樣：**

```sql
CREATE TABLE metro_stations (
    station_id          VARCHAR(10) PRIMARY KEY,
    name                TEXT NOT NULL,
    is_interchange_metro         BOOLEAN DEFAULT FALSE,
    is_interchange_national_rail BOOLEAN DEFAULT FALSE,
    interchange_nr_station_id    VARCHAR(10) REFERENCES national_rail_stations(station_id)
);

CREATE TABLE metro_station_lines (
    station_id  VARCHAR(10) REFERENCES metro_stations(station_id),
    line        VARCHAR(5) NOT NULL,
    PRIMARY KEY (station_id, line)
);
```

**第四步 — 團隊討論：**
- 我們真的需要將地鐵線路拆出 `metro_station_lines` 關聯表嗎？還是以簡單的陣列欄位儲存即可？（提示：思考接下來的查詢是否需要頻繁根據線路進行過濾）
- `interchange_nr_station_id` 是否需要在這時候加上外鍵約束，還是在兩個資料表都建好後再以 ALTER TABLE 補上？
- `query_metro_schedules` 接下來需要從這個表中查出哪些欄位？

**人類做決策：** 團隊討論決定最終設計方案 — AI 僅提供選項。由於設計決定會影響後續所有人查詢函式的撰寫，因此全體成員必須達成一致。

---

### 範例 2：實作關聯式資料庫查詢 Stub

**場景：** Alice 正在實作 `query_metro_schedules`。

**第一步 — Alice 閱讀 stub 程式碼** (`databases/relational/queries.py`)：

```python
def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:
    """
    Return metro schedules that serve both origin and destination in the correct order.

    Args:
        origin_id:       e.g. "MS01"
        destination_id:  e.g. "MS09"
    """
    raise NotImplementedError("TODO: implement after designing your schema")
```

**第二步 — Alice 準備給 AI 的提示詞：**

```
[先貼上 AI_SESSION_CONTEXT.md]

請實作這個 Python 函式。規則：
- 使用模組中已定義的 _connect() 輔助功能，並採用 example_query() 中展示的 psycopg2.extras.RealDictCursor 游標模式。
- 嚴格遵守該 stub 函式的簽章與規格 — 不要修改任何參數名稱或回傳值型態。
- 僅能使用下方 Schema 中存在的資料表名稱與欄位名稱。

要實作的 stub：
[貼上方的 stub 程式碼]

我的 Schema (相關資料表)：
CREATE TABLE metro_schedules (
    schedule_id  VARCHAR(20) PRIMARY KEY,
    line         VARCHAR(5) NOT NULL,
    direction    VARCHAR(10),
    stops        JSONB NOT NULL   -- 有序的車站 ID 陣列，例如 ["MS01","MS02","MS09"]
);
```

**第三步 — AI 生成程式碼後，Alice 進行程式碼審查：**
- 它是否呼叫了該模組的 `_connect()`？ ✓ 或 ✗
- 它是否使用了 `RealDictCursor`？ ✓ 或 ✗
- 它是否回傳 `list[dict]` (而不是單一 row 物件)？ ✓ 或 ✗
- 它是查詢 `metro_schedules` 資料表嗎 (而不是 AI 自己編造的名字)？ ✓ 或 ✗

**第四步 — Alice 進行手動測試：**

```python
python

>>> from databases.relational.queries import query_metro_schedules
>>> result = query_metro_schedules("MS01", "MS09")
>>> print(type(result))      # 應為 <class 'list'>
>>> print(result)            # 應印出包含時刻表欄位的 dict 列表
>>> print(result[0].keys())  # 驗證回傳的 key 是否正確
```

---

### 範例 3：實作圖形資料庫查詢 Stub

**場景：** Bob 正在實作 `query_station_connections`。

**要實作的 stub** (`databases/graph/queries.py`)：

```python
def query_station_connections(station_id: str) -> list[dict]:
    """
    List all direct connections from a given station.

    Args:
        station_id: e.g. "MS01" or "NR01"
    """
    raise NotImplementedError("TODO: implement after designing your graph schema")
```

**Bob 的提示詞：**

```
[先貼上 AI_SESSION_CONTEXT.md]

請實作這個 Neo4j 查詢函式。規則：
- 使用模組中定義的 _driver() 輔助功能，並採用 example_count_nodes() 中展示的 driver.session() 區塊模式。
- 嚴格維持原本的函式簽章。
- 使用下方我們討論通過的圖形 Schema 節點標籤與關係類型。

要實作的 stub：
[貼上方的 stub 程式碼]

我們的圖形 Schema：
- 節點標籤：Station，屬性：{station_id, name, network}
- 關係類型：CONNECTS_TO，屬性：{line, travel_time_min}
```

**Bob 審查 AI 產出的程式碼：**
- 它是否呼叫了模組內的 `_driver()`？ ✓ 或 ✗
- 它是否正確寫了 `with driver.session() as session:`？ ✓ 或 ✗
- Cypher 語句中是否以 `Station` 作為節點標籤（節點不是編造的 `Node` 或 `stop`）？ ✓ 或 ✗
- 最終是否回傳了 `list[dict]`？ ✓ 或 ✗

**Bob 進行測試：**

```python
python

>>> from databases.graph.queries import query_station_connections
>>> result = query_station_connections("MS01")
>>> print(result)
>>> # 根據原始 JSON 數據，MS01 (Central Square) 連接至 MS05, MS02, MS06, MS07
>>> # 驗證查出的結果是否完全符合
```

---

### 範例 4：PR 審查與合併

**場景：** Alice 推送了 `feature/alice/metro-schedules-query` 分支並發起了 PR。

**Bob 擔任審查者 (Reviewer)，他檢查以下各點：**

1. 實作的函式定義是否與原本的 stub 簽章完全吻合？（參數沒有少、沒有變、回傳型態符合）
2. 查詢語法中使用的資料表與欄位名稱，是否與 `schema.sql` 嚴格對齊？
3. 是否採用了 `_connect()` 搭配 `RealDictCursor` 的標準程式碼模式？
4. 如果查無時刻表時，是否能優雅地處理空查詢結果？

**如果 Bob 發現了問題**，他在 GitHub 上留下審查評論：
> *"第 45 行：你的查詢用了 `stations`，但我們共享的 Schema 定義為 `metro_stations`。另外，回傳的 dict 漏掉了 `query_metro_fare` 接下來需要使用的 `departure_time` 欄位。"*

**Alice 修正程式碼**，將更新推送上去，並回覆該評論。

**當 Bob 批准 (Approve) 後**，Alice 將 PR 合併至 main：
- 在 GitHub 網頁上點擊 "Merge Pull Request"
- 在本地終端機更新你的工作分支：`git checkout main && git pull origin main`

---

### 範例 5：捕捉 AI 的命名不一致問題

**場景：** Carol 請 AI 協助實作 `query_national_rail_fare`。AI 給了她這樣的程式碼：

```python
cur.execute("SELECT * FROM fares WHERE route_id = %s", (schedule_id,))
```

但是，團隊設計的 Schema 中根本沒有一個叫 `fares` 的資料表 — 車票票價是根據 `national_rail_schedules` 中的 `base_fare_usd` 和 `per_stop_rate_usd` 經由公式動態計算出來的。

**如何發現這種錯誤：**
- 執行程式時，不是查不到資料（回傳 `[]`），就是直接噴出 `psycopg2.errors.UndefinedTable` 的資料表不存在錯誤。
- Carol 比對 AI 產出的程式碼與共享 Schema，發現了資料表不一致。

**解決方案：** Carol 重新整理了提示詞，將完整的 `CREATE TABLE` 語句餵給 AI，並附上嚴格的限制要求：
> *"切勿自行編造任何資料表或欄位名稱。請嚴格僅能使用下方 Schema 提供的結構進行實作。"*

**啟示：** 務必隨時把 Schema 當作 Prompt 的背景 context 提供給 AI。你不提供，AI 就會依照它自己的聯想力胡亂編造出看似合理但完全無法執行的名字。

---

## Part 4：實測有效的 AI 提示詞模板

這些提示詞模板是通用的，你可以在任何 AI 助理（Claude, Copilot, Cursor, Gemini 等）中直接使用。

### 模板 A：Schema 設計提案

```
我是一個正在進行資料庫專案開發的學生。以下是我們專案中
原始 JSON 模擬數據的範例 [檔案名稱]：

[貼上 1 到 3 個來自 train-mock-data/ 的 JSON 物件範例]

請幫我設計一個 PostgreSQL 的 Schema 資料表結構來存放這些資料。限制條件：
- 資料表與欄位名稱一律採用 snake_case 命名法
- ID 欄位請使用 VARCHAR 型態 (例如 "MS01", "NR_SCH01")
- 請勿將圖形關係(鄰近車站連接等)設計進 SQL 中 (因為我們有另外獨立的 Neo4j 圖形資料庫存放)
- 請在適合的欄位加上 PRIMARY KEY、NOT NULL 或 FOREIGN KEY 約束
- 請僅回傳 CREATE TABLE 語句本身，不需要多餘的文字說明

註：此 Schema 將會由三位隊員共同使用，在動工編寫查詢功能前，我們會先對資料表名稱達成共識。
```

### 模板 B：查詢功能實作

```
我正在實作一個基於 Python 與 PostgreSQL 的資料庫專案。
請嚴格遵循以下開發規則：
- 僅能使用下方 Schema 中定義的資料表與欄位名稱 — 切勿自行編造任何名稱
- 必須使用模組中已預先定義的 _connect() 輔助函式建立資料庫連線
- 必須採用 psycopg2.extras.RealDictCursor 游標 (使查詢結果以 dict 的型態回傳)
- 嚴格與 stub 的函式簽章對齊 — 請勿修改任何參數名稱與回傳資料型態
- 當查無任何符合的資料列時，必須回傳一個空列表 [] (而非回傳 None)
- 除非 docstring 中有特別要求錯誤捕獲，否則不需在程式碼中添加 try/except 結構

[在此貼上 AI_SESSION_CONTEXT.md 內容]

準備要實作的 stub 函式：
[在此貼上你要實作的 stub 函式定義與 docstring]

我們達共識的 Schema (僅提供此函式相關的表結構)：
[在此貼上此功能涉及的 CREATE TABLE 語句]
```

### 模板 C：程式碼 Code Review

```
請根據下方約定的合約與資料庫 Schema，審查這段 Python 查詢函式實作。
請為我檢查：
1. 它是否只使用了 Schema 中定義的資料表與欄位名稱？
2. 它回傳的結構與 keys 是否與 stub 要求的型態完全吻合？
3. 它是否遵循了 _connect() 與 RealDictCursor 的標準程式碼撰寫模式？
4. 當查無結果時，它是否能優雅地回傳空列表？
5. 是否存在 SQL 注入（SQL Injection）風險？（所有使用者輸入是否都有以 %s 參數化？）

請僅針對真正的邏輯與規格問題提出審查報告，不需要給予編碼風格(style)上的建議。

stub 定義 (合約規格)：
[貼上原始 stub 定義]

要審查的實作程式碼：
[貼上你寫完的程式碼]

專案 Schema：
[貼上相關的 CREATE TABLE 語句]
```

### 模板 D：問題排查與偵錯 (Debugging)

```
我的這段 Python 查詢函式目前執行報錯，請協助我排查並修復它。

報錯 Traceback 訊息：
[貼上完整的終端機錯誤報錯堆疊資訊]

我的實作程式碼：
[貼上出錯的函式程式碼]

專案 Schema：
[貼上相關的 CREATE TABLE 語句]

我預期這段程式要達成的效果：
[用一兩句話描述你的期望效果]
```

### 如何分享好用的提示詞？

當你在開發過程中，發現了某些能讓 AI 生成極高品質程式碼的提示詞技巧，請務必將它記錄在 `AI_SESSION_CONTEXT.md` 的 **Prompts log (提示詞紀錄)** 區塊中，讓隊友在接下來的工作中可以直接套用，避免做重複的嘗試。

---

## 附錄：每次開始開發前的自我檢查清單

請在每次啟動 AI 輔助開發工作階段前，照著這份清單確認一遍：

```
[ ] git checkout main && git pull origin main
[ ] 檢查 GitHub 上的 Pull Requests — 有沒有等待你協助 Code Review 的 PR？
[ ] 確認專案的 Docker 容器均已正常運行：docker compose ps
    (應顯示 postgres、neo4j、pgadmin 為 "Up" 狀態)
[ ] 確認 Python 虛擬環境 (.venv) 已成功啟用：python -c "import psycopg2; print('ok')"
[ ] 開啟 AI_SESSION_CONTEXT.md 並複製其完整內容貼到你的 AI 對話框作為起手式
[ ] 在團隊通訊管道知會隊友你即將動手開發的功能
```

如果 Docker 沒有啟動：請在專案根目錄執行 `docker compose up -d`。

如果你的虛擬環境尚未建立或啟動：請閱讀 README.md 中的 [Python 虛擬環境](README.md#python-virtual-environments) 說明章節。

---

## 快速參考指南

| 常見問題 | 該去哪裡尋找對應資訊？ |
|---|---|
| 我有哪些函式需要實作？ | 閱讀 `databases/relational/queries.py` 和 `databases/graph/queries.py` 中的 stubs 與 docstrings 說明 |
| 專案有哪些原始數據可供查詢？ | 查看 `train-mock-data/` 目錄 — 裡面有各種實體的 JSON 原始數據 |
| AI Agent 在調用我的函式時會帶入什麼參數？ | 閱讀 `skeleton/agent.py` — `TOOLS` 清單中詳細定義了傳遞參數規格 |
| 我該在哪裡設計 Relational Schema？ | 在 `databases/relational/schema.sql` 檔案中編寫建表語句（預設為空） |
| 每次開啟 AI 對話我該貼上什麼？ | 複製 `AI_SESSION_CONTEXT.md` 的內容貼給 AI 作為初始脈絡 |
| 通用的團隊協作規範與檢查表 | 參閱 `TEAM_PROJECT_GUIDE.md` 檔案 |
