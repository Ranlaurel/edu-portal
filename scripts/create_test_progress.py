"""Create test progress for Ranlaurel4 and Shvedko1."""
import sys
from datetime import date, timedelta
from pathlib import Path
import random

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.models import Attempt, Topic, User, UserProgress

def create_progress_for_user(db, username, num_topics=15):
    user = db.query(User).filter_by(username=username).first()
    if not user:
        print(f"User {username} not found")
        return
    
    # Get some random topics from grade 6
    topics = db.query(Topic).join(Topic.section).filter(
        Topic.section.has(Topic.section.property.mapper.class_.subject.has(grade=6))
    ).limit(50).all()
    
    if not topics:
        print("No topics found")
        return
    
    random.shuffle(topics)
    selected_topics = topics[:num_topics]
    
    today = date.today()
    
    for i, topic in enumerate(selected_topics):
        # Create 1-3 attempts per topic
        num_attempts = random.randint(1, 3)
        
        for attempt_num in range(num_attempts):
            # Score between 50-100, increasing over attempts
            base_score = random.randint(50, 85)
            score = min(100, base_score + attempt_num * 10)
            passed = score >= 70
            
            # Create attempt spread over last 30 days
            days_ago = random.randint(0, 30)
            attempt_date = today - timedelta(days=days_ago)
            
            attempt = Attempt(
                user_id=user.id,
                topic_id=topic.id,
                score=score,
                passed=passed,
                created_at=attempt_date
            )
            db.add(attempt)
        
        # Create progress record
        best_score = min(100, base_score + (num_attempts - 1) * 10)
        status = "passed" if best_score >= 70 else "needs_review"
        
        # Some topics need review
        if status == "passed" and random.random() < 0.3:
            next_review = today + timedelta(days=random.randint(1, 7))
        else:
            next_review = None
        
        progress = UserProgress(
            user_id=user.id,
            topic_id=topic.id,
            status=status,
            best_score=best_score,
            attempts=num_attempts,
            interval_stage=random.randint(0, 2) if status == "passed" else 0,
            next_review_at=next_review,
            wrong_question_ids=None if best_score >= 85 else "1,3,5"
        )
        db.add(progress)
    
    db.commit()
    print(f"Created progress for {username}: {num_topics} topics, {num_topics * 2} attempts (avg)")


def main():
    db = SessionLocal()
    try:
        create_progress_for_user(db, "Ranlaurel4", num_topics=18)
        create_progress_for_user(db, "Shvedko1", num_topics=12)
        print("Test progress created successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
