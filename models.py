#!/usr/bin/env python3
"""Data models for Rio Hondo College course schedule data."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class MeetingTime(BaseModel):
    """Represents a single meeting time for a course."""
    days: str = Field(description="Days of the week (e.g., 'MW', 'TR', 'F')")
    start_time: Optional[str] = Field(None, description="Start time (e.g., '9:00 AM')")
    end_time: Optional[str] = Field(None, description="End time (e.g., '10:50 AM')")
    is_arranged: bool = Field(False, description="True if time is 'arr' (to be arranged)")


class Enrollment(BaseModel):
    """Enrollment information for a course."""
    capacity: int = Field(description="Maximum enrollment capacity")
    actual: int = Field(description="Current enrollment count")
    remaining: int = Field(description="Seats remaining")


class Course(BaseModel):
    """Represents a single course offering."""
    crn: str = Field(description="Course Reference Number")
    subject: str = Field(description="Subject code (e.g., 'ACCT', 'ENGL')")
    course_number: str = Field(description="Course number (e.g., '101', 'C1000')")
    title: str = Field(description="Course title")
    units: float = Field(description="Number of units")
    instructor: str = Field(description="Instructor name")
    instructor_email: Optional[str] = Field(None, description="Instructor email")
    meeting_times: List[MeetingTime] = Field(description="List of meeting times")
    location: str = Field(description="Location (e.g., 'Online ASYNC', 'A207')")
    enrollment: Enrollment = Field(description="Enrollment information")
    status: str = Field(description="Course status (e.g., 'Open', 'Closed')")
    section_type: str = Field(description="Type of section (e.g., 'LEC', 'LAB')")
    zero_textbook_cost: bool = Field(False, description="True if zero textbook cost")
    delivery_method: str = Field(description="Delivery method (e.g., 'Online ASYNC', 'In-Person', 'Hybrid')")
    weeks: int = Field(description="Number of weeks for the course")
    start_date: Optional[str] = Field(None, description="Course start date")
    end_date: Optional[str] = Field(None, description="Course end date")
    additional_hours: Optional[str] = Field(None, description="Additional arranged hours info")
    book_link: Optional[str] = Field(None, description="Link to bookstore for textbooks")


class ScheduleData(BaseModel):
    """Container for all collected schedule data."""
    term: str = Field(description="Term identifier (e.g., 'Fall 2025')")
    term_code: str = Field(description="Term code (e.g., '202570')")
    collection_timestamp: datetime = Field(description="When this data was collected")
    source_url: str = Field(description="URL where data was collected from")
    courses: List[Course] = Field(description="List of all courses")
    total_courses: int = Field(description="Total number of courses collected")
    departments: List[str] = Field(description="List of unique departments in collection")
    
    def model_post_init(self, __context):
        """Calculate derived fields after initialization."""
        if not self.total_courses:
            self.total_courses = len(self.courses)
        if not self.departments:
            self.departments = sorted(list(set(course.subject for course in self.courses)))


class CollectionMetadata(BaseModel):
    """Metadata about a collection run."""
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    courses_collected: int
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    success: bool = True