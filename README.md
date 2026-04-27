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

2. Set managed Groq API key in code config:

Edit `pipeline/config.py` and set:

```python
MANAGED_GROQ_API_KEY = "your-groq-api-key"
```

3. Initialize Groq model/base URL override (no API key prompt):

```bash
python scripts/init_config.py
```

4. Run API:

```bash
uvicorn main:app --reload
```

5. Open the UI:

Visit `http://127.0.0.1:8000/` in your browser.

6. Compile prompt via API:

```bash
curl -X POST http://127.0.0.1:8000/compile \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Build a CRM with login, contacts, dashboard, role-based access"}'
```

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
