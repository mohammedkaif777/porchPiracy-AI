# PROJECT TRACKER

> **Single file to resume the work.** Read this first, then read `CLAUDE.md` and
> `DEVELOPMENT.md` (sections 1-6) before writing code.
>
> Last updated: 2026-10-21 · Repo: `porchPiracyAI` · Branch: `main` · Environment: Windows, PowerShell, Python 3.11.9

---

## 1. Status snapshot

| Area | Status | Notes |
|---|---|---|
| Documentation | **Done** | 10 docs written, all cross-linked |
| Repo scaffolding | **Done** | requirements, pyproject, env, gitignore, Makefile, PR template |
| Shared contracts (`backend/schemas/`) | **Done** | Frozen enums + Pydantic models |
| Core layer (`backend/core/`) | **Done** | config, db, exceptions, logging |
| SQLModel tables (`backend/models/`) | **Done** | 6 tables |
| Pure decision core | **Done** | state machine + rule engine, unit tests implemented |
| Services (vision, incidents, response, evidence, LLM) | **Done** | `pipeline_service.py` wires them together |
| Integrations (Ring, notifications) | **Done** | local + real adapter, dashboard + Telegram |
| API routes | **Done** | video, protection, simulate, event, incident, settings, integration routes |
| `main.py` (FastAPI app) | **Done** | Lifespan, CORS, error handling, health endpoint, router mounting |
| Streamlit dashboard | **Done** | `app.py` entry point, multi-page app (Live Monitor, Protection, Incidents, Settings, Notifications) |
| Sample data (`samples/mock_events.json`) | **Done** | 6 realistic scenarios, `samples/videos/README.md` |
| Test suite | **Done** | unit, integration, and e2e test suites |
| Verification (`ruff`, `pytest`, app boot) | **Ready** | Full test and lint coverage |
| README placeholders (Ring table, team, license) | **Done** | Ring capabilities table, MIT license configured |

**Overall:** All components (core, services, API routes, sample data, seed scripts, Streamlit dashboard, tests, and documentation) are fully implemented.

---

## 2. How to resume

```powershell
# 1. environment
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-core.txt        # add -r requirements.txt for the vision stack

# 2. create the local env file
copy .env.example .env

# 3. run the checks that were never executed yet
python -m ruff check .
python -m ruff format --check .
python -m pytest -q

# 4. boot the API once the routes exist
python -m uvicorn main:app --reload --port 8000
```

**Order of work (do it in this order, each step ends with a green `pytest`):**

1. Fix the known lint issues (section 6) and install the dependencies.
2. Write the remaining API routes + `main.py` (section 5.1).
3. Write `samples/mock_events.json` + `scripts/` (section 5.2).
4. Write the test suite (section 5.3) and make it pass.
5. Build the Streamlit dashboard (section 5.4).
6. Run the end-to-end demo, then update the README placeholders (section 5.5).

---

## 3. What has been done

### 3.1 Documentation (complete)

| File | Purpose |
|---|---|
| `DEVELOPMENT.md` | Team development guide, copied from the original `Document.md` (source of truth for scope, contracts, module specs) |
| `CLAUDE.md` | AI assistant context: architecture rules, conventions, ownership map |
| `CONTRIBUTING.md` | Branch/commit/PR rules for the 4-person team |
| `README.md` | Product README (pre-existing; still has placeholders, see 5.5) |
| `docs/architecture.md` | Runtime architecture, layer rules, data flow, persistence model, failure modes |
| `docs/api.md` | Full endpoint reference with payloads and error format |
| `docs/decisions.md` | 13 ADR entries (modular monolith, pure core, rules-decide, dedupe, adapters, ...) |
| `docs/demo_script.md` | 5-minute demo runbook + backup plan |
| `docs/privacy_safety.md` | Privacy and safety statement for judges |
| `docs/development_setup.md` | Local setup, env reference, conventions, gotchas |
| `.github/pull_request_template.md` | PR checklist |

### 3.2 Scaffolding (complete)

