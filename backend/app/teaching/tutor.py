"""The adaptive tutor: explain, question, evaluate, adapt.

This module is the heart of the "human-like teaching" loop:
    Explain -> Demonstrate -> Question -> Evaluate -> Adapt -> Continue

All spoken narration is produced in the learner's chosen language, while
staying grounded in uploaded material via RAG.
"""
from __future__ import annotations

import uuid

from ..llm import get_llm
from ..rag.retriever import retrieve_context
from ..schemas import (
    Evaluation,
    LearnerProfile,
    LessonPlan,
    Question,
    Segment,
    SegmentContent,
    VisualSpec,
)

TEACHER_SYS = (
    "You are 'Aria', a warm, encouraging human-like AI teacher. You explain "
    "clearly, use vivid real-world analogies and examples, and speak directly "
    "to the student ('you'). You never sound like a robot reading text. You "
    "teach progressively and check understanding. Keep spoken narration "
    "natural and conversational."
)

_ADAPT_INSTRUCTION = {
    "reteach": "The student did NOT understand. Re-explain this concept from "
    "scratch using a COMPLETELY different, simpler analogy and a concrete "
    "everyday example. Go slower.",
    "simplify": "Simplify drastically. Use the simplest possible words and one "
    "very concrete analogy. Assume no background.",
    "harder": "The student understood well. Add depth, a more advanced example "
    "and a subtle nuance to push them further.",
    "example": "Give one more different worked example of this concept.",
}


def teach_segment(
    plan: LessonPlan,
    segment: Segment,
    profile: LearnerProfile,
    material_id: str | None = None,
    adapt: str | None = None,
) -> SegmentContent:
    """Produce the spoken + visual content for one lesson segment."""
    llm = get_llm()
    context = retrieve_context(
        material_id, f"{segment.title}. {segment.concept}", k=4
    )
    grounding = (
        f"\n\nUse ONLY facts supported by this source material:\n{context}"
        if context
        else ""
    )
    adapt_note = f"\n\nADAPTATION: {_ADAPT_INSTRUCTION.get(adapt, '')}" if adapt else ""

    prompt = f"""Teach this ONE segment of the lesson "{plan.topic}" ({plan.subject}).

SEGMENT: {segment.title}
CONCEPT: {segment.concept}
OBJECTIVE: {segment.objective}
LEARNER LEVEL: {segment.difficulty}
TEACHING LANGUAGE: {profile.language}  (narration + on-screen text in THIS language)
STYLE: {profile.style}
PLANNED VISUAL: {segment.visual_type}
{grounding}{adapt_note}

Return JSON:
{{
  "narration": "60-130 words of natural spoken teaching in {profile.language}. "
               "Speak to the student, use an analogy, build intuition.",
  "on_screen": ["3-5 very short bullet points shown on screen (in {profile.language})"],
  "example": "one concrete worked example (short)",
  "visual": {{
     "type": "{segment.visual_type}",
     "title": "short visual title",
     "bullets": ["for slide/diagram: short labels"],
     "equation": "for equation type: a formula in plain text, e.g. V = I * R",
     "code": "for code type: a short runnable snippet",
     "code_lang": "python|javascript|cpp|java",
     "x": [numbers for graph x-axis, optional],
     "y": [numbers for graph y-axis, optional],
     "x_label": "graph x label",
     "y_label": "graph y label",
     "curve_label": "graph legend label",
     "items": ["for timeline/diagram: ordered steps or events"],
     "rows": [["for table: row cells"]],
     "note": "optional caption"
  }}
}}

Keep narration engaging and human. For a {segment.visual_type} visual, fill the
matching fields (e.g. graph -> x and y arrays of ~10 points)."""

    data = llm.json(prompt, system=TEACHER_SYS, max_tokens=1800)
    v = data.get("visual", {}) or {}

    # Convert values returned by the LLM into the expected format.
    def as_text(value, default=""):
        if value is None:
            return default
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        if isinstance(value, dict):
            return str(value)
        return str(value)

    def as_text_list(value):
        if not isinstance(value, list):
            return [str(value)] if value else []
        return [
            " ".join(str(part) for part in item)
            if isinstance(item, list)
            else str(item)
            for item in value
            if item is not None
        ]

    def as_number_list(value):
        if not isinstance(value, list):
            return None
        try:
            return [float(item) for item in value]
        except (TypeError, ValueError):
            return None

    v = data.get("visual", {}) or {}

    # Convert values returned by the LLM into the expected format.
    def as_text(value, default=""):
        if value is None:
            return default
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        if isinstance(value, dict):
            return str(value)
        return str(value)

    def as_text_list(value):
        if not isinstance(value, list):
            return [str(value)] if value else []
        return [
            " ".join(str(part) for part in item)
            if isinstance(item, list)
            else str(item)
            for item in value
            if item is not None
        ]

    def as_number_list(value):
        if not isinstance(value, list):
            return None
        try:
            return [float(item) for item in value]
        except (TypeError, ValueError):
            return None

    visual = VisualSpec(
        type=as_text(v.get("type"), segment.visual_type),
        title=as_text(v.get("title"), segment.title),
        bullets=as_text_list(v.get("bullets", [])),
        x=as_number_list(v.get("x")),
        y=as_number_list(v.get("y")),
        x_label=as_text(v.get("x_label"), "x"),
        y_label=as_text(v.get("y_label"), "y"),
        curve_label=as_text(v.get("curve_label")),
        equation=as_text(v.get("equation")),
        code=as_text(v.get("code")),
        code_lang=as_text(v.get("code_lang"), "python"),
        items=as_text_list(v.get("items", [])),
        rows=[
            as_text_list(row) if isinstance(row, list)
            else [str(row)]
            for row in (v.get("rows", []) or [])
        ] if isinstance(v.get("rows", []), list) else [],
        note=as_text(v.get("note")),
    )
      
    return SegmentContent(
        segment_id=segment.id,
        title=segment.title,
        narration=data.get("narration", ""),
        on_screen=data.get("on_screen", []) or [],
        example=data.get("example", ""),
        visual=visual,
    )


