from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db import Base


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)

    sections = relationship("Section", back_populates="subject", order_by="Section.order")


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    name = Column(String, nullable=False)
    order = Column(Integer, default=0)

    subject = relationship("Subject", back_populates="sections")
    topics = relationship("Topic", back_populates="section", order_by="Topic.order")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    source_uid = Column(String, nullable=True)
    title = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    order = Column(Integer, default=0)
    has_content = Column(Boolean, default=False)

    section = relationship("Section", back_populates="topics")
    lesson = relationship("Lesson", back_populates="topic", uselist=False)
    questions = relationship("Question", back_populates="topic", order_by="Question.order")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), unique=True, nullable=False)
    content_md = Column(Text, nullable=False)

    topic = relationship("Topic", back_populates="lesson")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    type = Column(String, nullable=False)  # single | multiple | dropdown | fill_blank | matching
    text = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)  # fill_blank correct answer (accepted list joined by "|")
    order = Column(Integer, default=0)

    topic = relationship("Topic", back_populates="questions")
    options = relationship("Option", back_populates="question", order_by="Option.order")
    pairs = relationship("MatchPair", back_populates="question", order_by="MatchPair.order")


class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    text = Column(String, nullable=False)
    is_correct = Column(Boolean, default=False)
    order = Column(Integer, default=0)

    question = relationship("Question", back_populates="options")


class MatchPair(Base):
    __tablename__ = "match_pairs"

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    left_text = Column(String, nullable=False)
    right_text = Column(String, nullable=False)
    order = Column(Integer, default=0)

    question = relationship("Question", back_populates="pairs")


class UserProgress(Base):
    __tablename__ = "user_progress"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_user_topic"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, default=1, nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    status = Column(String, default="not_started")  # not_started | passed | needs_review
    best_score = Column(Integer, default=0)  # percent
    attempts = Column(Integer, default=0)
    interval_stage = Column(Integer, default=0)  # index into REVIEW_INTERVALS_DAYS
    next_review_at = Column(Date, nullable=True)
