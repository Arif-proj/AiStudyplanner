"""
StudyMate AI - Flask application.
Run with:  python app.py
"""
import re
import sys
import datetime as dt

from bson import ObjectId
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify)
from markupsafe import Markup
from pymongo.errors import PyMongoError, DuplicateKeyError
from werkzeug.security import generate_password_hash, check_password_hash

import config
import ai_planner
from utils.auth import login_required
from utils.database import get_db, check_connection, create_indexes

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

DIFFICULTIES = ("Easy", "Medium", "Hard")
STATUSES = ("Pending", "In Progress", "Completed")
PRIORITIES = ("High", "Medium", "Low")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ======================================================================
# Helpers
# ======================================================================
def oid(value):
    """Safely convert a string to ObjectId (None if invalid)."""
    try:
        return ObjectId(value)
    except Exception:
        return None


def uid():
    return ObjectId(session["user_id"])


def valid_date(value):
    try:
        dt.datetime.strptime(value, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False


def valid_time(value):
    try:
        dt.datetime.strptime(value, "%H:%M")
        return True
    except (TypeError, ValueError):
        return False


def field(name, maxlen=100):
    return (request.form.get(name) or "").strip()[:maxlen]


def go_back(default_endpoint):
    """Return to the page the form was sent from (same site only)."""
    ref = request.referrer
    if ref and ref.startswith(request.host_url):
        return redirect(ref)
    return redirect(url_for(default_endpoint))


def subject_stats(subjects, topics):
    """Add topic counts, progress % and days remaining to each subject."""
    today = dt.date.today()
    result = []
    for s in subjects:
        mine = [t for t in topics if t["subject_id"] == s["_id"]]
        done = sum(1 for t in mine if t["status"] == "Completed")
        result.append({**s, "total": len(mine), "done": done,
                       "percent": round(done * 100 / len(mine)) if mine else 0,
                       "days_left": ai_planner.days_until(s["exam_date"], today)})
    return result


def enrich_tasks(db, user_id, tasks):
    """Attach subject/topic names and end time to task documents."""
    subjects = {s["_id"]: s["name"] for s in db.subjects.find({"user_id": user_id})}
    topics = {t["_id"]: t["name"] for t in db.topics.find({"user_id": user_id})}
    for t in tasks:
        t["subject_name"] = subjects.get(t["subject_id"], "(deleted subject)")
        t["topic_name"] = topics.get(t["topic_id"], "(deleted topic)")
        t["end_time"] = ai_planner.add_minutes(t["start_time"], t["duration"])
    return tasks


def minutes_per_day(db, user_id):
    """{date: minutes studied} from completed tasks + Pomodoro sessions."""
    totals = {}
    for t in db.study_tasks.find({"user_id": user_id, "status": "Completed"}):
        day = (t.get("completed_at") or t["created_at"]).date()
        totals[day] = totals.get(day, 0) + t.get("duration", 0)
    for s in db.study_sessions.find({"user_id": user_id}):
        day = s["completed_at"].date()
        totals[day] = totals.get(day, 0) + s.get("duration", 0)
    return totals


def current_streak(days):
    """Consecutive study days ending today (or yesterday)."""
    day = dt.date.today()
    if day not in days:
        day -= dt.timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= dt.timedelta(days=1)
    return streak


# ======================================================================
# Template helpers
# ======================================================================
@app.template_filter("priority_badge")
def priority_badge(priority):
    style = {"High": ("danger", "🔴"), "Medium": ("warning", "🟡"),
             "Low": ("success", "🟢")}.get(priority, ("secondary", "⚪"))
    return Markup(f'<span class="badge rounded-pill text-bg-{style[0]}">'
                  f'{style[1]} {priority}</span>')


@app.template_filter("status_badge")
def status_badge(status):
    colour = {"Completed": "success", "In Progress": "info",
              "Pending": "secondary"}.get(status, "secondary")
    return Markup(f'<span class="badge rounded-pill text-bg-{colour}">{status}</span>')


@app.template_filter("nicedate")
def nicedate(value):
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value or "—"


@app.template_filter("t12")
def t12(value):
    try:
        return dt.datetime.strptime(value, "%H:%M").strftime("%I:%M %p")
    except (TypeError, ValueError):
        return value or ""


@app.errorhandler(PyMongoError)
def database_error(error):
    app.logger.error("Database error: %s", type(error).__name__)   # no secrets logged
    message = "MongoDB connection failed. Please try again in a moment."
    if request.path.startswith("/planner/generate"):
        return jsonify(ok=False, message=message), 503
    return f"<h3 style='font-family:sans-serif;padding:2rem'>{message}</h3>", 503


@app.errorhandler(404)
def not_found(error):
    return "<h3 style='font-family:sans-serif;padding:2rem'>Page not found. " \
           "<a href='/'>Go home</a></h3>", 404


# ======================================================================
# Public pages: home, register, login, logout
# ======================================================================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, college = field("name"), field("college")
        email = field("email").lower()
        password = request.form.get("password", "")

        if not (name and email and password and college):
            flash("Please enter all required fields.", "danger")
        elif not EMAIL_RE.match(email):
            flash("Please enter a valid email address.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
        else:
            try:
                get_db().users.insert_one({
                    "name": name, "email": email, "college": college,
                    "password": generate_password_hash(password),   # never plain text
                    "daily_hours": 4, "preferred_start_time": "08:00",
                    "created_at": dt.datetime.utcnow()})
            except DuplicateKeyError:
                flash("An account with this email already exists.", "danger")
            else:
                flash("Account created! Please log in.", "success")
                return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = field("email").lower()
        password = request.form.get("password", "")
        if not (email and password):
            flash("Please enter all required fields.", "danger")
        else:
            user = get_db().users.find_one({"email": email})
            if user and check_password_hash(user["password"], password):
                session.clear()
                session["user_id"] = str(user["_id"])
                session["user_name"] = user["name"]
                return redirect(url_for("dashboard"))
            flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ======================================================================
# Dashboard
# ======================================================================
@app.route("/dashboard")
@login_required
def dashboard():
    db, user = get_db(), uid()
    subjects = list(db.subjects.find({"user_id": user}))
    topics = list(db.topics.find({"user_id": user}))
    completed = sum(1 for t in topics if t["status"] == "Completed")
    per_day = minutes_per_day(db, user)

    stats = {
        "subjects": len(subjects),
        "topics": len(topics),
        "completed": completed,
        "pending": len(topics) - completed,
        "hours": round(sum(per_day.values()) / 60, 1),
        "streak": current_streak(set(per_day)),
    }
    today_tasks = list(db.study_tasks.find(
        {"user_id": user, "study_date": dt.date.today().isoformat()}
    ).sort("start_time", 1))
    enrich_tasks(db, user, today_tasks)

    hour = dt.datetime.now().hour
    greeting = ("Good Morning" if hour < 12 else
                "Good Afternoon" if hour < 17 else "Good Evening")
    return render_template("dashboard.html", stats=stats, tasks=today_tasks,
                           greeting=greeting)


# ======================================================================
# Subjects
# ======================================================================
def read_subject_form():
    name, exam_date, difficulty = field("name"), field("exam_date"), field("difficulty")
    if not (name and exam_date and difficulty):
        return None, "Please enter all required fields."
    if not valid_date(exam_date) or difficulty not in DIFFICULTIES:
        return None, "Please enter a valid exam date and difficulty."
    return {"name": name, "exam_date": exam_date, "difficulty": difficulty}, None


@app.route("/subjects")
@login_required
def subjects():
    db, user = get_db(), uid()
    data = subject_stats(list(db.subjects.find({"user_id": user}).sort("exam_date", 1)),
                         list(db.topics.find({"user_id": user})))
    return render_template("subjects.html", subjects=data)


@app.route("/subjects/add", methods=["POST"])
@login_required
def subjects_add():
    doc, error = read_subject_form()
    if error:
        flash(error, "danger")
    else:
        doc.update(user_id=uid(), created_at=dt.datetime.utcnow())
        get_db().subjects.insert_one(doc)
        flash("Subject added.", "success")
    return redirect(url_for("subjects"))


@app.route("/subjects/edit/<id>", methods=["POST"])
@login_required
def subjects_edit(id):
    doc, error = read_subject_form()
    if error or not oid(id):
        flash(error or "Subject not found.", "danger")
    else:
        get_db().subjects.update_one({"_id": oid(id), "user_id": uid()}, {"$set": doc})
        flash("Subject updated.", "success")
    return redirect(url_for("subjects"))


@app.route("/subjects/delete/<id>", methods=["POST"])
@login_required
def subjects_delete(id):
    db, user, sid = get_db(), uid(), oid(id)
    if sid and db.subjects.delete_one({"_id": sid, "user_id": user}).deleted_count:
        # remove everything that belonged to this subject
        db.topics.delete_many({"subject_id": sid, "user_id": user})
        db.study_tasks.delete_many({"subject_id": sid, "user_id": user})
        flash("Subject and its topics deleted.", "info")
    return redirect(url_for("subjects"))


# ======================================================================
# Topics
# ======================================================================
def read_topic_form():
    name, difficulty = field("name"), field("difficulty")
    status = field("status") or "Pending"
    if not (name and difficulty):
        return None, "Please enter all required fields."
    if difficulty not in DIFFICULTIES or status not in STATUSES:
        return None, "Please choose a valid difficulty and status."
    try:
        minutes = int(field("estimated_minutes") or ai_planner.DEFAULT_MINUTES[difficulty])
    except ValueError:
        return None, "Estimated study time must be a number of minutes."
    if not 10 <= minutes <= 240:
        return None, "Estimated study time must be between 10 and 240 minutes."
    return {"name": name, "difficulty": difficulty,
            "estimated_minutes": minutes, "status": status}, None


@app.route("/topics")
@login_required
def topics():
    db, user = get_db(), uid()
    subs = list(db.subjects.find({"user_id": user}).sort("name", 1))
    all_topics = list(db.topics.find({"user_id": user}).sort("created_at", 1))
    groups = [{"subject": s, "topics": [t for t in all_topics if t["subject_id"] == s["_id"]]}
              for s in subs]
    selected = request.args.get("subject", "")
    if selected:
        groups = [g for g in groups if str(g["subject"]["_id"]) == selected]
    return render_template("topics.html", subjects=subs, groups=groups, selected=selected)


@app.route("/topics/add", methods=["POST"])
@login_required
def topics_add():
    db, user = get_db(), uid()
    subject = db.subjects.find_one({"_id": oid(field("subject_id")), "user_id": user}) \
        if oid(field("subject_id")) else None
    doc, error = read_topic_form()
    if not subject:
        flash("Please select a subject.", "danger")
    elif error:
        flash(error, "danger")
    else:
        doc.update(user_id=user, subject_id=subject["_id"], created_at=dt.datetime.utcnow())
        db.topics.insert_one(doc)
        flash("Topic added.", "success")
    return go_back("topics")


@app.route("/topics/edit/<id>", methods=["POST"])
@login_required
def topics_edit(id):
    doc, error = read_topic_form()
    if error or not oid(id):
        flash(error or "Topic not found.", "danger")
    else:
        get_db().topics.update_one({"_id": oid(id), "user_id": uid()}, {"$set": doc})
        flash("Topic updated.", "success")
    return go_back("topics")


@app.route("/topics/complete/<id>", methods=["POST"])
@login_required
def topics_complete(id):
    if oid(id):
        get_db().topics.update_one({"_id": oid(id), "user_id": uid()},
                                   {"$set": {"status": "Completed"}})
        flash("Topic marked as completed. 🎉", "success")
    return go_back("topics")


@app.route("/topics/delete/<id>", methods=["POST"])
@login_required
def topics_delete(id):
    db, user, tid = get_db(), uid(), oid(id)
    if tid:
        db.topics.delete_one({"_id": tid, "user_id": user})
        db.study_tasks.delete_many({"topic_id": tid, "user_id": user})
        flash("Topic deleted.", "info")
    return go_back("topics")


# ======================================================================
# AI Study Planner
# ======================================================================
@app.route("/planner")
@login_required
def planner():
    db, user = get_db(), uid()
    profile = db.users.find_one({"_id": user}) or {}
    subs = list(db.subjects.find({"user_id": user}).sort("name", 1))
    return render_template("planner.html", subjects=subs, profile=profile)


@app.route("/planner/generate", methods=["POST"])
@login_required
def planner_generate():
    """Retrieve data -> score -> sort -> allocate -> save -> return JSON."""
    db, user = get_db(), uid()
    data = request.get_json(silent=True) or request.form
    today = dt.date.today()

    subject_id = data.get("subject_id") or "all"
    start = data.get("start_time") or "08:00"
    end = data.get("end_time") or "20:00"
    try:
        hours = float(data.get("hours"))
    except (TypeError, ValueError):
        hours = 0

    if not (valid_time(start) and valid_time(end)) or not 0.5 <= hours <= 16:
        return jsonify(ok=False, message="Please enter all required fields."), 400
    if ai_planner.to_minutes(end) - ai_planner.to_minutes(start) < 30:
        return jsonify(ok=False, message="End time must be at least 30 minutes after start time."), 400

    query = {"user_id": user}
    if subject_id != "all":
        if not oid(subject_id):
            return jsonify(ok=False, message="Subject not found."), 400
        query["_id"] = oid(subject_id)
    subjects_ = list(db.subjects.find(query))
    if not subjects_:
        return jsonify(ok=False, message="Please add a subject first."), 400

    # Optional exam date override (only for one selected subject)
    exam_override = data.get("exam_date")
    if exam_override and subject_id != "all":
        if not valid_date(exam_override):
            return jsonify(ok=False, message="Please enter a valid exam date."), 400
        db.subjects.update_one({"_id": subjects_[0]["_id"]}, {"$set": {"exam_date": exam_override}})
        subjects_[0]["exam_date"] = exam_override

    ids = [s["_id"] for s in subjects_]
    topics_ = list(db.topics.find({"user_id": user, "subject_id": {"$in": ids}}))

    try:
        ranked = ai_planner.rank_topics(subjects_, topics_, today)
        if not ranked:
            return jsonify(ok=False, message="No pending topics available."), 400
        result = ai_planner.build_schedule(ranked, int(hours * 60), start, end, today)
        if not result["tasks"]:
            return jsonify(ok=False, message="Unable to generate study plan."), 400
        tips = ai_planner.recommendations(subjects_, topics_, today)
    except Exception:
        app.logger.exception("Planner failure")
        return jsonify(ok=False, message="Unable to generate study plan."), 500

    # Regenerating replaces the old *pending* tasks for these subjects.
    db.study_tasks.delete_many({"user_id": user, "subject_id": {"$in": ids}, "status": "Pending"})
    now = dt.datetime.utcnow()
    db.study_tasks.insert_many([{
        "user_id": user, "subject_id": t["subject_id"], "topic_id": t["topic_id"],
        "study_date": t["study_date"], "start_time": t["start_time"],
        "duration": t["duration"], "priority": t["priority"],
        "status": "Pending", "created_at": now} for t in result["tasks"]])
    db.users.update_one({"_id": user},
                        {"$set": {"daily_hours": hours, "preferred_start_time": start}})

    days = {}
    for t in result["tasks"]:
        days.setdefault(t["study_date"], []).append({
            "start": t["start_time"],
            "end": ai_planner.add_minutes(t["start_time"], t["duration"]),
            "subject": t["subject_name"], "topic": t["topic_name"],
            "priority": t["priority"], "duration": t["duration"]})
    plan = [{"date": d,
             "day": dt.datetime.strptime(d, "%Y-%m-%d").strftime("%A"),
             "label": nicedate(d), "tasks": items} for d, items in sorted(days.items())]

    return jsonify(ok=True, plan=plan, recommendations=tips,
                   total=len(result["tasks"]), unscheduled=len(result["unscheduled"]))


# ======================================================================
# Tasks
# ======================================================================
@app.route("/tasks")
@login_required
def tasks():
    db, user = get_db(), uid()
    items = list(db.study_tasks.find({"user_id": user}).sort(
        [("study_date", 1), ("start_time", 1)]))
    return render_template("tasks.html", tasks=enrich_tasks(db, user, items),
                           today=dt.date.today().isoformat())


@app.route("/tasks/complete/<id>", methods=["POST"])
@login_required
def tasks_complete(id):
    db, user, tid = get_db(), uid(), oid(id)
    task = db.study_tasks.find_one({"_id": tid, "user_id": user}) if tid else None
    if task:
        db.study_tasks.update_one({"_id": tid},
                                  {"$set": {"status": "Completed",
                                            "completed_at": dt.datetime.utcnow()}})
        db.topics.update_one({"_id": task["topic_id"], "user_id": user},
                             {"$set": {"status": "Completed"}})
        flash("Great job! Task completed. ✅", "success")
    return go_back("tasks")


@app.route("/tasks/update/<id>", methods=["POST"])
@login_required
def tasks_update(id):
    """Edit duration/priority and/or reschedule date and time."""
    changes = {}
    if field("study_date"):
        if not valid_date(field("study_date")):
            flash("Please enter a valid date.", "danger")
            return go_back("tasks")
        changes["study_date"] = field("study_date")
    if field("start_time"):
        if not valid_time(field("start_time")):
            flash("Please enter a valid time.", "danger")
            return go_back("tasks")
        changes["start_time"] = field("start_time")
    if field("duration"):
        try:
            minutes = int(field("duration"))
        except ValueError:
            minutes = 0
        if not 10 <= minutes <= 240:
            flash("Duration must be between 10 and 240 minutes.", "danger")
            return go_back("tasks")
        changes["duration"] = minutes
    if field("priority") in PRIORITIES:
        changes["priority"] = field("priority")
    if changes and oid(id):
        get_db().study_tasks.update_one({"_id": oid(id), "user_id": uid()}, {"$set": changes})
        flash("Task updated.", "success")
    return go_back("tasks")


@app.route("/tasks/delete/<id>", methods=["POST"])
@login_required
def tasks_delete(id):
    if oid(id):
        get_db().study_tasks.delete_one({"_id": oid(id), "user_id": uid()})
        flash("Task deleted.", "info")
    return go_back("tasks")


# ======================================================================
# Progress
# ======================================================================
@app.route("/progress")
@login_required
def progress():
    db, user = get_db(), uid()
    subs = subject_stats(list(db.subjects.find({"user_id": user}).sort("name", 1)),
                         list(db.topics.find({"user_id": user})))
    total = sum(s["total"] for s in subs)
    done = sum(s["done"] for s in subs)
    overall = round(done * 100 / total) if total else 0

    per_day = minutes_per_day(db, user)
    week = [dt.date.today() - dt.timedelta(days=i) for i in range(6, -1, -1)]
    task_status = {"Completed": 0, "Pending": 0}
    for t in db.study_tasks.find({"user_id": user}):
        task_status["Completed" if t["status"] == "Completed" else "Pending"] += 1

    chart = {
        "subjects": {"labels": [s["name"] for s in subs], "values": [s["percent"] for s in subs]},
        "weekly": {"labels": [d.strftime("%a") for d in week],
                   "values": [round(per_day.get(d, 0) / 60, 1) for d in week]},
        "tasks": {"labels": ["Completed", "Pending"],
                  "values": [task_status["Completed"], task_status["Pending"]]},
    }
    return render_template("progress.html", subjects=subs, overall=overall, chart=chart)


# ======================================================================
# Pomodoro (timer runs in JavaScript; we only log finished sessions)
# ======================================================================
@app.route("/pomodoro")
@login_required
def pomodoro():
    db, user = get_db(), uid()
    topics_ = list(db.topics.find({"user_id": user, "status": {"$ne": "Completed"}}).sort("name", 1))
    subjects_ = {s["_id"]: s["name"] for s in db.subjects.find({"user_id": user})}
    for t in topics_:
        t["subject_name"] = subjects_.get(t["subject_id"], "")
    return render_template("pomodoro.html", topics=topics_, selected=request.args.get("topic", ""))


@app.route("/pomodoro/log", methods=["POST"])
@login_required
def pomodoro_log():
    data = request.get_json(silent=True) or {}
    minutes = data.get("duration")
    if not isinstance(minutes, int) or not 1 <= minutes <= 120:
        return jsonify(ok=False), 400
    get_db().study_sessions.insert_one({
        "user_id": uid(), "topic_id": oid(data.get("topic_id")) if data.get("topic_id") else None,
        "duration": minutes, "completed_at": dt.datetime.utcnow()})
    return jsonify(ok=True)


# ======================================================================
# Profile
# ======================================================================
@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=get_db().users.find_one({"_id": uid()}))


@app.route("/profile/update", methods=["POST"])
@login_required
def profile_update():
    name, college = field("name"), field("college")
    start = field("preferred_start_time")
    try:
        hours = float(field("daily_hours"))
    except ValueError:
        hours = 0
    if not (name and college) or not valid_time(start) or not 0.5 <= hours <= 16:
        flash("Please enter all required fields.", "danger")
    else:
        get_db().users.update_one({"_id": uid()}, {"$set": {
            "name": name, "college": college,
            "daily_hours": hours, "preferred_start_time": start}})
        session["user_name"] = name
        flash("Profile updated.", "success")
    return redirect(url_for("profile"))


# ======================================================================
if __name__ == "__main__":
    try:                                   # lets Windows consoles print emojis
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if check_connection():
        create_indexes()
    print("🚀 StudyMate AI Server Running")
    app.run(debug=True)
