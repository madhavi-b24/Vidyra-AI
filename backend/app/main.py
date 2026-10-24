"""AI Teacher API — orchestrates RAG, the adaptive tutor, and video.

Run:  uvicorn app.main:app --reload  (from the backend/ directory)
"""
from __future__ import annotations

import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .rag import store as vec
from .schemas import LearnerProfile, Question
from .storage import db
from .teaching import assessment, misconception, planner, profile as profile_parser, tutor

app = FastAPI(title="AI Teacher", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# In-memory teaching sessions (per running server).
SESSIONS: dict[str, dict] = {}

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


# ----------------------------- health -------------------------------------
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_ready": bool(settings.gemini_api_key) or settings.llm_provider == "ollama",
        "tts": settings.tts_provider,
        "avatar": settings.avatar_mode,
        "embeddings": settings.embeddings_provider,
    }


# ----------------------------- upload -------------------------------------
@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    dest = settings.uploads_path / file.filename
    dest.write_bytes(await file.read())
    try:
        info = vec.ingest_document(str(dest), file.filename)
    except Exception as exc:
        raise HTTPException(400, f"Could not process file: {exc}")
    return info


# ----------------------------- plan ---------------------------------------
class PlanReq(BaseModel):
    instruction: str = ""       # free-text scenario, e.g. "Teach me Ch4 in Hindi..."
    topic: str = ""
    material_id: str | None = None
    name: str = "Student"
    level: str = "beginner"
    language: str = "English"
    time_minutes: int = 20
    goal: str = ""
    style: str = "simple examples"


@app.post("/api/plan")
def create_plan(req: PlanReq):
    try:
        if req.instruction.strip():
            prof, topic = profile_parser.parse_instruction(req.instruction, req.topic)
            prof.name = req.name
            if req.material_id and not topic:
                topic = "the uploaded material"
        else:
            prof = LearnerProfile(
                name=req.name, level=req.level, language=req.language,
                time_minutes=req.time_minutes, goal=req.goal, style=req.style,
            )
            topic = req.topic or "the uploaded material"

        plan = planner.make_plan(topic, prof, req.material_id)
        db.save_profile(prof)
        sid = str(uuid.uuid4())[:12]
        SESSIONS[sid] = {
            "profile": prof, "plan": plan, "material_id": req.material_id,
            "contents": {}, "questions": {}, "quiz": [],
        }
        return {"session_id": sid, "profile": prof.model_dump(),
                "plan": plan.model_dump()}
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(500, f"Planning failed: {exc}")


def _session(sid: str) -> dict:
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Session not found. Create a plan first.")
    return s


# --------------------------- teach a segment ------------------------------
class TeachReq(BaseModel):
    session_id: str
    segment_id: int
    adapt: str | None = None    # reteach|simplify|harder|example


@app.post("/api/teach")
def teach(req: TeachReq):
    s = _session(req.session_id)
    seg = next((x for x in s["plan"].segments if x.id == req.segment_id), None)
    if not seg:
        raise HTTPException(404, "Segment not found")
    try:
        content = tutor.teach_segment(
            s["plan"], seg, s["profile"], s["material_id"], adapt=req.adapt
        )
        if not req.adapt:
            s["contents"][seg.id] = content
        return content.model_dump()
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(500, f"Teaching failed: {exc}")


# --------------------------- ask a question -------------------------------
class QReq(BaseModel):
    session_id: str
    segment_id: int


@app.post("/api/question")
def question(req: QReq):
    s = _session(req.session_id)
    seg = next((x for x in s["plan"].segments if x.id == req.segment_id), None)
    if not seg:
        raise HTTPException(404, "Segment not found")
    q = tutor.make_question(seg, s["profile"])
    s["questions"][q.id] = (q, seg.concept)
    return q.model_dump()


# --------------------------- evaluate answer ------------------------------
class AnswerReq(BaseModel):
    session_id: str
    question_id: str
    answer: str


@app.post("/api/answer")
def answer(req: AnswerReq):
    s = _session(req.session_id)
    entry = s["questions"].get(req.question_id)
    if not entry:
        raise HTTPException(404, "Question not found")
    q, concept = entry
    ev = tutor.evaluate_answer(q, req.answer, concept, s["profile"])
    out = {"evaluation": ev.model_dump()}
    # adaptive re-teach on misconception
    if not ev.correct and ev.misconception:
        rem = misconception.remediate(concept, ev.misconception, req.answer, s["profile"])
        s["questions"][rem["recheck"].id] = (rem["recheck"], concept)
        out["remediation"] = {
            "narration": rem["narration"],
            "analogy": rem["analogy"],
            "example": rem["example"],
            "recheck": rem["recheck"].model_dump(),
        }
    return out


# --------------------------- generate video -------------------------------
class VideoReq(BaseModel):
    session_id: str


@app.post("/api/video")
def video(req: VideoReq):
    s = _session(req.session_id)
    from .media import video as vid

    plan = s["plan"]
    contents = []
    for seg in plan.segments:
        c = s["contents"].get(seg.id)
        if c is None:
            c = tutor.teach_segment(plan, seg, s["profile"], s["material_id"])
            s["contents"][seg.id] = c
        contents.append(c)

    out = settings.outputs_path / f"lesson_{req.session_id}.mp4"
    try:
        vid.build_lesson_video(
            contents, s["profile"], plan.topic, plan.subject, out
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(500, f"Video generation failed: {exc}")
    return {"video_url": f"/outputs/{out.name}"}


# ------------------------------- quiz -------------------------------------
class QuizReq(BaseModel):
    session_id: str
    n: int = 5


@app.post("/api/quiz")
def quiz(req: QuizReq):
    s = _session(req.session_id)
    qs = assessment.build_quiz(s["plan"], s["profile"], req.n)
    s["quiz"] = qs
    return {"questions": [q.model_dump() for q in qs]}


class GradeReq(BaseModel):
    session_id: str
    answers: dict[str, str]


@app.post("/api/grade")
def grade(req: GradeReq):
    s = _session(req.session_id)
    qs: list[Question] = s.get("quiz", [])
    if not qs:
        raise HTTPException(400, "No quiz to grade. Call /api/quiz first.")
    evals, report = assessment.grade_quiz(s["plan"], qs, req.answers, s["profile"])
    db.record_result(report)
    return {
        "evaluations": [e.model_dump() for e in evals],
        "report": report.model_dump(),
    }


@app.get("/api/history")
def history():
    return {"history": db.get_history()}


@app.get("/api/path")
def learning_path(topic: str, level: str = "beginner"):
    prof = LearnerProfile(level=level)
    return {"steps": assessment.learning_path(topic, prof)}


# --------------------------- static serving -------------------------------
app.mount("/outputs", StaticFiles(directory=str(settings.outputs_path)), name="outputs")


@app.get("/")
def index():
    idx = FRONTEND_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return JSONResponse({"message": "AI Teacher API running. Frontend not found."})


if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="app")