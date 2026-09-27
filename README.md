# Vera Merchant AI Assistant — Local VS Code Implementation

This implementation follows the supplied magicpin Vera challenge dataset and HTTP judge examples.

## Local run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python test_real_dataset.py
python generate_submission.py
python validate_submission.py
python run_server.py
```

Server: `http://127.0.0.1:8080`

Endpoints:
- `GET /v1/healthz`
- `GET /v1/metadata`
- `POST /v1/context`
- `POST /v1/tick`
- `POST /v1/reply`

The generated `dataset/` is deterministic from the supplied seeds and contains 5 categories, 50 merchants, 200 customers, 100 triggers and 30 canonical test pairs.

The optional `app.py` is a Streamlit demo/testing layer. It is not required by the judge API. Install `requirements-ui.txt` only when you want the UI.

## Context versioning rule

`POST /v1/context` is version-aware: a lower version returns `409 stale_version`, a higher version replaces atomically, and an equal version is accepted as an idempotent no-op.

After starting the server, verify it with:

```powershell
python test_context_version.py
```

Expected sequence: `200, 200, 200, 200, 409`.

## Live HTTP smoke test

In VS Code terminal 1:

```powershell
python run_server.py
```

In VS Code terminal 2:

```powershell
python scripts/live_api_smoke.py
```

This pushes the generated 5/50/200 dataset contexts into the local server, checks the warmup counts, pushes a real trigger, calls `/v1/tick`, and exercises `/v1/reply`.
