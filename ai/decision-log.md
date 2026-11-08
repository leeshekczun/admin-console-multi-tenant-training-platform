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

- Verification milestone after 332c315: A1-A7 passed in the isolated test database. See
  verification/acceptance.json for exact results and export timings. Additional UI evidence is in
  verification/browser-scenarios.txt. User requested a pause for manual acceptance before further work.
- Dependency correction: initial audit found Vue/Vite issues; applied recommended compatible fixes
  Vue 3.5.45 and Vite 6.4.5. Installation reported zero vulnerabilities and production build passed.
- Startup database identity is checked before creating isolated records. A check against occupied
  port 8012 correctly rejected a database mismatch; a dedicated candidate on 18013 passed.
  Evidence: verification/startup-candidate.txt. Related milestone commit: see next git commit after 332c315.
