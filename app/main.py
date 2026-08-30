"""
FastAPI application — serves the web UI and orchestrates the review workflow.

Endpoints:
    POST /api/review           — start a review, runs until human checkpoint
    GET  /api/review/{id}      — get current state (pending flags or complete)
    POST /api/review/{id}/submit — submit human decisions, produces final report
    GET  /api/review/{id}/report — return the final brief
    GET  /api/review/{id}/trajectory — return agent trajectory log
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Contract Risk Analyst")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# In-memory session store: session_id → state snapshot
_sessions: dict[str, dict] = {}


class ReviewRequest(BaseModel):
    contract_text: str
    contract_type: str  # "nda" or "saas_msa"


class SubmitRequest(BaseModel):
    approved_flags: list[dict]


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text())


@app.post("/api/review")
async def start_review(req: ReviewRequest):
    if req.contract_type not in ("nda", "saas_msa"):
        raise HTTPException(400, "contract_type must be 'nda' or 'saas_msa'")
    if not req.contract_text.strip():
        raise HTTPException(400, "contract_text is required")

    from graph.workflow import start_review as _start

    try:
        session_id, state = _start(req.contract_text, req.contract_type)
    except Exception as e:
        raise HTTPException(500, str(e))

    _sessions[session_id] = state

    # Serialise flagged clauses for the client
    flagged = [
        f.model_dump() if hasattr(f, "model_dump") else f
        for f in state.get("flagged_clauses", [])
    ]
    template_issues = [
        i.model_dump() if hasattr(i, "model_dump") else i
        for i in state.get("template_issues", [])
    ]

    return {
        "session_id": session_id,
        "status": "pending_review",
        "flagged_clauses": flagged,
        "missing_clauses": state.get("missing_clauses", []),
        "template_issues": template_issues,
    }


@app.get("/api/review/{session_id}")
async def get_review(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(404, "Session not found")
    state = _sessions[session_id]
    return {
        "session_id": session_id,
        "status": "complete" if state.get("final_brief") else "pending_review",
        "flagged_clauses": [
            f.model_dump() if hasattr(f, "model_dump") else f
            for f in state.get("flagged_clauses", [])
        ],
        "missing_clauses": state.get("missing_clauses", []),
    }


@app.post("/api/review/{session_id}/submit")
async def submit_review(session_id: str, req: SubmitRequest):
    if session_id not in _sessions:
        raise HTTPException(404, "Session not found")

    from graph.workflow import resume_review

    try:
        final_state = resume_review(session_id, req.approved_flags)
    except Exception as e:
        raise HTTPException(500, str(e))

    _sessions[session_id] = final_state

    return {
        "session_id": session_id,
        "status": "complete",
        "final_brief": final_state.get("final_brief", ""),
    }


@app.get("/api/review/{session_id}/report")
async def get_report(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(404, "Session not found")
    state = _sessions[session_id]
    brief = state.get("final_brief", "")
    if not brief:
        raise HTTPException(400, "Report not yet generated — submit human review first")
    return {"final_brief": brief}


@app.get("/api/review/{session_id}/trajectory")
async def get_trajectory(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(404, "Session not found")
    state = _sessions[session_id]
    trajectory = [
        t.model_dump() if hasattr(t, "model_dump") else t
        for t in state.get("trajectory", [])
    ]
    return {"trajectory": trajectory}