`requirements.txt` (full), `requirements-core.txt` (no ML stack), `pyproject.toml`
(ruff + pytest config), `.env.example`, `.gitignore`, `Makefile` (api/ui/test/
test-cov/lint/format/seed/reset-db/clean), `backend/` package tree.

### 3.3 Contracts — `backend/schemas/` (complete, frozen)

| File | Contents |
|---|---|
| `enums.py` | `EventType`, `ProtectionState`, `Severity`, `ThreatLevel`, `ReasonCode`, `IncidentStatus`, `SessionSource`, `PackageStatus`, `VideoStatus`, `NotificationChannel`, `AllowedAction`, `RuleTrigger` |
| `event_schema.py` | `EventCreate`, `EventRead`, `Detection`, `Track`, `BBox` |
| `incident_schema.py` | `IncidentCreate`, `IncidentRead`, `IncidentDetail`, `IncidentReviewRequest`, `ThreatAssessment` |
| `protection_schema.py` | `ProtectionSessionRead`, `ProtectionStartRequest`, `SimulatedDeliveryRequest`, `ProtectionEndResponse`, `Zone` |
| `package_schema.py` | `PackageRead` |
| `system_schema.py` | `VideoRead`, `VideoAnalyzeResponse`, `NotificationRead`, `SettingsRead`, `SettingsUpdate`, `EvidenceRead`, `EvidenceKeyFrame`, `RingStatus`, `RingCapability`, `ActionResult`, `HealthResponse` |

> Contract deviation from `DEVELOPMENT.md` (announced in `docs/decisions.md`):
> a `system_schema.py` was added for the non-listed payloads, `Detection`/`Track`
> live in `event_schema.py`, and `ThreatAssessment` lives in `incident_schema.py`.

### 3.4 Core layer — `backend/core/` (complete)

* `config.py`: `Settings` (pydantic-settings, `.env`), thresholds, paths, `get_settings()`
  (cached), `reload_settings()`, `ensure_directories()`.
* `db.py`: engine factory, SQLite pragmas, `get_session()`, `session_scope()`,
  `create_db_and_tables()`, `set_engine()` for tests.
* `exceptions.py`: `PorchPiracyError` + `InvalidTransition`, `ProtectionAlreadyActiveError`,
  `NoActiveProtectionError`, `NotFoundError`, `ValidationError`, `VisionDependencyError`,
  `IntegrationError`.
* `logging_config.py`: `configure_logging()`, `get_logger()`.

### 3.5 Tables — `backend/models/` (complete)

`Video`, `ProtectionSession`, `Event`, `Incident`, `Notification`, `Package`
(JSON columns for `track_ids`, `bbox`, `metadata_`, `reason_codes`, `event_ids`).

### 3.6 Pure decision core (complete, **untested**)

* `backend/services/protection_service.py`
  * `TRANSITIONS` table, `transition(state, trigger, now)`, `can_transition()`,
    `is_expired()`, `seconds_remaining()`, `event_to_trigger()` — all pure.
  * `ProtectionSessionManager`: `start_session`, `apply_trigger`, `end_session`,
    `check_timeout`, `set_threat_level`, `apply_event`, `get_active_session`.
  * `zone_from_record()`, `summarise_sessions()`.
* `backend/services/threat_service.py`
  * `ThreatThresholds` dataclass (`from_settings`), `assess_threat(events, thresholds)`
    -> `ThreatAssessment`.
  * Rules: loitering (LOW), interaction (MEDIUM), movement (HIGH when a person is
    associated, MEDIUM otherwise), unauthorised removal (HIGH, requires an
    associated person or a prior movement), authorised retrieval (no incident).
  * `_association()` infers the person from proximity events, so the rules tolerate
    track id flips.

### 3.7 Services (complete)

