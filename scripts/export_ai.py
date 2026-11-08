"""Copy the native, complete chronological session log, never a curated summary."""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('source',type=Path,help='Original Codex rollout JSONL for this session')
parser.add_argument('--commits',default='See git history and ai/decision-log.md')
args=parser.parse_args()
raw=args.source.read_bytes()
# An active writer may have an incomplete final line; copy only complete native records.
raw=raw[:raw.rfind(b'\n')+1]
records=[json.loads(line) for line in raw.splitlines()]
meta=next(x['payload'] for x in records if x['type']=='session_meta')
session_id=meta['id']
models=sorted({x['payload'].get('model','') for x in records if x['type']=='turn_context'}-{''})
start=records[0]['timestamp']
end=records[-1]['timestamp']
target=Path('ai/sessions')/(session_id+'.jsonl')
target.parent.mkdir(parents=True,exist_ok=True)
target.write_bytes(raw)
with Path('ai/session-index.csv').open('w',newline='') as stream:
    writer=csv.writer(stream,lineterminator='\n')
    writer.writerow(['session_id','tool','model','started_at','ended_at','export_file','purpose','related_commits'])
    writer.writerow([session_id,'Codex',';'.join(models),start,end,str(target),'Planning; implementation; verification; documentation',args.commits])
Path('docs/ai-export-index.md').write_text(f'''# AI export index

Native Codex session: `{session_id}`. Model identifiers as recorded: `{';'.join(models)}`.
Time range: `{start}` through `{end}` (UTC, original timestamps).
Export file: [`{target}`](../{target}). Records: {len(records)}.
Session CSV: [`ai/session-index.csv`](../ai/session-index.csv).
Decisions: [`ai/decision-log.md`](../ai/decision-log.md).

This is a byte-for-byte snapshot of all complete native JSONL records at the cutoff,
including user messages, full assistant messages, original tool calls, commands, edits,
outputs, errors, configuration and timestamps as recorded by the tool. No curated prompt
list or screenshot is substituted. Original source text and native user messages retain
their original language; authored code, UI and documentation are English.
The source was parsed and the copied bytes verified identical. Native private reasoning
is encrypted by the tool; it is not decrypted or recreated. No inline autocomplete or
second AI session was used. Browser automation used CUA (timeout) and Playwright (success);
their calls and outputs are present in this session's log.

Exported at {datetime.now(timezone.utc).isoformat()}.
The snapshot cannot contain its own completed tool output or subsequent final commit/push
and handoff. Those actions are outside this cutoff and are disclosed here; git history
provides their timestamps. Refresh this script before the final documentation commit.
No real credentials or private third-party data were intentionally used; demo identities
and local filesystem paths are retained as evidence. This file does not certify Section 6.
''')
assert target.read_bytes()==raw
print(f'Export verified: {len(records)} native records, {start} -> {end}, {target}')
