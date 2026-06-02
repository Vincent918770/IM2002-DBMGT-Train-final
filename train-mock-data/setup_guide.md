# TransitFlow 測試人員專屬 Setup 與環境配置指南 (Setup & Configuration Guide)

本指南專為**測試人員**設計，旨在幫助您快速理解 TransitFlow 專案的安裝與初始化步驟，並提供詳細的指令說明，讓您能順利啟動本地測試環境。

---

## 💡 關鍵解答：我還需不需要安裝 Ollama？

**答案：是的，如果您使用預設的本地 AI 設定，您必須在執行指令前先安裝 Ollama！**

*   **為什麼需要？**
    *   Setup 步驟 5 中的指令 `ollama pull llama3.2:1b` 和 `ollama pull nomic-embed-text` 是呼叫 Ollama 本地軟體的命令。
    *   如果您的電腦沒有安裝並執行 Ollama，系統會出現 `command not found: ollama` 的錯誤，導致無法下載模型，AI 助理也將無法運作。
*   **如何安裝？**
    *   請至官方網站下載並完成安裝：[ollama.com/download](https://ollama.com/download)
    *   安裝後，請確保 **Ollama 應用程式已在背景執行**（可在系統工作列中看到圖示）。
*   **例外情況（不裝 Ollama 的方法）：**
    *   如果您不想在本地安裝 Ollama（因為它較佔電腦資源），您可以選擇使用 **Google Gemini API**。
    *   這樣做的話，您**完全不需要安裝 Ollama**，也不用執行 `ollama pull`。
    *   **如何切換成 Gemini：**
        1. 申請免費的 Gemini API Key：[aistudio.google.com](https://aistudio.google.com/app/apikey)
        2. 打開專案根目錄的 `.env` 檔案。
        3. 修改設定：將 `LLM_PROVIDER=ollama` 改成 `LLM_PROVIDER=gemini`。
        4. 新增您的 API Key：`GEMINI_API_KEY=您的金鑰`。
        5. 注意：因為 Gemini 的向量模型维度與 Ollama 不同，您需要將 `databases/relational/schema.sql` 中的 `embedding vector(768)` 改為 `embedding vector(3072)`，然後重新啟動 Docker 並重新 seed 向量資料庫。

---

## 🛠️ Setup 步驟整理與詳細釋義

以下是專案 Setup 的 7 大步驟，以及各個步驟對測試人員的實際意義：

### 1. 複製專案、建立虛擬環境與安裝 Python 套件
*   **指令：**
    *   **Windows (PowerShell):**
        ```powershell
        git clone https://github.com/NCUIM-Lab710-Teaching/IM2002-DBMGT-Train-final transitflow
        cd transitflow
        python -m venv .venv
        .venv\Scripts\Activate.ps1
        pip install -r requirements.txt
        ```
    *   **macOS / Linux:**
        ```bash
        git clone https://github.com/NCUIM-Lab710-Teaching/IM2002-DBMGT-Train-final transitflow
        cd transitflow
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
        ```
*   **步驟意思：**
    *   `git clone` & `cd`: 將專案的程式碼從 GitHub 下載到本機，並進入專案目錄。
    *   `python -m venv .venv`: 建立名為 `.venv` 的 **Python 虛擬環境**。這就像是為這個專案建立一個獨立的沙盒，避免專案的套件與您電腦上其他 Python 專案的套件發生版本衝突。
    *   `Activate.ps1` / `activate`: **啟用虛擬環境**。啟用後，您的終端機提示字元前會出現 `(.venv)`，代表您接下來所有的 Python 操作都在沙盒中進行。
    *   `pip install -r requirements.txt`: 安裝本專案執行所需的所有第三方套件（例如 Gradio 網頁介面、PostgreSQL 和 Neo4j 的資料庫連線驅動等）。

---

### 2. 建立環境變數設定檔
*   **指令：**
    *   **Windows / macOS / Linux (終端機通用):**
        ```bash
        cp .env.example .env
        ```
*   **步驟意思：**
    *   複製範本檔案 `.env.example` 並命名為 `.env`。
    *   `.env` 是存放環境變數與金鑰的本地檔案（不會被 Git 追蹤上傳）。測試人員可以在此調整使用的 LLM 提供者（Ollama 或 Gemini）或輸入 API 金鑰。

---

### 3. 啟動資料庫服務
*   **指令：**
    *   **終端機通用：**
        ```bash
        docker compose up -d
        ```
*   **步驟意思：**
    *   使用 Docker 在背景啟動專案所需的三個資料庫相關服務，測試人員不需手動在本機安裝與設定 PostgreSQL 或 Neo4j：
        1.  **PostgreSQL** (Port 5433): 存放結構化關聯式資料（如使用者、購票紀錄）與向量資料。
        2.  **Neo4j** (Port 7688): 存放地鐵與鐵路路線圖的圖形資料（用來計算最短路徑與路線規劃）。
        3.  **pgAdmin** (Port 5051): 提供網頁版的圖形化介面，讓測試人員可以登入並直接查看 PostgreSQL 內的資料表。
    *   可以使用 `docker compose ps` 指令來確認服務狀態是否均為 `healthy`（健康/正常運行中）。

---

### 4. 寫入關聯式資料庫初始資料 (Seed Relational Database)
*   **指令：**
    *   **Windows (PowerShell):**
        ```powershell
        python skeleton/seed_postgres.py
        ```
    *   **macOS / Linux:**
        ```bash
        python3 skeleton/seed_postgres.py
        ```
*   **步驟意思：**
    *   **「Seeding」的意思是將測試用假資料（Mock Data）寫入資料庫**。
    *   此步驟會讀取 `train-mock-data/` 資料夾下的 JSON 檔案（例如使用者、班表、座位圖、購票紀錄等），並寫入 PostgreSQL 資料庫中，以供測試時查詢。
    *   *註：在實際開發中，測試人員需要確認開發人員已在 `skeleton/seed_postgres.py` 中實現了匯入邏輯。*

---

### 5. 下載本地 AI 模型並初始化向量資料庫 (Seed Vector Database)
*   **指令：**
    *   **下載模型 (前提：已安裝並執行 Ollama 軟體)：**
        ```bash
        ollama pull llama3.2:1b        # 下載 1.3 GB 的對話模型 (Llama 3.2 1B)
        ollama pull nomic-embed-text   # 下載 274 MB 的向量嵌入模型
        ```
    *   **寫入向量資料 (Seed Vector):**
        *   **Windows (PowerShell):**
            ```powershell
            python skeleton/seed_vectors.py
            ```
        *   **macOS / Linux:**
            ```bash
            python3 skeleton/seed_vectors.py
            ```
*   **步驟意思：**
    *   `ollama pull`: 下載 AI 助理要用到的「大語言模型（LLM）」與「向量嵌入模型」。
    *   `seed_vectors.py`: 將 `train-mock-data/` 中的政策文件（如退票規定、攜帶自行車規範等文字）讀取出來，利用本地的嵌入模型將文字轉換為數學向量（Vector Embedding），並存入 PostgreSQL 的 pgvector 擴充功能中。
    *   這使得 AI 助理能夠進行 **RAG (檢索增強生成)**，也就是能夠理解使用者問題的「語意」，並找出最相關的規定回答。

---

### 6. 初始化圖形資料庫 (Seed Graph Database)
*   **指令：**
    *   **Windows (PowerShell):**
        ```powershell
        python skeleton/seed_neo4j.py
        ```
    *   **macOS / Linux:**
        ```bash
        python3 skeleton/seed_neo4j.py
        ```
*   **步驟意思：**
    *   執行 Cypher 語法（圖形資料庫專用查詢語言），將地鐵站、火車站等「節點（Nodes）」以及路線、轉乘等「關係/邊（Relationships/Edges）」建立在 Neo4j 資料庫中。
    *   這為測試 AI 助理規劃乘車路線、路徑尋找等功能做好了準備。

---

### 7. 啟動 AI 助理網頁介面
*   **指令：**
    *   **Windows (PowerShell):**
        ```powershell
        python skeleton/ui.py
        ```
    *   **macOS / Linux:**
        ```bash
        python3 skeleton/ui.py
        ```
*   **步驟意思：**
    *   啟動基於 Gradio 框架的網頁服務，並在終端機輸出網址（預設為 `http://localhost:7860`）。
    *   測試人員只要在瀏覽器打開此網址，即可與智慧鐵路助理進行交談測試，甚至可以在介面中點選登入、註冊，或開啟資料庫偵錯面板（Database Debug Panel）來觀察背後呼叫了哪些資料庫工具。

---

## 📋 測試人員快速驗證清單 (Verification Cheatsheet)

當您完成上述所有步驟後，可以在對話框中輸入以下問題，來驗證三個資料庫與 AI 是否成功串接運作：

1.  **驗證 PostgreSQL 關聯式資料庫：**
    *   *問題：* "What national rail trains run from Central (NR01) to Stonehaven (NR05)?"
    *   *預期結果：* 應顯示正確的班車時刻與車次。
2.  **驗證 Neo4j 圖形資料庫：**
    *   *問題：* "What is the fastest metro route from MS01 to MS14?"
    *   *預期結果：* 應顯示最佳路線規劃（包含轉乘資訊與乘車時間）。
3.  **驗證 pgvector 向量搜尋 (RAG)：**
    *   *問題：* "My train was delayed 45 minutes — what compensation am I entitled to?"
    *   *預期結果：* AI 應能精確找出延遲賠償規定 (RF005)，回答您可以獲得 50% 的票價退款。
