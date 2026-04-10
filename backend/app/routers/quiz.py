"""
AirVision Quiz Router — Name-based (no login required)
Users enter their name to start a quiz. Scores are tracked on a leaderboard.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.database import get_db_connection

router = APIRouter()


@router.get("/quiz/topics")
async def list_quiz_topics():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT topic_id, title, description, category, difficulty,
               question_count, time_minutes, points_available, icon_color
        FROM quiz_topics ORDER BY topic_id
    """)
    topics = []
    for row in cursor.fetchall():
        topics.append({
            "topic_id": row[0], "title": row[1], "description": row[2],
            "category": row[3], "difficulty": row[4], "question_count": row[5],
            "time_minutes": row[6], "points_available": row[7], "icon_color": row[8],
        })
    conn.close()
    return {"topics": topics}


@router.get("/quiz/topics/{topic_id}")
async def get_quiz_questions(topic_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT title, question_count, time_minutes FROM quiz_topics WHERE topic_id = ?", (topic_id,))
    topic = cursor.fetchone()
    if not topic:
        conn.close()
        raise HTTPException(status_code=404, detail="Quiz topic not found")

    # Get questions WITHOUT correct answers (prevent cheating)
    cursor.execute("""
        SELECT question_id, question_text, option_a, option_b, option_c, option_d, knowledge_area
        FROM quiz_questions WHERE topic_id = ?
        ORDER BY question_id
    """, (topic_id,))

    questions = []
    for row in cursor.fetchall():
        questions.append({
            "question_id": row[0], "question_text": row[1],
            "option_a": row[2], "option_b": row[3],
            "option_c": row[4], "option_d": row[5],
            "knowledge_area": row[6],
        })
    conn.close()

    return {
        "topic_id": topic_id, "title": topic[0],
        "question_count": topic[1], "time_minutes": topic[2],
        "questions": questions,
    }


@router.post("/quiz/submit")
async def submit_quiz(submission: dict):
    """
    Submit quiz answers. No login required — just a name.
    Body: { "player_name": "Ronak", "topic_id": 1, "answers": {"1":"A","2":"C",...}, "time_taken_sec": 120 }
    """
    player_name = submission.get("player_name", "Anonymous").strip()
    if not player_name:
        player_name = "Anonymous"

    topic_id = submission.get("topic_id")
    answers = submission.get("answers", {})
    time_taken = submission.get("time_taken_sec", 0)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get topic info
    cursor.execute("SELECT title, question_count, points_available FROM quiz_topics WHERE topic_id = ?", (topic_id,))
    topic = cursor.fetchone()
    if not topic:
        conn.close()
        raise HTTPException(status_code=404, detail="Quiz topic not found")

    # Fetch correct answers
    cursor.execute("""
        SELECT question_id, question_text, correct_answer, explanation, knowledge_area,
               option_a, option_b, option_c, option_d
        FROM quiz_questions WHERE topic_id = ?
    """, (topic_id,))
    questions = cursor.fetchall()

    # Grade
    score = 0
    total = len(questions)
    review = []
    knowledge_scores = {}

    for q in questions:
        qid = str(q[0])
        correct = q[2]
        user_answer = answers.get(qid, "")
        is_correct = user_answer.upper() == correct.upper() if user_answer else False

        if is_correct:
            score += 1

        area = q[4] or "General"
        if area not in knowledge_scores:
            knowledge_scores[area] = {"correct": 0, "total": 0}
        knowledge_scores[area]["total"] += 1
        if is_correct:
            knowledge_scores[area]["correct"] += 1

        review.append({
            "question_id": q[0], "question_text": q[1],
            "correct_answer": correct, "user_answer": user_answer,
            "is_correct": is_correct, "explanation": q[3],
            "knowledge_area": area,
            "options": {"A": q[5], "B": q[6], "C": q[7], "D": q[8]},
        })

    percentage = (score / total * 100) if total > 0 else 0

    # Calculate points
    points_earned = score
    if score == total:
        points_earned += 3  # Perfect score bonus

    # Save attempt to quiz_attempts (use player_name instead of user_id)
    #cursor.execute("""
    #    INSERT INTO quiz_attempts
    #   (user_id, topic_id, score, total_questions, percentage, time_taken_sec, points_earned)
    #    VALUES (?, ?, ?, ?, ?, ?, ?)
    #""", (0, topic_id, score, total, percentage, time_taken, points_earned))

    # Save to leaderboard table
    cursor.execute("""
        INSERT INTO leaderboard (player_name, topic_id, score, total_questions, percentage, points_earned, time_taken_sec)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (player_name, topic_id, score, total, percentage, points_earned, time_taken))

    # Update leaderboard totals
    cursor.execute("""
        SELECT id FROM leaderboard_totals WHERE player_name = ?
    """, (player_name,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE leaderboard_totals SET
                total_points = total_points + ?,
                quizzes_taken = quizzes_taken + 1,
                avg_score = (SELECT AVG(percentage) FROM leaderboard WHERE player_name = ?),
                last_played = ?
            WHERE player_name = ?
        """, (points_earned, player_name, datetime.now(timezone.utc).isoformat(), player_name))
    else:
        cursor.execute("""
            INSERT INTO leaderboard_totals (player_name, total_points, quizzes_taken, avg_score, last_played)
            VALUES (?, ?, 1, ?, ?)
        """, (player_name, points_earned, percentage, datetime.now(timezone.utc).isoformat()))

    conn.commit()
    conn.close()

    # Format knowledge areas
    knowledge_areas = {}
    for area, scores in knowledge_scores.items():
        knowledge_areas[area] = round(scores["correct"] / scores["total"] * 100, 1)

    return {
        "player_name": player_name,
        "topic_id": topic_id, "topic_title": topic[0],
        "score": score, "total_questions": total,
        "percentage": round(percentage, 1),
        "points_earned": points_earned,
        "time_taken_sec": time_taken,
        "questions_review": review,
        "knowledge_areas": knowledge_areas,
    }


@router.get("/quiz/leaderboard")
async def get_leaderboard():
    """Get the top players leaderboard sorted by total points."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT player_name, total_points, quizzes_taken, avg_score, last_played
        FROM leaderboard_totals
        ORDER BY total_points DESC
        LIMIT 50
    """)

    leaderboard = []
    for i, row in enumerate(cursor.fetchall()):
        leaderboard.append({
            "rank": i + 1,
            "player_name": row[0],
            "total_points": row[1],
            "quizzes_taken": row[2],
            "avg_score": round(row[3], 1) if row[3] else 0,
            "last_played": row[4],
        })

    conn.close()
    return {"leaderboard": leaderboard}


