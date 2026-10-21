# Architecture

## 1. System shape

porchPiracyAI is a **modular monolith**: one Python application, one database, one
deployment, but strict module boundaries so each part can be developed, tested and
replaced independently. No microservices, no message broker, no separate services.

```
                 ┌──────────────────────────────────────────────┐
                 │              Streamlit dashboard            │
                 │  Live Monitor │ Protection │ Incidents │ ⚙  │
                 └───────────────────────┬──────────────────────┘
                                         │ HTTP (frontend/api_client.py)
                                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                                 FastAPI backend                             │
│                                                                            │
│  api/routes/  video · protection · event · incident · simulate · settings   │
│       │                                                                    │
│       ▼                                                                    │
│  services/                                                               │
│    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│    │ vision layer  │→ │ event layer   │→ │ decision layer│               │
│    │ video_service │  │ event_service │  │ protection_   │               │
│    │ detection_    │  │ (geometry,    │  │ service (pure)│               │
│    │ tracking_     │  │  cooldown)    │  │ threat_service│               │
│    │ service       │  └───────┬───────┘  │ (pure)        │               │
│    └───────────────┘          │          └───────┬───────┘               │
│           │                  │                  │                        │
│           └──────────────────┴──────────────────┘                        │
│                              ▼                                           │
│                    incident_service (dedupe/escalate)                     │
│                              ▼                                           │
│                     response_service (orchestration)                      │
│                              ▼                                           │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐    │
│   │ Ring integration│ │ notifications  │ │ evidence + LLM explain  │    │
│   │ (local/real)   │ │ (dashboard/tg) │ │ (clip, blur, report)    │    │
│   └────────────────┘  └────────────────┘  └────────────────────────┘    │
│                              ▼                                           │
│                     SQLModel + SQLite (data/porchpiracy.db)              │
└────────────────────────────────────────────────────────────────────────────┘
```

## 2. Layer responsibilities

| Layer | Package | Responsibility | May depend on |
|---|---|---|---|
| Contracts | `backend/schemas` | Enums and Pydantic models exchanged between modules | nothing |
| Core | `backend/core` | Settings, DB engine/session, logging, custom exceptions | pydantic-settings, sqlmodel |
| Models | `backend/models` | SQLModel tables (persistence only) | core, schemas |
| Vision | `backend/services/{video,detection,tracking,event}_service.py` | Frames → detections → tracks → `Event` objects | schemas, core config. **No DB, no HTTP.** |
| Decision | `backend/services/{protection,threat}_service.py` | Pure state machine and pure rule engine | schemas only |
| Response | `backend/services/{incident,response}_service.py` | Incident lifecycle, orchestration of side effects | models, schemas, integrations |
| Evidence/LLM | `backend/services/{evidence,llm}_service.py` | Clip cutting, face blur, report, explanation | core, schemas |
| API | `backend/api` | HTTP boundary, request/response translation | services, models |
| UI | `frontend`, `app.py` | Streamlit pages; all HTTP through `frontend/api_client.py` | HTTP only |

Dependency rule: **arrows point inwards**. The UI knows nothing about the DB; the
vision layer knows nothing about the DB; the decision layer knows nothing about HTTP.

## 3. Data flow: video → incident

```
video file
   │  video_service.iter_frames(path, stride=FRAME_STRIDE)
   ▼
frames ──► detection_service.detect(frame) ──► [Detection(cls, bbox, conf)]
                                    │
                                    ▼
                   tracking_service.update_tracks(detections) ──► [Track(id, cls, bbox)]
                                    │
                                    ▼
                 event_service.classify_events(tracks, t, state)
                                    │  geometry: near / interaction / movement / removed
                                    │  state-change + cooldown de-dup
                                    ▼
                              Event (schema)
                                    │  on_event callback
                                    ▼
                     POST /events  (or direct service call)
                                    │
                                    ▼
   persist event → protection_service.apply_event → threat_service.assess(events)
                                    │
                     ┌──────────────┴───────────────┐
                     ▼                              ▼
             incident_service                  threat level on session
          (dedupe / escalate)                          │
                     │                                  │
                     ▼                                  ▼
              response_service ──► notifier, deterrent, evidence, LLM explanation
                     │
                     ▼
                   SQLite  ──► GET /incidents ──► dashboard
```

## 4. The two pure cores

Both live in `backend/services` and have no I/O. This is the single most important
structural rule of the codebase: it is what makes threat decisions testable,
deterministic and explainable.

### 4.1 Protection state machine — `protection_service.py`

```
IDLE ──delivery/manual──► PACKAGE_DETECTED ──package stable──► PROTECTION_ACTIVE
                                                                    │
   ┌────────────────────────────────────────────────────────────────┤
   ▼                              ▼                                ▼
PACKAGE_RETRIEVED            PROTECTION_TIMEOUT               manual end
   │                              │                                │
   └──────────────► PROTECTION_ENDED ◄────────────────────────────┘
```

