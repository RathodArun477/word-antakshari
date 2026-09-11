# Word Antakshari — Path to Production

Handoff doc. Everything below is a concrete, actionable fix or decision needed
to take this from "functionally working in development" to "production-ready
for ~1000 concurrent players," organized by priority. Pair this with
`PROJECT_STATUS.md` (what's built/broken/untested) and `CONTRACT.md` (the
event spec) — this doc is specifically about *closing the gap to production*.

---

## Priority 1 — Must fix before any real users touch this

### 1.1 Resolve the three active bugs
See `PROJECT_STATUS.md` Section 2 for full detail. In order of likely effort:
- **Rejoin voting** — broken, undiagnosed. Start by adding print/log
  statements at each step of `rejoin_handlers.py` (request received, vote
  started, each vote cast, tally result) and running one full manual test
  with backend logs open the whole time.
- **`life_lost` not reaching frontend** — backend confirmed correct, frontend
  code confirmed correct, but the served bundle doesn't contain it. Strongly
  suspect a stale/misconfigured dev server. First things to check: run
  `ps aux | grep vite` and confirm only one process; confirm the port in the
  terminal's startup message matches the browser's address bar exactly. If
  that doesn't resolve it, try a completely different browser or an
  incognito window to rule out browser-extension interference with the dev
  server's HMR/WebSocket connection.
- **Guessing phase behavior mismatch** — needs the original developer's
  detailed explanation of what's wrong before this can be diagnosed at all.

### 1.2 Revert debug-only config
`backend/config.py`: `CORRECT_STREAK_FOR_DOUBLE_POWERUP` is currently `1`
for testing. **Must be `5`** before anything resembling a real playtest.

### 1.3 Lock down CORS
`backend/app.py` currently has `cors_allowed_origins="*"` — fine for local
dev, a real security hole in production (allows any website to open a
socket connection to your backend). Before deploying:
```python
socketio.init_app(app, cors_allowed_origins=["https://your-actual-frontend-domain.com"])
```

### 1.4 Real `.env` on the deployment target
Confirm `GEMINI_API_KEY` is set via actual environment variables on
whatever hosts the backend — never commit `.env` itself (confirm it's in
`.gitignore`). Same for `REDIS_HOST`/`REDIS_PORT` if the production Redis
instance isn't `localhost`.

---

## Priority 2 — Needed for the "1000 concurrent players" target specifically

### 2.1 Move remaining in-memory state to Redis
`room_registry.py` and `sockets/registry.py` are already Redis-backed. Three
more in-memory dicts still aren't, and won't survive a server restart or
work correctly across multiple worker processes:
- `sockets/powerup_handlers.py` → `_pending_steal_offers`
- `sockets/challenge_handlers.py` → `_active_challenges`
- `sockets/rejoin_handlers.py` → `_active_votes`

**Solution:** same pattern already used for `GameRoom` — add `to_dict()`/
`from_dict()` methods (or just store as plain JSON-serializable dicts, since
these are simpler than `GameRoom`), and read/write through Redis with a
short TTL (these are short-lived by nature — a few minutes is plenty).

### 2.2 Horizontal scaling setup
Once running more than one backend worker process, Flask-SocketIO needs a
message queue so all workers can broadcast to the same rooms:
```python
socketio = SocketIO(async_mode="threading", message_queue="redis://localhost:6379/0")
```
Combined with a load balancer using **sticky sessions** (same client always
routes to the same worker) — WebSocket connections are stateful and can't be
freely load-balanced without this.

### 2.3 Load testing
Before trusting the 1000-player target, actually test it. Tools like
`locust` or a custom `python-socketio` client script that spins up hundreds
of simulated connections would validate real throughput — nothing in this
project has been tested past a handful of manual browser tabs.

---

## Priority 3 — Real gaps worth closing before calling this done

### 3.1 `is_host` should be an explicit field
Currently inferred by checking if a player is first in the `players` array
— fragile, and breaks the moment array ordering ever changes for any reason
(e.g. if a future feature reorders players for display). Add an
`is_host: bool` field to `PublicPlayerInfo` in the contract, set correctly
in `GameRoom.add_player`, and update the frontend to read it directly
instead of inferring.