@router.get("/quiz/leaderboard/{player_name}")
async def get_player_stats(player_name: str):
    """Get a specific player's quiz history and stats."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Player totals
    cursor.execute("""
        SELECT total_points, quizzes_taken, avg_score FROM leaderboard_totals WHERE player_name = ?
    """, (player_name,))
    totals = cursor.fetchone()

    # Recent attempts
    cursor.execute("""
        SELECT l.topic_id, qt.title, l.score, l.total_questions, l.percentage,
               l.points_earned, l.time_taken_sec, l.played_at
        FROM leaderboard l
        JOIN quiz_topics qt ON l.topic_id = qt.topic_id
        WHERE l.player_name = ?
        ORDER BY l.played_at DESC LIMIT 20
    """, (player_name,))

    history = []
    for row in cursor.fetchall():
        history.append({
            "topic_title": row[1],
            "score": f"{row[2]}/{row[3]} ({row[4]:.0f}%)",
            "points_earned": row[5],
            "time_taken": row[6],
            "played_at": row[7],
        })

    # Rank
    cursor.execute("""
        SELECT COUNT(*) + 1 FROM leaderboard_totals
        WHERE total_points > (SELECT COALESCE(total_points, 0) FROM leaderboard_totals WHERE player_name = ?)
    """, (player_name,))
    rank = cursor.fetchone()[0]

    conn.close()

    return {
        "player_name": player_name,
        "total_points": totals[0] if totals else 0,
        "quizzes_taken": totals[1] if totals else 0,
        "avg_score": round(totals[2], 1) if totals and totals[2] else 0,
        "rank": rank,
        "history": history,
    }
