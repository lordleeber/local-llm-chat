# Mac 端：架設 MLX API server

聊天網頁（見 [README.md](README.md)）連的是 Mac 上的 `mlx_lm.server`。以下是它的架設方式，換一台 Mac 也可以照著做。

## 架構

```
Win11 瀏覽器 (index.html)
      │  Tailscale
      ▼
Mac  100.103.191.79:8080  ── mlx_lm.server（在 tmux 裡手動啟動）
                              └─ AutisticAF/Huihui-Qwen3.8-27B-abliterated-mlx-4Bit
```

- 硬體：Apple Silicon MacBook Pro，24 GB 統一記憶體。
- 模型：Qwen3.8-27B 的 abliterated（去審查）版，由 huihui-ai 製作，MLX 4-bit，檔案約 15.1 GB，載入後峰值約 15.5 GB。
- 速度：生成約 16 tokens/秒，讀 prompt 約 30–50 tokens/秒。
- 對話快取：每個 token 約 0.065 MB（64 層裡只有 16 層是完整 attention），32K tokens 約 2.2 GB。
- 思考開關：用 `chat_template_kwargs: {"enable_thinking": false}` 關閉；Qwen3.8 不吃 `/no_think`。
- server 只監聽 Tailscale IP，不監聽區網或 `0.0.0.0`。`mlx_lm.server` 沒有任何認證，
  開在區網上等於同網段的人都能用。

## 1. 安裝 mlx-lm

