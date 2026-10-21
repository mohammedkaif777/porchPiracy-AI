# Decision Log (ADR)

Short entries, 2 to 3 lines each. Newest first.

---

## 2026-10-21 Modular monolith over microservices
- **Decision:** One Python application (`backend/` + `frontend/`) with one SQLite DB and one process.
- **Why:** A hackathon has hours, not days. A single deployable removes network failure modes from the demo and lets every module ship in one commit.
- **Alternatives considered:** FastAPI + Streamlit as separate deploys (unnecessary operational overhead); Celery/Redis for the analysis queue (a background task in FastAPI is enough).
- **Owner:** P2

## 2026-10-21 Pure-function decision core
- **Decision:** The protection state machine and the threat rule engine are pure functions; `now` and thresholds are passed in as arguments.
- **Why:** The rules are the product. Purity makes every branch unit-testable, replayable from `mock_events.json`, and auditable by judges.
- **Alternatives considered:** Class-based services reading the clock and settings internally (untestable without patching).
- **Owner:** P2

## 2026-10-21 Rules decide, models observe
- **Decision:** Detection models only produce observations; incidents are created by deterministic rules, never by a model or an LLM.
- **Why:** Judges must be able to explain every alert with reason codes and event IDs. "The AI decided" is not an acceptable answer for a security product.
- **Alternatives considered:** LLM-as-judge (non-deterministic, hallucination risk, no audit trail).
- **Owner:** P2

## 2026-10-21 Package disappearance is not theft
- **Decision:** `PACKAGE_REMOVED` raises HIGH only when a person track is associated with the package (overlap or co-movement) or the package moved first. A bare disappearance yields `MONITORING`.
- **Why:** Occlusion, camera angle and delivery-person pickups all look identical to theft in a single frame. False theft accusations are the worst failure mode of this product.
- **Alternatives considered:** Treating a lost package track as theft (too many false positives).
- **Owner:** P2

## 2026-10-21 Optional heavy dependencies, lazy imports
- **Decision:** `ultralytics`, `supervision`, `cv2` are imported inside functions, never at module import time.
- **Why:** The API, the dashboard and the whole test suite must run on a clean machine without the 500 MB of ML stack. Failing soft beats failing to boot.
- **Alternatives considered:** Separate requirements files per service (microservice smell, adds deployment complexity).
- **Owner:** P1

## 2026-10-21 Package detection strategy (spike)
- **Decision:** Person detection with Ultralytics YOLO (COCO class `person`); package detection through a dedicated package model path with a COCO-proxy fallback (`suitcase`, `handbag`, `backpack`) when the dedicated weights are absent.
- **Why:** COCO has no `package` class. A dedicated model path keeps the door open for a fine-tuned Roboflow parcel model, while the proxy fallback lets the pipeline run end-to-end on day one.
- **Alternatives considered:** YOLO-World / OWL-ViT open-vocabulary prompting (heavier, slower on CPU); fine-tuning without a labelled dataset (no time).
- **Owner:** P1

## 2026-10-21 Evidence is cut from the original video with OpenCV
- **Decision:** Evidence clips are produced with OpenCV VideoCapture/VideoWriter around the incident window (±5 s), with key frames written as JPEG and faces blurred with a Haar cascade.
- **Why:** `opencv-python` is already a dependency; the OpenCV path has no external binary and works on every demo machine. `ffmpeg` is used when available for better quality.
- **Alternatives considered:** `ffmpeg` only (adds a system dependency that may be missing on the judge machine); storing full videos per incident (wasteful).
- **Owner:** P4

## 2026-10-21 Ring behind an adapter with an explicit local mode
- **Decision:** `RingIntegration` ABC with `LocalAdapter` and `RealAdapter`, selected by `RING_MODE`. The real adapter reads credentials from env vars and degrades to a `degraded` status when they are missing.
- **Why:** The exact Ring capability set available to us is not known up front. The adapter boundary means the rest of the app never changes, and the UI can state honestly which capabilities are real and which are simulated.
- **Alternatives considered:** Calling the Ring SDK inline (couples everything to an SDK we cannot yet test).
- **Owner:** P4

## 2026-10-21 Simulated deterrent is a first-class, labeled record
- **Decision:** The Alexa deterrent writes a `notification` row with `simulated = true` and is rendered with a "Simulated" badge in the UI.
- **Why:** Honesty about what is real is a judging criterion. Labeling it in the data model, not just the UI, makes it impossible to forget.
- **Alternatives considered:** Omitting the deterrent (loses a differentiator); hiding the simulated flag (violates privacy/safety rules).
- **Owner:** P4

## 2026-10-21 Mock-first endpoints and `samples/mock_events.json`
- **Decision:** Every API endpoint works against mock data before the vision pipeline is finished, and `make seed` loads the mock event stream into the database.
- **Why:** Removes the team dependency bottleneck: frontend, integration and QA work are unblocked from hour one.
- **Alternatives considered:** Building the backend bottom-up only (P3 would idle).
- **Owner:** P2

## 2026-10-21 Incident de-duplication by (session, person, reason group) with a cooldown
- **Decision:** One incident per session + person track + reason group within `INCIDENT_COOLDOWN_SECONDS` (default 30). Later severity escalations update the existing incident.
- **Why:** A person lingering for two minutes must not produce a hundred alerts. Coalescing also keeps the evidence bundle and the notification history meaningful.
- **Alternatives considered:** One incident per event (alert spam); one incident per session (loses the attacker/track distinction).
- **Owner:** P2

## 2026-10-21 LLM explanation is optional and non-authoritative
- **Decision:** Ollama produces a 2–3 sentence explanation from a compact structured summary; a deterministic template is the fallback. The LLM receives no frames and can trigger no actions.
- **Why:** Improves the "why was it flagged" moment for judges without putting an LLM in the safety-critical path or sending footage off the machine.
- **Alternatives considered:** Mandatory LLM (breaks the demo when Ollama is down); sending frames to a cloud LLM (violates the privacy rules).
- **Owner:** P4
