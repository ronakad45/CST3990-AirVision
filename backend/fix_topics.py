"""Remove empty duplicate quiz topics. Run ONCE: python fix_topics.py"""
import sqlite3, os

conn = sqlite3.connect(os.path.join("data", "airvision.db"))
c = conn.cursor()

# Delete all topics with 0 questions (keep only IDs 1-6)
c.execute("DELETE FROM quiz_topics WHERE topic_id > 6")
print(f"Removed {c.rowcount} empty duplicate topics")

# Verify
c.execute("SELECT topic_id, title, question_count FROM quiz_topics ORDER BY topic_id")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]} ({row[2]} questions)")

conn.commit()
conn.close()
print("Done!")