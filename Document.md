# porchPiracyAI: Team Development Guide

> Amazon AI Hackathon | Primary Track: Ring
> Team of 4 | Python modular monolith | AI-assisted development

This file is the single source of truth for the team. Everyone reads sections 1 to 6 first. Then each person reads their own module section and uses the prompts in section 10 with their AI coding assistant.

---

## Table of Contents

1. Project summary
2. Tech stack and versions
3. Team roles and ownership
4. Repository structure
5. Contracts (schemas, API, events)
6. Core logic specs (state machine, threat rules)
7. Module specs per person
8. Ring integration plan
9. Privacy and safety rules
10. AI prompts: master prompt and per-person prompts
11. AI-assisted workflow rules
12. Git workflow
13. Testing plan
14. Timeline
15. Definition of Done and demo script
16. Risks
17. Appendix: configs, files to create, checklists

---

## 1. Project summary

**porchPiracyAI** is a package protection system. It watches porch video, detects a delivered package, enters a protected state, tracks people and the package, assesses threat with deterministic rules, creates an incident with evidence, and triggers a (simulated) deterrent and a homeowner notification.

**Differentiator:** cameras record what happened. porchPiracyAI recognizes what is happening and responds.

**Hard requirement:** the app must process real video (not hardcoded alerts) and must integrate with a real Ring API, SDK, simulator, or device that we can access. A mock-only Ring dashboard may not qualify. Validate this in the first hours.

### MVP (P0)

| Feature | Expected behavior |
|---|---|
| Video ingestion | Upload a prerecorded porch video |
| Package detection | Detect packages in frames |
| Person detection | Detect people in the monitored area |
| Tracking | Stable IDs for people and packages across frames |
| Delivery workflow | Delivery (real or simulated) activates protection |
| Protection mode | State machine until retrieval, manual end, or timeout |
| Threat assessment | Rule engine separates normal from suspicious activity |
| Incident response | Incident created when rules fire, with no duplicate alerts |
| Evidence capture | Clip, key frames, timestamps saved |
| Dashboard | Package status, protection state, threat level, incidents |

### P1 (differentiators, after P0 works)

Visual protection zone, configurable loitering time, LLM explanations, incident timeline, face blurring, evidence report export, simulated Alexa deterrent, notification history.

### P2 (only if time remains)

Real-time streams, live Ring event integration, real Ring device actions, real notification channel.

---

## 2. Tech stack and versions

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11 | One language for all four members |
| Backend | FastAPI + Uvicorn | OpenAPI docs at `/docs` |
| Dashboard | Streamlit | Use `st.fragment(run_every=...)` or `streamlit-autorefresh` |
| Video | OpenCV, ffmpeg | Frames, clips, face blur |
| Detection | Ultralytics YOLO (people) + package detector | See 7.1; there is no "package" class in COCO |
| Tracking | `supervision` ByteTrack (MIT) | Stable track IDs |
| Models | Pydantic v2 + SQLModel | Same schema for API and DB |
| Database | SQLite | Video files on disk, paths in DB |
| Local LLM | Ollama (Llama 3.2 3B or Qwen 2.5 3B) | Optional; explanations only |
| Testing | pytest, httpx | State machine and rules are pure functions |
| Quality | ruff, pre-commit | Fewer merge fights |
| Config | pydantic-settings, `.env` | Never commit secrets |

Notes:

- Ultralytics YOLO is AGPL-3.0. Fine for a hackathon; check before commercializing.
- Package detection options, in order of preference: (1) fine-tune on a public Roboflow package/parcel dataset, (2) open-vocabulary detector (YOLO-World or OWL-ViT with prompt "cardboard box"), (3) COCO proxy classes (suitcase, handbag, backpack) as a last resort.

### `requirements.txt` (starting point)

```
fastapi
uvicorn[standard]
pydantic>=2
pydantic-settings
sqlmodel
python-multipart
httpx
opencv-python
numpy
ultralytics
supervision
streamlit
streamlit-autorefresh
requests
pytest
pytest-cov
ruff
pre-commit
python-dotenv
reportlab
```

---

## 3. Team roles and ownership

Each person owns specific folders. Do not edit another person's folder without telling them. Shared files (`backend/schemas/`, `backend/core/config.py`) change only by announcement in the group chat plus the same PR.

| Role | Person | Owns |
|---|---|---|
| **P1: Vision and AI Pipeline** | ______ | `detection_service.py`, `tracking_service.py`, `event_service.py`, `video_service.py` |
| **P2: Backend and Decision Engine** | ______ | `protection_service.py`, `threat_service.py`, `incident_service.py`, `models/`, `api/`, `core/` |
| **P3: Frontend and UX** | ______ | `frontend/`, demo polish, report export UI |
| **P4: Integrations, Evidence, QA, Pitch** | ______ | `integrations/`, `evidence_service.py`, `llm_service.py`, `tests/e2e`, demo assets, pitch deck |

