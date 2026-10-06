"""
StudyMate AI - Smart Recommendation Engine (rule-based, no ML, no external API).

Pipeline (easy to explain in a viva):
    1. rank_topics()    -> calculate a Priority Score for every unfinished topic
    2. build_schedule() -> allocate the sorted topics into daily time slots
    3. recommendations()-> friendly tips generated from simple rules

Priority Score = Exam Urgency + Difficulty + Pending/Completion + Previous Progress
"""
from datetime import datetime, date, timedelta

# ---------- Rule tables ----------
DEFAULT_MINUTES = {"Easy": 30, "Medium": 45, "Hard": 60}
DIFFICULTY_SCORE = {"Easy": 5, "Medium": 10, "Hard": 15}
COMPLETION_SCORE = {"Pending": 10, "In Progress": 5, "Completed": 0}
BREAK_MINUTES = 10      # gap between two study blocks
MAX_PLAN_DAYS = 14      # the plan looks at most two weeks ahead


# ---------- Small helpers ----------
def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def days_until(exam_date, today=None):
    """Days left until the exam (None if the date is missing/invalid)."""
    today = today or date.today()
    exam = parse_date(exam_date)
    return None if exam is None else (exam - today).days


def to_minutes(hhmm):
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def to_hhmm(total_minutes):
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def add_minutes(hhmm, minutes):
    return to_hhmm(to_minutes(hhmm) + minutes)


# ---------- Scoring rules ----------
def urgency_score(days_left):
    """1-3 days: very high | 4-7: high | 8-14: medium | 15+: normal."""
    if days_left is None:
        return 10
    if days_left <= 3:
        return 40
    if days_left <= 7:
        return 30
    if days_left <= 14:
        return 20
    return 10


def urgency_label(days_left):
    if days_left is None or days_left > 14:
        return "Normal Priority"
    if days_left <= 3:
        return "Very High Priority"
    if days_left <= 7:
        return "High Priority"
    return "Medium Priority"


def progress_score(subject_percent_done):
    """Subjects we have barely started get a small boost."""
    if subject_percent_done < 25:
        return 2
    if subject_percent_done < 60:
        return 1
    return 0


def priority_label(score):
    if score >= 50:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def topic_duration(topic):
    """Use the student's estimate, otherwise the default for the difficulty."""
    minutes = topic.get("estimated_minutes")
    if isinstance(minutes, int) and minutes > 0:
        return minutes
    return DEFAULT_MINUTES.get(topic.get("difficulty"), 45)


# ---------- Step 1: rank topics ----------
def rank_topics(subjects, topics, today=None):
    """Return unfinished topics sorted by priority score (highest first)."""
    today = today or date.today()
    ranked = []
    for subject in subjects:
        days_left = days_until(subject.get("exam_date"), today)
        if days_left is not None and days_left < 0:
            continue                                   # exam already over
        mine = [t for t in topics if t["subject_id"] == subject["_id"]]
        done = sum(1 for t in mine if t.get("status") == "Completed")
        percent = round(done * 100 / len(mine)) if mine else 0

        for topic in mine:
            status = topic.get("status", "Pending")
            if status == "Completed":
                continue                               # never planned again
            score = (urgency_score(days_left)
                     + DIFFICULTY_SCORE.get(topic.get("difficulty"), 10)
                     + COMPLETION_SCORE.get(status, 10)
                     + progress_score(percent))
            ranked.append({
                "topic_id": topic["_id"],
                "subject_id": subject["_id"],
                "subject_name": subject["name"],
                "topic_name": topic["name"],
                "exam_date": subject.get("exam_date"),
                "days_left": days_left,
                "score": score,
                "priority": priority_label(score),
                "duration": topic_duration(topic),
            })
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


# ---------- Step 2: allocate time ----------
def build_schedule(ranked, daily_minutes, start_time, end_time, today=None):
    """
    Fill each day with the highest-priority topics that still fit.
    Returns {"tasks": [...], "unscheduled": [...]}.
    """
    today = today or date.today()
    window_start, window_end = to_minutes(start_time), to_minutes(end_time)
    capacity = min(daily_minutes, window_end - window_start)
    if capacity <= 0:
        return {"tasks": [], "unscheduled": list(ranked)}

    remaining = list(ranked)
    tasks = []
    for offset in range(MAX_PLAN_DAYS):
        if not remaining:
            break
        day = today + timedelta(days=offset)
        cursor, used = window_start, 0
        for item in list(remaining):
            exam = parse_date(item["exam_date"])
            if exam is not None and day > exam:
                continue                               # cannot study after the exam
            duration = min(item["duration"], capacity)
            if used + duration > capacity or cursor + duration > window_end:
                continue
            tasks.append({**item,
                          "study_date": day.isoformat(),
                          "start_time": to_hhmm(cursor),
                          "duration": duration})
            used += duration
            cursor += duration + BREAK_MINUTES
            remaining.remove(item)
    return {"tasks": tasks, "unscheduled": remaining}


# ---------- Step 3: smart recommendations ----------
def recommendations(subjects, topics, today=None):
    """Rule-based tips shown below the generated plan."""
    today = today or date.today()
    tips = []
    by_subject = {}
    for s in subjects:
        mine = [t for t in topics if t["subject_id"] == s["_id"]]
        done = sum(1 for t in mine if t.get("status") == "Completed")
        by_subject[s["_id"]] = (s, mine, done)

    # 1) Nearest exam within a week
    upcoming = [(days_until(s.get("exam_date"), today), s) for s in subjects]
    upcoming = [(d, s) for d, s in upcoming if d is not None and 0 <= d <= 7]
    if upcoming:
        days_left, subject = min(upcoming, key=lambda x: x[0])
        pending = [t for t in by_subject[subject["_id"]][1] if t.get("status") != "Completed"]
        pending.sort(key=lambda t: DIFFICULTY_SCORE.get(t.get("difficulty"), 10), reverse=True)
        focus = " and ".join(t["name"] for t in pending[:2])
        when = "today" if days_left == 0 else f"in {days_left} day{'s' if days_left != 1 else ''}"
        text = f"Your {subject['name']} exam is {when}."
        if focus:
            text += f" Focus on {focus} today."
        tips.append(("💡", "Recommendation", text))

    # 2) Pending hard topics
    hard = [t for t in topics if t.get("difficulty") == "Hard" and t.get("status") != "Completed"]
    if hard:
        tips.append(("⚡", "Priority Alert",
                     f"You have {len(hard)} pending hard topic{'s' if len(hard) != 1 else ''}. "
                     "Consider adding 30 extra minutes to your study schedule."))

    # 3) Best progress in a subject that is not finished yet
    best = None
    for s, mine, done in by_subject.values():
        if mine and done < len(mine):
            percent = round(done * 100 / len(mine))
            if percent >= 50 and (best is None or percent > best[0]):
                best = (percent, s, len(mine) - done)
    if best:
        percent, subject, left = best
        tips.append(("🎯", "Progress Tip",
                     f"You have completed {percent}% of {subject['name']}. "
                     f"Only {left} topic{'s' if left != 1 else ''} remain."))

    if not tips:
        tips.append(("🌱", "Study Tip",
                     "Study in focused blocks and take a short break between topics."))
    return [{"icon": i, "title": t, "text": x} for i, t, x in tips]
