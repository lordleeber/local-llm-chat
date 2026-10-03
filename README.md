# Local LLM Chat

在 Win11（或任何電腦）的瀏覽器裡，和 Mac 上 `mlx_lm.server` 跑的本地模型聊天的網頁介面。
只有一個 `index.html`，不需要安裝任何東西。

功能：串流回覆、多個對話（存在瀏覽器裡）、Markdown／程式碼／表格、Qwen3 思考過程可收合、
「不思考（/no_think）」開關、停止生成、顯示 tokens/秒。

## 使用方式（Windows）

前提：這台電腦已安裝並登入 Tailscale，和 Mac 在同一個 tailnet。

### 方法 A：直接開檔案（最簡單）

1. 下載這個 repo（GitHub 頁面 Code → Download ZIP）並解壓縮。
2. 雙擊 `index.html`，用 Edge 或 Chrome 開啟。
3. 左下角「設定」預設已填好：
   - API Base URL：`http://100.103.191.79:8080/v1`
   - 模型：`mlx-community/Josiefied-Qwen3-14B-abliterated-v3-4bit`
4. 按「測試連線」，看到 ✓ 就可以開始聊天。

`mlx_lm.server` 預設會送 CORS 標頭（`--allowed-origins` 預設 `*`），所以直接開檔案就能連。

### 方法 B：透過本機 proxy（方法 A 被瀏覽器擋住時）

如果瀏覽器出現 CORS 或「存取區域網路」之類的阻擋，改用這個方式，瀏覽器只會連 `localhost`，
再由本機的小程式轉送到 Mac。

1. 安裝 Python（`winget install Python.Python.3.12`，或從 python.org 下載，勾選 Add to PATH）。
2. 雙擊 `start-chat.bat`，會自動開啟 `http://localhost:8000/?proxy=1`。
3. 要關掉時，在黑色視窗按 Ctrl+C。

指令列用法：`python serve.py --proxy --target http://100.103.191.79:8080 --port 8000`

## 小提醒

- Mac 上的 server 重啟後，第一個請求要多等約 30 秒載入模型。
- 勾選「不思考」會在訊息結尾加上 `/no_think`，跳過思考，回得比較快。
- 對話記錄只存在這台電腦的瀏覽器裡（localStorage）。
- Markdown 顯示用到 jsDelivr CDN；離線時會改成純文字顯示，聊天功能不受影響。

## 現成的替代方案

也可以用 Chatbox、Open WebUI 等支援 OpenAI 相容 API 的客戶端，設定相同：
API Host `http://100.103.191.79:8080`（有些要填到 `/v1`）、API Key 隨便填（例如 `none`）、
模型 `mlx-community/Josiefied-Qwen3-14B-abliterated-v3-4bit`。