### Dependency flow

```
P1 (events) ---> P2 (state machine, threats, incidents) ---> P3 (dashboard)
                        ^                                       ^
P4 (Ring, evidence, LLM, notifications) ------------------------+
```

Everyone develops against the frozen contracts and mocks first, so nobody waits on anybody.

---

## 4. Repository structure

```
porchPiracyAI/
├── README.md
├── DEVELOPMENT.md            # this file
├── CLAUDE.md                 # AI assistant context (copy of section 10.1 + conventions)
├── requirements.txt
├── .env.example
├── .gitignore
├── pyproject.toml            # ruff config
├── Makefile                  # run, test, lint shortcuts
│
├── main.py                   # FastAPI entry point
├── app.py                    # Streamlit entry point
│
├── frontend/
│   ├── dashboard.py
│   ├── pages/
│   │   ├── 1_Live_Monitor.py
│   │   ├── 2_Protection.py
│   │   ├── 3_Incidents.py
│   │   └── 4_Settings.py
│   ├── components.py
│   ├── api_client.py         # all backend calls live here
│   └── styles.py
│
├── backend/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── video_routes.py
│   │   │   ├── protection_routes.py
│   │   │   ├── event_routes.py
│   │   │   ├── incident_routes.py
│   │   │   └── simulate_routes.py
│   │   └── dependencies.py
│   ├── core/
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   ├── logging_config.py
│   │   └── db.py
│   ├── models/               # SQLModel tables
│   │   ├── package.py
│   │   ├── protection_session.py
│   │   ├── event.py
│   │   ├── incident.py
│   │   └── notification.py
│   ├── schemas/              # SHARED CONTRACTS, change by announcement only
│   │   ├── event_schema.py
│   │   ├── incident_schema.py
│   │   ├── protection_schema.py
│   │   └── package_schema.py
│   ├── services/
│   │   ├── video_service.py
│   │   ├── detection_service.py
│   │   ├── tracking_service.py
│   │   ├── event_service.py
│   │   ├── protection_service.py
│   │   ├── threat_service.py
│   │   ├── incident_service.py
│   │   ├── evidence_service.py
│   │   ├── llm_service.py
│   │   └── response_service.py
│   └── integrations/
│       ├── ring/
│       │   ├── base.py
│       │   ├── local_adapter.py
│       │   └── adapter.py    # real Ring adapter
│       └── notifications/
│           ├── base.py
│           ├── dashboard_notifier.py
│           └── telegram_notifier.py   # optional
│
├── data/
│   ├── uploads/              # uploaded videos (gitignored)
│   ├── annotated/            # annotated output videos (gitignored)
│   ├── evidence/             # incident clips and frames (gitignored)
│   └── porchpiracy.db        # SQLite (gitignored)
│
├── models_weights/           # detector weights (gitignored)
├── samples/                  # small test videos + mock JSON (committed)
│   ├── videos/
│   └── mock_events.json
│
├── tests/
│   ├── unit/
│   │   ├── test_protection_state_machine.py
│   │   ├── test_threat_rules.py
│   │   └── test_event_classifier.py
│   ├── integration/
│   │   └── test_api.py
│   └── e2e/
│       └── test_full_flow.py
│
└── docs/
    ├── architecture.md
    ├── api.md
    ├── decisions.md          # short ADR log
    └── demo_script.md
```

### `.gitignore` essentials

```
.env
data/
models_weights/
__pycache__/
.venv/
*.mp4
!samples/videos/*.mp4
*.db
.streamlit/secrets.toml
```

### `.env.example`

```
DATABASE_URL=sqlite:///data/porchpiracy.db
BACKEND_URL=http://localhost:8000
PROTECTION_TIMEOUT_MINUTES=360
LOITER_THRESHOLD_SECONDS=8
NEAR_PACKAGE_DISTANCE_PX=150
FRAME_STRIDE=2
DETECTION_CONF_THRESHOLD=0.45
PERSON_MODEL_PATH=models_weights/yolov8n.pt
PACKAGE_MODEL_PATH=models_weights/package.pt
RING_MODE=local            # local | real
RING_CLIENT_ID=
RING_CLIENT_SECRET=
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
LLM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## 5. Contracts (freeze in hour 0 to 1)

Commit these to `backend/schemas/` before anyone writes feature code.

### 5.1 Enums

```python
class EventType(str, Enum):
    PACKAGE_DETECTED = "PACKAGE_DETECTED"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"
    PERSON_APPROACHING = "PERSON_APPROACHING"
    PERSON_NEAR_PACKAGE = "PERSON_NEAR_PACKAGE"
    LOITERING_DETECTED = "LOITERING_DETECTED"
    PACKAGE_INTERACTION = "PACKAGE_INTERACTION"
    PACKAGE_MOVEMENT_DETECTED = "PACKAGE_MOVEMENT_DETECTED"
    PACKAGE_REMOVED = "PACKAGE_REMOVED"
    PACKAGE_RETRIEVED = "PACKAGE_RETRIEVED"   # authorized retrieval

