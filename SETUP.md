# CampusPath — Frontend + Backend Setup

## Quick Start

### Backend (Python / FastAPI)
```bash
pip install fastapi uvicorn pydantic
uvicorn backend:app --reload --port 8000
```
API docs auto-generated at: http://localhost:8000/docs

### Frontend
Open `frontend.html` directly in any browser.
The frontend runs fully standalone (all algorithms are also implemented in JS).
To wire it to the backend, replace fetch calls with `http://localhost:8000/...`.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/courses` | All 20 courses |
| GET | `/courses/{code}` | Single course |
| POST | `/topo` | Run DFS / Kahn's / both |
| POST | `/planner` | Semester grouping |
| POST | `/student-plan` | Personalized remaining plan |
| POST | `/cycles` | Cycle detection with optional injected edges |
| POST | `/os/race` | Race condition demo (no locks) |
| POST | `/os/semaphore` | Counting semaphore demo |
| POST | `/os/rwlock` | Reader-Writer lock demo |
| GET | `/stats` | Graph statistics |

## Frontend Pages
- **Dashboard** — overview, run-all button, live terminal
- **Course Graph** — interactive draggable canvas, course registry table
- **Topo Sort** — DFS + Kahn's with op-count comparison
- **Semester Planner** — greedy credit-bin grouping
- **Race Condition** — animated interleaved thread log, corruption evidence
- **Semaphore** — live thread-state bars, blocking/unblocking animation
- **RW Lock** — reader/writer state timeline
- **My Plan** — personalized remaining course order
- **Cycle Detector** — inject back-edges, DFS white/grey/black tracing
