# Evidence Relay

Evidence Relay 是零第三方依賴的本機 Python CLI，記錄程式協作的檔案認領、驗證命令與交接證據。研究重點是：**程式修改後，先前成功的驗證還能不能當成目前證據？** 靜態 dashboard 使用虛構資料；本次可靠性實驗使用 CLI。

## 來源、AI 協作與本次貢獻

原專案公開來源：https://github.com/zncen/evidence-relay 。原版 commit 為 `00b7203`（完整值與 SHA-256 見實驗 JSON），本地 tag `baseline-00b7203` 保留基準。這次從既有 repository 建立獨立 clone，沒有搬走或覆蓋原專案未追蹤的示範影片／字幕。

這是使用者與 OpenAI Codex 協作的研究所作品集改善。Codex 協助設計、程式實作、回歸測試、實驗和文件；不宣稱使用者親手撰寫所有程式，也不把原型功能算成本次新增成果。新增貢獻：跨程序交易邊界、內容綁定證據、過期偵測、受限命令執行，以及可追溯的原版／改進版比較。MIT 授權沿用 LICENSE。此輪沒有寄信、操作交易服務、推送或發布。

## 一鍵重現與展示

需求：Linux／POSIX、本機檔案系統、Python 3.10+、Git。無需 pip 安裝、網路或任何服務憑證。

```bash
python3 experiments/reproduce.py
python3 demo/reliability_demo.py
```

第一個命令執行完整測試、從 Git 讀取原版程式、比較兩版並產生 `experiments/results/reproduced/{tests.txt,comparison.json,summary.md}`。最終程式的原始資料保留於 `experiments/results/verified/comparison.json`，摘要在 [summary.md](experiments/results/verified/summary.md)。初次與中途結果亦保留於 results 根目錄與 final 子目錄，各自記錄當時程式 hash；最終驗收請以 verified 為準。所有實驗目標 ledger 都位於自動清理的獨立暫存目錄；中斷實驗只終止自己啟動的 PID。

第二個命令建立可丟棄的 `answer.py`，執行 assert、顯示 `current / passed`，改檔後顯示 `stale / passed`，方便在兩分鐘內展示「歷史成功 ≠ 目前有效」。更多實驗定義見 [experiments/README.md](experiments/README.md)。

## CLI

```bash
python3 relay.py --root /path/to/project init --project 'My project'
python3 relay.py --root /path/to/project claim --agent codex \
  --task 'Implement parser' --files parser.py tests/test_parser.py
# 從 claim JSON 複製 id，下列 clm_ID 需替換成實際值
python3 relay.py --root /path/to/project verify --agent codex --claim-id clm_ID \
  --command 'python3 -m unittest discover -s tests -v' --timeout 60 \
  --require-output 'Ran 5 tests'
python3 relay.py --root /path/to/project handoff --agent codex --claim-id clm_ID --title 'Parser review'
python3 relay.py --root /path/to/project status
python3 relay.py --root /path/to/project release clm_ID
```

`--require-output` 是使用者明訂的文字接受條件，上例的測試數須符合真實專案；CLI 不會自動理解或證明測試涵蓋率。退出 0 但未指定條件，記為 `command_succeeded`；退出 0 且保留輸出包含指定字串，才記為 `passed`；缺字串是 `requirements_unmet`。任意命令可印出相同字串，因此這是明確的機械判準，不是安全認證或測試框架解析器。

`verify` 與 `handoff` 必須指定有效且由該 agent 持有的 `--claim-id`。記錄綁定認領 ID、任務、檔案邊界、執行前後內容 SHA-256。handoff 只取該認領的證據並重新算快照，`current` 與歷史命令 `status` 分開顯示；成功但內容變動的命令仍保留退出碼，CLI 退出 1、證據標為不穩定。舊版缺少快照的證據不會成為 current。

`verify` 預設 timeout 300 秒，可設 0 至 86400 間的秒數；超時退出 124，終止此命令專屬 process group。stdout/stderr 合併並持續排空，只保留最後 4000 原始 bytes（UTF-8 解碼替換無效字元），不在記憶體累積全部輸出；`output_truncated` 提示截斷，接受字串必須出現在保留尾端。

## 交易與快照取捨

沿用 `.evidence-relay/ledger.json`，以穩定的 `ledger.lock` 和 POSIX `flock` 包住完整讀取／檢查／寫入；每次使用唯一暫存檔，flush、fsync、replace，再 fsync 目錄。保留 JSON 可讀性與現有 dashboard 開檔能力，避免 SQLite 加上 JSON 匯出雙份狀態。代價是全 ledger 重寫與序列化；適合小型本機協作，不適合高吞吐服務、Windows 或未驗證的網路檔案系統。

長時間命令不持鎖：先鎖內讀認領／快照，再執行，結束重新持鎖讀最新 ledger、檢查認領和快照、附加事件。不同命令可並行，完成順序決定事件順序。中斷時 OS 釋放鎖；rename 前舊檔保留、之後新檔可見。若程序已提交但未回覆，結果可能已存在，必須先查 ledger，不能假定失敗就重試。強制中斷可留下無害的唯一 `.tmp` 檔或未索引 handoff；不宣稱 exactly-once，也未測斷電耐久性。`init --force` 明確重設歷史，勿用在運行中的工作流程。

快照保守涵蓋整棵工作樹，包括未提交、未追蹤及 ignored 檔、檔名與權限；只排除 `.git`、`.evidence-relay`、`__pycache__`。symlink 僅 hash 連結目標文字、不追隨外部內容。`.env` 正確保留前導點，不保存其內容於 ledger。全樹快照使無關檔案或測試產物改動也要求重驗，換取不漏掉未宣告依賴；大型工作樹有 I/O 成本。

限制：flock 是合作式協定，不防止手動改 ledger；檔案認領以正規化相對路徑作邊界，目錄與子檔視為重疊，但不解析 symlink 別名／大小寫別名。內容 hash 是前後檢查，不能偵測改後還原的 ABA，也不是整個檔案系統的不可變快照；快照期間或 handoff 產生後仍可能被外部編輯器修改。它不隔離測試命令、不驗證命令誠實性，亦不 hash 外部環境、套件、資料庫或 Git submodule 指向以外的依賴。輸出可能含敏感資料，ledger 預設不納入 Git。

## Dashboard 與原始展示

```bash
python3 -m http.server 8000
```

開啟 `http://localhost:8000/dashboard/`。它是原型的虛構 ledger 瀏覽器，本輪沒有更新成即時過期證據檢查器；要驗收新語意請用 CLI／新展示腳本。原始競賽展示構想保留於 DEMO.md，並不代表本次已提交競賽或發布。
