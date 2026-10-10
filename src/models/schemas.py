from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="Tin nhắn từ user")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Phản hồi từ agent")
    analysis: str = Field(default="", description="Phân tích nội bộ")


GuidanceArea = Literal[
    "computing",
    "data_ai",
    "electrical",
    "mechanical",
    "vehicles_aerospace",
    "chemistry_materials",
    "biology_food_environment",
    "business_management",
    "education_psychology",
    "languages_media",
    "physics_sciences",
]


class ProgramGuidanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strengths: list[GuidanceArea] = Field(default_factory=list, max_length=4)
    interests: list[GuidanceArea] = Field(default_factory=list, max_length=4)
    improvements: list[GuidanceArea] = Field(default_factory=list, max_length=4)
    strengths_note: str = Field(default="", max_length=400)
    interests_note: str = Field(default="", max_length=400)
    career_direction: str = Field(default="", max_length=240)
    improvements_note: str = Field(default="", max_length=300)
    priorities: str = Field(default="", max_length=240)

    @field_validator("strengths", "interests", "improvements")
    @classmethod
    def unique_areas(cls, value):
        return list(dict.fromkeys(value))

    @field_validator("strengths_note", "interests_note", "career_direction", "improvements_note", "priorities")
    @classmethod
    def trim_text(cls, value):
        return " ".join(value.split())


class ProgramGuidanceSource(BaseModel):
    title: str
    page: int
    end_page: int
    local_url: str
    url: str
    version: str
    document_status: str


class ProgramGuidanceProfileSummary(BaseModel):
    strengths: list[str]
    interests: list[str]
    direction: list[str]
    development_goals: list[str]
    priorities: list[str]


class ProgramGuidanceCriteriaMatch(BaseModel):
    group: str
    criteria: list[str]
    topic: str
    program_name_terms: list[str]


class ProgramGuidanceUnmatchedCriteria(BaseModel):
    group: str
    criteria: list[str]
    message: str
    topic: str = ""


class ProgramGuidanceSuggestion(BaseModel):
    code: str
    name: str
    badge: str
    reasons: list[str]
    matched_strengths: list[str]
    matched_interests: list[str]
    criteria_matches: list[ProgramGuidanceCriteriaMatch]
    unmatched_criteria: list[ProgramGuidanceUnmatchedCriteria]
    insufficient_data: list[str]
    considerations: list[str]
    source: ProgramGuidanceSource


class ProgramGuidanceResponse(BaseModel):
    suggestions: list[ProgramGuidanceSuggestion] = Field(max_length=3)
    profile_summary: ProgramGuidanceProfileSummary
    unmatched_criteria: list[ProgramGuidanceUnmatchedCriteria]
    notice: str
    message: str
