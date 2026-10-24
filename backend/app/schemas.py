"""Pydantic schemas shared across the app."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Level = Literal["beginner", "intermediate", "advanced"]
VisualType = Literal[
    "slide", "graph", "equation", "code", "timeline", "diagram", "map", "table"
]


# ----------------------------- learner ------------------------------------
class LearnerProfile(BaseModel):
    name: str = "Student"
    level: Level = "beginner"
    language: str = "English"          # e.g. "Hindi", "Hinglish", "Tamil"
    time_minutes: int = 20
    goal: str = ""                     # e.g. "exam prep", "interview"
    style: str = "simple examples"     # preferred teaching style
    prior_knowledge: str = ""


# ----------------------------- lesson -------------------------------------
class Segment(BaseModel):
    id: int
    title: str
    concept: str
    objective: str
    minutes: float = 2.0
    visual_type: VisualType = "slide"
    difficulty: Level = "beginner"
    question_after: bool = True


class LessonPlan(BaseModel):
    topic: str
    subject: str = "General"
    summary: str = ""
    total_minutes: int = 20
    language: str = "English"
    segments: list[Segment] = Field(default_factory=list)


# --------------------------- taught content -------------------------------
class VisualSpec(BaseModel):
    type: VisualType = "slide"
    title: str = ""
    bullets: list[str] = Field(default_factory=list)
    # graph
    x: list[float] | None = None
    y: list[float] | None = None
    x_label: str = "x"
    y_label: str = "y"
    curve_label: str = ""
    # equation / code
    equation: str = ""
    code: str = ""
    code_lang: str = "python"
    # timeline / diagram / table
    items: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    note: str = ""


class SegmentContent(BaseModel):
    segment_id: int
    title: str
    narration: str                       # spoken by the AI teacher (voice)
    on_screen: list[str] = Field(default_factory=list)
    example: str = ""
    visual: VisualSpec = Field(default_factory=VisualSpec)


class Question(BaseModel):
    id: str
    segment_id: int | None = None
    type: Literal["mcq", "short", "concept", "problem"] = "concept"
    text: str
    options: list[str] = Field(default_factory=list)
    answer: str = ""
    hint: str = ""


class Evaluation(BaseModel):
    correct: bool = False
    understanding: float = 0.0           # 0..1
    misconception: Optional[str] = None
    feedback: str = ""
    action: Literal["advance", "reteach", "simplify", "harder", "example"] = "advance"


class ReportCard(BaseModel):
    topic: str
    score: float
    strong_areas: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    recommendation: str = ""
    next_topic: str = ""