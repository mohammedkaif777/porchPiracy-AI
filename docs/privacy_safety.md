# Privacy and Safety Statement

This is the statement shown to judges and the answer to "can I trust this with video
of my house?". It is a product statement, not legal advice.

---

## 1. Where your data goes

| Data | Where it lives | Leaves the machine? |
|---|---|---|
| Uploaded video | `data/uploads/` on your machine | **No** |
| Annotated video | `data/annotated/` on your machine | **No** |
| Evidence clips and key frames | `data/evidence/` on your machine | **No** |
| Detections, events, incidents | `data/porchpiracy.db` (SQLite) on your machine | **No** |
| Deterrent and notification history | `data/porchpiracy.db` on your machine | **No** |
| LLM explanation text | Generated locally, stored in the incident row | **No** |

All inference (detection, tracking, classification) runs locally. When the optional
LLM is enabled it runs against a local Ollama instance and receives a **compact
structured summary** — reason codes, durations, event types — never frames and never
video. If Ollama is unavailable the system falls back to deterministic templates and
continues to work.

The only outbound network call the project makes is the optional Telegram notifier,
which is disabled unless both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set, and
which sends only an alert message, never video.

## 2. We blur faces

Evidence clips and key frames are processed with a face-blur step before they are
written to disk or exported. Blurring is applied to exported evidence, so a shared
report does not carry identifiable faces.

We do **not** use face recognition. There is no identity database, no embedding
storage, no "known person" matching, and no attempt to determine who anyone is. Track
IDs are per-video counters with no meaning outside that video.

## 3. We never accuse anyone

The system reports **behaviour**, never identity.

- Alert wording: "potential package theft, for review".
- Never "thief detected", never "intruder identified", never a name.
- Severity is about the observed sequence, not about a person.
- Every incident is a proposal for a human to review, and the dashboard makes that
  review explicit (`REVIEWED` / `DISMISSED`).

## 4. We never contact emergency services

There is no automatic police call, no automatic 911, no automatic emergency dispatch
and no automatic notification of any third party. A detected incident produces a
local record and a dashboard notification for the homeowner. Escalation to any
external party is a human decision.

## 5. A human stays in the loop

- Sensitive external actions require homeowner confirmation.
- Only allowlisted actions can execute — the action set is a fixed enum
  (`AllowedAction`); there is no free-text command path.
- The LLM can only produce explanatory text. It cannot create incidents, change
  severities, trigger actions or call tools.
- The threat rules are deterministic, version-controlled and unit-tested. The same
  event sequence always produces the same incident, which is what makes the output
  auditable.

## 6. Simulated features are labeled

Any feature that does not act on a real device or a real service is marked
`simulated: true` in the database and shown with a **Simulated** badge in the UI.
This includes the Alexa voice deterrent and the local Ring adapter.

| Feature | Default state | How it is labeled |
|---|---|---|
| Alexa voice deterrent | Simulated | "Simulated" badge in the notification panel |
| Ring local adapter | Simulated | Ring status card shows mode `local` and lists simulated capabilities |
| Telegram notifier | Off unless configured | Enabled/disabled state shown in settings |
| Face blur in evidence | Active | Metadata field `faces_blurred` |

We would rather show a judge a clearly-labeled simulation than an ambiguous claim.

## 7. Data you can delete

Everything lives in one directory and one SQLite file. Deleting `data/` removes all
uploaded video, annotations, evidence and database records. Nothing is replicated to
a cloud service, so there is no remote copy to forget about.

## 8. Known limitations we state openly

- Package detection quality depends on the model and the camera angle.
- Tracking can lose identity during heavy occlusion; the rules use time windows and
  spatial proximity to tolerate this.
- This is a hackathon prototype, not a certified security product.
- A "HIGH" incident means *potential* theft worth a human look. False positives are
  possible and are reduced, not eliminated, by conservative thresholds and the
  "person must be associated with the package" rule.

## 9. Quick answers

**Do you upload my video anywhere?** No. Everything is local.
**Do you identify people?** No. No face recognition, ever.
**Do you call the police?** No, never automatically.
**Can the AI take actions on its own?** No. Actions are allowlisted and the LLM
cannot trigger them.
**Why is this flagged as theft?** Reason codes and event IDs are stored with the
incident, so every alert is explainable.
**Is the deterrent real?** It is simulated, and it says so in the UI.
