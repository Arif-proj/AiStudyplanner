# StudyMate AI – AI-Based Study Planner

A lightweight study-planner web app for students. A **rule-based AI engine** (plain Python, no ML, no paid API)
ranks topics by exam urgency, difficulty, status and progress, then builds a daily timetable.

**Stack:** HTML, CSS, Bootstrap 5, JavaScript, Font Awesome, Chart.js · Python 3, Flask · MongoDB Atlas (PyMongo)

## Local setup

1. Create a virtual environment: `python -m venv venv`
2. Activate it – Windows: `venv\Scripts\activate` · macOS/Linux: `source venv/bin/activate`
3. Install packages: `pip install -r requirements.txt`
4. Edit `.env` (never commit it):
   ```
   MONGO_URI=your_mongodb_atlas_connection_string
   SECRET_KEY=your_secret_key
   DATABASE_NAME=studymate_ai
   ```
5. Run: `python app.py`
6. Open: http://127.0.0.1:5000

### MongoDB Atlas quick guide
1. Create a free cluster → *Database Access*: add a user + password.
2. *Network Access*: add your current IP address (or 0.0.0.0/0 for a demo).
3. *Connect → Drivers*: copy the `mongodb+srv://...` string into `MONGO_URI` (replace `<password>`).
Collections (`users`, `subjects`, `topics`, `study_tasks`, `study_sessions`) are created automatically.

Generate a secret key: `python -c "import secrets; print(secrets.token_hex(32))"`

## How the AI engine works (`ai_planner.py`)

**Priority Score = Exam Urgency + Difficulty + Completion Status + Previous Progress**

| Rule | Points |
|---|---|
| Exam in 1–3 days / 4–7 / 8–14 / 15+ | 40 / 30 / 20 / 10 |
| Topic difficulty Hard / Medium / Easy | 15 / 10 / 5 |
| Status Pending / In Progress / Completed | 10 / 5 / skipped |
| Subject less than 25% / 25–60% / more done | 2 / 1 / 0 |

Score ≥ 50 → **High**, ≥ 35 → **Medium**, otherwise **Low**.
Default study time: Easy 30 min, Medium 45 min, Hard 60 min (or the student's own estimate).

1. `rank_topics()` – scores and sorts all unfinished topics.
2. `build_schedule()` – fills each day (up to 14 days) with the highest-priority topics that fit the daily hours and the start/end window, with a 10-minute gap between blocks. Nothing is planned after a subject's exam date.
3. `recommendations()` – rule-based tips (exam alert, pending hard topics, progress tip).

Regenerating a plan replaces the old *pending* tasks for the selected subjects; completed tasks are kept.

## Viva summary
- **Problem:** students struggle to organise subjects, topics and exam preparation.
- **Solution:** StudyMate AI analyses subjects, topics, difficulty, exam dates, study hours and progress, then generates a personalised timetable.
- **Flow:** Input → Priority calculation → Time allocation → Schedule → Progress tracking + Pomodoro timer.

## Notes
- Study Hours on the dashboard = completed task minutes + logged Pomodoro minutes.
- Passwords are hashed with Werkzeug; sessions use Flask's signed cookies; all data is filtered by the logged-in user.
- For production, run behind a WSGI server (e.g. gunicorn) with `debug=False` and HTTPS.
