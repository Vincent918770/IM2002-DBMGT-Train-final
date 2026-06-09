Section 1—Entity-Relational Diagram

Section 2 — Normalisation Justification (正規化與設計決策)
1. 正規化設計決策 (符合 3NF)
在我們的資料庫設計中，我們刻意在 national_rail_bookings (台鐵訂單) 與 metro_travel_history (捷運乘車紀錄) 表格中落實了第三正規化 (3NF)。
設計決策： 雖然訂單表中儲存了起站與迄站的 ID (origin_station_id, destination_station_id)，但我們沒有將「車站名稱」儲存在訂單表中。
理論基礎與相依性： 這個決策基於Functional Dependency 原則。在 metro_stations 表格中，車站名稱功能相依於作為候選鍵的 station_id。
達成 3NF 的理由： 如果將車站名稱直接存在訂單表中，將產生Transitive Dependency，即 booking_id → origin_station_id → 車站名稱。透過將車站名稱移除，僅保留在 stations 表格中，我們消除了資料重複性，並成功防止了更新異常 (Update Anomaly)。
2. 反正規化設計取捨 (De-normalisation Trade-off)
儘管系統已高度正規化，但我們針對訂單表與乘車紀錄表中的 amount_usd (結帳金額) 欄位，刻意採取了反正規化 (De-normalisation) 的設計選擇。
設計決策： 在購票當下，系統即計算出最終的 amount_usd 並直接儲存 (Hardcode) 在訂單紀錄中，而非在每次查詢時透過 JOIN national_rail_fares 動態計算。
效能與一致性考量 (Trade-off Justification)：
歷史資料一致性： 票價會隨時間變動，若完全依賴 JOIN 動態計算，未來一旦票價調漲，過去歷史訂單的顯示金額就會出錯。
系統效能提升： 預先儲存結帳金額免去了未來財務稽核時高昂的多表聚合查詢成本，極大地提升了系統的讀取效能 (Performance)。
3. 密碼雜湊與安全性設計 (Password Hashing)
針對 users_confidential (機密資料) 表格，系統嚴禁儲存明碼密碼，並採用 Argon2id 演算法進行密碼雜湊處理。
演算法選擇 (為何捨棄 MD5 / SHA-1)： 傳統的 MD5 與 SHA-1 是為快速處理摘要而設計，極易遭受現代 GPU 的暴力破解攻擊。相反地，Argon2id 是一種記憶體密集型演算法，它引入了可配置的運算成本因子 (Cost factor) 及密鑰延展 (Key stretching) 技術。這會刻意拖慢運算過程，使硬體加速的暴力破解成本變得極為高昂且不切實際。
鹽值 (Salt) 的管理與防禦機制： 在雜湊前，系統會為每位使用者的密碼附加一串隨機且獨一無二的 Salt。其核心作用是防禦彩虹表攻擊 (Rainbow-table attacks)。
實例說明： 若「用戶 A」和「用戶 B」使用相同的弱密碼 "P@ssw0rd123"，在沒有 Salt 的情況下，資料庫會存入完全相同的雜湊值。但加入獨立 Salt 後 (Hash("P@ssw0rd123" + Salt_A) vs. Hash("P@ssw0rd123" + Salt_B))，即使密碼相同，最終存儲的雜湊結果也截然不同，從而使預先計算的彩虹表查詢失效。