用 [uv](https://docs.astral.sh/uv/) 建一個獨立的 venv：

```bash
mkdir -p ~/llm && cd ~/llm
uv venv --python /opt/homebrew/bin/python3.14 .venv
uv pip install --python .venv/bin/python -U mlx-lm
.venv/bin/python -c "import mlx_lm, mlx.core as mx; print(mlx_lm.__version__, mx.default_device())"
# 應該印出版本號和 Device(gpu, 0)
```

> 為什麼指定 Python 3.14：macOS 防火牆開著時，沒在允許清單裡的程式收不到外部連線，
> 系統會跳視窗詢問；遠端登入時沒人能點，連線就會被重置（`curl: (56) Connection reset by peer`）。
> 這台 Mac 的防火牆清單裡已經允許 Homebrew 的 Python 3.14，所以用它建 venv 就不需要 sudo。
> 改用其他 Python 時，要到 Mac 本機點一次允許，或執行：
> `sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add <python 的實際路徑> --unblockapp <同一路徑>`

## 2. 下載模型

```bash
.venv/bin/hf download AutisticAF/Huihui-Qwen3.8-27B-abliterated-mlx-4Bit
```

模型會存到 `~/.cache/huggingface/hub/`。

建議加上 `HF_HUB_DISABLE_XET=1`（例如 `HF_HUB_DISABLE_XET=1 .venv/bin/hf download ...`），
改用一般 HTTP 下載；xet 下載器曾經卡住不動。

如果下載卡住（`.incomplete` 檔的大小很久都不變），重跑 `hf download` 不一定會接續。
可以改用 `curl` 續傳卡住的分片，再用 sha256 驗證：

```bash
# 分片的 sha256 就是 HF 回應標頭 x-linked-etag 的值，也是 blobs/ 底下的檔名
curl -sIL https://huggingface.co/AutisticAF/Huihui-Qwen3.8-27B-abliterated-mlx-4Bit/resolve/main/model-00001-of-00003.safetensors | grep -i x-linked-etag

# 從已下載的部分接著下載
cp -c ~/.cache/huggingface/hub/models--AutisticAF--Huihui-Qwen3.8-27B-abliterated-mlx-4Bit/blobs/<sha>.*.incomplete shard1.part
curl -L -C - --retry 5 -o shard1.part https://huggingface.co/AutisticAF/Huihui-Qwen3.8-27B-abliterated-mlx-4Bit/resolve/main/model-00001-of-00003.safetensors
shasum -a 256 shard1.part   # 要和 x-linked-etag 一致

# 放回 HF cache
D=~/.cache/huggingface/hub/models--AutisticAF--Huihui-Qwen3.8-27B-abliterated-mlx-4Bit
mv shard1.part $D/blobs/<sha>
rm -f $D/blobs/*.incomplete
ln -s ../../blobs/<sha> $D/snapshots/*/model-00001-of-00003.safetensors
```

最後再跑一次 `hf download`，它會檢查並補上缺的檔案。

## 3. 用 tmux 啟動

用 tmux 手動開，關掉 SSH 也會繼續跑（IP 要換成自己的；Tailscale IP 可用 `tailscale ip -4` 查）：

```bash
mkdir -p ~/llm/logs
tmux new -s llm
HF_HUB_OFFLINE=1 ~/llm/.venv/bin/mlx_lm.server \
  --model AutisticAF/Huihui-Qwen3.8-27B-abliterated-mlx-4Bit \
  --host 100.103.191.79 --port 8080 \
  --chat-template-args '{"reasoning_effort":"medium"}' \
  --prompt-cache-bytes 1073741824 \
  2>&1 | tee -a ~/llm/logs/server.log
```

按 `Ctrl-b d` 離開 tmux，server 會在背景繼續跑；`tmux attach -t llm` 可以回去看。

- `HF_HUB_OFFLINE=1`：啟動時不連 Hugging Face 檢查更新，直接用本機的模型。
- `--chat-template-args {"reasoning_effort":"medium"}`：Qwen3.8 預設的思考程度是 `xhigh`，會在 system prompt 加上
  「仔細思考、驗證假設」的指示，常常想到用光 `max_tokens`，結果只有思考、沒有回答。`medium` 就是不加這段指示。
  請求裡帶的 `chat_template_kwargs` 會跟這個值合併；請求有指定 `reasoning_effort` 時，以請求的為準。
- `--prompt-cache-bytes 1073741824`：對話快取上限 1 GB，超過時丟掉最舊的。不設的話快取會一直長，
  最後 GPU 記憶體不足（見下方注意事項）。
- `tee -a`：畫面上看得到 log，同時寫進 `~/llm/logs/server.log`，方便之後 `grep`。

這樣開的 server 不會自動重啟：程式掛掉、Mac 重開機之後，都要手動再開一次。
Tailscale 還沒連上時綁定 IP 會失敗，等 Tailscale 連上再開。

## 4. 驗證

```bash
curl http://100.103.191.79:8080/v1/models
curl http://100.103.191.79:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"用一句話介紹你自己"}],"max_tokens":100,"chat_template_kwargs":{"enable_thinking":false}}'
```

第一個請求要多等約 30 秒載入模型。從另一台電腦測時，在瀏覽器開 `/v1/models` 看到 JSON 就代表連得到；
直接開 `/v1` 會顯示 not found，這是正常的。

## 日常維運

| 要做的事 | 指令 |
|---|---|
| 看 log（含每個請求的來源 IP） | `tail -f ~/llm/logs/server.log` |
| 回到 server 畫面 | `tmux attach -t llm`（`Ctrl-b d` 離開） |
| 看有沒有在跑 | `pgrep -fl mlx_lm.server` |
| 停止 | 在 tmux 裡按 `Ctrl-C` |
| 重啟（也會清掉對話快取） | 在 tmux 裡 `Ctrl-C`，再按 `↑` 和 Enter 重跑同一個指令 |
| 看記憶體 | `top -l 1 \| grep PhysMem`、`sysctl vm.swapusage` |

## 注意事項

- **記憶體**：24 GB 跑 15 GB 的模型很緊，Chrome、Slack 這類大程式最好關掉。server 會快取最近的對話來加快回應，快取會一直變大
  （27B 模型聊不到 10 則就到 1.7 GB），所以啟動指令裡設了 `--prompt-cache-bytes` 1 GB 上限。
  閒置太久時，macOS 可能把模型權重壓縮或寫進 swap，下一個請求會很慢；重啟 server 可以恢復。
- **GPU 記憶體不足（OOM）**：症狀是送出後一直沒有回答，server 仍回 HTTP 200，程式也沒有結束。
  log 裡會有 `[METAL] Command buffer execution failed: Insufficient Memory`，負責生成的執行緒已經死掉，
  之後每個請求都不會有回應，一定要重啟 server。檢查方式：`grep -i 'insufficient memory' ~/llm/logs/server.log`。
  曾在模型 15.1 GB 加上 1.68 GB 對話快取時發生；設了快取上限還是會發生的話，就要換更小的模型。
  Docker Desktop 的 VM 會另外佔約 3.5 GB，沒用到時建議關掉，並取消它的開機自動啟動。
- **Homebrew 升級 Python**：`brew upgrade` 把 Python 3.14 升到新的小版本後，路徑會改變，
  venv 可能壞掉，防火牆也可能重新擋住。遇到時重做第 1 步，並重新允許防火牆。
- **請求會切換模型**：`mlx_lm.server` 會照請求裡的 `model` 欄位載入模型，HF cache 裡有的模型都會被載入。
  客戶端還填著舊模型名稱的話，server 會換回舊模型，而且一次只放一個模型。
  `/v1/models` 會列出 cache 裡所有模型，不代表它們都已經載入。
- **換模型**：先 `hf download` 新模型，停掉 server，改啟動指令裡的 `--model` 再重開。
  刪掉不用的模型：`hf cache rm model/<repo id>`（可先加 `--dry-run` 預覽）。
- **不推薦 `mlx-community/Josiefied-Qwen3-14B-abliterated-v3-4bit`**：最初用的模型（9.2 GB、約 25 tok/s），
  實際使用起來不好用，已經換掉並從 cache 刪除，之後不要再換回來。
- **安全性**：只開在 Tailscale 上。不要改成 `--host 0.0.0.0`，除非前面另外加上有認證的 reverse proxy。