* `transition(state, trigger, now) -> ProtectionState` — pure, raises `InvalidTransition`.
* `is_expired(session, now) -> bool` — pure, `now` passed in.
* The DB-backed `ProtectionSessionManager` wraps the pure functions and persists state.

### 4.2 Threat rule engine — `threat_service.py`

Input: ordered events of the active session + thresholds.
Output: `ThreatAssessment(level, severity, reason_codes, should_create_incident)`.

| Rule | Reason code | Severity |
|---|---|---|
| Person near package for ≥ `LOITER_THRESHOLD_SECONDS` | `LOITERING_OVER_THRESHOLD` | LOW |
| Person bbox overlaps package bbox (contact) | `PACKAGE_INTERACTION` | MEDIUM |
| Package centroid displaced beyond threshold | `PACKAGE_MOVED` | HIGH |
| Package removed with an associated person track | `PACKAGE_REMOVED_UNAUTHORIZED` | HIGH |

Threat levels: `NONE` → `MONITORING` → `SUSPICIOUS` → `THREAT`.

The engine never sees a frame. It only sees events with timestamps, which is why a
single ambiguous frame can never raise a HIGH alert.

## 5. Persistence model

| Table | Purpose | Key columns |
|---|---|---|
| `packages` | Detected packages | `id`, `video_id`, `track_id`, `bbox`, `confidence`, `status` |
| `protection_sessions` | One active protection session | `id`, `state`, `source`, `started_at`, `expires_at`, `threat_level`, `protection_zone` |
| `events` | Raw vision events | `id`, `session_id`, `type`, `timestamp_s`, `frame_index`, `track_ids`, `confidence`, `bbox`, `metadata` |
| `incidents` | Escalated incidents | `id`, `session_id`, `severity`, `reason_codes`, `event_ids`, `start_s`, `end_s`, `status`, `evidence_path`, `explanation` |
| `notifications` | Homeowner alerts + deterrent log | `id`, `incident_id`, `channel`, `message`, `simulated`, `created_at` |
| `videos` | Uploaded videos and analysis progress | `id`, `filename`, `path`, `status`, `progress`, `annotated_path`, `created_at` |

Files (videos, annotated output, evidence clips, key frames) live on disk under `data/`;
only paths are stored in the DB.

## 6. Integration boundary

```
             backend/integrations/ring/base.py  (ABC)
                    ▲                        ▲
       ring/local_adapter.py         ring/adapter.py   (real Ring)
            (dev/test only)            (RING_MODE=real)
```

`RingIntegration` exposes `get_device_status()`, `get_recent_events()` and
`trigger_supported_action(action)` where `action` is restricted to the `AllowedAction`
enum. The app never calls Ring code directly — it calls the adapter — so the rest of the
system is unaffected by what the real Ring environment offers.

Notifications follow the same pattern:
`integrations/notifications/base.py` → `dashboard_notifier.py` (always on, writes to DB),
`telegram_notifier.py` (optional, enabled by env vars).

## 7. Configuration

All tunables live in `backend/core/config.py` (pydantic-settings) and are overridable
through `.env` / environment variables. The threat engine and state machine receive
threshold values as arguments, never by reading the settings object internally — that
keeps them pure.

| Setting | Default | Effect |
|---|---|---|
| `PROTECTION_TIMEOUT_MINUTES` | 360 | Session auto-expiry |
| `LOITER_THRESHOLD_SECONDS` | 8 | Time near package before LOW |
| `NEAR_PACKAGE_DISTANCE_PX` | 150 | "Near package" distance |
| `FRAME_STRIDE` | 2 | Process every Nth frame |
| `DETECTION_CONF_THRESHOLD` | 0.45 | Minimum detection confidence |
| `INCIDENT_COOLDOWN_SECONDS` | 30 | Incident de-duplication window |
| `RING_MODE` | `local` | `local` or `real` adapter |

## 8. Failure modes and degradation

| Failure | Behaviour |
|---|---|
| `ultralytics` / `supervision` / `cv2` not installed | API and dashboard still run; vision analysis reports a clear "vision dependencies missing" error instead of crashing |
| Model weights missing | Same as above, with the expected path printed |
| Ollama unavailable | LLM explanations fall back to deterministic templates |
| Ring real adapter without credentials | Ring status endpoint reports `degraded` with the reason; the app keeps working on the local adapter |
| Video has no detectable package | Protection session still runs; no incident is raised |

## 9. Why these choices

* **SQLite + SQLModel** — zero-ops local storage, one schema shared by API and DB.
* **SQLite over a server DB** — video files are on local disk anyway; a network DB would
  add failure modes to the demo for no benefit.
* **FastAPI** — automatic OpenAPI docs, typed request bodies via Pydantic.
* **Streamlit** — fastest path to a polished dashboard; multi-page support built in.
* **ByteTrack** — MIT licensed, fast, and stable enough for short clips.
* **Pure decision core** — the rules are the product; they must be provably testable
  and auditable for judges.
