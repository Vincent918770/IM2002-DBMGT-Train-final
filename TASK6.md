# Task 6 Extension: Lost Items and Penalties

This document outlines the modifications made to support the **Lost Items** and **Penalties** features as part of the optional Task 6 Extension.

This extension adds substantial new database code to track lost objects reported across the transit network, and manage penalty fines (such as fare evasion) for registered users. These backend capabilities are integrated with the AI agent to make LLM know the lost item and penalty system, though it conflict to STUDENT TASK in agent.py, allowing users to query their lost items and view outstanding penalties directly via the chat interface.

## Modified Files

Every file listed below includes the `# TASK 6 EXTENSION:` comment near the top, as required by the submission guidelines. Inline comments in both Chinese and English (for user 10LJN09) explain the database operations.

### 1. `databases/relational/schema.sql`

**Added Tables:**

- `lost_items`: Stores records of lost objects, including their location, status, and value.
- `penalties`: Stores user violation and fine records.

**Added Types:**

- `lost_item_status`: ENUM type (`'reported'`, `'found'`, `'claimed'`, `'police'`, `'donated'`, `'destroyed'`, `'love_umbrella'`).
- `penalty_status`: ENUM type (`'unpaid'`, `'paid'`, `'appealed'`).

### 2. `databases/relational/queries.py`

**Added Database Query Functions:**

- `query_lost_items(station_id, status)`: Queries lost items with optional filters.
- `execute_report_lost_item(...)`: Inserts a new lost item record.
- `execute_update_lost_item_status(...)`: Updates the status of an existing lost item.
- `query_lost_item(item_id)`: Fetches a specific lost item by its ID.
- `query_user_penalties(user_id)`: Retrieves all penalty records for a specific user.
- `execute_issue_penalty(...)`: Issues a new penalty to a user.
- `execute_pay_penalty(penalty_id)`: Marks a penalty as paid.

### 3. `skeleton/agent.py`

**Added AI Agent Tools:**

- `get_lost_item`: Added to `TOOLS` JSON schema. Enables the LLM to call `query_lost_item`.
- `get_user_penalties`: Added to `TOOLS` JSON schema. Enables the LLM to call `query_user_penalties`.
- `_execute_tool`: Added execution logic to route the `get_lost_item` and `get_user_penalties` tool names to their corresponding database functions.
