# 實驗設計與重現

```bash
python3 experiments/reproduce.py
# 或僅重跑比較，保留輸出至指定位置
python3 experiments/run.py --output /tmp/relay-comparison.json --repeats 3
python3 experiments/summarize.py /tmp/relay-comparison.json
```

原版直接取本 repository `git show 00b7203:relay.py`；不下載、不修改基準程式。改進版讀目前 `relay.py`。JSON 保存程式 hash、Python／OS、CPU 數、命令、每個子程序退出碼、stdout/stderr、最終 ledger 與耗時。最終驗收結果 `results/verified/comparison.json`；初次／中途結果 `results/comparison.json` 與 `results/final/` 也保留，請依各檔 hash 區分版本；`results/baseline-regressions.txt` 是實作前的紅燈測試，其中缺介面錯誤屬回歸契約，不拿來計算 stale 偵測率。摘要由 `summarize.py` 自動生成。

## stale evidence

各自獨立 fixture：不改檔、修改已提交檔、修改未追蹤檔、修改 `.env`、命令自己改檔、另一任務的交接。已提交案例會先在隔離 Git repo 建立 fixture commit，之後只改工作樹、不改 HEAD。五個後者預期不可引用舊成功證據，第一個預期仍可引用。

原版接受定義為實際產生的 handoff 含 `- passed:`；改進版為該任務 handoff 有 `current` 且 `passed`。這是在使用者交接流程上比較可接受的歷史證據，不聲稱原版有不存在的 stale API。另一任務案例測任務錯配，與四種內容變動分開記錄。

漏報 FN = 預期不可引用卻接受；誤報 FP = 未改檔卻不接受。分母分別是 5、1，均只有單次情境測試，不能外推生產環境錯誤率、統計信賴區間或精確率。本設計沒有負案例大量抽樣；全樹策略對無關檔案的保守失效不算本 fixture 的 FP，也不宣稱已解決。

## 多程序競爭

兩版均以真實獨立程序，2／4／8 程序各跑同檔與不同檔、每組三輪。外部 readiness barrier 同時放行。worker 唯一插樁是在 `load_ledger` 讀取完成後延遲 40ms，兩版相同，用來放大交易視窗；改進版仍遵守其實際鎖。未修改衝突判斷、寫入或例外，基準的共享 `.tmp` 衝突原樣保留 stdout/stderr。此為控制式競爭重現，不是未插樁吞吐量基準。

- 額外成功認領數：同一檔案所有返回成功的認領數減一，下限零，包含曾對外宣稱成功但最終遺失的認領。
- 遺失已確認事件：成功回覆的 claim ID 未出現在最終 ledger。失敗回覆卻曾寫入的事件不算已確認，也不直接推定全無副作用。
- 非預期錯誤：返回非 0、非衝突碼 2；共享暫存檔錯誤獨立列示，不能把操作失敗當作「沒有雙重認領所以安全」。
- 時間：每輪從啟動程序到收完結果的 wall clock 平均，含 Python 啟動、barrier、人工延遲與 fsync；沒有速度提升主張。原版操作失敗比例不同，不能公平解讀為等量成功工作的速度比較。

另一個無 race 插樁案例把 verify 卡在實際命令外部 gate，期間新增另一個 claim，再讓命令結束；直接量測新事件是否被舊 ledger 覆蓋。

## 程序中斷

worker 在真實 `os.replace` 前或後寫 marker，父程序確認 marker 後只 SIGKILL 該 worker。檢查 JSON 能否解析、舊已確認事件有否保留、新未確認事件是否存在，並執行另一 claim 證明可恢復。這是精確注入的程序中斷，不是磁碟故障、系統斷電、任意時點的蒙地卡羅抽樣或完整 crash-consistency 證明。

兩版在本次中斷案例都能保住舊事件；replace 後未回覆的事件也都可能已提交。因此此欄沒有可宣稱的改善數值。新版本保證合作式 ledger 交易不交錯、鎖隨死亡釋放，並非具備自動重試去重或 exactly-once。

## 解讀與界線

結果只涵蓋這些合成情境。沒有使用真實客戶資料、其他專案、交易服務或網路。實驗只在獨立暫存工作區建立假檔案（`.env` 亦為假資料），process kill 指定自己建立的 PID。ledger 格式、顯示語意與接受條件不同的部分已在上方定義；沒有虛構原版不具備的驗證能力，也沒有將機械輸出字串比對說成測試正確性的證明。
