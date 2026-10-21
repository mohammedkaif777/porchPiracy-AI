# Contributing

Short version for a 4-person hackathon team. Full details in `DEVELOPMENT.md`
sections 11 and 12.

## Branches

```
main                    always runnable
feature/p1-detection
feature/p2-state-machine
feature/p3-incident-page
feature/p4-evidence
```

- Never commit directly to `main` after setup.
- Merge to `main` every 2-3 hours. Long-lived branches cause pain.
- One reviewer per PR, a quick look is enough.

## Commits

`<area>: <what>`

```
vision: add ByteTrack wrapper
backend: dedupe incidents by person track
frontend: incident list with severity colors
integrations: local Ring adapter with device status
docs: demo script runbook
```

## Before you open a PR

```bash
make lint
make test
```

Both must be green. The CI check is exactly these two commands.

## PR template

- What changed?
- Why?
- How to test it (the exact command and the expected output)?
- Contracts touched? If yes: which files, and was it announced in the group chat?
- Checklist: ruff + pytest pass, tests added for new logic, no secrets or videos
  committed, simulated features labeled.

## Shared files

`backend/schemas/`, `backend/core/config.py`, `requirements.txt` and `pyproject.toml`
are shared. Announce the change in the group chat first and merge it fast.

## AI-assisted work

- One task per AI session, with the master prompt plus your role prompt.
- Never commit AI output you have not run.
- Logic without tests does not get merged.
- Never paste secrets or private footage into an AI tool.
- Verify any API the AI invents (especially the Ring SDK) against real documentation.
- Record meaningful choices in `docs/decisions.md`.
