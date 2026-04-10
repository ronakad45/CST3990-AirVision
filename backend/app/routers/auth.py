"""
AirVision Authentication Router
User registration, login, and profile endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
from datetime import datetime

from passlib.context import CryptContext

from app.database import get_db_connection
from app.models.schemas import UserRegister, UserLogin
from app.utils.helpers import create_jwt_token, decode_jwt_token

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Dependency to extract and validate the current user from JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ")[1]
    try:
        payload = decode_jwt_token(token)
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.post("/register")
async def register(user: UserRegister):
    """Register a new user account."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if email already exists
    cursor.execute("SELECT user_id FROM users WHERE email = ?", (user.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check if username already exists
    cursor.execute("SELECT user_id FROM users WHERE username = ?", (user.username,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Username already taken")

    # Hash password and insert user
    hashed = pwd_context.hash(user.password)
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, last_active)
        VALUES (?, ?, ?, ?)
    """, (user.username, user.email, hashed, datetime.utcnow().strftime("%Y-%m-%d")))

    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Generate JWT token
    token = create_jwt_token(user_id, user.email)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user_id,
            "username": user.username,
            "email": user.email,
            "total_points": 0,
            "quizzes_taken": 0,
            "avg_score": 0.0,
            "streak_days": 0,
        }
    }


@router.post("/login")
async def login(credentials: UserLogin):
    """Authenticate user and return JWT token."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id, username, email, password_hash, total_points, quizzes_taken, avg_score, streak_days
        FROM users WHERE email = ?
    """, (credentials.email,))

    row = cursor.fetchone()

    if not row or not pwd_context.verify(credentials.password, row[3]):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Update last active
    cursor.execute("UPDATE users SET last_active = ? WHERE user_id = ?",
                   (datetime.utcnow().strftime("%Y-%m-%d"), row[0]))
    conn.commit()
    conn.close()

    token = create_jwt_token(row[0], row[2])

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": row[0],
            "username": row[1],
            "email": row[2],
            "total_points": row[4],
            "quizzes_taken": row[5],
            "avg_score": row[6],
            "streak_days": row[7],
        }
    }


@router.get("/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    """Get the current user's profile."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id, username, email, total_points, quizzes_taken, avg_score, streak_days, created_at
        FROM users WHERE user_id = ?
    """, (user["user_id"],))

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": row[0],
        "username": row[1],
        "email": row[2],
        "total_points": row[3],
        "quizzes_taken": row[4],
        "avg_score": row[5],
        "streak_days": row[6],
        "created_at": row[7],
    }