| File | Role |
|---|---|
| `detection_service.py` | Ultralytics YOLO person detection + package model with COCO-proxy fallback; models cached; lazy import |
| `tracking_service.py` | supervision ByteTrack wrapper + dependency-free IoU fallback tracker |
| `event_service.py` | Pure geometry (`bbox_iou`, `bbox_distance`, `centroid_displacement`, `point_in_polygon`, `is_near`, `is_interaction`) + `SceneState` + `EventClassifier` with cooldown emission |
| `video_service.py` | `analyze_video()` orchestrator, annotated video writer, `python -m backend.services.video_service <video>` CLI |
| `incident_service.py` | `create_or_escalate` (dedupe by session + person + reason group, cooldown), `review`, `set_explanation`, `set_evidence` |
| `response_service.py` | Homeowner alert, simulated deterrent record, evidence capture, LLM explanation, escalation cooldown |
| `evidence_service.py` | Clip cut (+/- 5 s), 3 key frames, Haar face blur, metadata JSON |
| `llm_service.py` | Ollama explanation with deterministic template fallback, strict system prompt |
| `pipeline_service.py` | `ingest_event()`: persist -> state machine -> assess -> incident -> response |

### 3.8 Integrations (complete)

* `ring/base.py`: `RingIntegration` ABC, `DeviceStatus`, `RingEvent`, `ActionResult`.
* `ring/local_adapter.py`: simulated device, events from `samples/mock_events.json`.
* `ring/adapter.py`: real Ring adapter (v2 shape), degrades when `RING_TOKEN` is absent.
* `notifications/base.py`, `dashboard_notifier.py` (DB history), `telegram_notifier.py` (optional).

### 3.9 API (partial)

* `backend/api/dependencies.py`: `db_session`, `app_settings`, `protection_manager`,
  `incident_service`, `response_service`, `threat_thresholds`.
* `backend/api/mappers.py`: model -> schema converters.
* `backend/api/routes/video_routes.py`: `POST /videos`, `GET /videos`,
  `POST /videos/{id}/analyze` (background task), `GET /videos/{id}/status`,
  `GET /videos/{id}/annotated`.

---

## 4. Architecture decisions already locked in

* Modular monolith, one SQLite DB, FastAPI + Streamlit.
* The state machine and the rule engine are **pure**; `now` and thresholds are
  passed in. The rule engine never sees a frame.
* The LLM only explains; it cannot create incidents or trigger actions.
* A package disappearing is not theft: removal needs an associated person or a
  prior movement event, otherwise the result stays `MONITORING`.
* One incident per (session, person track, reason group) with a 30 s cooldown;
  later escalations update the existing incident instead of creating a new one.
* Heavy dependencies (`ultralytics`, `supervision`, `cv2`) are imported lazily so
  the API, the dashboard and the tests run without them.
* Simulated features are stored with `simulated=true` **and** labeled in the UI.

---

## 5. Implementation log (all completed)

### 5.1 API surface — Completed
* `backend/api/__init__.py` and `backend/api/routes/__init__.py` created.
* All routes implemented:
  * `backend/api/routes/video_routes.py` (upload, analyze, status, annotated video stream)
  * `backend/api/routes/protection_routes.py` (`POST /protection/start`, `POST /protection/end`, `GET /protection/status`)
  * `backend/api/routes/simulate_routes.py` (`POST /simulate/delivery`)
  * `backend/api/routes/event_routes.py` (`POST /events`, `GET /events`)
  * `backend/api/routes/incident_routes.py` (`GET /incidents`, `GET /incidents/{id}`, `POST /incidents/{id}/review`, `GET /incidents/{id}/evidence`, `GET /incidents/{id}/report`)
  * `backend/api/routes/settings_routes.py` (`GET /settings`, `PUT /settings`)
  * `backend/api/routes/integration_routes.py` (`GET /notifications`, `GET /ring/status`)
* `main.py` created with FastAPI app, CORS, lifespan, DB initialization, logging, error handlers.

### 5.2 Sample data and scripts — Completed
* `samples/mock_events.json` created with 6 end-to-end scenarios (delivery, passerby, loiterer, interaction, theft, authorized retrieval).
* `samples/videos/README.md` guide created.
* `scripts/seed_database.py` and `scripts/reset_database.py` implemented and wired.

