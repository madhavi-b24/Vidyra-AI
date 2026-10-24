"""Final assessment + personalized learning report."""
from __future__ import annotations

import uuid

from ..llm import get_llm
from ..schemas import (
    Evaluation,
    LearnerProfile,
    LessonPlan,
    Question,
    ReportCard,
)
from .tutor import TEACHER_SYS, evaluate_answer


def build_quiz(plan: LessonPlan, profile: LearnerProfile, n: int = 5) -> list[Question]:
    llm = get_llm()
    concepts = "; ".join(f"{s.title}: {s.concept}" for s in plan.segments)
    prompt = f"""Create a {n}-question final quiz for the lesson "{plan.topic}".
Cover the most important concepts. Mix MCQ, short-answer and one problem.
LANGUAGE: {profile.language}
LEVEL: {profile.level}
CONCEPTS COVERED: {concepts}

Return JSON: {{ "questions": [
  {{"type":"mcq|short|problem","text":"...","options":["..."],"answer":"...","hint":"..."}}
]}}"""
    data = llm.json(prompt, system=TEACHER_SYS, max_tokens=1800)
    out = []
    for q in data.get("questions", [])[:n]:
        out.append(
            Question(
                id=str(uuid.uuid4())[:8],
                type=q.get("type", "short"),
                text=q.get("text", ""),
                options=q.get("options", []) or [],
                answer=str(q.get("answer", "")),
                hint=q.get("hint", ""),
            )
        )
    return out


def grade_quiz(
    plan: LessonPlan,
    questions: list[Question],
    answers: dict[str, str],
    profile: LearnerProfile,
) -> tuple[list[Evaluation], ReportCard]:
    evals: list[Evaluation] = []
    for q in questions:
        ans = answers.get(q.id, "")
        evals.append(evaluate_answer(q, ans, q.text, profile))

    correct = sum(1 for e in evals if e.correct)
    score = round(100 * correct / max(1, len(questions)), 1)
    report = _report(plan, questions, evals, score, profile)
    return evals, report


def _report(plan, questions, evals, score, profile) -> ReportCard:
    llm = get_llm()
    lines = []
    for q, e in zip(questions, evals):
        lines.append(
            f"Q: {q.text} | correct={e.correct} | understanding={e.understanding} "
            f"| misconception={e.misconception}"
        )
    detail = "\n".join(lines)
    prompt = f"""Write a personalized learning report for "{plan.topic}".
SCORE: {score}%
RESULTS:
{detail}

Return JSON:
{{
  "strong_areas": ["concepts the student understood"],
  "weak_areas": ["concepts needing work"],
  "misconceptions": ["specific wrong ideas observed"],
  "recommendation": "2-3 sentence, specific, actionable revision advice in {profile.language}",
  "next_topic": "the single best next topic to learn"
}}"""
    data = llm.json(prompt, system=TEACHER_SYS, max_tokens=900)
    return ReportCard(
        topic=plan.topic,
        score=score,
        strong_areas=data.get("strong_areas", []) or [],
        weak_areas=data.get("weak_areas", []) or [],
        misconceptions=data.get("misconceptions", []) or [],
        recommendation=data.get("recommendation", ""),
        next_topic=data.get("next_topic", ""),
    )


def learning_path(topic: str, profile: LearnerProfile) -> list[str]:
    """AI-generated structured learning path for a broad topic."""
    llm = get_llm()
    prompt = f"""Create an ordered learning path (6-9 steps) to master "{topic}"
for a {profile.level} learner. Return JSON: {{"steps":["step 1", ...]}}"""
    data = llm.json(prompt, system=TEACHER_SYS, max_tokens=700)
    return data.get("steps", []) or []