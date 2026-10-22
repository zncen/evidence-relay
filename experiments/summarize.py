"""Render counts directly from raw comparison JSON."""
import json
import sys
from pathlib import Path


def summarize(source):
    d = json.loads(source.read_text())
    lines = ['# 可重現比較結果', '', '此表由 summarize.py 從原始 JSON 產生；不是效能基準或普遍錯誤率估計。', '',
             '| 版本 | stale 漏報 | 未改檔誤報 | 長 verify 遺失事件 |', '| --- | --- | --- | --- |']
    for version in ['baseline', 'improved']:
        rows = [r for r in d['stale'] if r['version'] == version]
        long = next(r for r in d['long_verify'] if r['version'] == version)
        lines.append(f"| {version} | {sum(r['false_negative'] for r in rows)}/{sum(r['expected_stale'] for r in rows)} | {sum(r['false_positive'] for r in rows)}/{sum(not r['expected_stale'] for r in rows)} | {long['lost_acknowledged_events']} |")
    lines += ['', '| 版本 | 程序數 | 同一檔案 | 額外成功認領數 | 遺失已確認事件 | 非預期錯誤 | 平均秒 |', '| --- | --- | --- | --- | --- | --- | --- |']
    for version in ['baseline', 'improved']:
        for n in [2, 4, 8]:
            for same in [False, True]:
                rows = [r for r in d['races'] if r['version'] == version and r['processes'] == n and r['same_file'] == same]
                lines.append(f"| {version} | {n} | {same} | {sum(r['double_claims'] for r in rows)} | {sum(r['lost_acknowledged_events'] for r in rows)} | {sum(r['unexpected_errors'] for r in rows)} | {sum(r['seconds'] for r in rows)/len(rows):.3f} |")
    lines += ['', '| 版本 | 中斷位置 | 舊事件保留 | 未回覆前已提交 | 恢復命令 exit |', '| --- | --- | --- | --- | --- |']
    for r in d['interruptions']:
        lines.append(f"| {r['version']} | {r['phase']} replace | {r['prior_acknowledged_survives']} | {r['unacknowledged_commit_present']} | {r['recovery']['exit_code']} |")
    lines += ['', '環境與程式 SHA-256：', '', '```json', json.dumps(d['environment'], indent=2), '```', '']
    return '\n'.join(lines)

if __name__ == '__main__':
    source = Path(sys.argv[1])
    print(summarize(source))
