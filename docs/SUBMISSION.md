# Submission checklist

## During the hackathon

- [ ] **Public** GitHub repo created, project pushed
- [ ] No secret versioned: `git ls-files | grep -E "\.env$|demo_credentials|\.db$"` must print nothing
- [ ] Aikido: account created, repo connected, **baseline audit run**, "before" screenshot in `docs/aikido/before.png`
- [ ] Aikido fixes logged in [SECURITY.md](SECURITY.md#fix-log), findings marked as resolved, audit re-run, "after" screenshot in `docs/aikido/after.png`
- [ ] `pytest` green
- [ ] (Optional) `GEMINI_API_KEY` tested locally, not committed
- [ ] (Optional) `ELEVENLABS_API_KEY` tested locally, not committed
- [ ] (Optional) Cloud Run deployment with `ALLOWED_HOSTS` set, URL tested in a private window

## Video

- [ ] Follow [DEMO_SCRIPT.md](DEMO_SCRIPT.md), duration **< 3 minutes**
- [ ] No key or password visible on screen
- [ ] Link accessible without sign-in (unlisted YouTube, public Loom…)

## Builderbase (one team member)

- [ ] Short description: [PITCH.md](PITCH.md#short-description-builderbase-about-80-words)
- [ ] Video link
- [ ] GitHub repo link
- [ ] Aikido before and after screenshots
- [ ] Open **every link in a private window** before submitting
- [ ] Submit. After the final submission, no more code changes.

## Suggested split (4 people)

| Role | Responsibilities |
| --- | --- |
| Data and engine | `data/`, `app/engine/` (signals, decision, feedback), engine tests |
| API, security, human in the loop | `app/routes/`, `app/security.py`, `app/engine/hitl.py`, Aikido, security tests |
| Front end and demo | `static/`, channel views, translations, screenshots |
| Pitch and video | [VISION.md](VISION.md), [PITCH.md](PITCH.md), video, Builderbase |
