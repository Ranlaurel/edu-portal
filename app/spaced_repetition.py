from datetime import date, timedelta

# Leitner-style schedule: days until next review at each stage.
REVIEW_INTERVALS_DAYS = [1, 3, 7, 16, 35]


def on_pass(progress) -> None:
    """Advance the review schedule after a passing attempt."""
    stage = min(progress.interval_stage or 0, len(REVIEW_INTERVALS_DAYS) - 1)
    progress.next_review_at = date.today() + timedelta(days=REVIEW_INTERVALS_DAYS[stage])
    progress.interval_stage = min(stage + 1, len(REVIEW_INTERVALS_DAYS) - 1)


def on_fail(progress) -> None:
    """Reset the review schedule after a failing attempt on a previously-passed topic."""
    progress.interval_stage = 0
    progress.next_review_at = date.today() + timedelta(days=REVIEW_INTERVALS_DAYS[0])
