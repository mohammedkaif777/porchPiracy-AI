# CLAUDE.md

AI assistant context for **porchPiracyAI** — Amazon AI Hackathon, Ring track.
Read this before writing code. It encodes the non-negotiable rules of the project.

---

## What the product does

It ingests porch video, detects people and packages, tracks them, classifies events,
runs a deterministic threat rule engine inside a protection-mode state machine,
creates incidents with evidence clips (face-blurred), notifies the homeowner,
and triggers a SIMULATED deterrent. It integrates with a real Ring API/SDK/
simulator/device (via a `RingIntegration` adapter) and processes real video.

**Differentiator:** cameras record what happened. porchPiracyAI recognizes what is happening and responds.

## Stack

Python 3.11, FastAPI + Uvicorn, Streamlit, OpenCV, ffmpeg, Ultralytics YOLO,
supervision ByteTrack, Pydantic v2 + SQLModel, SQLite, Ollama (optional),
pytest, httpx, ruff.

## Architecture rules

- Modular monolith. Folders: `frontend/`, `backend/{api,core,models,schemas,services,integrations}/`.
- Contracts live in `backend/schemas/` and the API list in `DEVELOPMENT.md` section 5. Do NOT
  change a contract without telling me; if a change is required, propose it explicitly.
- Protection state machine and threat rules are PURE functions (no I/O, no DB, no clock
  calls inside; pass `now` in). They must have unit tests.
- Detection/tracking/event code never touches the DB or HTTP directly; it emits `Event`
  objects through a callback.
- The LLM only explains structured events. It never decides, creates incidents,
  or executes actions. Incident creation is deterministic.
- A package disappearing is NOT proof of theft. Use event sequences and time windows.
- Protection state and incident state are separate.
- Deduplicate incidents (one per session + person track + reason group within a cooldown).
- Never use face recognition. Never auto-contact police. Label simulated features "Simulated".
- Config via `pydantic-settings`; no hardcoded thresholds or secrets.
- Every incident stores `reason_codes` and the `event_ids` that triggered it.

## Code conventions

- Type hints everywhere, Pydantic models at boundaries, small functions, docstrings
  for public functions.
- Follow ruff defaults, line length 100.
- Log with the `logging` module, not `print`.
- Raise custom exceptions from `backend/core/exceptions.py`.
- Write pytest tests alongside new logic. Keep tests fast and deterministic.
- Optional heavy dependencies (`ultralytics`, `supervision`, `cv2`) must be imported
  lazily so the backend, the API and the test suite run without them.

## How to work with me

1. Before writing code, restate the task in 2 to 3 lines and list the files you will
   create or change. Only touch files in my owned area (stated below).
2. Prefer the simplest thing that works for a hackathon. No new frameworks or services
   unless I ask. No microservices.
3. Write complete, runnable code (no placeholders like "...rest of code").
4. After the code, give: how to run it, how to test it, and what could break.
5. If a requirement is ambiguous or conflicts with a contract, ask one short question
   instead of guessing.
6. Do not refactor files outside my area.

## Privacy and safety (non-negotiable, `DEVELOPMENT.md` section 9)

- Video is stored locally; no uploads to external AI services.
- Blur faces in exported evidence.
- Never auto-call police. Never accuse an identifiable person. No face recognition.
- Sensitive external actions require homeowner confirmation.
- Only allowlisted actions can run (`AllowedAction` enum). An LLM can never execute
  commands or trigger actions.
- Incident creation and escalation are deterministic and logged with reason codes.
- Simulated features are always labeled "Simulated" in the UI.
- Alert wording: "potential package theft, for review", never "thief detected".

## Ownership map

| Area | Owner | Files |
|---|---|---|
| Vision and AI Pipeline | P1 | `backend/services/{video,detection,tracking,event}_service.py`, `tests/unit/test_event_classifier.py` |
| Backend and Decision Engine | P2 | `main.py`, `backend/api/`, `backend/core/`, `backend/models/`, `backend/schemas/`, `backend/services/{protection,threat,incident,response}_service.py` |
| Frontend and UX | P3 | `app.py`, `frontend/` |
| Integrations, Evidence, QA | P4 | `backend/integrations/`, `backend/services/{evidence,llm}_service.py`, `tests/e2e/`, `docs/demo_script.md` |

Shared files (`backend/schemas/`, `backend/core/config.py`, `requirements.txt`) change only
by announcement in the group chat plus the same PR.

## Commands

```bash
make api      # uvicorn main:app --reload --port 8000
make ui       # streamlit run app.py
make test     # pytest -q
make lint     # ruff check . && ruff format --check .
make seed     # load samples/mock_events.json into the database
```

## Where things are documented

| Doc | Content |
|---|---|
| `DEVELOPMENT.md` | Source of truth: scope, contracts, module specs, prompts, plan |
| `docs/architecture.md` | Runtime architecture, data flow, module map |
| `docs/api.md` | Endpoint reference with payloads |
| `docs/decisions.md` | ADR log: model choices, thresholds, why |
| `docs/demo_script.md` | 5-minute demo runbook |
| `docs/privacy_safety.md` | Privacy and safety statement for judges |
| `docs/development_setup.md` | Local environment setup, conventions, gotchas |
