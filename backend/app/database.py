"""
AirVision Database Module
Creates and manages the SQLite database with all required tables.

Tables:
    - cities: Target cities metadata
    - air_quality_readings: Raw pollutant measurements from OpenAQ
    - weather_data: Meteorological observations from OpenWeather
    - predictions: ML model forecast outputs
    - model_metrics: Training evaluation results per model
    - users: User accounts for authentication
    - quiz_topics: Air quality quiz categories
    - quiz_questions: Individual quiz questions with options
    - quiz_attempts: User quiz attempt records
    - point_activities: Points earned from quiz activities
"""

import sqlite3
import os
from pathlib import Path
from app.config import settings


def get_db_connection():
    """Create and return a database connection with row factory enabled."""
    os.makedirs(os.path.dirname(settings.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_tables():
    """Create all database tables if they do not already exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # ─── CITIES TABLE ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            city_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            city_name   TEXT NOT NULL UNIQUE,
            country     TEXT NOT NULL,
            latitude    REAL NOT NULL,
            longitude   REAL NOT NULL,
            timezone    TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── AIR QUALITY READINGS TABLE ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS air_quality_readings (
            reading_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id     INTEGER NOT NULL,
            timestamp   TIMESTAMP NOT NULL,
            pm25        REAL,
            pm10        REAL,
            no2         REAL,
            o3          REAL,
            co          REAL,
            so2         REAL,
            aqi         INTEGER,
            source      TEXT DEFAULT 'openaq',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (city_id) REFERENCES cities(city_id),
            UNIQUE(city_id, timestamp)
        )
    """)

    # ─── WEATHER DATA TABLE ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_data (
            weather_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id         INTEGER NOT NULL,
            timestamp       TIMESTAMP NOT NULL,
            temperature     REAL,
            humidity        REAL,
            wind_speed      REAL,
            wind_direction  REAL,
            pressure        REAL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (city_id) REFERENCES cities(city_id),
            UNIQUE(city_id, timestamp)
        )
    """)

    # ─── PREDICTIONS TABLE ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            prediction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id         INTEGER NOT NULL,
            forecast_date   DATE NOT NULL,
            predicted_aqi   REAL,
            predicted_pm25  REAL,
            confidence      REAL,
            model_used      TEXT NOT NULL,
            alert_level     TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (city_id) REFERENCES cities(city_id)
        )
    """)

    # ─── MODEL METRICS TABLE ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_metrics (
            metric_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name      TEXT NOT NULL,
            rmse            REAL,
            mae             REAL,
            r_squared       REAL,
            training_samples INTEGER,
            test_samples    INTEGER,
            feature_count   INTEGER,
            trained_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── USERS TABLE ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT NOT NULL UNIQUE,
            email           TEXT NOT NULL UNIQUE,
            password_hash   TEXT NOT NULL,
            total_points    INTEGER DEFAULT 0,
            quizzes_taken   INTEGER DEFAULT 0,
            avg_score       REAL DEFAULT 0.0,
            streak_days     INTEGER DEFAULT 0,
            last_active     DATE,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── QUIZ TOPICS TABLE ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_topics (
            topic_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT NOT NULL UNIQUE,
            description     TEXT,
            category        TEXT NOT NULL,
            difficulty      TEXT NOT NULL CHECK(difficulty IN ('Beginner', 'Intermediate', 'Advanced')),
            question_count  INTEGER DEFAULT 0,
            time_minutes    INTEGER DEFAULT 5,
            points_available INTEGER DEFAULT 10,
            icon_color      TEXT DEFAULT '#3B82F6',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── QUIZ QUESTIONS TABLE ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_questions (
            question_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id        INTEGER NOT NULL,
            question_text   TEXT NOT NULL,
            option_a        TEXT NOT NULL,
            option_b        TEXT NOT NULL,
            option_c        TEXT NOT NULL,
            option_d        TEXT NOT NULL,
            correct_answer  TEXT NOT NULL CHECK(correct_answer IN ('A', 'B', 'C', 'D')),
            explanation     TEXT,
            knowledge_area  TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (topic_id) REFERENCES quiz_topics(topic_id)
        )
    """)

    # ─── QUIZ ATTEMPTS TABLE ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            attempt_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            topic_id        INTEGER NOT NULL,
            score           INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            percentage      REAL NOT NULL,
            time_taken_sec  INTEGER,
            points_earned   INTEGER DEFAULT 0,
            completed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (topic_id) REFERENCES quiz_topics(topic_id)
        )
    """)

    # ─── POINT ACTIVITIES TABLE ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS point_activities (
            activity_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            activity_type   TEXT NOT NULL,
            points_earned   INTEGER NOT NULL,
            description     TEXT,
            reference_id    INTEGER,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # ─── INDEXES FOR PERFORMANCE ───
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_aq_city_time ON air_quality_readings(city_id, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_weather_city_time ON weather_data(city_id, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_city ON predictions(city_id, forecast_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user ON quiz_attempts(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_points_user ON point_activities(user_id)")

    conn.commit()
    conn.close()
    print("Database tables created successfully!")


def seed_cities():
    """Insert the target cities into the database if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    for city_name, info in settings.TARGET_CITIES.items():
        cursor.execute("""
            INSERT OR IGNORE INTO cities (city_name, country, latitude, longitude, timezone)
            VALUES (?, ?, ?, ?, ?)
        """, (city_name, info["country_code"], info["latitude"], info["longitude"], info["timezone"]))

    conn.commit()
    conn.close()
    print(f"Seeded {len(settings.TARGET_CITIES)} cities.")


def seed_quiz_data():
    """Populate quiz topics and questions for the Air Quality Awareness system."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Skip if already seeded
    cursor.execute("SELECT COUNT(*) FROM quiz_topics")
    if cursor.fetchone()[0] >= 6:
        conn.close()
        print("Quiz data already seeded.")
        return

    # ─── QUIZ TOPICS ───
    topics = [
        ("AQI Fundamentals", "Learn what the Air Quality Index means and how it is calculated.", "Air Quality", "Beginner", 10, 5, 10, "#3B82F6"),
        ("Pollutant Identification", "Test your knowledge on PM2.5, PM10, NO₂, O₃, CO, and SO₂.", "Pollutants", "Intermediate", 10, 6, 10, "#8B5CF6"),
        ("Health Effects of Air Pollution", "Understand how polluted air affects respiratory and cardiovascular health.", "Health Effects", "Intermediate", 10, 6, 10, "#EF4444"),
        ("Dust Storms in the Gulf", "How sand and dust storms affect PM levels in the Middle East.", "Environment", "Advanced", 8, 5, 8, "#D97706"),
        ("Climate and Air Quality", "The link between weather, seasons, and pollution patterns.", "Environment", "Beginner", 10, 5, 10, "#10B981"),
        ("Indoor vs Outdoor Air Quality", "Compare pollution sources inside and outside buildings.", "Health Effects", "Intermediate", 10, 5, 10, "#06B6D4"),
    ]

    for t in topics:
        cursor.execute("""
            INSERT OR IGNORE INTO quiz_topics 
            (title, description, category, difficulty, question_count, time_minutes, points_available, icon_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, t)

    # ─── QUIZ QUESTIONS: AQI Fundamentals (topic_id = 1) ───
    aqi_questions = [
        (1, "What does AQI stand for?", "Air Quality Index", "Air Quantity Indicator", "Atmospheric Quality Index", "Ambient Quality Indicator", "A", "AQI stands for Air Quality Index, a standardised measure of air pollution levels.", "AQI Basics"),
        (1, "What AQI range is classified as 'Good'?", "0 – 50", "51 – 100", "101 – 150", "0 – 100", "A", "An AQI of 0 to 50 is considered Good, meaning air quality poses little or no risk.", "AQI Basics"),
        (1, "What colour represents 'Moderate' air quality on the AQI scale?", "Green", "Yellow", "Orange", "Red", "B", "Yellow represents Moderate AQI (51–100). Air quality is acceptable but may be a concern for sensitive individuals.", "AQI Basics"),
        (1, "What AQI range is classified as 'Unhealthy for Sensitive Groups'?", "0 – 50", "51 – 100", "101 – 150", "151 – 200", "C", "AQI 101–150 is coded orange and means sensitive groups such as those with asthma should reduce outdoor exertion.", "AQI Basics"),
        (1, "Which organisation developed the AQI system used internationally?", "World Health Organization", "United States EPA", "European Environment Agency", "United Nations", "B", "The US Environmental Protection Agency (EPA) developed the AQI framework that is widely adopted globally.", "AQI Basics"),
        (1, "How many main categories does the standard AQI scale have?", "4", "5", "6", "8", "C", "The standard AQI scale has 6 categories: Good, Moderate, USG, Unhealthy, Very Unhealthy, and Hazardous.", "AQI Basics"),
        (1, "An AQI value of 175 falls into which category?", "Moderate", "Unhealthy for Sensitive Groups", "Unhealthy", "Very Unhealthy", "C", "AQI 151–200 is classified as Unhealthy, meaning everyone may begin to experience health effects.", "AQI Basics"),
        (1, "What is the maximum AQI value on the standard scale?", "300", "400", "500", "1000", "C", "The standard AQI scale runs from 0 to 500. Values above 300 are considered Hazardous.", "AQI Basics"),
        (1, "Which pollutant is most commonly used as the primary AQI indicator?", "CO", "SO₂", "PM2.5", "NO₂", "C", "PM2.5 is the most commonly reported AQI indicator because fine particles pose the greatest health risk to most people.", "AQI Basics"),
        (1, "What does a 'Hazardous' AQI level (301–500) mean?", "Air is clean", "Only sensitive people are affected", "Everyone should stay indoors", "Health emergency conditions for entire population", "D", "Hazardous AQI means emergency conditions where the entire population is likely to be affected.", "AQI Basics"),
    ]

    # ─── QUIZ QUESTIONS: Pollutant Identification (topic_id = 2) ───
    pollutant_questions = [
        (2, "What does PM2.5 refer to?", "Particles smaller than 2.5 millimetres", "Particles smaller than 2.5 micrometres", "Pollution measurement at 2.5 metres height", "Particulate matter at 2.5% concentration", "B", "PM2.5 refers to particulate matter with a diameter of 2.5 micrometres or less — roughly 30 times thinner than a human hair.", "Pollutant Types"),
        (2, "Which pollutant is primarily produced by vehicle exhaust in cities?", "SO₂", "O₃", "NO₂", "PM10", "C", "Nitrogen dioxide (NO₂) is primarily produced by combustion engines in vehicles and is a major urban pollutant.", "Emission Sources"),
        (2, "What is ground-level ozone (O₃)?", "The same as the ozone layer", "A secondary pollutant formed by sunlight reacting with other pollutants", "Directly emitted by factories", "A natural gas that is always safe", "B", "Ground-level ozone is a secondary pollutant formed when NOₓ and VOCs react in the presence of sunlight.", "Pollutant Types"),
        (2, "Which gas has the chemical formula CO?", "Carbon dioxide", "Carbon monoxide", "Chlorine oxide", "Calcium oxide", "B", "CO is carbon monoxide, a colourless and odourless gas produced by incomplete combustion of fuels.", "Pollutant Types"),
        (2, "What is the main natural source of SO₂ in the atmosphere?", "Forests", "Oceans", "Volcanic eruptions", "Soil bacteria", "C", "Volcanic eruptions are the largest natural source of SO₂. Human sources include coal-burning power plants.", "Emission Sources"),
        (2, "PM10 particles are roughly the size of what?", "A grain of sand", "A human hair", "Dust or pollen", "A tennis ball", "C", "PM10 particles (10 micrometres or less) are comparable in size to dust, pollen, and mould spores.", "Pollutant Types"),
        (2, "Which pollutant is measured in parts per million (ppm)?", "PM2.5", "PM10", "CO", "Both PM2.5 and PM10", "C", "Carbon monoxide is typically measured in ppm, while particulate matter is measured in µg/m³.", "Pollutant Types"),
        (2, "Why is PM2.5 considered more dangerous than PM10?", "It is heavier", "It can penetrate deep into the lungs and bloodstream", "It is more visible", "It smells worse", "B", "PM2.5 particles are so small they can bypass the nose and throat, penetrate deep into lung tissue, and even enter the bloodstream.", "Health Standards"),
        (2, "What is the WHO annual guideline limit for PM2.5?", "5 µg/m³", "15 µg/m³", "25 µg/m³", "50 µg/m³", "A", "The WHO updated its PM2.5 annual guideline to 5 µg/m³ in 2021, down from the previous 10 µg/m³.", "Health Standards"),
        (2, "Which of these is NOT a criteria air pollutant?", "PM2.5", "Lead", "CO₂", "SO₂", "C", "CO₂ (carbon dioxide) is a greenhouse gas but not classified as a criteria air pollutant by the EPA. The six criteria pollutants are PM, O₃, CO, NO₂, SO₂, and Lead.", "Pollutant Types"),
    ]

    # ─── QUIZ QUESTIONS: Health Effects (topic_id = 3) ───
    health_questions = [
        (3, "Which body system is most directly affected by air pollution?", "Digestive system", "Respiratory system", "Skeletal system", "Reproductive system", "B", "The respiratory system (lungs, airways) is the first point of contact and most directly affected by inhaled pollutants.", "Health Effects"),
        (3, "Long-term exposure to PM2.5 has been linked to which condition?", "Improved lung function", "Cardiovascular disease", "Stronger immune system", "Better sleep quality", "B", "Studies consistently link long-term PM2.5 exposure to increased risk of heart attacks, strokes, and other cardiovascular diseases.", "Health Effects"),
        (3, "Which group is most vulnerable to air pollution health effects?", "Healthy adults aged 25–40", "Professional athletes", "Children, elderly, and people with respiratory conditions", "People who work indoors", "C", "Children, the elderly, and those with pre-existing respiratory or cardiovascular conditions are most vulnerable to air pollution.", "Health Effects"),
        (3, "What respiratory condition can be triggered by high NO₂ levels?", "Better breathing", "Asthma attacks", "Improved oxygen intake", "Stronger lungs", "B", "High NO₂ levels can inflame airways and trigger asthma attacks, particularly in children and sensitive individuals.", "Health Effects"),
        (3, "Ground-level ozone can cause which of the following?", "Skin tanning", "Throat irritation and chest pain", "Improved vision", "Stronger bones", "B", "Ground-level ozone irritates the respiratory tract, causing throat irritation, chest pain, coughing, and reduced lung function.", "Health Effects"),
        (3, "What is the health significance of the AQI colour 'red'?", "Air is perfectly safe", "Only people with allergies are affected", "Everyone may experience health effects", "Only industrial workers are at risk", "C", "Red AQI (151–200, Unhealthy) means everyone may begin to experience health effects and sensitive groups may experience more serious effects.", "Health Effects"),
        (3, "Carbon monoxide poisoning primarily affects which organ?", "Liver", "Kidneys", "Brain and heart", "Stomach", "C", "CO binds to haemoglobin more readily than oxygen, reducing oxygen delivery to the brain and heart, which can be fatal at high concentrations.", "Health Effects"),
        (3, "How can individuals protect themselves on high-pollution days?", "Exercise outdoors more vigorously", "Stay indoors and keep windows closed", "Open all windows for ventilation", "Spend more time near busy roads", "B", "On high-pollution days, staying indoors with windows closed and using air purifiers if available is the recommended protective action.", "Health Effects"),
        (3, "Which long-term condition has been associated with childhood exposure to air pollution?", "Increased height", "Reduced lung development", "Improved academic performance", "Stronger immune system", "B", "Children exposed to chronic air pollution can experience reduced lung growth and development that persists into adulthood.", "Health Effects"),
        (3, "What percentage of global deaths does the WHO attribute to ambient air pollution annually?", "Less than 1%", "About 4–7%", "About 15%", "Over 25%", "B", "The WHO estimates that ambient air pollution contributes to approximately 4.2 million premature deaths worldwide each year.", "Health Effects"),
    ]

    all_questions = aqi_questions + pollutant_questions + health_questions

    for q in all_questions:
        cursor.execute("""
            INSERT OR IGNORE INTO quiz_questions
            (topic_id, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, knowledge_area)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, q)

    conn.commit()
    conn.close()
    print(f"Seeded {len(topics)} quiz topics and {len(all_questions)} questions.")


# ─── RUN DIRECTLY TO INITIALISE DATABASE ───
if __name__ == "__main__":
    create_tables()
    seed_cities()
    seed_quiz_data()