class ProtectionState(str, Enum):
    IDLE = "IDLE"
    PACKAGE_DETECTED = "PACKAGE_DETECTED"
    PROTECTION_ACTIVE = "PROTECTION_ACTIVE"
    PACKAGE_RETRIEVED = "PACKAGE_RETRIEVED"
    PROTECTION_TIMEOUT = "PROTECTION_TIMEOUT"
    PROTECTION_ENDED = "PROTECTION_ENDED"

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class ThreatLevel(str, Enum):
    NONE = "NONE"
    MONITORING = "MONITORING"
    SUSPICIOUS = "SUSPICIOUS"
    THREAT = "THREAT"

class ReasonCode(str, Enum):
    LOITERING_OVER_THRESHOLD = "LOITERING_OVER_THRESHOLD"
    PACKAGE_INTERACTION = "PACKAGE_INTERACTION"
    PACKAGE_MOVED = "PACKAGE_MOVED"
    PACKAGE_REMOVED_UNAUTHORIZED = "PACKAGE_REMOVED_UNAUTHORIZED"
```

### 5.2 Event (P1 produces, P2 consumes)

```json
{
  "event_id": "uuid",
  "session_id": "uuid | null",
  "type": "PERSON_NEAR_PACKAGE",
  "timestamp_s": 72.4,
  "frame_index": 1810,
  "track_ids": {"person": 4, "package": 2},
  "confidence": 0.91,
  "bbox": {"person": [x1, y1, x2, y2], "package": [x1, y1, x2, y2]},
  "metadata": {}
}
```

### 5.3 Incident (P2 produces, P3 and P4 consume)

```json
{
  "incident_id": "uuid",
  "session_id": "uuid",
  "severity": "LOW | MEDIUM | HIGH",
  "reason_codes": ["LOITERING_OVER_THRESHOLD", "PACKAGE_REMOVED_UNAUTHORIZED"],
  "event_ids": ["uuid", "uuid"],
  "start_s": 68.0,
  "end_s": 80.5,
  "status": "OPEN | REVIEWED | DISMISSED",
  "evidence_path": null,
  "explanation": null,
  "created_at": "iso8601"
}
```

### 5.4 Protection session

```json
{
  "session_id": "uuid",
  "state": "PROTECTION_ACTIVE",
  "started_at": "iso8601",
  "expires_at": "iso8601",
  "source": "MANUAL | SIMULATED_DELIVERY | RING",
  "threat_level": "NONE",
  "package_track_id": 2,
  "protection_zone": [[x, y], [x, y], [x, y], [x, y]]
}
```

### 5.5 API endpoints (frozen)

| Method | Path | Purpose | Owner |
|---|---|---|---|
| POST | `/videos` | Upload video, returns `video_id` | P2 |
| POST | `/videos/{id}/analyze` | Start analysis (background task) | P2 calls P1 |
| GET | `/videos/{id}/status` | Progress, current frame/time | P2 |
| GET | `/videos/{id}/annotated` | Annotated video stream/file | P2 |
| POST | `/simulate/delivery` | Simulated delivery, starts protection | P2 |
| POST | `/protection/start` | Manual start | P2 |
| POST | `/protection/end` | Manual end | P2 |
| GET | `/protection/status` | Current session and threat level | P2 |
| POST | `/events` | Ingest event from vision pipeline | P2 |
| GET | `/events?session_id=` | List events | P2 |
| GET | `/incidents` | List incidents | P2 |
| GET | `/incidents/{id}` | Incident detail | P2 |
| POST | `/incidents/{id}/review` | Mark reviewed/dismissed | P2 |
| GET | `/incidents/{id}/evidence` | Evidence clip/frames | P4 |
| GET | `/incidents/{id}/report` | Exported report | P4 |
| GET | `/notifications` | Notification history | P4 |
| GET | `/ring/status` | Ring device/integration status | P4 |
| GET | `/settings` / PUT `/settings` | Thresholds | P2 |

**Rule:** any contract change is announced in the group chat and the schema file is updated in the same PR.

---

## 6. Core logic specs

### 6.1 Protection state machine (pure functions, no I/O)

```
IDLE
  | delivery confirmed (real/simulated) or manual start
  v
PACKAGE_DETECTED --> PROTECTION_ACTIVE
                          |
                          +--> PACKAGE_RETRIEVED --> PROTECTION_ENDED
                          +--> PROTECTION_TIMEOUT --> PROTECTION_ENDED
                          +--> manual end --> PROTECTION_ENDED