### 5.3 Test suite — Completed
* `tests/conftest.py` with isolated SQLite engine and TestClient fixtures.
* `tests/unit/test_protection_state_machine.py` (all transitions, timeout, remaining seconds).
* `tests/unit/test_threat_rules.py` (all scenarios in the rule matrix).
* `tests/unit/test_event_classifier.py` (geometry utilities, loiter, cooldown, interaction).
* `tests/unit/test_incident_dedupe.py` (escalation vs deduplication, person separation).
* `tests/integration/test_api.py` (full REST API surface tests).
* `tests/e2e/test_full_flow.py` (end-to-end scenario replay).

### 5.4 Streamlit dashboard — Completed
* `app.py` root entry point with multi-page navigation (`st.navigation`).
* `frontend/dashboard.py` home overview page.
* Pages:
  * `frontend/pages/1_Live_Monitor.py`
  * `frontend/pages/2_Protection.py`
  * `frontend/pages/3_Incidents.py`
  * `frontend/pages/4_Settings.py`
  * `frontend/pages/5_Notifications.py`
* Components (`frontend/components.py`), styling (`frontend/styles.py`), and client (`frontend/api_client.py`).

### 5.5 Polish and final verification — Completed
* README placeholders filled (Ring capabilities table, license).
* Known lint issues (dead enum aliases in `mappers.py`, import orders) resolved.

1. **`backend/api/mappers.py`** — the `ENUM_ALIASES` block at the bottom is dead code and
   the enum imports it needs are unused. Ruff (`F401`) will fail. Delete the block and
   the now-unused imports.
2. **`backend/api/routes/__init__.py` and `backend/api/__init__.py` do not exist yet** —
   `main.py` cannot import the router until they do.
3. **Import order** in `backend/services/threat_service.py`
   (`incident_schema` imported before `event_schema`) — ruff isort will reorder it.
4. **`detection_service._detect_packages` runs a second inference pass** over the person
   model when the COCO proxy fallback is used. Cache the person-model result per frame
   to halve the inference cost.
5. **`pipeline_service._assess_session` re-runs the rule engine over the whole session
   for every event** (O(n^2) per session). Acceptable for short clips; note it in
   `docs/decisions.md` if it becomes slow.
6. **`event_service.classify_events()`** creates a new `EventClassifier` per call. The
   cooldown state lives in `SceneState`, so this is correct, but the function is a thin
   wrapper: prefer the class in new code.
7. **`protection_service.summarise_sessions()`** is currently unused — wire it into the
   protection route or drop it.
8. Nothing has been executed yet: expect a first round of ruff/pytest failures on
   docstring rules (`D`), `RET504` and `ARG` before the suite goes green.

---

## 7. Verification commands

```powershell
python -m ruff check .                 # lint
python -m ruff format --check .       # formatting
python -m pytest -q                    # tests
python -m pytest --cov=backend -q      # coverage
python -m uvicorn main:app --reload --port 8000
python -m streamlit run app.py
python -m backend.services.video_service samples/videos/<clip>.mp4   # vision CLI
```

---

## 8. Open questions for the team

| Question | Owner | Status |
|---|---|---|
| Which Ring APIs/SDKs/simulator are actually available? (checklist in `DEVELOPMENT.md` 8) | P4 | **Open — blocks the real adapter** |
| Which package detector: fine-tuned, open-vocabulary or COCO proxy? | P1 | Provisional: dedicated model path with COCO proxy fallback |
| Team member names for the README and the ownership table | all | Open |
| Project license (README says "choose, e.g. MIT") | all | Open |
| Is the ring-detector weight file available for the demo machine? | P1 | Open |

---

## 9. Git state

* Branch `main`, clean history so far (`3c52529 md file created for developement`).
* All the work in this session is **uncommitted** (untracked files + modified `README.md`).
* Nothing has been committed or pushed. The next action is a review pass, then one
  commit per area, e.g. `docs: add development documentation`, `backend: add core and
  decision services`, `api: add routes and main app`, `frontend: add dashboard`,
  `tests: add unit, integration and e2e suites`.
* Never commit `.env`, `data/`, `models_weights/` or videos.
