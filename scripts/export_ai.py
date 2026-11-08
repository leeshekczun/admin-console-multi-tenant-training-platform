"""Export original Codex project logs and maintain a multi-session index."""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('source',type=Path,nargs='+',help='Original project Codex rollout JSONL files')
parser.add_argument('--commits',required=True,help='Verified related commits, separated by semicolons')
parser.add_argument('--purpose',default='Planning; implementation; verification; documentation')
args=parser.parse_args()
index=Path('ai/session-index.csv')
existing={}
if index.exists():
    with index.open(newline='') as stream:
        existing={row['session_id']:row for row in csv.DictReader(stream)}
for source in args.source:
    raw=source.read_bytes()
    raw=raw[:raw.rfind(b'\n')+1]
    records=[json.loads(line) for line in raw.splitlines()]
    meta=next(x['payload'] for x in records if x['type']=='session_meta')
    if Path(meta['cwd']).resolve()!=Path.cwd().resolve():
        raise ValueError('Refusing to export a session from a different project')
    session_id=meta['id']
    models=sorted({x['payload'].get('model','') for x in records if x['type']=='turn_context'}-{''})
    target=Path('ai/sessions')/(session_id+'.jsonl')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(raw)
    assert target.read_bytes()==raw
    existing[session_id]={'session_id':session_id,'tool':'Codex','model':';'.join(models),
        'started_at':records[0]['timestamp'],'ended_at':records[-1]['timestamp'],
        'export_file':str(target),'purpose':args.purpose,'related_commits':args.commits}
    print(f'Export verified: {len(records)} native records, {target}, cutoff {records[-1]["timestamp"]}')
fields=['session_id','tool','model','started_at','ended_at','export_file','purpose','related_commits']
rows=sorted(existing.values(),key=lambda x:x['started_at'])
with index.open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
lines=['# AI export index','','All times below are UTC, preserving original native timestamps.','',
    '| Session | Tool / model | Time range | Native export | Purpose | Related commits |',
    '| --- | --- | --- | --- | --- | --- |']
for row in rows:
    export=Path(row['export_file'])
    records=[json.loads(line) for line in export.read_bytes().splitlines()]
    lines.append(f'| {row["session_id"]} | {row["tool"]} / {row["model"]} | {row["started_at"]} to {row["ended_at"]} | [{export.name}](../{export}) ({len(records)} records) | {row["purpose"]} | {row["related_commits"]} |')
lines.extend(['','Machine-readable index: [`ai/session-index.csv`](../ai/session-index.csv).',
    'Decisions and evidence: [`ai/decision-log.md`](../ai/decision-log.md).','',
    '## Export boundary and limitations','',
    'Each JSONL is a byte-for-byte snapshot of every complete native record at its cutoff. It includes',
    'user prompts, full assistant messages, tool calls, commands, edits, outputs, failures, configuration',
    'and timestamps/model identifiers as recorded by Codex. No curated transcript replaces native evidence.',
    'Private reasoning remains in its native encrypted representation; no decryption or reconstruction is performed.',
    'Only a partially written final line, if present, is excluded until the next refresh.',
    'Original user messages and source attachments retain their original language; authored code, UI and docs are English.','',
    'Tool use includes Codex shell/app tooling, CUA browser automation and Playwright/Chrome.',
    'The original tool calls/results, including failed attempts, are inside the native session logs.',
    'No separate inline autocomplete was used by this implementation agent. The independent reviewer',
    'session and the branch-confirmation session are separately indexed, rather than attributed to the main session.',
    'A scan of the local session metadata identified these project-bound sessions; other tools or sessions',
    'not recorded on this computer cannot be certified by this agent. The candidate must disclose any such use.','',
    'No real credentials or private third-party data were intentionally used. Demo identities, empty-password',
    'local test configuration and local paths remain as evidence. No broad redaction or interaction rewriting was applied.','',
    f'Index refreshed at {datetime.now(timezone.utc).isoformat()}.',
    'The active export cannot include its own completed output or the final commit/push and handoff.',
    'No code changes follow the final refresh; subsequent actions are packaging and handoff only.',
    'Their timestamps are available in git history. A reviewer requiring a final post-handoff native log',
    'can copy the original log afterward as a separate evidence attachment, without rewriting this cutoff.',
    'Section 6 independent written answers are outside AI assistance and are not certified here.',''])
Path('docs/ai-export-index.md').write_text('\n'.join(lines))
