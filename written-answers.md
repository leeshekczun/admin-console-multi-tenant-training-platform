1. During a rolling update, old instances will continue to read and write to `display_name`, so deleting the column will cause all old instances to fail. New instances and old instances will write different columns, causing incorrect data.
   During a rollback, the old code will be unable to locate the deleted column, making a rollback impossible.
   We can try this process: Add a nullable `full_name` column. Update the application to dual write to both columns, and read from `full_name`, falling back to the old column if the new one is null, and backfill historical data.
   Once all instances are running the new version and the rollback window has passed, execute a separate deployment to stop dual write and delete the `display_name` column.

2. TTL only determines how long a stale value persists in the cache; it does not prevent process A from writing an outdated `ACTIVE` status back into the cache after process B has already revoked it.
   The window for error occurs during the interval between process A reading from the database and writing to the cache. Shortening the TTL still has this window.
   New design: Assume the cache key is `cert:{id}`, then
   Process A: After reading `ACTIVE` from the database, it performs `SET cert:{id} ACTIVE NX`.
   Process B: After committing the transaction, it performs `SET cert:{id} REVOKED`.
   If A’s SETNX succeeds first, followed by B’s SET so B overwrites the value to REVOKED. The cache remains correct.
   If B’s SET executes first, followed by A’s SETNX, since the key already exists, A will fail and does not overwrite the REVOKE value.

3. B increases to 2s the 100ms timeout request goes up to 3+1 = 4 calls, with every call hitting the timeout limit.
   This causes 400ms of latency/request. All 50 workers blocked waiting for B, then only 125 qps less than 1000qps.
   We can use seperate pool, and a circuit breaker for B.
