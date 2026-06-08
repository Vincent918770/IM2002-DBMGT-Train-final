# TransitFlow 日常啟動與更新指南 (Daily Run & Update Guide)

本指南專為**測試人員**設計，說明在「第一次環境建置完成後」，每天日常測試或更新系統資料時所需的啟動指令。

---

## 💡 關鍵提醒：如果您使用本地 Ollama 模型

每次開機測試前，請確保 **Ollama 應用程式已在系統背景執行**（可在系統工作列中看到圖示）。如果您在 `.env` 中使用的是 Gemini，則可忽略此提醒。

---

## 💻 Windows 專區 (PowerShell)

### 1. 日常啟動 (每天測試只需執行這些)

如果您只是要啟動 AI 助理網頁，不需重新寫入資料：

1. **啟動 Docker 資料庫服務 (若未啟動)：**
   ```powershell
   docker compose up -d
   ```
2. **啟用虛擬環境並啟動網頁介面：**
   ```powershell
   .venv\Scripts\Activate.ps1
   python skeleton/ui.py
   ```
   啟動後，在瀏覽器打開終端機提示的網址 (例如 `http://localhost:7860`) 即可開始對談測試。

### 2. 資料更新與重置 (只有當 JSON 假資料修改時才執行)

如果您或團隊修改了 `train-mock-data/` 裡面的設定檔 (例如：新增了罰款政策、修改了票價或車站名稱)，請依序執行以下指令來重新寫入資料庫：

1. **確保已啟用虛擬環境：**
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
2. **更新關聯式資料庫 (PostgreSQL)：**
   ```powershell
   python skeleton/seed_postgres.py
   ```
3. **更新向量資料庫 (RAG 政策知識)：**
   ```powershell
   python skeleton/seed_vectors.py
   ```
4. **更新圖形資料庫 (Neo4j 路線)：**
   ```powershell
   python skeleton/seed_neo4j.py
   ```

---

## 🍎 macOS / Linux 專區 (Terminal)

### 1. 日常啟動 (每天測試只需執行這些)

如果您只是要啟動 AI 助理網頁，不需重新寫入資料：

1. **啟動 Docker 資料庫服務 (若未啟動)：**
   ```bash
   docker compose up -d
   ```
2. **啟用虛擬環境並啟動網頁介面：**
   ```bash
   source .venv/bin/activate
   python3 skeleton/ui.py
   ```
   啟動後，在瀏覽器打開終端機提示的網址 (例如 `http://localhost:7860`) 即可開始對談測試。

### 2. 資料更新與重置 (只有當 JSON 假資料修改時才執行)

如果您或團隊修改了 `train-mock-data/` 裡面的設定檔 (例如：新增了罰款政策、修改了票價或車站名稱)，請依序執行以下指令來重新寫入資料庫：

1. **確保已啟用虛擬環境：**
   ```bash
   source .venv/bin/activate
   ```
2. **更新關聯式資料庫 (PostgreSQL)：**
   ```bash
   python3 skeleton/seed_postgres.py
   ```
3. **更新向量資料庫 (RAG 政策知識)：**
   ```bash
   python3 skeleton/seed_vectors.py
   ```
4. **更新圖形資料庫 (Neo4j 路線)：**
   ```bash
   python3 skeleton/seed_neo4j.py
   ```

---

## 📋 測試人員快速驗證清單 (Verification Cheatsheet)

當您重新啟動或更新資料庫後，可以在系統的對話框中輸入以下問題，來驗證三個資料庫與 AI 是否成功串接運作：

1. **驗證 PostgreSQL 關聯式資料庫：**
   - _問題：_ "What national rail trains run from Central (NR01) to Stonehaven (NR05)?"
   - _預期結果：_ 應顯示正確的班車時刻與車次。
2. **驗證 Neo4j 圖形資料庫：**
   - _問題：_ "What is the fastest metro route from MS01 to MS14?"
   - _預期結果：_ 應顯示最佳路線規劃（包含轉乘資訊與乘車時間）。
3. **驗證 pgvector 向量搜尋 (RAG)：**
   - _問題：_ "My train was delayed 45 minutes — what compensation am I entitled to?"
   - _預期結果：_ AI 應能精確找出延遲賠償規定 (RF005)，回答您可以獲得 50% 的票價退款。
     llama3.1:8b --正確回答
