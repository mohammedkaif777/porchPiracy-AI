# porchPiracyAI

**AI-powered package protection for the Ring ecosystem.**

> Amazon AI Hackathon | Primary Track: Ring

Traditional security cameras record what happened. **porchPiracyAI recognizes what is happening and responds.**

Package theft ("porch piracy") is usually discovered only after the package is gone. porchPiracyAI turns a passive camera feed into an active protection workflow: it detects a delivery, guards the package, spots suspicious behavior, creates an incident with evidence, and triggers a response, all processed locally on real video.

---

## Table of Contents

- [How it works](#how-it-works)
- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Usage and demo walkthrough](#usage-and-demo-walkthrough)
- [Ring integration](#ring-integration)
- [Threat assessment](#threat-assessment)
- [Privacy and safety](#privacy-and-safety)
- [Project structure](#project-structure)
- [Testing](#testing)
- [API](#api)
- [Configuration](#configuration)
- [Limitations](#limitations)
- [Roadmap](#roadmap)
- [Team](#team)
- [License and acknowledgements](#license-and-acknowledgements)

---

## How it works

1. **Delivery event:** a delivery (real, simulated, or manual) activates **protection mode**.
2. **Vision pipeline:** each video frame is analyzed to detect people and packages and track them with stable IDs.
3. **Event classification:** raw tracks become meaningful events such as `PERSON_NEAR_PACKAGE`, `LOITERING_DETECTED`, `PACKAGE_INTERACTION`, and `PACKAGE_REMOVED`.
4. **Threat assessment:** a deterministic rule engine and a protection state machine evaluate the event sequence. A single frame is never treated as proof.
5. **Incident response:** when the rules fire, the system creates one incident (no duplicate alerts), saves a face-blurred evidence clip, notifies the homeowner, and triggers a simulated deterrent.
6. **Explanation:** an optional local LLM explains the evidence in plain language. It never makes security decisions.

---

## Features

### Core

- Upload a prerecorded porch video and watch it analyzed with live annotations
- Package and person detection with multi-object tracking
- Delivery workflow that activates protection mode (manual or simulated delivery)
- Protection state machine with timeout, retrieval, and manual end
- Rule-based threat assessment with configurable thresholds
- Incident creation with severity, reason codes, and de-duplication
- Evidence capture: incident clip, key frames, and timestamps
- Dashboard showing package status, protection state, threat level, and incidents

### Differentiators

- Visual package protection zone
- Configurable loitering duration
- LLM-generated incident explanations (local, optional)
- Incident timeline and notification history
- Privacy-preserving face blurring in exported evidence
- Exportable evidence report
- Simulated Alexa voice deterrent (clearly labeled as simulated)

---

## Architecture

```
              Ring API / SDK / Simulator
                         |
                Ring Integration Layer
                         |
                         v
+----------------------------------------------------+
|                  PARCEL GUARD AI                   |
|                                                    |
|  Video Ingestion -> Computer Vision Pipeline       |
|  (frames)           (detect, track, geometry)      |
|                              |                     |
|                              v                     |
|                     Event Classification           |
|                              |                     |
|                              v                     |
|            Threat Assessment (rules + state machine)|
|                     |                |             |
|                     v                v             |
|           Incident Management    Optional local    |
|           (alerts, evidence)     LLM explanations  |
|                     |                              |
|                     v                              |
|            Response Orchestrator                   |
|     (notification | deterrent | audit log)         |
+---------------------+------------------------------+
                      |
                      v
              Streamlit Dashboard
```

porchPiracyAI is a **modular monolith**: one Python application with clear module boundaries, so each piece can be developed, tested, and replaced independently.

Key design decisions:

- **Deterministic decisions, AI-assisted understanding.** Vision models produce observations; rules decide. The LLM only explains.
- **Pure-function core.** The protection state machine and threat rules have no I/O, so they are fully unit-testable.
- **Protection state and incident state are separate.** A package stays protected while an incident is under review.
- **Local-first.** Video and inference stay on the machine.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Backend | FastAPI, Uvicorn |
| Dashboard | Streamlit |
| Video | OpenCV, ffmpeg |
| Detection | Ultralytics YOLO (people) plus a package detector |
| Tracking | `supervision` ByteTrack |
| Data | Pydantic v2, SQLModel, SQLite |
| Local LLM (optional) | Ollama (Llama 3.2 3B or Qwen 2.5 3B) |
| Testing | pytest, httpx |
| Quality | ruff, pre-commit |

---

## Getting started

### Prerequisites

- Python 3.11
- ffmpeg installed and on your `PATH`
- (Optional) [Ollama](https://ollama.com) for LLM explanations
- (Optional) A CUDA-capable GPU for faster inference; CPU works with frame skipping

### Installation

```bash
git clone <your-repo-url>
cd porchPiracyAI

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

### Download models

Place model weights in `models_weights/`:

```bash
# Person detector (auto-downloads on first run, or place manually)
models_weights/yolov8n.pt

# Package detector (fine-tuned or open-vocabulary; see docs/decisions.md)
models_weights/package.pt
```

> The weights are not committed to the repo. See `docs/decisions.md` for which package detector we chose and why.

### (Optional) Local LLM

```bash
ollama pull llama3.2:3b
# then set LLM_ENABLED=true in .env
```

### Run

In two terminals:

```bash
# Terminal 1: backend API
make api          # uvicorn main:app --reload --port 8000

# Terminal 2: dashboard
make ui           # streamlit run app.py
```

- Dashboard: http://localhost:8501
- API docs (OpenAPI): http://localhost:8000/docs

---

## Usage and demo walkthrough

1. Open the dashboard and go to **Live Monitor**.
2. **Upload** a porch video (samples are in `samples/videos/`).
3. Click **Simulate delivery**. Protection mode becomes **active**.
4. Start analysis and watch people and packages get boxed and tracked on the annotated video.
5. When suspicious behavior occurs, an **incident** appears with:
   - severity (LOW, MEDIUM, HIGH)
   - reason codes
   - an event timeline
   - a face-blurred evidence clip
   - a plain-language explanation
6. Check **Notifications** for the homeowner alert and the (simulated) deterrent.
7. Use **Protection** to end protection manually, or let it expire (default 6 hours, configurable).
8. Export an **evidence report** from the incident detail page.

### Sample scenarios

| Video | Expected result |
|---|---|
| Delivery only | No incident |
| Passerby walks past | No incident |
| Person lingers near package | LOW incident |
| Person touches package, leaves it | MEDIUM incident |
| Person takes package | HIGH incident plus evidence clip |
| Homeowner retrieves package | Protection ends, no incident |

---

## Ring integration

porchPiracyAI connects to the Ring ecosystem through a dedicated `RingIntegration` abstraction, so the AI pipeline is decoupled from any specific Ring capability.

```
RingIntegration (base)
   |-- RealAdapter   -> supported Ring API / SDK / simulator / device
   `-- LocalAdapter  -> development and testing only
```

Switch modes with `RING_MODE=local|real` in `.env`.

**Integration status:** `<fill in: what is connected, e.g. device status, motion/delivery events, supported actions>`

**Not simulated vs simulated (be explicit):**

| Capability | Status |
|---|---|
| `<capability 1>` | `<Real / Simulated>` |
| `<capability 2>` | `<Real / Simulated>` |

> We only use capabilities the available Ring integration actually supports. We do not assume arbitrary video access or programmable alarms.

---

## Threat assessment

Decisions are made by a deterministic rule engine over event sequences, never a single frame and never an LLM.

| Observed activity | Interpretation | Response |
|---|---|---|
| Person walks past | Normal | None |
| Brief approach | Ambiguous | Keep monitoring |
| Person near package beyond threshold | Potentially suspicious | LOW incident |
| Person interacts with package | Needs assessment | MEDIUM incident |
| Package removed by unidentified person | Potential theft | HIGH incident |
| Retrieval after homeowner-authorized action | Authorized | End protection |

Important: a package disappearing from view does not by itself prove theft; it may be a homeowner pickup, a delivery person, or an occlusion. The system accounts for this uncertainty, and every alert is worded as **potential package theft, for homeowner review**.

Each incident records its **reason codes** and the **events** that triggered it, so every alert is explainable and auditable.

---

## Privacy and safety

- Video is processed and stored **locally**; nothing is sent to external AI services.
- Faces are **blurred** in exported evidence.
- **No face recognition**, and no identification of individuals.
- The system **never automatically contacts police** and never accuses a named person.
- Sensitive external actions require homeowner confirmation.
- Only **allowlisted actions** can run; the LLM cannot execute commands or trigger actions.
- Simulated features (such as the Alexa deterrent) are always labeled **Simulated** in the UI.

---

## Project structure

```
porchPiracyAI/
├── main.py                    # FastAPI entry point
├── app.py                     # Streamlit entry point
├── frontend/                  # Dashboard pages and components
├── backend/
│   ├── api/                   # FastAPI routes
│   ├── core/                  # Config, DB, logging, exceptions
│   ├── models/                # SQLModel tables
│   ├── schemas/               # Shared data contracts
│   ├── services/              # Vision, events, protection, threat, incidents, evidence, LLM
│   └── integrations/          # Ring adapters and notifiers
├── samples/                   # Sample videos and mock events
├── tests/                     # unit / integration / e2e
├── docs/                      # architecture, API, decisions, demo script
└── DEVELOPMENT.md             # team development guide
```

---

## Testing

```bash
make test         # pytest -q
make lint         # ruff check . && ruff format --check .
```

- **Unit:** protection state machine, threat rules, event classification, de-duplication
- **Integration:** API endpoints and event replay from `samples/mock_events.json`
- **End-to-end:** upload -> delivery -> analysis -> incident -> evidence -> dashboard

---

## API

Interactive docs are served at `http://localhost:8000/docs`. Main endpoints:

| Method | Path | Purpose |
|---|---|---|
| POST | `/videos` | Upload a video |
| POST | `/videos/{id}/analyze` | Start analysis |
| POST | `/simulate/delivery` | Simulate a delivery and start protection |
| POST | `/protection/start` / `/protection/end` | Manual control |
| GET | `/protection/status` | Current protection session and threat level |
| GET | `/events` | List detected events |
| GET | `/incidents` / `/incidents/{id}` | List and inspect incidents |
| GET | `/incidents/{id}/evidence` | Evidence clip and frames |
| GET | `/incidents/{id}/report` | Exportable report |
| GET | `/ring/status` | Ring integration status |

---

## Configuration

Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
|---|---|---|
| `PROTECTION_TIMEOUT_MINUTES` | `360` | How long protection stays active |
| `LOITER_THRESHOLD_SECONDS` | `8` | Time near the package before a LOW incident |
| `NEAR_PACKAGE_DISTANCE_PX` | `150` | Distance considered "near" the package |
| `FRAME_STRIDE` | `2` | Process every Nth frame |
| `DETECTION_CONF_THRESHOLD` | `0.45` | Minimum detection confidence |
| `RING_MODE` | `local` | `local` or `real` |
| `LLM_ENABLED` | `false` | Enable local LLM explanations |

---

## Limitations

- Package detection quality depends on the model and camera angle.
- Prerecorded video is the primary demo mode; real-time streaming is future work.
- Tracking can lose identities in heavy occlusion; rules use time windows to tolerate this.
- The deterrent is simulated; real device actions depend on what the Ring integration supports.
- This is a hackathon prototype and not a certified security product.

---

## Roadmap

- Real-time stream processing
- Live Ring event ingestion and supported device actions
- Authorized delivery-event integration
- Richer scene understanding
- Real notification channels (push, SMS)
- Multi-package and multi-camera support

---

## Team

| Name | Role | Focus |
|---|---|---|
| `<Name>` | Vision and AI Pipeline | Detection, tracking, event classification |
| `<Name>` | Backend and Decision Engine | API, state machine, threat rules, incidents |
| `<Name>` | Frontend and UX | Streamlit dashboard, demo polish |
| `<Name>` | Integrations, Evidence, QA | Ring, evidence, LLM, testing, pitch |

---

## License and acknowledgements

- License: `<choose, e.g. MIT>`. Note that Ultralytics YOLO is licensed under AGPL-3.0; review this before any commercial use.
- Built with FastAPI, Streamlit, OpenCV, Ultralytics YOLO, supervision, SQLModel, and Ollama.
- Built for the Amazon AI Hackathon (Ring track).  