def make_question(
    segment: Segment, profile: LearnerProfile, kind: str | None = None
) -> Question:
    llm = get_llm()
    qkind = kind or ("mcq" if segment.difficulty == "beginner" else "concept")
    prompt = f"""Create ONE {qkind} question to check understanding of:
CONCEPT: {segment.concept}
LEVEL: {segment.difficulty}
LANGUAGE: {profile.language}

Return JSON:
{{
  "type": "{qkind}",
  "text": "the question (in {profile.language})",
  "options": ["only for mcq: 4 options"],
  "answer": "correct answer (or correct option text)",
  "hint": "a small hint"
}}"""
    data = llm.json(prompt, system=TEACHER_SYS, max_tokens=600)
    return Question(
        id=str(uuid.uuid4())[:8],
        segment_id=segment.id,
        type=data.get("type", qkind),
        text=data.get("text", ""),
        options=data.get("options", []) or [],
        answer=str(data.get("answer", "")),
        hint=data.get("hint", ""),
    )


def evaluate_answer(
    question: Question,
    student_answer: str,
    concept: str,
    profile: LearnerProfile,
) -> Evaluation:
    """Grade the answer AND detect misconceptions, choosing a next action."""
    llm = get_llm()
    prompt = f"""You are grading a student's answer like a caring teacher.

CONCEPT: {concept}
QUESTION: {question.text}
EXPECTED ANSWER: {question.answer}
STUDENT ANSWER: "{student_answer}"
LEARNER LEVEL: {profile.level}

Judge understanding, not just keyword match. If wrong, identify the specific
MISCONCEPTION (what wrong mental model produced this answer), not just "wrong".

Return JSON:
{{
  "correct": true/false,
  "understanding": 0.0-1.0,
  "misconception": "the specific wrong idea, or null if correct",
  "feedback": "short constructive feedback in {profile.language}, encouraging",
  "action": "advance|reteach|simplify|harder|example"
}}

Rules for action:
- correct & strong -> "advance" (or "harder" if they seem ready for more)
- partially correct -> "example"
- wrong / low understanding -> "reteach" (or "simplify" if very confused)"""
    data = llm.json(prompt, system=TEACHER_SYS, max_tokens=700)
    misc = data.get("misconception")
    if isinstance(misc, str) and misc.strip().lower() in {"null", "none", ""}:
        misc = None
    return Evaluation(
        correct=bool(data.get("correct", False)),
        understanding=float(data.get("understanding", 0.0)),
        misconception=misc,
        feedback=data.get("feedback", ""),
        action=data.get("action", "advance"),
    )