```

Rules:

- Protection state and incident state are separate. A package stays protected while an incident is under review.
- Timeout default is 360 minutes and is configurable.
- Only one active session at a time for the MVP.
- Signature: `transition(state, trigger, now) -> new_state`. Invalid transitions raise `InvalidTransition`.

### 6.2 Threat rule engine (deterministic, pure functions)

Input: ordered list of events in the active session plus config thresholds. Output: `ThreatAssessment(level, severity, reason_codes, should_create_incident)`.

| Observed sequence | Interpretation | Result |
|---|---|---|
| Person passes outside the zone | Normal | NONE |
| Person briefly near package (below threshold) | Ambiguous | MONITORING |
| Person near package at least `LOITER_THRESHOLD_SECONDS` | Suspicious | LOW incident |
| Person interacts with package (bbox overlap or contact) | Needs assessment | MEDIUM incident |
| Package moved or removed by an unidentified person while protected | Potential theft | HIGH incident |
| Package removed after a homeowner-authorized retrieval action | Authorized | End protection, no incident |

Constraints:

- Package disappearing from view alone is not proof of theft. Require a person track associated with the package leaving the zone, or movement events before the disappearance. Wording is always "potential" and "for homeowner review".
- Deduplicate: one incident per (session, person track, reason group) inside a cooldown window (default 30 s). Later escalation updates the existing incident's severity instead of creating a new one.
- Rules are tolerant of track ID flips: use time windows and spatial proximity, not a single frame.
- Every incident stores the reason codes and the event IDs that triggered it.

### 6.3 Event classification (P1)

Per frame: detections -> tracks -> geometry:

- `near`: distance between person bbox and package bbox is at most `NEAR_PACKAGE_DISTANCE_PX` or the person is inside the protection zone.
- `interaction`: person bbox overlaps package bbox above an IoU threshold for N consecutive frames.
- `movement`: package centroid displacement above a threshold versus its baseline position.
- `removed`: package track lost for M seconds while a person track was last seen overlapping or leaving with it.
- Emit an event only on state change or after cooldown, never one per frame.

### 6.4 LLM explanation (P4, optional)

- Input: the compact structured incident summary (reason codes, durations, event list). Never raw frames.
- Output: 2 to 3 sentences of explanation. The LLM cannot create or change incidents and cannot execute actions.
- The system prompt must include: "Describe only the provided events. Do not invent details. Do not identify people."
- If Ollama is unavailable, fall back to a template-based explanation.

---

## 7. Module specs per person

### 7.1 P1: Vision and AI Pipeline

**Files:** `video_service.py`, `detection_service.py`, `tracking_service.py`, `event_service.py`

**Tasks (in order):**

1. **Detector spike (first 2 hours, highest risk).** Run a person detector plus a package detector on a sample porch video. Decide: fine-tuned, open-vocabulary, or COCO proxy. Record the decision in `docs/decisions.md`.
2. `video_service.py`: open video, iterate frames with `FRAME_STRIDE`, report progress, write the annotated output video.
3. `detection_service.py`: `detect(frame) -> list[Detection]` with class, bbox, and confidence. Load models once.
4. `tracking_service.py`: wrap ByteTrack so detections become tracks with stable IDs.
5. `event_service.py`: geometry (near, interaction, movement, removed), protection zone polygon, event emission with cooldown, output per the Event schema.
6. `analyze_video(video_path, session_id, on_event)` orchestrator: callback posts each event to `POST /events` or calls the service directly.
7. Tune thresholds on all test videos.

**Interfaces:**

```python
class Detection(BaseModel):
    cls: Literal["person", "package"]
    bbox: tuple[float, float, float, float]
    confidence: float