Section 3—Graph Database Design Rationale 
Criterion 1: Explains what data is stored as nodes, as relationships, and as properties — with justification for each choice
Nodes儲存車站實體：
設計：使用Station作為基礎標籤，並根據所屬網路加上具體的MetroStation或 NationalRailStation標籤。
理由：車站是關聯圖中的點。採用多重標籤的策略可以在全域路徑搜尋時統一針對Station進行查詢，也能在需要區分網路時快速透過標籤過濾。
Relationship 儲存車站之間的連接與可達性：
設計： 建立了三種關聯類型：METRO_LINK、RAIL_LINK，以及跨網轉乘用的 INTERCHANGE_TO。
理由：將物理上的軌道與轉乘通道轉換成圖中的邊。區分這些關聯類型，可以讓路徑演算法在尋找時透過關聯類型來做網路隔離。
屬性儲存靜態資訊與邊權重：
節點屬性：存有station_id, name, network, lines等實體靜態描述。
關聯屬性：存有travel_time_min、fare、fare_first。
理由：在圖形資料庫中，將「時間」與「票價」設計為關聯使這些數值可以直接作為Dijkstra演算法計算最短時間或最低票價時的權重，大幅簡化運算邏輯。
Criterion 2: Argues why a graph database is better than a relational database for the routing use cases
最短路徑比較： 若要在關聯式資料庫中找圖形路徑，必須利用遞迴通用資料表運算式，每推進一站，就需要對資料表進行一次JOIN。當路徑長度增加時，會產生巨大的運算負擔與記憶體消耗，但如果是用圖形資料庫可以直接呼叫 APOC 的 apoc.algo.dijkstra 演算法，在記憶體中透過指標直接遍歷相鄰節點，尋找最短路徑的時間複雜度極低，效能不會隨著路徑跳數增加而顯著下降。
Criterion 3: Describes at least two query types and explains how the graph model enables them
查詢類型 1：最低票價路徑 (Cheapest Route)
描述： query_cheapest_route 函數允許使用者尋找兩站之間花費最少的路徑，甚至能動態切換票價等級。
模型支援方式： 由於我們的graph model將票價預先計算並儲存為關聯的屬性，這使得Cypher查詢可以直接將動態變數傳遞給Dijkstra演算法。
查詢類型 2：跨網轉乘路徑 (Cross-Network Interchange Path)
描述： query_interchange_path 函數用於找尋捷運換台鐵或台鐵換捷運的路線。
模型支援方式：graph model對於變動長度路徑的支援極佳。像是程式碼中使用了MATCH path =(start)- [:METRO_LINK|RAIL_LINK|INTERCHANGE_TO*1..15]-(end)這樣的語法尋找經過的站距為1到15的路徑，並透過WHERE ANY(r IN relationships(path) WHERE type(r) = 'INTERCHANGE_TO')過濾出其中包含跨網轉乘關聯的路徑。
Criterion 4: Discusses node identity: which property uniquely identifies nodes and why
識別屬性：選station_id 作為節點的唯一識別屬性。
理由：
唯一性： 在交通系統中，車站代碼（如 "MS01", "NR05"）是不會隨意變動的主鍵。相比之下，車站名稱可能會有重複或未來發生改名，並不適合做唯一識別。
查詢效能優化： 在 Neo4j中，建立UNIQUE Constraint同時會在該屬性上建立底層索引。如queries.py中所有的路徑查詢開頭都是 MATCH (start:Station {station_id: $origin_id})，利用 station_id 的索引可以讓資料庫更快的鎖定起始與終點節點，作為圖形遍歷的起點，確保查詢具備極佳的效能。
 
Section 4—Vector / RAG Design
Criterion 1: 嵌入資料與餘弦相似度 (What is Embedded & Why Cosine Similarity)
What is Embedded
在我們的 RAG系統架構中，存入向量資料庫的檔案有:booking_rules.json, penalty_fares.json,travel_policies.json, refund_policy.json我們將這些非結構化的文本儲存於向量資料庫中，使得讓 AI 能夠理解並精準引用。
Why Cosine Similarity is Appropriate
Cosine Similarity只計算兩個向量之間的夾角 (cos θ)，直接忽略了向量的長度差異，因此在利用向量空間中評估兩筆資料的相似度時，會具備長度獨立性 (Magnitude-independent)，可以更專注於衡量向量在空間中的方向相似度而不是文本長度。
 
Criterion 2: 完整的 RAG 系統管線 (The Full RAG Pipeline)
1. 查詢嵌入 (Query Embedding)
當使用者提出問題後，LLM呼叫嵌入模型並將該段文字轉換為向量表示
2. 相似度搜尋 (Similarity Search)
獲得查詢向量後，系統會將其傳遞給底層的向量資料庫進行檢索，在此階段資料庫會計算查詢向量與庫存政策文件向量之間的餘弦相似度 (Cosine Similarity)，並篩選出距離最近、語意最相關的條文段落。
3. 處理檢索出的文件 (Retrieved Documents)
為了避免將無用的雜訊或過長的文本塞爆LLM的視窗，系統對檢索回來的資料進行了結構化與截斷處理，確保傳遞給語言模型的資訊精簡且具備高相關性。
4. 提示詞組裝與生成回答 (LLM Prompt to Answer)
最後，系統會將這些檢索並處理好的文件，透過函式轉換為純文字格式，最後讓模型就會基於具體的政策條文，生成精準、具備事實根據的最終答案返回給使用者。
 
 
Criterion 3: 嵌入維度選擇與供應商切換風險 (Embedding Dimension & Provider Switch Consequence)
1. 系統實作的實際維度 (Actual Dimension Used)
在我們的專案實作中，我們選擇使用 Ollama 作為嵌入模型提供商。因此，當我們將政策文件（如 booking_rules.json, refund_policy.json）轉換為向量並存入pgvector時，系統所生成的向量實際維度為 768。
2. 切換供應商導致的災難性後果 (Consequence of Switching Providers After Seeding)
在向量資料庫完成Seeding後，如果中途將系統設定切換為其他供應商，將會發生維度不匹配的錯誤，導致整個 RAG 系統崩潰且索引完全無法使用。
發生原因：不同的嵌入模型架構會將文字映射到不同大小的空間中。Ollama產生的向量長度固定為 768 個浮點數；而 Gemini 產生的向量長度固定為 3072 個浮點數。在關聯式資料庫中，儲存向量的欄位在建立資料表時就必須宣告固定的維度，當供應商切換為Gemini後，若使用者輸入新的查詢，系統會呼叫 Gemini 生成一個 3072 維的查詢向量。接著，系統試圖拿這個 3072 維的查詢向量，去和資料庫裡已經存好的 768 維的政策文件向量計算餘弦相似度。這在數學上是無效的，資料庫會直接拋出型別錯誤並拒絕執行查詢。

