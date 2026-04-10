"""
Fix quiz: remove duplicates, keep 10-15 unique questions per topic.
Run ONCE: python fix_quiz.py
"""

import sqlite3
import os

DB_PATH = os.path.join("data", "airvision.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Count before
cursor.execute("SELECT COUNT(*) FROM quiz_questions")
print(f"Questions before cleanup: {cursor.fetchone()[0]}")

# Show per-topic counts
cursor.execute("""
    SELECT qt.title, qt.topic_id, COUNT(qq.question_id) 
    FROM quiz_topics qt 
    LEFT JOIN quiz_questions qq ON qt.topic_id = qq.topic_id 
    GROUP BY qt.topic_id
""")
print("\nBefore:")
for row in cursor.fetchall():
    print(f"  {row[0]} (ID:{row[1]}): {row[2]} questions")

# Step 1: Remove exact duplicate questions (keep the first one)
cursor.execute("""
    DELETE FROM quiz_questions WHERE question_id NOT IN (
        SELECT MIN(question_id) FROM quiz_questions GROUP BY topic_id, question_text
    )
""")
removed = cursor.rowcount
print(f"\nRemoved {removed} duplicate questions")

# Step 2: For topics with more than 15 questions, keep only the first 15
for topic_id in range(1, 7):
    cursor.execute("SELECT COUNT(*) FROM quiz_questions WHERE topic_id = ?", (topic_id,))
    count = cursor.fetchone()[0]
    if count > 15:
        cursor.execute("""
            DELETE FROM quiz_questions WHERE question_id NOT IN (
                SELECT question_id FROM quiz_questions 
                WHERE topic_id = ? 
                ORDER BY question_id ASC 
                LIMIT 15
            ) AND topic_id = ?
        """, (topic_id, topic_id))
        print(f"  Topic {topic_id}: trimmed from {count} to 15")

# Step 3: Update question counts in quiz_topics
for topic_id in range(1, 7):
    cursor.execute("SELECT COUNT(*) FROM quiz_questions WHERE topic_id = ?", (topic_id,))
    count = cursor.fetchone()[0]
    cursor.execute("UPDATE quiz_topics SET question_count = ?, points_available = ? WHERE topic_id = ?",
                   (count, count, topic_id))

# Step 4: Reassign clean question IDs
cursor.execute("SELECT question_id FROM quiz_questions ORDER BY topic_id, question_id")
all_ids = [row[0] for row in cursor.fetchall()]

conn.commit()

# Show after
cursor.execute("""
    SELECT qt.title, qt.topic_id, COUNT(qq.question_id), qt.question_count
    FROM quiz_topics qt 
    LEFT JOIN quiz_questions qq ON qt.topic_id = qq.topic_id 
    GROUP BY qt.topic_id
""")
print("\nAfter cleanup:")
for row in cursor.fetchall():
    print(f"  {row[0]} (ID:{row[1]}): {row[2]} questions")

cursor.execute("SELECT COUNT(*) FROM quiz_questions")
print(f"\nTotal questions: {cursor.fetchone()[0]}")

conn.close()
print("\nDone! Restart server: uvicorn app.main:app --reload --port 8000")