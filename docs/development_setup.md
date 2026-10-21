# Development Setup

Local environment, conventions and gotchas. Read this before your first commit.

---

## 1. Prerequisites

| Tool | Version | Required | Notes |
|---|---|---|---|
| Python | 3.11 | yes | `python --version` |
| pip | 24+ | yes | ships with Python |
| ffmpeg | any recent | no | only used to improve evidence clip quality; OpenCV path works without it |
| Git | any | yes | |
| Ollama | any | no | optional, local LLM explanations only |

Optional CUDA GPU: speeds up detection roughly 5-10x. CPU works, use `FRAME_STRIDE=2`
or `3` to keep the demo responsive.

## 2. Setup

```bash
git clone <repo-url>
cd porchPiracyAI

python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
pre-commit install
```

Verify:

```bash
make test          # pytest -q
make lint          # ruff check . && ruff format --check .
make api           # http://localhost:8000/docs
make ui            # http://localhost:8501
```

## 3. `.env` reference

Copy `.env.example` to `.env` and adjust. Everything is optional except the database
URL, which has a working default.

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///data/porchpiracy.db` | SQLModel connection string |
| `BACKEND_URL` | `http://localhost:8000` | Used by the Streamlit app to reach the API |
| `PROTECTION_TIMEOUT_MINUTES` | `360` | Session expiry in minutes |
| `LOITER_THRESHOLD_SECONDS` | `8` | Near-package duration that triggers a LOW incident |
| `NEAR_PACKAGE_DISTANCE_PX` | `150` | "Near" distance between person and package boxes |
| `FRAME_STRIDE` | `2` | Process every Nth frame |
| `DETECTION_CONF_THRESHOLD` | `0.45` | Minimum detection confidence |
| `PERSON_MODEL_PATH` | `models_weights/yolov8n.pt` | Person detector weights |
| `PACKAGE_MODEL_PATH` | `models_weights/package.pt` | Package detector weights |
| `RING_MODE` | `local` | `local` or `real` |
| `RING_CLIENT_ID` / `RING_CLIENT_SECRET` | empty | Only for `RING_MODE=real` |
| `OLLAMA_URL` | `http://localhost:11434` | Local Ollama endpoint |
| `OLLAMA_MODEL` | `llama3.2:3b` | Ollama model tag |
| `LLM_ENABLED` | `false` | Enables LLM explanations |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | empty | Optional Telegram notifier |
| `INCIDENT_COOLDOWN_SECONDS` | `30` | Incident de-duplication window |
| `USE_MOCK` | `false` | Streamlit reads `samples/mock_events.json` instead of the API |

**Never commit `.env`.** It is in `.gitignore`.

## 4. Model weights

Weights are not committed. Options:

1. Let Ultralytics auto-download `yolov8n.pt` on first run (needs internet once).
2. Place the file manually at `models_weights/yolov8n.pt`.

For package detection, put a parcel detector at `models_weights/package.pt`. If that
file is missing, the pipeline falls back to COCO proxy classes (`suitcase`, `handbag`,
`backpack`) and reports that it did so.

## 5. Directories created on first run

```
data/uploads/      uploaded videos
data/annotated/    annotated output videos
data/evidence/     incident clips, key frames, reports
data/              porchpiracy.db (SQLite)
models_weights/    detector weights
```

`data/` and `models_weights/` are gitignored. `samples/` is committed.

## 6. Common commands

```bash
make api          # uvicorn main:app --reload --port 8000
make ui           # streamlit run app.py
make test         # pytest -q
make test-cov     # pytest --cov=backend --cov-report=term-missing
make lint         # ruff check . && ruff format --check .
make format       # ruff format . && ruff check --fix .
make seed         # load samples/mock_events.json into the database
make reset-db     # delete and recreate the SQLite database
```

## 7. Coding conventions

- Type hints on every public function.
- Pydantic models at boundaries; dataclasses only for internal hot-loop structures.
- `logging.getLogger(__name__)`, never `print` (except in `__main__` CLIs).
- Line length 100, ruff defaults.
- Public functions get a docstring stating what it returns, not how it works.
- Custom exceptions live in `backend/core/exceptions.py`.
- One concern per function; keep functions under ~40 lines.
- No new runtime dependencies without a team announcement.

## 8. Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: ultralytics` | ML extras not installed | `pip install -r requirements.txt`, or use mock mode |
| API starts but analysis 500s | Model weights missing | Download weights or set `USE_MOCK=true` for the dashboard |
| `sqlite3.OperationalError: unable to open database file` | `data/` missing | `make reset-db` creates it |
| Dashboard shows "backend unreachable" | API not running | `make api` in another terminal, check `BACKEND_URL` |
| Streamlit page is blank | Import error in a page file | `streamlit run app.py` prints the traceback in the terminal |
| Ruff complains about import order | Unsorted imports | `make format` |
| Port 8000 in use | Another process | `uvicorn main:app --reload --port 8001` and update `BACKEND_URL` |
| Video analysis is slow | CPU inference | Raise `FRAME_STRIDE` to 3, use `yolov8n` |
| Duplicate incidents | Multiple sessions on the same events | One active session is enforced; check `GET /protection/status` |

## 9. Where to put new code

| Change | Location |
|---|---|
| New API endpoint | `backend/api/routes/`, then register in `backend/api/routes/__init__.py` |
| New DB table | `backend/models/`, then import in `backend/models/__init__.py` |
| New event type or schema field | `backend/schemas/` — **announce it first** |
| New threshold | `backend/core/config.py` — **announce it first** |
| New detection logic | `backend/services/detection_service.py` |
| New threat rule | `backend/services/threat_service.py` + a test in `tests/unit/test_threat_rules.py` |
| New UI element | `frontend/components.py`, then used by a page |

## 10. Test layout

| Path | Scope | Needs the ML stack? |
|---|---|---|
| `tests/unit/` | Pure logic: state machine, threat rules, event geometry, dedupe | No |
| `tests/integration/` | API endpoints over HTTP with a temporary database | No |
| `tests/e2e/` | Full flow: upload → delivery → events → incident → evidence | Only the vision part |

Tests must be deterministic: no `sleep`, no real clock, no network. Use
`freezegun`-style injection (pass `now` explicitly) instead.
