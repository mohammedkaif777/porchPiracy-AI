# API Reference

Base URL: `http://localhost:8000`
Interactive OpenAPI UI: `http://localhost:8000/docs` · ReDoc: `http://localhost:8000/redoc`

All request and response bodies are JSON unless noted. Schemas are defined in
`backend/schemas/` and are the frozen contract (see `DEVELOPMENT.md` section 5).

---

## Enums

| Enum | Values |
|---|---|
| `EventType` | `PACKAGE_DETECTED`, `DELIVERY_CONFIRMED`, `PERSON_APPROACHING`, `PERSON_NEAR_PACKAGE`, `LOITERING_DETECTED`, `PACKAGE_INTERACTION`, `PACKAGE_MOVEMENT_DETECTED`, `PACKAGE_REMOVED`, `PACKAGE_RETRIEVED` |
| `ProtectionState` | `IDLE`, `PACKAGE_DETECTED`, `PROTECTION_ACTIVE`, `PACKAGE_RETRIEVED`, `PROTECTION_TIMEOUT`, `PROTECTION_ENDED` |
| `Severity` | `LOW`, `MEDIUM`, `HIGH` |
| `ThreatLevel` | `NONE`, `MONITORING`, `SUSPICIOUS`, `THREAT` |
| `ReasonCode` | `LOITERING_OVER_THRESHOLD`, `PACKAGE_INTERACTION`, `PACKAGE_MOVED`, `PACKAGE_REMOVED_UNAUTHORIZED` |
| `IncidentStatus` | `OPEN`, `REVIEWED`, `DISMISSED` |
| `SessionSource` | `MANUAL`, `SIMULATED_DELIVERY`, `RING` |

---

## Health

### `GET /health`

```json
{ "status": "ok", "service": "porchpiracyai", "version": "0.1.0" }
```

---

## Videos

### `POST /videos`

Upload a video file. `multipart/form-data`, field name `file`.

**201 Created**

```json
{
  "video_id": "6f1c...",
  "filename": "porch.mp4",
  "status": "UPLOADED",
  "progress": 0.0,
  "created_at": "2026-10-21T09:15:00Z"
}
```

### `GET /videos`

List uploaded videos, newest first.

**200 OK** — array of video status objects.

### `POST /videos/{video_id}/analyze`

Start analysis of an uploaded video in a background task. The vision pipeline emits
events that flow through `POST /events` internally.

**202 Accepted**

```json
{ "video_id": "6f1c...", "status": "ANALYZING", "message": "Analysis started" }
```

**409 Conflict** — the video is already being analyzed or has already been analyzed.

### `GET /videos/{video_id}/status`

```json
{
  "video_id": "6f1c...",
  "filename": "porch.mp4",
  "status": "ANALYZING",
  "progress": 0.42,
  "frames_processed": 512,
  "total_frames": 1220,
  "current_time_s": 21.3,
  "duration_s": 50.8,
  "annotated_ready": false,
  "error": null
}
```

`status` ∈ `UPLOADED` · `ANALYZING` · `COMPLETED` · `FAILED`.

### `GET /videos/{video_id}/annotated`

Streams the annotated video (`video/mp4`) with overlay boxes, track IDs and the
protection zone. **404** if the annotated file does not exist yet.

---

## Simulated delivery

### `POST /simulate/delivery`

Simulates a package delivery and activates protection mode.

**Request** (all fields optional)

```json
{ "package_track_id": 2, "protection_zone": [[0,0],[1,0],[1,1],[0,1]] }
```

**201 Created**

```json
{
  "session_id": "a71b...",
  "state": "PROTECTION_ACTIVE",
  "source": "SIMULATED_DELIVERY",
  "started_at": "2026-10-21T09:20:00Z",
  "expires_at": "2026-10-21T15:20:00Z",
  "threat_level": "NONE",
  "package_track_id": 2,
  "protection_zone": [[0,0],[1,0],[1,1],[0,1]]
}
```

**409 Conflict** — a protection session is already active.

---

## Protection

### `POST /protection/start`

Manually start protection. Body optional: `{ "package_track_id": 2 }`.

**201 Created** — same shape as the simulated-delivery response, with `"source": "MANUAL"`.

### `POST /protection/end`

Manually end the active protection session.

**200 OK**

```json
{ "session_id": "a71b...", "state": "PROTECTION_ENDED", "message": "Protection ended manually" }
```

**404 Not Found** — no active session.

### `GET /protection/status`

```json
{
  "session_id": "a71b...",
  "state": "PROTECTION_ACTIVE",
  "source": "SIMULATED_DELIVERY",
  "started_at": "2026-10-21T09:20:00Z",
  "expires_at": "2026-10-21T15:20:00Z",
  "threat_level": "SUSPICIOUS",
  "package_track_id": 2,
  "protection_zone": [[0,0],[1,0],[1,1],[0,1]],
  "seconds_remaining": 21000
}
```

When no session exists the response is `{"state": "IDLE", "threat_level": "NONE", ...}`
with `session_id: null` (HTTP 200 — the dashboard polls this endpoint).

---

## Events

### `POST /events`

Ingest one event from the vision pipeline. This is the main ingestion endpoint:
persist → update protection → assess threat → maybe create an incident → respond.

**Request**

