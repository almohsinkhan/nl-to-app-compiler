# NL App Compiler

Production-style pipeline that converts natural-language application descriptions into strict, validated application blueprints.

## Features

- Multi-stage pipeline (intent -> system design -> schema generation -> refinement)
- Strict JSON blueprint with deterministic structure
- Simple validation checks for API/DB, auth enforcement, and UI/API binding
- Minimal targeted repair step with retry tracking and repair logs
- Execution awareness via SQLAlchemy model materialization and schema simulation
- FastAPI interface
- Evaluation harness with normal and edge prompts

## Quick Start

1. Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Set managed Groq API key using a `.env` file:

Create a `.env` file in the root directory (or use the existing one) and add your Groq API key:

```env
MANAGED_GROQ_API_KEY=gsk_your_api_key_here
```

3. Run API:

```bash
python main.py
```

4. Open the UI:

Visit `http://127.0.0.1:8000/` in your browser. The frontend is served directly by the FastAPI backend!

5. Compile prompt via API:

```bash
curl -X POST http://127.0.0.1:8000/compile \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Build a CRM with login, contacts, dashboard, role-based access"}'
```

## Deployment (Render)

This application is configured for a unified deployment on Render where both the frontend and backend run as a single web service.

1. Create a new **Web Service** on Render and connect your GitHub repository.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `python main.py`
4. Add Environment Variable:
   - Key: `MANAGED_GROQ_API_KEY`
   - Value: `gsk_your_api_key_here`

Render automatically injects the `$PORT` environment variable, which `main.py` detects to bind the Uvicorn server properly. The frontend is automatically served from the `web/` directory at the root (`/`) path, making cross-origin configuration unnecessary.

Compile responses now include:
- `issues`: detected issue messages
- `issue_details`: structured issue metadata
- `repaired`: repair actions applied during retries
- `retries`: repair retry count

## Validation + Repair Flow

After blueprint generation, the compiler runs a lightweight reliability pass:

1. Validation checks:
- API -> DB consistency: endpoint request/response fields must exist in source table fields
- Auth enforcement: write endpoints (`POST`, `PUT`, `PATCH`, `DELETE`) must have `auth_required=true` (except `/auth/*`)
- UI -> API consistency: each `binds_to_endpoint` must exist in API endpoint names

2. Repair actions (minimal edits only):
- Missing auth on write endpoint -> set `auth_required=true`
- Invalid API field not in DB -> remove the invalid field from endpoint payload schema
- Invalid UI endpoint binding -> clear `binds_to_endpoint` and component fields

3. Retry:
- If validation finds issues, one repair pass is applied and `retries` is incremented

## API Endpoints

- `GET /` - web UI
- `GET /api` - API root metadata
- `POST /config/init` - initialize Groq model/base URL override (managed API key is used automatically)
- `POST /config/set` - alias for config init
- `GET /config/status` - configuration state
- `POST /compile` - compile NL prompt into blueprint
- `POST /evaluate` - run benchmark prompts

## Compile Response Shape

```json
{
  "valid": true,
  "blueprint": { "...": "..." },
  "issues": ["Missing auth in write endpoint 'create_contact'."],
  "issue_details": [{ "code": "SIMPLE_VALIDATION_FAILED", "message": "...", "location": "simple_validator", "severity": "error" }],
  "repaired": ["Added auth_required=true to endpoint 'create_contact'."],
  "retries": 1,
  "latency_ms": 42
}
```

## Quick Evaluation (5-10 prompts)

```bash
python scripts/evaluate_quick.py --limit 10
```

Example metrics:
- `success_rate`
- `avg_latency`
- `avg_retries`
- per-prompt `issues`, `repaired`, and `retries`
# nl-to-app-compiler
