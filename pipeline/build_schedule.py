"""Build a school-year calendar mapping each topic to a specific teaching DAY
(not just a week), for every subject that has real lesson.md/quiz.json content.

Standard Russian school calendar, 2026/2027 academic year, ~37 teaching weeks with the
usual quarter breaks, Monday-Friday school days only. Each subject's topics are spread
evenly across all school days (round-robin by proportion), so most days get one new
topic per subject and the rest are left as review/practice buffer days. Subjects with
fewer topics (e.g. english, biology, geography -- lower weekly-hour subjects in the
real curriculum) naturally get a lower day-to-day frequency than russian/math/
literature without any extra scheduling logic -- topic count IS the frequency knob.

HOUR_ONLY_SUBJECTS below is for subjects that don't have real content yet: they get
placeholder slots on fixed weekdays at the standard federal curriculum (БУП) weekly-hour
count, so the schedule still reflects real annual lesson totals. Empty for now -- every
subject in this app has real content.

Usage: python pipeline/build_schedule.py
Writes: content/schedule.json
"""
import json
from datetime import date, timedelta
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"

TERMS = [
    (date(2026, 9, 1), date(2026, 10, 25)),
    (date(2026, 11, 5), date(2026, 12, 29)),
    (date(2027, 1, 12), date(2027, 3, 22)),
    (date(2027, 4, 1), date(2027, 5, 24)),
]

SUBJECTS = [
    "russian", "math", "english",
    "biology", "geography", "vseobschaya-istoriya", "istoriya-rossii", "literature",
]

# weekday() -> 0=Mon .. 4=Fri. Which "hours only" (no real content yet) subjects meet
# on which weekday.
HOUR_ONLY_SUBJECTS = {}


def school_days():
    days = []
    for start, end in TERMS:
        cur = start
        while cur <= end:
            if cur.weekday() < 5:  # Mon-Fri
                days.append(cur)
            cur += timedelta(days=1)
    return days


def flatten_topics(manifest):
    topics = []
    for section in manifest["sections"]:
        for t in section["topics"]:
            topics.append({"slug": t["slug"], "title": t["title"], "section": section["name"]})
    return topics


def assign(topics, days):
    n_topics = len(topics)
    n_days = len(days)
    schedule = [None] * n_days
    for i, topic in enumerate(topics):
        day_idx = min(int(i * n_days / n_topics), n_days - 1)
        while schedule[day_idx] is not None and day_idx < n_days - 1:
            day_idx += 1
        schedule[day_idx] = topic
    return schedule


def main():
    days = school_days()
    subjects = {}
    for subj_dir in SUBJECTS:
        manifest_path = CONTENT_DIR / subj_dir / "topics.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        subjects[subj_dir] = {
            "name": manifest["subject"]["name"],
            "schedule": assign(flatten_topics(manifest), days),
        }

    hour_only_totals = {
        key: sum(1 for d in days if d.weekday() in cfg["weekdays"])
        for key, cfg in HOUR_ONLY_SUBJECTS.items()
    }
    hour_only_counters = {key: 0 for key in HOUR_ONLY_SUBJECTS}

    result = {"days": []}
    for i, d in enumerate(days):
        day_subjects = {subj: data["schedule"][i] for subj, data in subjects.items()}

        for key, cfg in HOUR_ONLY_SUBJECTS.items():
            if d.weekday() in cfg["weekdays"]:
                hour_only_counters[key] += 1
                day_subjects[key] = {
                    "generic": True,
                    "title": cfg["name"],
                    "lesson_number": hour_only_counters[key],
                    "total": hour_only_totals[key],
                }
            else:
                day_subjects[key] = None

        entry = {
            "date": d.isoformat(),
            "weekday": d.strftime("%A"),
            "subjects": day_subjects,
        }
        result["days"].append(entry)

    out_path = CONTENT_DIR / "schedule.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    n_topics = {s: len(flatten_topics(json.loads((CONTENT_DIR / s / "topics.json").read_text(encoding="utf-8")))) for s in SUBJECTS}
    print(f"Wrote {out_path}: {len(days)} school days, {n_topics} topics per subject, hour-only totals: {hour_only_totals}.")


if __name__ == "__main__":
    main()