Section 5—AI Tool Usage Evidence
範例一：
Context
在進行大眾運輸路網的圖形資料庫專案時，我寫了seed_neo4j.py，用於將捷運與國鐵車站的JSON原始資料匯入Neo4j資料庫中。為了確保資料在匯入時沒有任何遺漏，且圖形Schema的設計良好，我將程式碼與資料提供給AI進行審查，確認有沒有錯誤。
Prompt
我上傳的seed_neo4j.py檔案的目標是負責將兩份包含捷運與國鐵車站資料的JSON檔匯入Neo4j中。幫我仔細檢查程式碼與JSON檔，確認程式有沒有漏了JSON資料中的任何關鍵欄位或轉乘關聯
（附上 seed_neo4j.py 完整程式碼與2個JSON資料）
Outcome
AI告訴我經過它仔細比對後，我的程式碼並沒有漏掉任何關鍵資料。並告訴我一些值得注意的細節以及可以微調的建議，像是我在原本程式寫的Fallback Pairs部分是沒有必要的，可以直接刪除。
 
範例二：
Context
在專案初期階段，為了更了解圖形資料庫的特點及優點，因此我決定請AI協助我理解圖形資料庫的核心概念
Prompt
請幫我詳細解釋什麼是圖形資料庫及其核心組成要素，另外請具體對比它與傳統關聯式資料庫的差異與優勢。
Outcome
AI 詳細解釋了圖形資料庫是以「圖論」為基礎的 NoSQL，其核心結構由節點（Nodes）、邊（Edges）與屬性（Properties）組成。AI還有提供了一份精準的對比：傳統 RDBMS 依賴較消耗資源的JOIN，而圖形資料在查詢時則是透過直接走訪指標來運作，查詢時間只取決於走訪的節點數，不受總資料量影響。

範例三：
Context
在寫seed_postgres.py時，我請AI

Prompt
Outcome

Section 6 — Reflection & Trade-offs (系統反思與設計取捨)
1. 具體設計決策與考量 (Design Decisions)
決策一：中繼表採用「複合主鍵」 (Composite Primary Keys)
應用表格： metro_schedule_stops, national_rail_schedule_stops
具體考量 (Reasoning)： 我們放棄一般的自動遞增 ID，改以 (schedule_id, station_id) 作為複合主鍵。此決策旨在確保最高層級的資料完整性 (Data Integrity)。透過在資料庫底層 (Database level) 建立絕對的唯一性約束，能嚴格防止同一交通班次出現重複停靠站的異常，這比單純依賴應用程式層 (Application layer) 檢查更為可靠，徹底杜絕了髒資料 (Dirty Data) 的產生。
決策二：以客製化 VARCHAR 取代 SERIAL 與 UUID
應用表格： users (會員主鍵)
具體考量 (Reasoning)： 這是一項針對營運實務與系統效能的深度權衡 (Trade-off)：
捨棄 SERIAL： 連續數字易受 IDOR 資安攻擊（駭客易猜測他人 ID），且易與系統其他流水號混淆。
捨棄 UUID： 雖具安全性，但 36 字元毫無人類可讀性，導致極高的客服溝通成本；且其隨機性在每天數百萬筆的乘車紀錄中，會引發嚴重的 B-Tree 索引膨脹 (Index Bloat)，大幅拖垮查詢效能。
採用 varchar(50)： 允許儲存帶有前綴的短英數編號（如 MTR-A8492）。打破了規律性防範攻擊，保持了極佳的客服溝通便利性，且在海量資料的 JOIN 與儲存效能上遠優於 UUID。
2. 正式環境差異考量 (Production System Differences)
生產環境隱憂： 未導入資料庫連線池 (Connection Pooling) 會導致資源耗盡。
具體改變說明：
現狀與痛點： 目前開發階段應用程式直接與資料庫建立連線。但在真實大眾運輸生產環境中，面對上下班尖峰時刻的高併發 (High Concurrency) 請求（海量閘門與 App），PostgreSQL 直連會迅速耗盡記憶體並觸發最大連線數限制，導致資料庫癱瘓 (Connection exhaustion)。
上線架構變更： 正式環境絕對禁止直連，必須在架構中引入 Connection Pooler (例如 PgBouncer)。透過預先建立並管理一小組固定的底層連線，讓成千上萬的短暫外部請求「排隊共用」，這是確保系統在高負載下維持穩定的絕對關鍵。

Section 7—Optional Extension Bonus










