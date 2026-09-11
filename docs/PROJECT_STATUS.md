# Word Antakshari — Known Issues & Remaining Testing

Status snapshot as of this debugging session. Update as items get resolved.

---

## Active, unresolved bugs

### 1. `life_lost` event not reaching the frontend
- **Symptom:** Lives correctly decrease on the backend (confirmed via server logs — `life_lost` is emitted with correct data on both timeout and steal-loss), but the UI never visibly updates. Lives only show correctly after a full page refresh (which pulls fresh state via `reconnect_success`).
- **Ruled out:** Code itself is correct (listener exists, properly scoped, no syntax errors). Confirmed via DevTools Sources tab that the string `life_lost` does not appear in the actual bundle the browser is running, despite being present in the source file on disk.
- **Currently suspected cause:** Stale Vite dev server process — possibly running on a different port than the browser is actually connected to (similar root cause to the earlier `app.py`/`run.py` backend duplicate-process bug). Cache clear (`node_modules/.vite`, `dist`) did not resolve it.
- **Next step:** Confirm the exact port Vite prints on startup matches the browser's address bar exactly; check for multiple running `vite`/`node` processes via `ps aux`.

### 2. Rejoin voting not working correctly
- **Symptom:** Confirmed broken by manual testing. Specific failure mode not yet diagnosed — needs a fresh test pass with backend terminal output captured to identify where it breaks (request flow, vote casting, tally, or result application).

### 3. Guessing phase — not fully matching expectations
- User flagged this as "not totally what I expected" — full explanation pending. Do not assume the earlier fixes (stale-popup cleanup, leave-blank button, streak display) fully resolved the intended behavior until this is clarified and retested.

---

## Recently changed, needs fresh retest

### Double-score powerup
- Redesigned mid-session: originally "activate now, doubles your next word's score," changed to **instant** — clicking it immediately doubles current total score, consumed on use. Backend (`game/powerups.py`, `sockets/powerup_handlers.py`) and frontend (`powerups.ts`, new `double_score_activated` event) were rewritten for this. **Not yet retested** after the rewrite — first attempt was during the same period the `life_lost` bug was discovered, so it's unclear if double-score itself works or was masked by the same stale-bundle issue.

### Guess streak threshold
- `CORRECT_STREAK_FOR_DOUBLE_POWERUP` in `config.py` was temporarily set to `1` (from `5`) for easier debugging. **Must be reverted to `5` before considering the game done** — do not forget this before any final playtest or deployment.

---

## Confirmed working (as of last successful test)

- Room creation / join, correctly isolated per browser tab (after `sessionStorage` fix)
- Lobby waiting room with live player list
- Game start, turn flow, letter-chain mechanic (random start, chains off last letter, reroll on skip, carries over on timeout)
- Word validation (local wordlist, WordNet, Gemini fallback — after SDK migration to `google-genai`)
- Scoring formula
- Guessing phase mechanics: popup appears/disappears correctly, decoys now prefer same-starting-letter as the real word
- Skip powerup (after `data=None` signature fix)
- Steal powerup — all 4 challenge types (reaction_race, unscramble, fastest_word, math_flash), using correct-answer-wins-immediately logic (not first-submission-regardless)

---

## Not yet tested at all

- Round-limit win condition (Rounds mode) — need a full game to actually hit the round cap
- Mid-game page refresh / reconnect restoring correct turn state (timer, required letter, whose turn)
- Disconnect grace period (10–15s window) and subsequent kick after it expires
- Full playthrough of Rounds mode end-to-end (only Endless mode has been meaningfully tested so far)

---

## Known design gaps / fragile spots (not blocking, but worth fixing eventually)

- **`isHost` is inferred by array position** (first player in `room.players`), not an explicit backend field. Works today because `add_player` always inserts host first, but is fragile.
- **No `leave_room` event exists in the contract.** The "Leave Game" button disconnects the socket and resets local state, but the backend has no explicit signal that a player intentionally left — it only learns via the normal disconnect → grace period → kick flow, same as an accidental disconnect.
- **Steal challenge winner gains a life, not just the loser losing one** (`winner.lives += 1` in `resolve_steal_challenge`). This was an assumption made early on and never explicitly confirmed — worth double-checking this is the intended design.
- **`player_joined` event still doesn't carry full player data** — frontend patches around this by manually constructing a `PublicPlayerInfo` with default values (3 lives, 0 score) for any newly-joined player, which works but relies on knowing those defaults rather than the backend just sending them.

---

## Deferred by explicit decision (not bugs)

- All styling, animations, visual polish
- `socket/events.ts` typed-wrapper refactor (currently calling `socket.emit`/`socket.on` directly with inline types)
- Final `CONTRACT.md` / `FOLDER_STRUCTURE.md` update — needs to reflect: `required_letter` mechanic, `life_lost` event, `double_score_activated` event, decoy same-letter-first behavior, corrected steal-challenge resolution semantics, and the reconnect-state-restoration fields added to `RoomStateSnapshot`
