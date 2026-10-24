"""Turn a free-text student instruction into a structured learner profile.

Handles the assessment's user scenario, e.g.:
  "I am a beginner. Teach me Chapter 4 in 20 minutes. Explain it in Hindi
   using simple examples. Ask me questions during the lesson."
"""
from __future__ import annotations

from ..llm import get_llm
from ..schemas import LearnerProfile

SYS = "You extract structured learning preferences from a student's request."


def parse_instruction(instruction: str, fallback_topic: str = "") -> tuple[LearnerProfile, str]:
    llm = get_llm()
    prompt = f"""A student wrote this request:
\"\"\"{instruction}\"\"\"

Extract a JSON object with these keys:
- topic: the subject/chapter/topic to teach (string). If a chapter number is
  mentioned use "Chapter N". If none, use "".
- level: one of "beginner", "intermediate", "advanced".
- language: the teaching language they want (e.g. "English", "Hindi",
  "Hinglish", "Tamil", "Telugu"). Default "English".
- time_minutes: integer minutes available (default 20).
- goal: their objective if stated, else "".
- style: preferred teaching style if stated, else "simple examples".
- prior_knowledge: anything they already know, else "".
"""
    data = llm.json(prompt, system=SYS)
    topic = (data.get("topic") or fallback_topic or "").strip()
    profile = LearnerProfile(
        level=(data.get("level") or "beginner"),
        language=(data.get("language") or "English"),
        time_minutes=int(data.get("time_minutes") or 20),
        goal=data.get("goal") or "",
        style=data.get("style") or "simple examples",
        prior_knowledge=data.get("prior_knowledge") or "",
    )
    return profile, topic