```json
{
  "event_id": "1c2d...",
  "session_id": "a71b...",
  "type": "PERSON_NEAR_PACKAGE",
  "timestamp_s": 72.4,
  "frame_index": 1810,
  "track_ids": { "person": 4, "package": 2 },
  "confidence": 0.91,
  "bbox": { "person": [210, 380, 300, 640], "package": [520, 600, 700, 700] },
  "metadata": {}
}
```

`event_id` is optional; the server generates one when omitted. `session_id` is optional
for events observed before protection started.

**201 Created**

```json
{
  "event": { "...": "Event as stored" },
  "threat_level": "SUSPICIOUS",
  "incident_created": true,
  "incident": { "...": "Incident as stored, when created" }
}
```

### `GET /events`

Query parameters: `session_id` (optional), `video_id` (optional), `limit` (default 200),
`event_type` (optional). Filters combine when supplied together. The Live Monitor
uses `video_id` to exclude historical, manually submitted, and other-upload events.

**200 OK** — array of events, newest first.

---

## Incidents

### `GET /incidents`

Query parameters: `session_id` (optional), `status` (optional), `severity` (optional),
`limit` (default 100).

**200 OK**

```json
[
  {
    "incident_id": "b92c...",
    "session_id": "a71b...",
    "severity": "HIGH",
    "reason_codes": ["PACKAGE_REMOVED_UNAUTHORIZED", "PACKAGE_MOVED"],
    "event_ids": ["1c2d...", "3e4f..."],
    "start_s": 68.0,
    "end_s": 80.5,
    "status": "OPEN",
    "evidence_path": "data/evidence/inc-b92c/clip.mp4",
    "explanation": "The package left its original position while a person was beside it.",
    "created_at": "2026-10-21T09:22:41Z"
  }
]
```

### `GET /incidents/{incident_id}`

**200 OK** — one incident plus its triggering events:

```json
{
  "incident": { "...": "Incident" },
  "events": [ { "...": "Event" } ],
  "evidence": { "clip_path": "...", "key_frames": ["..."], "metadata": {} }
}
```

### `POST /incidents/{incident_id}/review`

Mark an incident as reviewed or dismissed. Reviewing does **not** end protection.

**Request**

```json
{ "status": "REVIEWED", "note": "Confirmed as a neighbour grabbing a parcel" }
```

`status` ∈ `REVIEWED` | `DISMISSED`. **200 OK** returns the updated incident.

### `GET /incidents/{incident_id}/evidence`

Returns the evidence bundle for an incident.

**200 OK**

```json
{
  "incident_id": "b92c...",
  "clip_path": "data/evidence/inc-b92c/clip.mp4",
  "clip_start_s": 63.0,
  "clip_end_s": 85.5,
  "key_frames": [
    { "path": "data/evidence/inc-b92c/frame_63.jpg", "timestamp_s": 63.0, "label": "start" }
  ],
  "faces_blurred": true,
  "metadata": { "reason_codes": ["..."], "severity": "HIGH" }
}
```

**404 Not Found** — the incident has no evidence yet.

### `GET /incidents/{incident_id}/report`

Exports a self-contained HTML evidence report (printable to PDF from the browser).

**200 OK** — `text/html` document containing incident details, reason codes, the event
timeline and the key frames (inlined as base64 so the report is a single file).

---

## Notifications

### `GET /notifications`

Query parameters: `incident_id` (optional), `limit` (default 100).

**200 OK**

```json
[
  {
    "notification_id": "d41e...",
    "incident_id": "b92c...",
    "channel": "dashboard",
    "message": "Potential package theft, for review. A person was near the package.",
    "simulated": true,
    "created_at": "2026-10-21T09:22:42Z"
  }
]
```

`channel` ∈ `dashboard` · `telegram` · `deterrent`. Every record with `simulated: true`
corresponds to a feature that is not a real device action and is labeled "Simulated" in
the UI.

---

## Ring integration

### `GET /ring/status`

Reports the integration state honestly.

**200 OK**

```json
{
  "mode": "local",
  "adapter": "LocalAdapter",
  "connected": true,
  "simulated": true,
  "capabilities": [
    { "name": "device_status", "supported": true, "simulated": true },
    { "name": "recent_events", "supported": true, "simulated": true },
    { "name": "trigger_action", "supported": false, "simulated": true }
  ],
  "device": { "name": "Front Door (Local Adapter)", "battery": 82, "signal": "good" },
  "message": "Running on the local development adapter. No Ring device is connected."
}
```

---

## Settings

### `GET /settings`

```json
{
  "protection_timeout_minutes": 360,
  "loiter_threshold_seconds": 8,
  "near_package_distance_px": 150,
  "frame_stride": 2,
  "detection_conf_threshold": 0.45,
  "incident_cooldown_seconds": 30,
  "ring_mode": "local",
  "llm_enabled": false
}
```

### `PUT /settings`

Update the tunables above. Only the supplied fields change.

**200 OK** — the full settings object after the update.

---

## Error format

Every error returns the same JSON body:

```json
{ "detail": "Protection session already active", "code": "PROTECTION_ALREADY_ACTIVE" }
```

| Status | When |
|---|---|
| 400 | Invalid payload (validation error from Pydantic) |
| 404 | Unknown video, session, incident, event or evidence bundle |
| 409 | Conflicting state (session already active, video already analyzed) |
| 422 | Pydantic request validation error |
| 500 | Unexpected error; details are logged server-side, not returned |
