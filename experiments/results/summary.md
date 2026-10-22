# 可重現比較結果

此表由 summarize.py 從原始 JSON 產生；不是效能基準或普遍錯誤率估計。

| 版本 | stale 漏報 | 未改檔誤報 | 長 verify 遺失事件 |
| --- | --- | --- | --- |
| baseline | 5/5 | 0/1 | 1 |
| improved | 0/5 | 0/1 | 0 |

| 版本 | 程序數 | 同一檔案 | 額外成功認領數 | 遺失已確認事件 | 非預期錯誤 | 平均秒 |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 2 | False | 0 | 3 | 0 | 0.124 |
| baseline | 2 | True | 0 | 1 | 3 | 0.125 |
| baseline | 4 | False | 0 | 6 | 3 | 0.156 |
| baseline | 4 | True | 7 | 9 | 2 | 0.156 |
| baseline | 8 | False | 0 | 10 | 13 | 0.202 |
| baseline | 8 | True | 12 | 12 | 9 | 0.213 |
| improved | 2 | False | 0 | 0 | 0 | 0.224 |
| improved | 2 | True | 0 | 0 | 0 | 0.209 |
| improved | 4 | False | 0 | 0 | 0 | 0.313 |
| improved | 4 | True | 0 | 0 | 0 | 0.295 |
| improved | 8 | False | 0 | 0 | 0 | 0.531 |
| improved | 8 | True | 0 | 0 | 0 | 0.483 |

| 版本 | 中斷位置 | 舊事件保留 | 未回覆前已提交 | 恢復命令 exit |
| --- | --- | --- | --- | --- |
| baseline | before replace | True | False | 0 |
| baseline | after replace | True | True | 0 |
| improved | before replace | True | False | 0 |
| improved | after replace | True | True | 0 |

環境與程式 SHA-256：

```json
{
  "python": "3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0]",
  "platform": "Linux-7.0.0-38-generic-x86_64-with-glibc2.39",
  "cpu_count": 12,
  "baseline_commit": "00b72031d10cafab4ee7f0478e9246fc99bcf011",
  "baseline_sha256": "7f314dba4608be30081cf1f536f7c20b3e79400644bd1feeca8965c768cc87fe",
  "improved_sha256": "c96d8e17c17a6d61053c920f0ccb903dd90f8070e8380a0a6fb8beddaa286b17",
  "command": "/usr/bin/python3 experiments/run.py --repeats 3",
  "race_delay_seconds": 0.04,
  "repeats": 3
}
```

