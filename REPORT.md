# EvidenceRelay 改善驗收紀錄

完成位置：本次工作區的 `evidence-relay/` 獨立 clone。既有 `/home/zncen/projects/evidence-relay` 未套用改動，原本未追蹤的 demo MP4/SRT 原樣保留。未推送、未發布、未寄信、未操作交易服務、未改其他作品。

## 追溯

- 原版：`00b72031d10cafab4ee7f0478e9246fc99bcf011`；本地 tag `baseline-00b7203`。
- 先寫回歸測試的 commit：`8c1ae70`；紅燈原始輸出 `experiments/results/baseline-regressions.txt`。
- 最終程式與實驗腳本 commit：`84b95f37fdd589f796e5f6961c8001892d292431`。
- `experiments/results/verified/` 為上述程式版本的驗收結果；JSON 的程式與 harness SHA-256 已重新核對。
- 本次新增 commit 使用 `Codex AI collaborator <codex@localhost>` 作者標記，沒有冒用使用者姓名。

## 變更檔案

`relay.py`：POSIX flock 的完整 ledger 交易、唯一暫存檔和 fsync、UUID、長 verify 結束重讀 ledger、明確認領與任務綁定、前後全工作樹 hash、handoff 重新檢查 freshness、`.env` 正規化、目錄子路徑衝突、timeout 及有界輸出。

`tests/test_regressions.py`、`tests/test_safety.py`、`tests/test_relay.py`：保留原整合測試並適配新 CLI；新增 stale、認領隔離、並行事件、長 verify、timeout、接受條件、symlink／權限等回歸測試。

`experiments/{run.py,worker.py,reproduce.py,summarize.py,README.md}`：隔離比較、排程與中斷注入、一鍵重現及原始結果摘要；資料在 `experiments/results/`。

`demo/reliability_demo.py`：可執行、暫存工作區的改檔前後展示。`README.md`、`DEMO.md`：來源、AI 協作、執行方式、實驗定義及限制。

## 驗收

`python3 experiments/reproduce.py --output experiments/results/verified` 成功。完整 11 項測試通過（3.334 秒，見 verified/tests.txt）；展示腳本成功，輸出保留於 results/demo.txt。已檢視程式、測試與文件 diff，`git diff --check` 通過。

| 最終控制式比較 | 原版 | 改進版 |
| --- | --- | --- |
| stale／錯任務證據漏報 | 5/5 | 0/5 |
| 未改檔誤報 | 0/1 | 0/1 |
| 2/4/8 程序、各同檔／不同檔、各三輪：額外成功認領總數 | 21 | 0 |
| 上述競爭：遺失已確認事件總數 | 44 | 0 |
| 上述競爭：非預期錯誤總數 | 25 | 0 |
| 長 verify 期間新增 claim 後遺失事件 | 1 | 0 |
| replace 前／後中斷：保留先前已確認事件 | 2/2 | 2/2 |

數字只描述合成 fixture，不能外推實際錯誤率。競爭以兩版同樣的 40ms 讀後延遲放大視窗。平均 wall clock、每個退出碼與 ledger 見 [verified/summary.md](experiments/results/verified/summary.md) 及 [原始 JSON](experiments/results/verified/comparison.json)。序列化增加耗時，且原版有操作失敗，不能當作等量成功工作速度比較。中斷案例兩版均成功，不宣稱改善。

## 展示與剩餘限制

在 repository 執行 `python3 demo/reliability_demo.py`，先看到 `current / passed`，改檔後看到 `stale / passed`；接著開啟 verified/summary.md，說明為何歷史退出 0 不代表現在可引用。

沒有未解授權或環境阻擋。共用協作板原先受沙箱唯讀限制，後以核准操作完成登記；`rg` 不存在，改用 grep/find。checkout 沒有 `.agents/skills`。原始 dashboard 仍為虛構資料瀏覽器，沒有新增即時 freshness 判斷。

已知限制：POSIX 本機合作式鎖；全樹 hash 有成本且無關檔案變動也會失效；前後快照不能偵測 ABA 或阻止快照後外部修改；不涵蓋外部依賴；文字接受條件不是測試框架語意或涵蓋率證明；尚未驗證斷電耐久性／NFS／Windows；replace 後未回覆的提交仍可能存在，沒有 exactly-once 自動重試保證。完整取捨見 README。