def detect(frame: np.ndarray) -> list[Detection]: ...
def update_tracks(detections: list[Detection]) -> list[Track]: ...
def classify_events(tracks: list[Track], t: float, state: SceneState) -> list[Event]: ...
def analyze_video(path: str, session_id: str, on_event: Callable[[Event], None]) -> AnalysisResult: ...
```

**Acceptance:** on every test video, correct events fire at roughly the right timestamps; throughput is at least about 5 effective FPS on a laptop; the annotated video shows boxes, track IDs, and the zone.

### 7.2 P2: Backend and Decision Engine

**Files:** `main.py`, `backend/api/`, `backend/core/`, `backend/models/`, `protection_service.py`, `threat_service.py`, `incident_service.py`, `response_service.py`

**Tasks (in order):**

1. Repo setup, `config.py` (pydantic-settings), `db.py`, SQLModel tables, and the shared schemas (hour 0 to 1, announce when done).
2. Stub every endpoint in 5.5 returning data from `samples/mock_events.json`, so P3 is unblocked fast.
3. `protection_service.py`: state machine (pure) plus a DB-backed session manager and the timeout checker.
4. `threat_service.py`: rule engine (pure) with a unit test for every row of the table in 6.2.
5. `incident_service.py`: create, dedupe, escalate, review and dismiss.
6. `response_service.py`: on a new incident, call P4's notifier, deterrent, and evidence service through interfaces.
7. `POST /events` pipeline: persist event -> update threat assessment -> maybe create an incident -> trigger response.
8. Background analysis: `/videos/{id}/analyze` runs P1's pipeline in a background task and updates progress.
9. Settings endpoints.

**Acceptance:** all unit tests for the state machine and rules pass; replaying `mock_events.json` produces the expected incidents with no duplicates; OpenAPI docs are accurate.

### 7.3 P3: Frontend and UX

**Files:** `app.py`, `frontend/`

**Tasks (in order):**

1. Streamlit skeleton with multipage navigation and `api_client.py`. Build a `USE_MOCK=true` mode that reads `samples/mock_events.json`.
2. **Live Monitor:** upload video, "Simulate delivery" button, annotated video player or frame viewer, a progress bar, and a live events feed.
3. **Protection:** status card (state, time remaining, source), threat level badge (NONE, MONITORING, SUSPICIOUS, THREAT), start and end controls.
4. **Incidents:** list with severity colors, detail view with reason codes, event timeline, evidence clip, and the AI explanation.
5. **Notifications panel:** history, plus a clearly labeled "Simulated Alexa deterrent" panel.
6. **Settings:** loitering threshold, timeout, distance threshold, protection zone input.
7. Evidence report export button (calls P4's endpoint).
8. **Ring status card:** shows device/integration status honestly (real or local adapter).
9. Polish: consistent theme, empty states, error states, and a demo mode that guides judges.

**Acceptance:** the full flow works with mock data on day 1 and with the live backend later; no raw JSON visible to users; any simulated element is labeled "Simulated".

### 7.4 P4: Integrations, Evidence, QA, Pitch

**Files:** `backend/integrations/`, `evidence_service.py`, `llm_service.py`, `tests/e2e/`, `docs/demo_script.md`, pitch deck

**Tasks (in order):**

1. **Ring validation (hours 0 to 3, do not wait).** Answer the checklist in section 8, ask the organizers directly, and report in the group chat what is actually available.
2. `RingIntegration` base class, `LocalAdapter` (reads sample events, simulates device status), and the real adapter for whatever is available.
3. Notification layer: `Notifier` base, dashboard notifier (writes to DB), optional Telegram notifier. Notification history endpoint.
4. Simulated deterrent: a function that logs "Simulated Alexa: 'This package is being monitored'" plus a DB record flagged `simulated=true`.
5. `evidence_service.py`: cut a clip around the incident (start minus 5 s to end plus 5 s) with OpenCV or ffmpeg, save key frames, apply face blur (OpenCV DNN or Haar), and save metadata with timestamps.
6. Report export (HTML or PDF) with incident details, timeline, reason codes, and key frames.
7. `llm_service.py`: Ollama explanation with a template fallback.
8. Test videos: shoot or source 4 to 5 clips (normal passerby, loiterer, theft, homeowner retrieval, delivery). Share them with P1.
9. E2E tests, demo script, backup demo recording, and the pitch deck.

**Acceptance:** an incident produces a playable, face-blurred clip; notification history shows entries; the Ring integration is demonstrably real, or its limits are clearly documented; the full demo can be run from a clean clone by following `docs/demo_script.md`.

---

## 8. Ring integration plan (P4 leads)

The Ring track requires using Ring APIs, SDKs, simulators, or devices. Do not assume Ring exposes arbitrary video access, programmable alarms, or every device control.

**Validation checklist (answer within 3 hours):**

1. Which Ring developer APIs or SDKs are available to us?
2. Is there a simulator or test environment from the organizers?
3. Can we retrieve device events or video through the supported interface?
4. Which actions are supported?
5. What authentication or approval is required?
6. Can the integration be demonstrated live during judging?

**Architecture:**

```python
class RingIntegration(ABC):
    @abstractmethod
    def get_device_status(self) -> DeviceStatus: ...
    @abstractmethod
    def get_recent_events(self) -> list[RingEvent]: ...
    @abstractmethod
    def trigger_supported_action(self, action: AllowedAction) -> ActionResult: ...
