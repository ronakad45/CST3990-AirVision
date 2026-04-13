# AirVision: Urban Air Quality Prediction for the Middle East

## Project Overview
AirVision is a web-based system that uses machine learning to forecast short-term urban air quality in Middle Eastern cities (Dubai, Abu Dhabi, Riyadh). It presents forecasts through an interactive dashboard and engages users through air quality quizzes.

## Tech Stack
- **Backend:** Python 3.10+, FastAPI, SQLite, scikit-learn, XGBoost
- **Frontend:** Vue.js 3, Chart.js, Tailwind CSS
- **Data Source:** OpenAQ API v3, OpenWeather API
- **ML Models:** Linear Regression, Random Forest, XGBoost

---

## Step-by-Step Setup Instructions (Windows)

### Prerequisites
1. **Python 3.10+** — Download from https://www.python.org/downloads/
   - During installation, CHECK "Add Python to PATH"
   - Verify: Open Command Prompt and type `python --version`

2. **Node.js 18+** — Download from https://nodejs.org/
   - Verify: Open Command Prompt and type `node --version`

3. **Git** — Download from https://git-scm.com/
   - Verify: `git --version`

4. **OpenAQ API Key** — Sign up at https://explore.openaq.org
   - After signing up, go to Settings → API Key

### Step 1: Clone/Download the Project
```bash
# If using Git:
cd C:\Users\YourName\Desktop
git clone <your-repo-url> airvision
cd airvision

# Or just extract the zip to a folder called 'airvision'
```

### Step 2: Set Up the Backend


# Open Command Prompt and navigate to the backend folder
cd airvision\backend

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate

# You should see (venv) at the start of your command line

# Install all Python dependencies
pip install -r requirements.txt


### Step 3: Configure Environment Variables


# Copy the example environment file
copy .env.example .env

# Open .env in a text editor (Notepad, VS Code, etc.) and fill in:
# - Your OpenAQ API key
# - Your OpenWeather API key (optional, get one from https://openweathermap.org/api)

### Step 4: Initialise the Database


# Make sure you're in the backend folder with venv activated
python -m app.database

# This creates the SQLite database file: backend/data/airvision.db
# You should see: "Database tables created successfully!"


### Step 5: Collect Air Quality Data


# Fetch historical data from OpenAQ (this may take a few minutes)
python -m app.services.data_collector

# You should see progress messages as data is fetched for each city


### Step 6: Train ML Models


# Train all three models and see comparison results
python -m app.ml.trainer

# This will output RMSE, MAE, and R² for each model


### Step 7: Start the Backend Server


# Start the FastAPI server
uvicorn app.main:app --reload --port 8000

# The API will be available at: http://localhost:8000
# API docs (Swagger): http://localhost:8000/docs


### Step 8: Set Up the Frontend


# Open a NEW Command Prompt window
cd airvision\frontend

# Install Node.js dependencies
npm install

# Start the development server
npm run dev

# The dashboard will be available at: http://localhost:5173


---

## Project Structure

airvision/
├── README.md
├── backend/
│   ├── .env.example          # Environment variables template
│   ├── .env                  # Your actual environment variables (git-ignored)
│   ├── requirements.txt      # Python dependencies
│   ├── data/
│   │   └── airvision.db      # SQLite database (created at Step 4)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI application entry point
│   │   ├── config.py         # Configuration and settings
│   │   ├── database.py       # Database connection and table creation
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py    # Pydantic models for API request/response
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── air_quality.py  # AQ data endpoints
│   │   │   ├── forecast.py     # Prediction endpoints
│   │   │   ├── quiz.py         # Quiz & points endpoints
│   │   │   └── auth.py         # Authentication endpoints
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── data_collector.py   # OpenAQ + OpenWeather data fetching
│   │   │   ├── preprocessing.py    # Data cleaning & feature engineering
│   │   │   └── aqi_calculator.py   # AQI computation logic
│   │   ├── ml/
│   │   │   ├── __init__.py
│   │   │   ├── trainer.py     # Model training and evaluation
│   │   │   └── predictor.py   # Load models and make predictions
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── helpers.py     # Utility functions
│   └── tests/
│       └── test_api.py        # API tests
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── App.vue
│       ├── main.js
│       ├── router/
│       ├── stores/
│       ├── views/
│       ├── components/
│       └── assets/


## API Endpoints Summary
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/current/{city} | Current AQ readings |
| GET | /api/forecast/{city} | Next-day AQI prediction |
| GET | /api/historical/{city} | Historical trends |
| GET | /api/compare | Compare cities |
| GET | /api/models/compare | Model performance metrics |
| POST | /api/auth/register | User registration |
| POST | /api/auth/login | User login |
| GET | /api/quiz/topics | List quiz topics |
| GET | /api/quiz/{topic_id} | Get quiz questions |
| POST | /api/quiz/submit | Submit quiz answers |
| GET | /api/points/{user_id} | Get user points |
