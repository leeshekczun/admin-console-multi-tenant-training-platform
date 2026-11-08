# Traceable decisions and corrections

Session IDs, native records, models and time ranges are in `session-index.csv` and
`../docs/ai-export-index.md`. All commit IDs below exist in the repository history.

| Decision | Session | Evidence | Related implementation/test commit |
| --- | --- | --- | --- |
| Accepted AI proposal: use MySQL transactions, uniqueness and a tenant row lock for certificate/audit consistency and idempotent retries | 01a1b9d1-2a96-7ee2-9c90-f7bdb17867f2 | ../verification/first-chain.md; ../verification/all-tests.txt | 332c315; 0e656c0 |
| Rejected/changed proposal: Docker was offered as an environment option; user required the already-running local MySQL instead | 01a1b9d1-2a96-7ee2-9c90-f7bdb17867f2 | Original approval in native log; MySQL 9.3.0 connection/initialization output; ../verification/clean-checkout-startup.txt | a19603b; 332c315 |
| Scope/design tradeoff: no reissue of revoked certificates, one certificate per enrollment; local-date sort with ascending certificate ID ties | 01a1b9d1-2a96-7ee2-9c90-f7bdb17867f2 | User approval in native log; ../verification/final-acceptance.json A6/A7; ../tests/test_api_units.py | 332c315; ff3b76f; 0e656c0 |
| Actual AI implementation error corrected: course lookup preceded existing-key fingerprint comparison, so a reused key with missing course returned 404 instead of 409 | Implementation 01a1b9d1-2a96-7ee2-9c90-f7bdb17867f2; independent review 01a1b9e6-95da-7513-a366-ad005f516447 | ../verification/key-misuse-before.txt; ../verification/key-misuse-after.txt; ../verification/key-misuse-http.txt; ../verification/final-acceptance.json A3 | Error present in ff3b76f; corrected in d4fe894; unit regression in 0e656c0 |
| Verification choice: use real MySQL with mock fault/timing wrappers, not a fake database as evidence of rollback/locking | 01a1b9d1-2a96-7ee2-9c90-f7bdb17867f2 | ../docs/test-coverage.md; ../verification/all-tests.txt | 0e656c0 |
| Dependency correction: initial audit reported Vue/Vite issues; update to audit-recommended compatible Vue 3.5.45 and Vite 6.4.5 | 01a1b9d1-2a96-7ee2-9c90-f7bdb17867f2 | ../verification/npm-audit.json (historical); clean install reports zero vulnerabilities in ../verification/clean-checkout-startup.txt | ff3b76f |
| Schedule tradeoff: user accepted product/tests, then explicitly authorized remaining evidence/documentation work outside the original time window | 01a1b9d1-2a96-7ee2-9c90-f7bdb17867f2 | Native user approval; ../docs/timing.md; ../verification/clean-checkout.md | Supplemental final documentation commit, identified in final handoff |

## Original failures and environment adjustments retained

- Port 8000 was already occupied; selected 8010 instead of disturbing another process.
- npm certificate validation failed twice. Stopped and asked; user approved a one-command
  `npm_config_strict_ssl=false` override. No permanent npm configuration was changed.
- CUA browser creation timed out. Bundled Playwright had no downloaded browser. Used installed Chrome.
- Startup check was strengthened to reject mismatched API/checker databases. A check against occupied
  8012 correctly rejected the other instance; a dedicated candidate on 18013 passed.
- Browser unit check initially selected the last generic status element, which could be the list's
  loading message; corrected the test locator to wait for the operation's COMPLETED heading.
- The first supplemental acceptance run overlapped another suite writing the same test database,
  invalidating a global-count assertion. This was the main agent's verification scheduling error.
  Failed output and JSON were retained as `../verification/final-acceptance-concurrent-interference.*`.
  The sequential rerun passed. README instructs users not to run mutating suites concurrently.
- The earlier single-session export index was incomplete once independent review had been used.
  Supplemental metadata discovery found the project branch-confirmation and independent-review logs;
  both original JSONL files are now separately exported/indexed. No review interaction is recreated.

## Commit history and evidence boundaries

- a19603b: approved delivery scope and initial native evidence.
- 332c315: first persisted core/browser workflow.
- ff3b76f: A1-A7 scripts, growth generator, browser evidence and dependency correction.
- d4fe894: missing-course idempotency-key conflict correction.
- 0e656c0: 17 API unit tests plus 5 controlled MySQL transaction tests, all passing.
- Supplemental final commit: documentation, multi-session export tooling and clean-clone/final regression
  evidence only. Its full hash/time is in the final handoff and git history; it is not self-inserted here.

No AI mistake or candidate action is fabricated for this log. Section 6 is not drafted, edited or
certified by the agent. Original user/source text is preserved in the native exports.