```

- `LocalAdapter`: development and testing only.
- `RealAdapter`: wired to whatever the hackathon gives us.
- `RING_MODE` env var switches between them. The final submission must use the real adapter for at least one meaningful capability (for example, a delivery or motion event starting protection, or a supported action on incident).
- The method names above are illustrative; adapt them to the real SDK.

---

## 9. Privacy and safety rules (non-negotiable)

- Video is stored locally; no uploads to external AI services.
- Blur faces in exported evidence.
- Never auto-call police. Never accuse an identifiable person. No face recognition.
- Sensitive external actions require homeowner confirmation.
- Only allowlisted actions can run (`AllowedAction` enum). An LLM can never execute commands or trigger actions.
- Incident creation and escalation are deterministic and logged with reason codes.
- Simulated features are always labeled "Simulated" in the UI.
- Alert wording: "potential package theft, for review", never "thief detected".

---

## 10. AI prompts

### 10.1 MASTER PROMPT (paste at the start of every AI session, or save as `CLAUDE.md`)

```
You are a senior engineer on a 4-person hackathon team building "porchPiracyAI",
an AI-powered package protection system for the Amazon AI Hackathon (Ring track).

## What the product does
It ingests porch video, detects people and packages, tracks them, classifies events,
runs a deterministic threat rule engine inside a protection-mode state machine,
creates incidents with evidence clips (face-blurred), notifies the homeowner,
and triggers a SIMULATED deterrent. It must integrate with a real Ring API/SDK/
simulator/device (via a RingIntegration adapter) and must process real video.

## Stack
Python 3.11, FastAPI + Uvicorn, Streamlit, OpenCV, ffmpeg, Ultralytics YOLO,
supervision ByteTrack, Pydantic v2 + SQLModel, SQLite, Ollama (optional),
pytest, ruff.

## Architecture rules
- Modular monolith. Folders: frontend/, backend/{api,core,models,schemas,services,integrations}/.
- Contracts live in backend/schemas/ and the API list in DEVELOPMENT.md section 5. Do NOT
  change a contract without telling me; if a change is required, propose it explicitly.
- Protection state machine and threat rules are PURE functions (no I/O, no DB, no clock
  calls inside; pass `now` in). They must have unit tests.
- Detection/tracking/event code never touches the DB or HTTP directly; it emits Event
  objects through a callback.
- The LLM only explains structured events. It never decides, creates incidents,
  or executes actions. Incident creation is deterministic.
- A package disappearing is NOT proof of theft. Use event sequences and time windows.
- Protection state and incident state are separate.
- Deduplicate incidents (one per session + person track + reason group within a cooldown).
- Never use face recognition. Never auto-contact police. Label simulated features "Simulated".
- Config via pydantic-settings; no hardcoded thresholds or secrets.

## Code conventions
- Type hints everywhere, Pydantic models at boundaries, small functions, docstrings
  for public functions.
- Follow ruff defaults, line length 100.
- Log with the `logging` module, not print.
- Raise custom exceptions from backend/core/exceptions.py.
- Write pytest tests alongside new logic. Keep tests fast and deterministic.

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

## My role and owned area
[PASTE YOUR ROLE PROMPT FROM SECTION 10.2 TO 10.5 HERE]
```

### 10.2 P1 role prompt (Vision and AI Pipeline)

```
I am P1 (Vision and AI Pipeline). I own: backend/services/{video,detection,tracking,event}_service.py
and tests/unit/test_event_classifier.py.

Output contract: Event objects exactly per backend/schemas/event_schema.py.
I never call the DB or HTTP; I call an `on_event` callback.

Current task: <describe, e.g. "implement detection_service.detect(frame) using
Ultralytics YOLO for people and a package detector; load models once; return
list[Detection] filtered by DETECTION_CONF_THRESHOLD">.

Constraints: must run on a laptop CPU/GPU at ~5+ effective FPS using FRAME_STRIDE;
emit events on state change with cooldown, not per frame; geometry thresholds come
from config; produce an annotated video with boxes, track IDs, and the protection zone.
Include a small CLI (`python -m backend.services.video_service sample.mp4`) so I can
test without the API.
```

### 10.3 P2 role prompt (Backend and Decision Engine)

```
I am P2 (Backend and Decision Engine). I own: main.py, backend/api/, backend/core/,
backend/models/, backend/schemas/ (shared, changes are announced), and
services protection_service.py, threat_service.py, incident_service.py, response_service.py.

Current task: <describe, e.g. "implement the protection state machine as pure
functions with an explicit transition table, InvalidTransition exception, and
pytest tests covering every valid and invalid transition, plus timeout">.

Constraints: state machine and threat rules are pure and take `now` as a parameter;
incidents are deduplicated with a cooldown; every incident stores reason_codes and
event_ids; endpoints match DEVELOPMENT.md section 5.5 exactly; until P1's pipeline is
ready, endpoints must work from samples/mock_events.json.
```

### 10.4 P3 role prompt (Frontend and UX)

```
I am P3 (Frontend and UX). I own: app.py and frontend/. I only talk to the backend
through frontend/api_client.py. I must support USE_MOCK=true reading samples/mock_events.json
so I am never blocked.

