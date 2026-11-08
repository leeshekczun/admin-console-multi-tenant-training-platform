# First core chain evidence

2026-11-08 14:39:48 Asia/Shanghai, local MySQL 9.3.0, database certificate_admin.

- POST /api/bulk-issue as alice@east.test, key first-chain-001, course_id 100: HTTP 200.
- Alex Lee and Morgan Park: issued, certificate IDs 3 and 4.
- Jamie Chen: skipped/incomplete. Taylor Smith: skipped/already_certified.
- GET /api/certificates: both issued certificates returned in the East scope.
- Direct SQL joined certificates/enrollments/learners/audit_events: certificates 1,2,3,4 each had exactly one ISSUED event.
- Seeded local dates: East 2026-01-11 00:30; West seed timestamp is the same UTC instant.
- Frontend Vite production build passed in 228ms.
- Browser evidence: browser-main.txt and browser-main.png (see their actual recorded outcome).

Environment corrections: port 8000 was occupied, so this application uses 8010.
npm certificate verification failed twice; user explicitly approved temporary npm_config_strict_ssl=false
for dependency installation. No persistent npm config changed. npm audit reported 4 findings
(1 moderate, 3 high) for the initial pinned dependency set; this is a recorded limitation pending review.
