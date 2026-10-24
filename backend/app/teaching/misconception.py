"""Misconception-aware re-teaching.

When a student answers incorrectly, we don't just mark it wrong -- we
diagnose the wrong mental model and re-explain with a fresh analogy, a new
example, and a re-check question. (Assessment criterion #12.)
"""
from __future__ import annotations

import uuid

from ..llm import get_llm
from ..schemas import LearnerProfile, Question
from .tutor import TEACHER_SYS


def remediate(
    concept: str,
    misconception: str,
    student_answer: str,
    profile: LearnerProfile,
) -> dict:
    """Return an alternative explanation + new analogy + re-check question."""
    llm = get_llm()
    prompt = f"""A student has a misconception. Fix it like a great teacher.

CONCEPT: {concept}
STUDENT'S MISCONCEPTION: {misconception}
WHAT THEY SAID: "{student_answer}"
LANGUAGE: {profile.language}
LEVEL: {profile.level}

Do NOT just repeat the earlier explanation. Return JSON:
{{
  "narration": "gentle correction in {profile.language}: acknowledge their "
               "thinking, expose the exact flaw, then re-explain correctly "
               "with a NEW analogy (80-130 words, spoken).",
  "analogy": "the fresh analogy in one line",
  "example": "a new concrete example that makes the correct idea obvious",
  "recheck": {{
      "text": "a new question to verify they now understand ({profile.language})",
      "answer": "expected answer",
      "hint": "small hint"
  }}
}}"""
    data = llm.json(prompt, system=TEACHER_SYS, max_tokens=1000)
    rc = data.get("recheck", {}) or {}
    question = Question(
        id=str(uuid.uuid4())[:8],
        type="concept",
        text=rc.get("text", ""),
        answer=str(rc.get("answer", "")),
        hint=rc.get("hint", ""),
    )
    return {
        "narration": data.get("narration", ""),
        "analogy": data.get("analogy", ""),
        "example": data.get("example", ""),
        "recheck": question,
    }