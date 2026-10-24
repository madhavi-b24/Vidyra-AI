"""Lesson planning: subject detection + time-aware structured lesson plan.

The planner is grounded in uploaded material (RAG) when available so the
lesson follows the real content and minimizes hallucination.
"""
from __future__ import annotations

from ..llm import get_llm
from ..rag.retriever import retrieve_context
from ..schemas import LearnerProfile, LessonPlan, Segment

SYS = (
    "You are an expert curriculum designer and master teacher. You plan "
    "lessons like a real human educator: you sequence concepts from simple "
    "to complex, pick the right depth for the learner's level and available "
    "time, and choose the most effective visual for each concept."
)

# Rough segment budget by available time -> keeps pacing human.
def _segment_budget(minutes: int) -> int:
    if minutes <= 5:
        return 3
    if minutes <= 20:
        return 5
    if minutes <= 45:
        return 7
    if minutes <= 90:
        return 9
    return 12


VISUAL_GUIDE = (
    "Choose visual_type per segment from: "
    "slide (default text points), graph (math functions/data trends), "
    "equation (formulas/derivations), code (programming), timeline (history/"
    "sequences), diagram (processes/structures/biology), map (geography/"
    "history), table (comparisons)."
)


def make_plan(
    topic: str,
    profile: LearnerProfile,
    material_id: str | None = None,
) -> LessonPlan:
    llm = get_llm()
    n = _segment_budget(profile.time_minutes)
    per_seg = round(profile.time_minutes / n, 1)

    context = retrieve_context(material_id, topic or "overview of the material", k=6)
    grounding = ""
    if context:
        grounding = (
            "\n\nGround the lesson STRICTLY in this uploaded material. Only "
            "teach what is supported by it; do not invent facts:\n" + context
        )

    prompt = f"""Design a personalized lesson.

TOPIC: {topic or "(derive the best topic from the material)"}
LEARNER LEVEL: {profile.level}
TEACHING LANGUAGE: {profile.language}
TIME AVAILABLE: {profile.time_minutes} minutes
GOAL: {profile.goal or "general understanding"}
STYLE: {profile.style}
PRIOR KNOWLEDGE: {profile.prior_knowledge or "none stated"}

{VISUAL_GUIDE}
{grounding}

Return JSON:
{{
  "topic": "final topic title",
  "subject": "Mathematics|Physics|Chemistry|Biology|History|Geography|Programming|Economics|Language|General",
  "summary": "1-2 sentence lesson overview",
  "segments": [
    {{
      "id": 1,
      "title": "short segment title",
      "concept": "the specific concept taught here",
      "objective": "what the student will be able to do after this",
      "minutes": {per_seg},
      "visual_type": "slide|graph|equation|code|timeline|diagram|map|table",
      "difficulty": "beginner|intermediate|advanced",
      "question_after": true
    }}
  ]
}}

Create exactly {n} segments. Order them pedagogically (foundations first).
Scale depth to the learner level and the {profile.time_minutes}-minute budget.
Make roughly 60-70% of segments end with a question (question_after=true)."""

    data = llm.json(prompt, system=SYS, max_tokens=3000)

    segs = []
    for i, s in enumerate(data.get("segments", []), 1):
        segs.append(
            Segment(
                id=int(s.get("id", i)),
                title=s.get("title", f"Part {i}"),
                concept=s.get("concept", ""),
                objective=s.get("objective", ""),
                minutes=float(s.get("minutes", per_seg)),
                visual_type=s.get("visual_type", "slide"),
                difficulty=s.get("difficulty", profile.level),
                question_after=bool(s.get("question_after", True)),
            )
        )
    return LessonPlan(
        topic=data.get("topic", topic or "Lesson"),
        subject=data.get("subject", "General"),
        summary=data.get("summary", ""),
        total_minutes=profile.time_minutes,
        language=profile.language,
        segments=segs,
    )