### 3.2 Add a real `leave_room` event
Right now "leaving" is just disconnecting the socket and hoping the grace
period/kick flow handles it — works, but is indistinguishable from an
accidental disconnect, and other players see "X disconnected, waiting for
reconnect" instead of "X left." A dedicated `leave_room` event that
immediately eliminates the player and broadcasts a clear "X left the game"
message would be a meaningfully better experience for very little backend
work — it's most of what `handle_disconnect` already does, just triggered
explicitly and immediately instead of after a timeout.

### 3.3 Confirm the steal-challenge life-transfer design
`resolve_steal_challenge` currently gives the winner `+1` life on top of
the loser losing one (a literal transfer). This was an assumption made
early in the build and never explicitly reconfirmed. Worth a five-minute
conversation to confirm this is actually the intended design before
shipping it — it meaningfully affects steal's power level (a full life
swing is much stronger than a one-sided loss).

### 3.4 Send full player data in `player_joined`
Currently only sends `{player_id, player_name, current_player_count}` —
frontend has to guess/hardcode default values (3 lives, 0 score, not
eliminated) for a newly-joined player rather than the backend just sending
the real `PublicPlayerInfo` object. Small fix, removes a fragile assumption.

---

## Priority 4 — Testing that should exist before shipping

No automated test currently covers: skip, double-score (especially post
mid-session redesign), rejoin voting, the round-limit win condition, or 3
of the 4 steal minigames (only `math_flash` has a `pytest` test). Given how
many real bugs have been found purely through manual testing this session,
writing `pytest` integration tests for at least skip, double-score, and
rejoin would catch regressions automatically going forward rather than
relying entirely on manual re-testing every time something nearby changes.

Also worth adding: a test for the letter-chaining mechanic specifically
(submit a word, confirm the next `turn_start`'s `required_letter` matches
the last letter of what was submitted) — this is core gameplay logic that
currently has zero automated coverage.

---

## Priority 5 — Polish, explicitly deferred by prior agreement, but real

- Styling/animation pass across all screens (currently functional but
  visually bare — Tailwind is set up, just not used decoratively yet)
- `socket/events.ts` typed-wrapper layer — currently every screen calls
  `socket.emit`/`socket.on` directly with inline type casts. Not wrong, but
  a thin wrapper module would centralize event names as constants (avoiding
  typo risk on string literals like `"turn_resolved"`) and could be a good
  first task for getting oriented in the codebase.
- Connection-lost banner currently flashes briefly on every normal page
  load (cosmetic side effect of `autoConnect: false`) — not a bug, just
  worth a cleaner loading-state treatment during the polish pass.

---

## Priority 6 — Deployment (deliberately not decided yet)

Per earlier project discussion: deployment platform was intentionally left
undecided until the app was functionally complete. Given the Redis
dependency and the desire for real WebSocket support (not just HTTP),
whatever's chosen needs to support:
- A persistent Redis instance (managed Redis add-on, or self-hosted)
- Long-lived WebSocket connections (not all serverless/FaaS platforms
  support this well — worth confirming before committing to a platform)
- Environment variable configuration for secrets

This is worth a fresh conversation once Priority 1–3 are actually resolved,
rather than deciding now and potentially having to rework it.

---

## Suggested order of attack for whoever picks this up

1. Diagnose and fix the three Priority 1 bugs (rejoin, life_lost, guessing)
2. Revert the debug config value
3. Write the missing `pytest` coverage (Priority 4) — do this *while*
   fixing the bugs above, since a failing test is a much faster feedback
   loop than manual browser testing for each fix
4. Close the Priority 3 gaps (is_host, leave_room, life-transfer
   confirmation, player_joined data)
5. Redis-migrate the remaining in-memory state (2.1) and set up the
   message queue (2.2) together, since they're the same category of change
6. Load test (2.3)
7. Lock down CORS and confirm production env vars (1.3, 1.4)
8. Styling pass (Priority 5)
9. Pick a deployment platform and ship (Priority 6)
