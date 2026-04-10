"""
Run this ONCE to add leaderboard tables and extra quiz questions.
Run: python add_leaderboard.py
"""

import sqlite3
import os

DB_PATH = os.path.join("data", "airvision.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ─── ADD LEADERBOARD TABLES ───

cursor.execute("""
    CREATE TABLE IF NOT EXISTS leaderboard (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        player_name     TEXT NOT NULL,
        topic_id        INTEGER NOT NULL,
        score           INTEGER NOT NULL,
        total_questions INTEGER NOT NULL,
        percentage      REAL NOT NULL,
        points_earned   INTEGER DEFAULT 0,
        time_taken_sec  INTEGER DEFAULT 0,
        played_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (topic_id) REFERENCES quiz_topics(topic_id)
    )
""")
print("Created: leaderboard table")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS leaderboard_totals (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        player_name     TEXT NOT NULL UNIQUE,
        total_points    INTEGER DEFAULT 0,
        quizzes_taken   INTEGER DEFAULT 0,
        avg_score       REAL DEFAULT 0.0,
        last_played     TIMESTAMP
    )
""")
print("Created: leaderboard_totals table")

cursor.execute("CREATE INDEX IF NOT EXISTS idx_lb_player ON leaderboard(player_name)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_lb_totals ON leaderboard_totals(total_points DESC)")

# ─── ADD MORE QUIZ QUESTIONS (Topics 4, 5, 6 — currently empty) ───

extra_questions = [
    # Topic 4: Dust Storms in the Gulf
    (4, "What is the primary pollutant increased during a dust storm?", "NO₂", "O₃", "PM10", "CO", "C", "Dust storms primarily increase PM10 levels as they carry large sand and dust particles.", "Dust & Weather"),
    (4, "Which season sees the most dust storms in the Gulf region?", "Winter", "Spring/Summer", "Autumn", "Monsoon season", "B", "The Gulf region experiences most dust storms during spring and summer months (March–August) due to the Shamal winds.", "Dust & Weather"),
    (4, "What is the 'Shamal' wind?", "A sea breeze", "A northwesterly wind that causes dust storms", "A monsoon wind", "A cold winter wind", "B", "The Shamal is a strong northwesterly wind common in the Gulf that lifts sand and dust, causing storms.", "Dust & Weather"),
    (4, "How can dust storms affect visibility?", "They improve visibility", "They have no effect", "They can reduce visibility to below 1 km", "They only affect visibility at night", "C", "Severe dust storms can reduce visibility to less than 1 kilometre, disrupting transport and daily life.", "Dust & Weather"),
    (4, "Which Middle Eastern country is most affected by dust storms?", "UAE", "Qatar", "Saudi Arabia", "Bahrain", "C", "Saudi Arabia experiences the most frequent and severe dust storms due to its large desert areas.", "Dust & Weather"),
    (4, "Dust storms can carry particles across which distances?", "A few metres", "A few kilometres", "Hundreds to thousands of kilometres", "Only within city boundaries", "C", "Saharan and Arabian dust can travel thousands of kilometres, sometimes reaching Europe and South Asia.", "Dust & Weather"),
    (4, "What health precaution should people take during a dust storm?", "Open windows for ventilation", "Stay indoors with windows closed", "Exercise outdoors", "No precautions needed", "B", "During dust storms, people should stay indoors, close windows, and use air purifiers if available.", "Dust & Weather"),
    (4, "Which pollutant sensor is most useful for detecting dust storms?", "CO sensor", "NO₂ sensor", "PM10 sensor", "SO₂ sensor", "C", "PM10 sensors detect the coarse particles that dominate during dust storm events.", "Dust & Weather"),

    # Topic 5: Climate and Air Quality
    (5, "How does temperature affect air pollution?", "Hot weather always reduces pollution", "Higher temperatures can increase ground-level ozone formation", "Temperature has no effect on pollution", "Cold weather always increases ozone", "B", "Higher temperatures accelerate photochemical reactions that form ground-level ozone from NOx and VOCs.", "Climate Factors"),
    (5, "What is a temperature inversion?", "When ground is warmer than air above", "When a layer of warm air traps cool air and pollutants near the ground", "When temperature drops at night", "When it rains heavily", "B", "Temperature inversions trap pollutants close to the surface by preventing vertical air mixing, worsening air quality.", "Climate Factors"),
    (5, "How does wind affect air quality?", "Wind always makes air quality worse", "Strong winds help disperse pollutants, improving air quality", "Wind has no effect", "Wind only affects indoor air quality", "B", "Wind disperses and dilutes pollutants, generally improving local air quality. Calm conditions allow pollutants to accumulate.", "Climate Factors"),
    (5, "What role does humidity play in air pollution?", "No role at all", "High humidity can increase the formation of secondary pollutants", "Humidity always cleans the air", "Humidity only affects temperature", "B", "High humidity promotes formation of secondary particulate matter and can trap pollutants near the surface.", "Climate Factors"),
    (5, "In which season is PM2.5 typically highest in Gulf cities?", "Spring", "Summer", "Autumn", "Winter", "D", "Winter often sees higher PM2.5 in Gulf cities due to temperature inversions, reduced wind mixing, and increased heating.", "Climate Factors"),
    (5, "How does rain affect air quality?", "Rain has no effect", "Rain washes pollutants out of the air temporarily", "Rain always makes pollution worse", "Rain only affects ozone levels", "B", "Rain acts as a natural air cleaner by washing out particulate matter and other pollutants through wet deposition.", "Climate Factors"),
    (5, "What is the urban heat island effect?", "Cities are cooler than rural areas", "Cities are warmer than surrounding areas due to concrete and human activity", "Cities have more rain than rural areas", "Cities have less pollution than rural areas", "B", "Urban areas absorb and re-emit more heat, creating warmer microclimates that can trap pollutants and increase ozone formation.", "Climate Factors"),
    (5, "How does climate change affect air quality?", "It has no connection", "Higher temperatures and changing weather patterns can worsen air quality", "Climate change only affects sea levels", "Climate change improves air quality everywhere", "B", "Climate change increases temperatures (more ozone), alters wind patterns, and increases wildfire frequency, all worsening air quality.", "Climate Factors"),
    (5, "What time of day is ozone typically highest?", "Early morning", "Afternoon", "Midnight", "Dawn", "B", "Ground-level ozone peaks in the afternoon when sunlight intensity is highest, driving photochemical reactions.", "Climate Factors"),
    (5, "Why is air quality monitoring important for public health?", "It is not important", "It helps people make informed decisions about outdoor activities", "It only matters for scientists", "It is only relevant in industrial areas", "B", "AQ monitoring enables health advisories, helps vulnerable groups avoid exposure, and guides policy decisions.", "Climate Factors"),

    # Topic 6: Indoor vs Outdoor Air Quality
    (6, "Can indoor air be more polluted than outdoor air?", "No, indoor air is always cleaner", "Yes, indoor air can be 2-5 times more polluted", "They are always equal", "Only in factories", "B", "The EPA estimates indoor air can be 2-5 times more polluted than outdoor air due to poor ventilation and indoor sources.", "Indoor AQ"),
    (6, "What is a common source of indoor PM2.5?", "Trees", "Cooking, especially frying and grilling", "Opening windows", "Using air purifiers", "B", "Cooking, particularly frying and grilling, releases fine particles and gases that significantly increase indoor PM2.5.", "Indoor AQ"),
    (6, "What is VOC in the context of indoor air quality?", "Very Old Carbon", "Volatile Organic Compound", "Variable Oxygen Content", "Visible Outdoor Chemical", "B", "VOCs are chemicals that easily become gases at room temperature, emitted from paints, cleaning products, and furniture.", "Indoor AQ"),
    (6, "How can indoor air quality be improved?", "Keep all windows permanently closed", "Use proper ventilation and air purifiers", "Use more air fresheners", "Increase indoor humidity to 100%", "B", "Good ventilation, air purifiers with HEPA filters, and reducing indoor pollution sources are the best strategies.", "Indoor AQ"),
    (6, "What household item can release formaldehyde?", "Glass windows", "New furniture and pressed-wood products", "Ceramic tiles", "Metal utensils", "B", "New furniture, pressed-wood products, and certain building materials can off-gas formaldehyde, a harmful VOC.", "Indoor AQ"),
    (6, "What does a HEPA filter remove?", "Only odours", "99.97% of particles 0.3 micrometres and larger", "Only gases", "Only dust mites", "B", "HEPA (High Efficiency Particulate Air) filters capture 99.97% of particles ≥0.3 µm, including PM2.5, pollen, and dust.", "Indoor AQ"),
    (6, "Carbon monoxide poisoning from indoor sources is typically caused by?", "Electric heaters", "Faulty gas heaters, stoves, or generators", "Air conditioning", "Ceiling fans", "B", "CO poisoning typically results from malfunctioning gas appliances, generators, or charcoal burning in enclosed spaces.", "Indoor AQ"),
    (6, "What is the 'sick building syndrome'?", "A building that is structurally unsafe", "Health symptoms caused by poor indoor air quality in buildings", "A building with mould on the outside", "A term for old buildings", "B", "Sick building syndrome refers to health symptoms (headaches, fatigue, irritation) linked to poor indoor air quality.", "Indoor AQ"),
    (6, "Which indoor activity releases the LEAST pollutants?", "Deep frying food", "Burning candles", "Reading a book", "Using a fireplace", "C", "Reading produces no airborne pollutants, while cooking, candles, and fireplaces all release particulate matter.", "Indoor AQ"),
    (6, "How often should HVAC filters be replaced for good indoor air quality?", "Once every 5 years", "Every 1-3 months", "Never, they are permanent", "Only when visibly dirty", "B", "HVAC filters should be replaced every 1-3 months for optimal air quality. Clogged filters reduce filtration effectiveness.", "Indoor AQ"),
]

inserted = 0
for q in extra_questions:
    cursor.execute("SELECT question_id FROM quiz_questions WHERE topic_id = ? AND question_text = ?", (q[0], q[1]))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO quiz_questions
            (topic_id, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, knowledge_area)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, q)
        inserted += 1

# Update question counts in quiz_topics
for topic_id in [4, 5, 6]:
    cursor.execute("SELECT COUNT(*) FROM quiz_questions WHERE topic_id = ?", (topic_id,))
    count = cursor.fetchone()[0]
    cursor.execute("UPDATE quiz_topics SET question_count = ? WHERE topic_id = ?", (count, topic_id))

conn.commit()
conn.close()

print(f"Added {inserted} new quiz questions")
print(f"Total questions now cover all 6 topics")
print("Leaderboard tables ready!")
print("\nDone! Restart the server: uvicorn app.main:app --reload --port 8000")
