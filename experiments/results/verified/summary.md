# 可重現比較結果

此表由 summarize.py 從原始 JSON 產生；不是效能基準或普遍錯誤率估計。

| 版本 | stale 漏報 | 未改檔誤報 | 長 verify 遺失事件 |
| --- | --- | --- | --- |
| baseline | 5/5 | 0/1 | 1 |
| improved | 0/5 | 0/1 | 0 |

| 版本 | 程序數 | 同一檔案 | 額外成功認領數 | 遺失已確認事件 | 非預期錯誤 | 平均秒 |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 2 | False | 0 | 3 | 1 | 0.127 |
| baseline | 2 | True | 2 | 2 | 1 | 0.120 |
| baseline | 4 | False | 0 | 7 | 2 | 0.151 |
| baseline | 4 | True | 6 | 6 | 3 | 0.150 |
| baseline | 8 | False | 0 | 11 | 10 | 0.191 |
| baseline | 8 | True | 13 | 15 | 8 | 0.196 |
| improved | 2 | False | 0 | 0 | 0 | 0.183 |
| improved | 2 | True | 0 | 0 | 0 | 0.178 |
| improved | 4 | False | 0 | 0 | 0 | 0.310 |
| improved | 4 | True | 0 | 0 | 0 | 0.286 |
| improved | 8 | False | 0 | 0 | 0 | 0.527 |
| improved | 8 | True | 0 | 0 | 0 | 0.481 |

| 版本 | 中斷位置 | 舊事件保留 | 未回覆前已提交 | 恢復命令 exit |
| --- | --- | --- | --- | --- |
| baseline | before replace | True | False | 0 |
| baseline | after replace | True | True | 0 |
| improved | before replace | True | False | 0 |
| improved | after replace | True | True | 0 |

環境與程式 SHA-256：

```json
{
  "recorded_at_utc": "2026-10-22T09:58:26.375128+00:00",
  "python": "3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0]",
  "platform": "Linux-7.0.0-38-generic-x86_64-with-glibc2.39",
  "cpu_count": 12,
  "baseline_commit": "00b72031d10cafab4ee7f0478e9246fc99bcf011",
  "checkout_commit": "84b95f37fdd589f796e5f6961c8001892d292431",
  "baseline_sha256": "7f314dba4608be30081cf1f536f7c20b3e79400644bd1feeca8965c768cc87fe",
  "improved_sha256": "99afb34d6ef6be230c376dd898d9664d7aeb29c13542c728d8828f6c42ad9005",
  "command": "/usr/bin/python3 experiments/run.py --repeats 3",
  "harness_sha256": {
    "run.py": "68bb4fb699958fc442a8de07e6272bb483bc2864befe9aae77b5413b6e1f1334",
    "worker.py": "60f416feb74e61b6ec35d11229e93de7d4343acc11e75242bbb048319e5ecdca"
  },
  "race_delay_seconds": 0.04,
  "repeats": 3
}
```
