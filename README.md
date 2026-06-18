# AI Agent Framework

A reusable, modular AI Agent Framework designed to power specialized workflows:
- Research Agents
- Interview Agents
- Resume Agents
- CRM Agents
- Sales Agents
- Proposal Agents
- Model Context Protocol (MCP) Agents
- Multi-Agent Systems

## Target Architecture

```
User Query
    ↓
 Planner
    ↓
Execution Plan
    ↓
Tool Selection
    ↓
Tool Execution
    ↓
Memory Storage
    ↓
Verification
    ↓
Response Generation
```

## Repository Structure

```
.
├── api/             # API routes and router logic
├── agents/          # Specialized agent definitions (Research, Interview, CRM, etc.)
├── core/            # Core framework logic (state, config, exceptions, executors)
│   ├── config.py
│   ├── exceptions.py
│   ├── executor.py
│   └── state.py
├── memory/          # Short-term and long-term memory adapters
├── models/          # LLM integrations and model definitions
├── planners/        # Planning strategies and reasoning loops
├── prompts/         # Base prompt templates
├── registry/        # Tool and agent registration management
├── tools/           # Reusable agent tool library
│   └── base.py
├── verification/    # Step verification/evaluation and output validation
├── tests/           # Automated unit and integration tests
├── main.py          # FastAPI application entrypoint
├── requirements.txt # Python project dependencies
└── .env             # Environment configuration variables
```

## Quickstart

### 1. Setup Environment
Install dependencies in your local Python environment:
```bash
pip install -r requirements.txt
```

Ensure a `.env` file exists in the root directory (based on the default setup).

### 2. Run the API Server
Start the FastAPI server:
```bash
uvicorn main:app --reload
```

The service runs at `http://127.0.0.1:8000`.

### 3. Verify endpoints
API docs are available at `http://127.0.0.1:8000/docs`. You can run a mock execution loop by doing:
```bash
# 1. Create a session
curl -X POST "http://127.0.0.1:8000/sessions" -H "Content-Type: application/json" -d '{"query": "Please add 10 and 15"}'

# 2. Trigger the plan execution (using the session_id from response)
curl -X POST "http://127.0.0.1:8000/sessions/<session_id>/execute"
```
