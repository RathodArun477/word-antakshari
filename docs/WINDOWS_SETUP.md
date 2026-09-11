# Running Word Antakshari on Windows (instead of Linux)

Everything else in the project (code, `CONTRACT.md`, event logic) is
identical — only local setup/commands differ. Below is what actually changes.

---

## 1. Redis — the main difference

Redis has no official native Windows build. Pick one:

- **Easiest: WSL2.** Install WSL2, then inside it run Redis exactly as on
  Linux (`sudo apt install redis-server`, `sudo service redis-server start`).
  The Windows-side Python/Node processes can still connect to it at
  `localhost:6379` normally — WSL2 shares localhost with Windows by default.
- **Alternative: Docker Desktop.** `docker run -d -p 6379:6379 redis` — no
  WSL Linux environment needed, just Docker.
- **Alternative: Memurai** (a Windows-native Redis-compatible server, free
  tier available) if avoiding WSL/Docker entirely is preferred.

Whichever is chosen, confirm it's running with:
```
redis-cli ping
```
should return `PONG`, same as on Linux.

---

## 2. Python virtual environment

Creating the venv is the same:
```
python -m venv venv
```

**Activating it differs:**
- Linux: `source venv/bin/activate`
- Windows (Command Prompt): `venv\Scripts\activate.bat`
- Windows (PowerShell): `venv\Scripts\Activate.ps1`
  (if PowerShell blocks script execution, run once as admin:
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`)

Everything after activation (`pip install -r requirements.txt`,
`python run.py`) is identical.

---

## 3. Node.js / npm

Install Node via the official Windows installer from nodejs.org (or `nvm-windows`,
a separate tool from the Linux `nvm` used before — same idea, different
installer). Once installed, `npm install`, `npm run dev` are identical to Linux.

---

## 4. Killing stuck processes

Linux used `pkill -f app.py` / `pkill -f vite` during debugging. Windows
equivalents:
```
taskkill /F /IM python.exe
taskkill /F /IM node.exe
```
(kills ALL python/node processes — more blunt than `pkill -f`, since Windows
doesn't have an easy built-in "match by command line substring." If more
precision is needed, use Task Manager's "Details" tab to find the specific
PID and `taskkill /F /PID <pid>`.)

---

## 5. Checking what's using a port

Linux used `lsof -i :5000`. Windows equivalent:
```
netstat -ano | findstr :5000
```
This prints the PID in the last column — cross-reference with Task Manager
or `tasklist /FI "PID eq <pid>"` to identify the process, then `taskkill /F /PID <pid>`.

---

## 6. Starting Redis at boot (optional, dev convenience)

On Linux this was `sudo systemctl start redis-server`. There's no equivalent
single command on native Windows — if using WSL2, Redis needs to be started
manually inside the WSL terminal each session (or configured via WSL's own
init system), or if using Docker, `docker start <container-name>` after the
first `docker run`.

---

## 7. Everything else — no changes needed

- All Python code (Flask, Flask-SocketIO, Redis client, Gemini SDK) is
  cross-platform as written — nothing in this codebase uses Linux-specific
  paths or shell calls.
- All TypeScript/Vite/Tailwind frontend code is fully cross-platform.
- `.env` file handling via `python-dotenv` works identically.
- `pytest` test suite runs the same way: `python -m pytest tests/integration/test_game_flow.py -v`

---

## Quick reference — full startup sequence on Windows

```
# Terminal 1 — Redis (via WSL2 or Docker, started separately first)

# Terminal 2 — backend
cd backend
venv\Scripts\activate
python run.py

# Terminal 3 — frontend
cd frontend
npm run dev
```
