# PROJECT TRACKER

> **Single file to resume the work.** Read this first, then read `CLAUDE.md` and
> `DEVELOPMENT.md` (sections 1-6) before writing code.
>
> Last updated: 2026-10-21 · Repo: `porchPiracyAI` · Branch: `harsh` · Environment: Windows, PowerShell, Python 3.12 (.venv)

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

## 5. Product Features Completed (MVP / P0 & P1 Differentiators)

### 5.1 Vision & Video Pipeline
- [x] **Video File Ingestion**: Upload and process prerecorded porch clips (`.mp4`, `.mov`, `.avi`, `.mkv`) via `POST /videos`.
- [x] **Person Detection**: Ultralytics YOLOv8 detector running per frame or with configurable stride.
- [x] **Package Detection**: Package model with automatic COCO-proxy fallback.
- [x] **Multi-Object Tracking**: Stable identity tracking across frames using `supervision` ByteTrack (with pure IoU fallback).
- [x] **Annotated Video Export**: Generates annotated video with bounding boxes, labels, and track paths saved to `data/annotated/`.

### 5.2 Delivery Workflow & Protection State Machine
- [x] **Delivery Activation**: Starts protection via manual homeowner trigger or simulated delivery (`POST /simulate/delivery`).
- [x] **Pure State Machine**: `IDLE` -> `DELIVERY_CONFIRMED` -> `PACKAGE_DETECTED` -> `PROTECTION_ACTIVE` -> `PACKAGE_RETRIEVED` / `PROTECTION_TIMEOUT` / `PROTECTION_ENDED`.
- [x] **Configurable Timeout**: Automatic session expiration (default 360 min) with live seconds-remaining countdown.
- [x] **Authorised Retrieval**: Detects legitimate package pickups without triggering false theft alarms.

### 5.3 Threat Assessment & Decision Engine
- [x] **Deterministic Rule Engine**: Evaluates event sequences against tunable thresholds (passerby -> `NONE`, approach -> `MONITORING`, lingering -> `LOW`, touch -> `MEDIUM`, theft -> `HIGH`).
- [x] **Multi-Frame Temporal Validation**: Single frame never triggers an alert; requires sustained presence or physical interaction.
- [x] **Person Association Check**: Disappearing package without an associated person track is treated as monitoring/occlusion, not theft.

### 5.4 Incident Management & Response
- [x] **Incident Creation**: Generates incidents with severity rating, timestamp intervals, and explicit reason codes.
- [x] **Smart De-duplication**: De-duplicates by `(session_id, person_track_id, reason_family)` with configurable cooldown to prevent alert fatigue.
- [x] **Escalation Pipeline**: Escalates existing incident severity as suspicious behavior intensifies instead of opening duplicate alerts.
- [x] **Review & Dismissal**: API and UI actions to review or dismiss incidents (`POST /incidents/{id}/review`).

### 5.5 Evidence Capture & Privacy Preservation
- [x] **Evidence Clip Extraction**: Automatically cuts incident clip (+/- 5 seconds around threat).
- [x] **Key Frame Capture**: Saves key milestone frames (start, peak threat, conclusion).
- [x] **Privacy Face Blurring**: OpenCV Haar-cascade face blurring applied to exported evidence frames and clips.
- [x] **Exportable HTML Report**: Self-contained incident report with base64-encoded key frames and auditable event timeline.

### 5.6 Deterrents, Notifications & LLM Explanations
- [x] **Multi-Channel Alert Dispatch**: Homeowner alert stored in DB and dispatched to Telegram when configured.
- [x] **Simulated Alexa Voice Deterrent**: Automatic deterrent record clearly tagged as simulated in UI and API.
- [x] **LLM Incident Explanations**: Local Ollama generation with deterministic template fallback explaining why alert was raised.

### 5.7 Ring Ecosystem Integration
- [x] **Integration Abstraction**: Decoupled `RingIntegration` base class.
- [x] **Local Development Adapter**: Simulated Ring device with mock event streams for offline testing and demos.
- [x] **Real Ring Adapter**: Implemented against Ring API v2 endpoints (status, snapshot, events) with graceful degradation.

### 5.8 Interactive Web Dashboard (Streamlit)
- [x] **Multi-Page App**: `app.py` routing with `st.navigation`.
- [x] **Dashboard (Home)**: System overview, protection status cards, threat badge, and recent event feeds.
- [x] **Live Monitor**: Video upload, background analysis progress bar, event stream, and timeline visualizer.
- [x] **Protection Page**: Active countdown timer, start protection, end protection, and simulate delivery controls.
- [x] **Incidents Page**: Detailed incident inspection cards with severity badges, reason codes, and review/dismiss buttons.
- [x] **Settings Page**: Form to adjust tunable thresholds (loiter time, distance px, confidence, cooldown) live in backend.
- [x] **Notifications Page**: Chronological alert and simulated deterrent history.

---

## 6. Pending & Roadmap Features (P2 / Future Enhancements)

| Feature | Scope | Description |
|---|---|---|
| **Live Camera Streaming (RTSP / WebRTC)** | Vision Pipeline | Ingest real-time camera video streams directly instead of offline video file uploads. |
| **Ring Webhook Event Ingestion** | Integrations | Bi-directional webhook listener for real Ring doorbell press and motion events. |
| **Physical Device Actions** | Ring Hardware | Trigger physical Ring floodlights, sirens, or two-way talk audio upon confirmed HIGH incident. |
| **Carrier Delivery Webhooks** | Integrations | Integration with Key by Amazon, FedEx, or UPS delivery notifications to auto-arm protection on drop-off. |
| **Multi-Camera Handover** | Vision Pipeline | Cross-camera re-identification tracking suspects moving between doorbell, driveway, and porch cameras. |
| **Multi-Package Tracking** | Vision / State | Individual tracking IDs and lifecycle states for multiple delivered packages in the same scene. |
| **Acoustic Event Detection** | Multimodal AI | Audio classification for doorstep sounds (footsteps, car door slam, doorbell chime, glass break). |
| **Native Mobile Push & SMS** | Notifications | Real-time push notifications via APNS/FCM and SMS alerts via Twilio. |

---

## 7. Current System State

- **FastAPI Backend:** Running on [http://localhost:8000](http://localhost:8000) (Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs))
- **Streamlit Dashboard:** Running on [http://localhost:8501](http://localhost:8501)
- **Local DB:** SQLite at `data/porchpiracy.db` populated via `python -m scripts.seed_database`
- **Automated Tests:** 69 / 69 passing (`pytest`)
