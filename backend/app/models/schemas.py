"""
AirVision Pydantic Schemas
Defines request and response models for the API endpoints.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, date


# ─── AIR QUALITY SCHEMAS ───

class AirQualityReading(BaseModel):
    """Single air quality measurement."""
    city: str
    timestamp: datetime
    pm25: Optional[float] = None
    pm10: Optional[float] = None
    no2: Optional[float] = None
    o3: Optional[float] = None
    co: Optional[float] = None
    so2: Optional[float] = None
    aqi: Optional[int] = None


class CurrentAQResponse(BaseModel):
    """Response for current air quality endpoint."""
    city: str
    timestamp: datetime
    pm25: Optional[float] = None
    pm10: Optional[float] = None
    no2: Optional[float] = None
    o3: Optional[float] = None
    co: Optional[float] = None
    so2: Optional[float] = None
    aqi: int
    category: str
    color: str
    health_advisory: str


class HistoricalResponse(BaseModel):
    """Response for historical data endpoint."""
    city: str
    time_range: str
    readings: List[AirQualityReading]
    average_aqi: float
    peak_aqi: float
    min_aqi: float


class CityComparisonResponse(BaseModel):
    """Response for city comparison endpoint."""
    cities: List[CurrentAQResponse]


# ─── FORECAST SCHEMAS ───

class ForecastResponse(BaseModel):
    """Response for prediction endpoint."""
    city: str
    forecast_date: date
    predicted_aqi: float
    predicted_pm25: float
    confidence: float
    model_used: str
    alert_level: str
    alert_color: str


class ModelComparisonResponse(BaseModel):
    """Response for model comparison endpoint."""
    model_name: str
    rmse: float
    mae: float
    r_squared: float
    training_samples: int


# ─── AUTH SCHEMAS ───

class UserRegister(BaseModel):
    """User registration request."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    """User login request."""
    email: str
    password: str


class UserProfile(BaseModel):
    """User profile response."""
    user_id: int
    username: str
    email: str
    total_points: int
    quizzes_taken: int
    avg_score: float
    streak_days: int
    created_at: datetime


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


# ─── QUIZ SCHEMAS ───

class QuizTopic(BaseModel):
    """Quiz topic summary."""
    topic_id: int
    title: str
    description: Optional[str] = None
    category: str
    difficulty: str
    question_count: int
    time_minutes: int
    points_available: int
    icon_color: str


class QuizQuestion(BaseModel):
    """Single quiz question with options."""
    question_id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    knowledge_area: Optional[str] = None


class QuizQuestionWithAnswer(QuizQuestion):
    """Quiz question with correct answer and explanation (for results)."""
    correct_answer: str
    explanation: Optional[str] = None


class QuizSubmission(BaseModel):
    """Quiz answers submitted by user."""
    topic_id: int
    answers: dict  # {question_id: "A"/"B"/"C"/"D"}
    time_taken_sec: int


class QuizResult(BaseModel):
    """Quiz attempt result."""
    topic_id: int
    topic_title: str
    score: int
    total_questions: int
    percentage: float
    points_earned: int
    time_taken_sec: int
    new_total_points: int
    questions_review: List[dict]
    knowledge_areas: dict


class PointActivity(BaseModel):
    """Single point-earning activity record."""
    activity_id: int
    activity_type: str
    points_earned: int
    description: Optional[str] = None
    created_at: datetime


class PointsSummary(BaseModel):
    """User points summary."""
    total_points: int
    quizzes_taken: int
    avg_score: float
    streak_days: int
    recent_activities: List[PointActivity]
    knowledge_strengths: dict
