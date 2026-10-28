"""Web app: paste a job post and a resume, see how well they match. Runs entirely on your machine."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from . import examples
from .llm import AIProvider, OllamaProvider
from .matcher import MAX_TEXT
from .service import Report, run

HERE = Path(__file__).parent

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",  # pages contain your resume
}


def fit_label(score: int | None) -> str:
    if score is None:
        return "No score"
    if score >= 75:
        return "Strong fit"
    if score >= 50:
        return "Good fit"
    if score >= 30:
        return "Stretch"
    return "Long shot"


class AnalyzeRequest(BaseModel):
    job: str = Field(min_length=1, max_length=MAX_TEXT)
    resume: str = Field(min_length=1, max_length=MAX_TEXT)


def report_json(report: Report) -> dict:
    a = report.analysis
    return {
        "score": a.score,
        "label": fit_label(a.score),
        "matched": [{"skill": m.skill, "required": m.required, "evidence": m.evidence} for m in a.matched],
        "missing": [{"skill": m.skill, "required": m.required, "related": m.related} for m in a.missing],
        "notes": a.notes,
        "ai": {
            "available": report.ai.available,
            "message": report.ai.message,
            "error": report.ai_error,
            "extra_requirements": [e.__dict__ for e in report.extras],
            "tips": [t.model_dump() for t in report.tips],
            "blocked": [{"suggestion": b.tip.suggestion, "reason": b.reason} for b in report.blocked],
        },
    }


def create_app(provider_factory: Callable[[], AIProvider | None] | None = None) -> FastAPI:
    if provider_factory is None:
        ai_on = os.environ.get("AI_ENABLED", "true").lower() not in {"0", "false", "no"}
        provider_factory = OllamaProvider.from_env if ai_on else (lambda: None)

    app = FastAPI(title="Honest Fit", docs_url="/api/docs", redoc_url=None)
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.globals["fit_label"] = fit_label
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    def page(request: Request, job: str = "", resume: str = "", report: Report | None = None, error: str = ""):
        context = {"job": job, "resume": resume, "report": report, "error": error, "max_text": MAX_TEXT}
        status = 422 if error else 200
        return templates.TemplateResponse(request, "index.html", context, status_code=status)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, example: bool = False):
        if example:
            return page(request, examples.JOB, examples.RESUME)
        return page(request)

    @app.post("/analyze", response_class=HTMLResponse)
    def analyze_form(request: Request, job: Annotated[str, Form()] = "", resume: Annotated[str, Form()] = ""):
        if not job.strip() or not resume.strip():
            return page(request, job, resume, error="Paste both the job post and your resume.")
        if len(job) > MAX_TEXT or len(resume) > MAX_TEXT:
            return page(
                request, job[:MAX_TEXT], resume[:MAX_TEXT], error=f"Each box takes up to {MAX_TEXT:,} characters."
            )
        return page(request, job, resume, run(job, resume, provider_factory()))

    @app.post("/api/analyze")
    def analyze_api(body: AnalyzeRequest) -> JSONResponse:
        return JSONResponse(report_json(run(body.job, body.resume, provider_factory())))

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
