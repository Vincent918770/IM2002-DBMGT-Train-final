# RAG 測試與改進分析 (TestpgvectorRAG)

## 測試情境
**使用模型：** Llama 3.2 1B
**測試問題：** What is the company policy on travelling with a bicycle on national rail?

---

## 1. 理想的回覆 (The Ideal Response)
根據 `travel_policies.json` 的設定，最完美且準確的回覆應該包含以下三個層次：

The company policy for travelling with a bicycle on National Rail depends on the type of bicycle:
1. **Foldable Bicycles (摺疊自行車):** 
   - Permitted at all times (No peak hour restrictions).
   - Free of charge ($0.00 fee).
   - Must be stored in the overhead rack or at the end of the carriage (Max dimensions: 90 × 45 × 30 cm).
2. **Standard Bicycles (標準非摺疊自行車):**
   - Permitted but **NOT allowed during peak hours** (07:00–09:30 and 16:30–19:00, Monday to Friday).
   - A fee of $2.00 applies, payable at the platform gate (first-come-first-served, cannot be reserved).
   - Maximum of 2 bicycles per train, and they must be placed in designated bicycle bays.
3. **Electric Scooters (電動滑板車):**
   - Strictly not permitted on National Rail services.

---

## 2. 為何回答都不一樣且充滿錯誤？
你在測試中遇到了典型的「AI 幻覺 (Hallucination)」與「上下文理解錯誤」，主要由以下三個原因造成：

1. **模型參數規模太小 (Model Size)：** 
   Llama 3.2 1B 是一個只有 10 億參數的極小型模型。雖然它跑得快，但對於理解「階層式的 JSON 結構」非常吃力。當它看到 `"foldable_bicycles": {"peak_hour_restriction": false}` 和 `"standard_bicycles": {"peak_hour_restriction": true}` 時，小模型很容易把兩者的屬性「揉合」在一起，導致它在第一次回答時誤以為摺疊腳踏車在尖峰時段也被禁止。
2. **生成溫度設定 (Temperature)：** 
   每次回答都不一樣，甚至第三次直接回答「我沒有 2023 年以後的資料（這是 LLM 的預設推託之詞）」，這表示在呼叫 LLM 時，`temperature` 的數值可能設定得比較高（例如 0.7 或 0.8）。在做 RAG 知識庫問答時，高溫度會鼓勵模型「發揮創意」，從而忽視我們餵給它的 Vector Context。
3. **RAG 餵給 AI 的格式是 Raw JSON：**
   觀察 `seed_vectors.py`，你會發現我們是直接用 `json.dumps(data)` 把 JSON 原始碼塞給模型。大型模型（如 GPT-4 或 Gemini Pro）可以直接讀懂 JSON，但 1B 的小模型看到一堆大括號和英文屬性名，很容易迷失重點。

---

## 3. 該怎麼做才能改進答案品質？
要讓 TransitFlow 的 RAG 系統變聰明，可以採取以下四個改進方案（從最簡單到最進階）：

### 方案 A：調整系統參數 (最簡單)
在您的後端程式碼（呼叫 Llama 的地方），將 **Temperature** 設定為 `0` 或 `0.1`。
*   **效果：** 強制模型收斂，不准發揮創意，這能大幅減少每次回答不一樣的狀況，並降低第三種「我不知道」的幻覺機率。

### 方案 B：強化 System Prompt
在 RAG 的系統提示詞中，加入嚴格的解析規則：
> "You are a customer service assistant. Answer ONLY based on the provided JSON context. Pay close attention to boolean values like 'false' and 'true'. Do not use any outside knowledge."

### 方案 C：將 JSON 預處理為 Markdown (強烈建議)
既然小模型看不懂 JSON，我們可以在 `seed_vectors.py` 存入資料庫前，將 JSON 轉換為人類與小模型都容易閱讀的 Markdown 條列式文本。
*   **做法：** 不要用 `json.dumps`，而是寫一個小腳本將資料轉成文字。
*   **例如將 JSON 轉為：** "Policy for foldable bicycles: Permitted is true. Peak hour restriction is false. Fee is 0..."
*   **效果：** 1B 模型讀純文字的理解能力遠大於讀 JSON 的能力。

### 方案 D：更換較大的模型
如果硬體允許，將模型升級至 **Llama 3.1 8B** 或使用雲端的 **Gemini 1.5 Flash / GPT-4o-mini**。
*   **效果：** 這是治本的方法。8B 以上的模型具備極佳的 JSON 結構理解能力，上述的問題幾乎會瞬間消失。