Current task: <describe, e.g. "build the Incidents page: severity-colored list,
detail view with reason codes, an event timeline, evidence clip player, and AI
explanation, with empty and error states">.

Constraints: Streamlit multipage; auto-refresh every 2 s during analysis using
st.fragment(run_every=2) or streamlit-autorefresh; no raw JSON shown to users;
anything simulated is labeled "Simulated"; wording is "potential package theft, for
review", never "thief detected"; a clean, demo-friendly look.
```

### 10.5 P4 role prompt (Integrations, Evidence, QA)

```
I am P4 (Integrations, Evidence, QA, Pitch). I own: backend/integrations/,
backend/services/evidence_service.py, backend/services/llm_service.py, tests/e2e/,
docs/demo_script.md.

Current task: <describe, e.g. "implement evidence_service.create_evidence(video_path,
incident) that cuts a clip from start_s-5 to end_s+5 with OpenCV/ffmpeg, saves 3 key
frames, blurs faces, and returns file paths and metadata">.

Constraints: Ring access goes through RingIntegration with RING_MODE=local|real;
only allowlisted actions can be triggered; the LLM receives only compact structured
summaries and has a template fallback; evidence stays local; faces are blurred in exports.
```

### 10.6 Reusable task prompts

**Write unit tests**
```
Write pytest tests for <file>. Cover every branch in the spec in DEVELOPMENT.md
section 6, edge cases, and invalid input. Tests must be deterministic: no sleeps,
no real clock, no network. Show how to run them.
```

**Code review**
```
Review this diff against DEVELOPMENT.md: contract violations, purity of the state
machine and rules, missing tests, privacy/safety rules (section 9), performance
problems, and anything that would break the demo. List issues by severity with fixes.
```

**Debug**
```
Here is the error and the relevant code. Give: the most likely cause, a minimal fix,
and how to confirm it. Do not rewrite unrelated code.
```

**Integration handoff**
```
Write a short integration note for <teammate>: what I built, function/endpoint
signatures, example input/output JSON, how to run it, and known limitations.
```

**Mock data generator**
```
Generate samples/mock_events.json for the scenarios: normal passerby, loiterer
(>threshold), interaction, theft (package removed), and authorized retrieval. Follow the
Event schema exactly, with realistic timestamps and track IDs.
```

---

## 11. AI-assisted workflow rules

1. **One task per AI session.** Start each session with the master prompt plus your role prompt plus one concrete task.
2. **Contracts first.** Give the AI the relevant schema file contents when working on anything that touches a boundary.
3. **Small steps.** Ask for one function or file at a time, run it, then continue.
4. **Always run the code.** Never merge AI output you have not executed. Run `pytest` and `ruff check .` before every PR.
5. **Ask for tests with the code.** Logic modules without tests do not get merged.
6. **Do not paste secrets** or private footage into AI tools.
7. **Read before committing.** You are responsible for every line, so be able to explain it during judging.
8. **Record decisions** (model choice, thresholds, why) in `docs/decisions.md` in 2 to 3 lines each.
9. **When the AI invents an API** (especially Ring), verify against the real documentation before relying on it.
10. **Keep CLAUDE.md in the repo root** with the master prompt so any AI tool picks up context automatically.

---

## 12. Git workflow

- `main` is always runnable. No direct commits to `main` after setup.
- Branches: `feature/p1-detection`, `feature/p2-state-machine`, `feature/p3-incident-page`, `feature/p4-evidence`.
- Commits: `<area>: <what>` (for example `vision: add ByteTrack wrapper`).
- PRs: small, one reviewer from another member (a quick look is fine), CI check = `ruff` + `pytest`.
- Merge to `main` at least every 2 to 3 hours. Long-lived branches cause pain.
- Shared files (`schemas/`, `config.py`, `requirements.txt`): announce first, merge fast.
- Setup commands:

```bash
git clone <repo> && cd porchPiracyAI
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
pre-commit install
```

- Run commands (`Makefile`):

```
make api      # uvicorn main:app --reload --port 8000
make ui       # streamlit run app.py
make test     # pytest -q
make lint     # ruff check . && ruff format --check .
```

---

## 13. Testing plan

| Level | What | Owner |
|---|---|---|
| Unit | State machine transitions, timeout, every threat rule, dedupe, event geometry | P2, P1 |
| Integration | API endpoints with httpx and a test DB; replay `mock_events.json` | P2 |
| Vision | Each sample video produces the expected event sequence within tolerance | P1 and P4 |
| E2E | Upload -> simulate delivery -> analyze -> incident -> evidence -> UI shows it | P4 |
| Manual | Demo rehearsal on a clean clone | All |

**Test video set (minimum):**

1. Delivery only, no one nearby (expect no incident).
2. Passerby walking past (expect no incident).
3. Loiterer near package for more than the threshold (expect LOW).
4. Person interacts with package and leaves it (expect MEDIUM).
5. Person takes package (expect HIGH incident plus evidence).
6. Homeowner retrieves package (expect protection ended, no incident).

---

## 14. Timeline

Scale to the real hackathon length. Percentages are of total time.

| Phase | Time | P1 | P2 | P3 | P4 |
|---|---|---|---|---|---|
| 0. Setup | 0 to 10% | Detector spike | Repo, schemas, DB, stubbed API | Streamlit skeleton with mock data | **Ring access check**, test videos |
| 1. Skeletons | 10 to 35% | Detection + tracking | State machine + tests | Upload, status, incident pages | Ring interface, local adapter, clip cutter |
| 2. Integration | 35 to 60% | Real event classifier | Threat engine, incident creation | Dashboard on live API | Notifications, deterrent, face blur |
| 3. End-to-end | 60 to 75% | Threshold tuning | Dedupe, timeouts, edge cases | Timeline, evidence view | Real Ring adapter, full-flow test |
| 4. Polish | 75 to 90% | Zone drawing, speed | Settings | UI polish, report export | LLM explanations |
| 5. Freeze | 90 to 100% | Bug fixes only | Bug fixes only | Rehearse demo | Pitch deck, backup video |

**Feature freeze at 90%.** Record a backup demo video before the final presentation.

Sync schedule: 15-minute standup every 3 to 4 hours, with blockers written in a shared checklist.

---

## 15. Definition of Done and demo script

### P0 Definition of Done

A judge can:

- [ ] Upload a porch video.
- [ ] Click "Simulate delivery" and see protection go active.
- [ ] Watch the video analyzed with boxes on people and packages.
- [ ] See a suspicious event raise an incident with severity, reason codes, and an evidence clip.
- [ ] See the Ring integration working through the real API, SDK, simulator, or device, or see clearly what is simulated.
- [ ] Run everything from a clean clone using the README.

### Demo script (about 5 minutes)

1. **Problem (30 s):** porch piracy; cameras only record.
2. **Live demo (2.5 min):** upload -> simulate delivery -> analysis runs -> incident appears with evidence.
3. **Why it was flagged (45 s):** reason codes, timeline, AI explanation.
4. **Ring integration (45 s):** show it honestly and clearly.
5. **Privacy and safety (30 s):** local processing, face blur, no auto-police, human in the loop.
6. **Roadmap (15 s):** live streams, real Ring actions, Alexa deterrent.

Always have a recorded backup of the demo.

---

## 16. Risks and mitigations

| Risk | Mitigation |
|---|---|
| No usable Ring API/SDK/simulator | P4 checks in hour 1; ask organizers; design the adapter around what is provided |
| Detector misses packages | Fine-tune or use open-vocabulary detection; shoot clear-angle videos |
| Track IDs flip | ByteTrack tuning; rules use time windows and proximity |
| Slow inference | Frame stride, downscale, small model |
| False theft alerts | "Potential" wording; no face recognition; conservative thresholds |
| Team blocked | Frozen contracts, mock data, small PRs |
| Live demo fails | Pre-recorded backup, test on the demo machine, offline-capable stack |
| Merge conflicts | Folder ownership, announce changes to shared files |

---

## 17. Appendix

### 17.1 First-hour checklist (everyone)

- [ ] P2 creates the repo, pushes the skeleton, and adds all members.
- [ ] Everyone clones, creates a venv, installs requirements, and runs `make test`.
- [ ] P2 commits `backend/schemas/` and announces it.
- [ ] P2 commits `samples/mock_events.json` (use the mock data generator prompt).
- [ ] P1 starts the detector spike; P3 starts the Streamlit skeleton in mock mode.
- [ ] P4 starts Ring validation and test video collection.
- [ ] `CLAUDE.md` is committed with the master prompt.

### 17.2 `docs/decisions.md` template

```
## <date> <decision title>
- Decision:
- Why:
- Alternatives considered:
- Owner:
```

### 17.3 PR template (`.github/pull_request_template.md`)

```
## What
## Why
## How to test
## Contracts touched? (yes/no, list)
## Checklist
- [ ] ruff + pytest pass
- [ ] Tests added for new logic
- [ ] No secrets or videos committed
- [ ] Simulated features labeled
```

### 17.4 Docs to write (owners)

| Doc | Owner | When |
|---|---|---|
| `README.md` (setup, run, demo) | P2 | Phase 4 |
| `docs/architecture.md` (diagram + module list) | P2 | Phase 3 |
| `docs/api.md` (or rely on `/docs`) | P2 | Phase 3 |
| `docs/decisions.md` | Everyone | Ongoing |
| `docs/demo_script.md` | P4 | Phase 4 |
| Pitch deck | P4 with P3 | Phase 5 |
| Privacy and safety statement (from section 9) | P4 | Phase 4 |