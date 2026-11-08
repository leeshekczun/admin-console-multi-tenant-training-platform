# Decisions

All entries refer to session 01a1b9d1-2a96-7ee2-9c90-f7bdb17867f2.
- Accepted: user approved MySQL transaction/unique constraint design and core-first slices.
- Corrected: user required local MySQL instead of the proposed Docker option. MySQL 9.3.0 confirmed.
- Tradeoff: no revoked certificate reissue; preserve one certificate per enrollment. User confirmed before implementation.
Verification evidence and related commits will be appended as exercised. No AI error is invented.

- Environment correction: port 8000 was in use; use 8010. Native log records failed bind and restart.
- npm certificate attempts failed; stopped and asked the user. User approved temporary
  npm_config_strict_ssl=false for this install only; no persistent configuration change.
- Browser tool timed out and bundled Playwright had no downloaded browser; used existing Chrome.
  First chain evidence: verification/first-chain.md and verification/browser-main.txt.
