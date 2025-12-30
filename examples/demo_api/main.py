"""Demo FastAPI backend for testing OMCP."""

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(
    title="Task Manager API",
    description="A simple task management API for testing OMCP",
    version="1.0.0",
)

# In-memory database
tasks_db: dict[int, dict] = {}
notes_db: dict[int, dict] = {}
task_id_counter = 1
note_id_counter = 1


# ============================================================================
# Models
# ============================================================================


class TaskCreate(BaseModel):
    """Create a new task."""
    title: str = Field(..., description="Task title", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="Task description")
    priority: str = Field("medium", description="Priority level: low, medium, high")
    due_date: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format")


class TaskUpdate(BaseModel):
    """Update an existing task."""
    title: Optional[str] = Field(None, description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    priority: Optional[str] = Field(None, description="Priority level")
    due_date: Optional[str] = Field(None, description="Due date")
    completed: Optional[bool] = Field(None, description="Completion status")


class Task(BaseModel):
    """Task response model."""
    id: int
    title: str
    description: Optional[str]
    priority: str
    due_date: Optional[str]
    completed: bool
    created_at: str


class NoteCreate(BaseModel):
    """Create a new note."""
    content: str = Field(..., description="Note content", min_length=1)
    task_id: Optional[int] = Field(None, description="Associated task ID")


class Note(BaseModel):
    """Note response model."""
    id: int
    content: str
    task_id: Optional[int]
    created_at: str


# ============================================================================
# Task Endpoints
# ============================================================================


@app.get("/tasks", response_model=list[Task], tags=["tasks"])
def list_tasks(
    completed: Optional[bool] = Query(None, description="Filter by completion status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of tasks to return"),
) -> list[dict]:
    """List all tasks with optional filtering."""
    tasks = list(tasks_db.values())

    if completed is not None:
        tasks = [t for t in tasks if t["completed"] == completed]

    if priority is not None:
        tasks = [t for t in tasks if t["priority"] == priority]

    return tasks[:limit]


@app.post("/tasks", response_model=Task, status_code=201, tags=["tasks"])
def create_task(task: TaskCreate) -> dict:
    """Create a new task."""
    global task_id_counter

    new_task = {
        "id": task_id_counter,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "due_date": task.due_date,
        "completed": False,
        "created_at": datetime.now().isoformat(),
    }

    tasks_db[task_id_counter] = new_task
    task_id_counter += 1

    return new_task


@app.get("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def get_task(task_id: int) -> dict:
    """Get a specific task by ID."""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return tasks_db[task_id]


@app.patch("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def update_task(task_id: int, task: TaskUpdate) -> dict:
    """Update a task's fields."""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    existing = tasks_db[task_id]
    update_data = task.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        existing[field] = value

    return existing


@app.delete("/tasks/{task_id}", status_code=204, tags=["tasks"])
def delete_task(task_id: int) -> None:
    """Delete a task."""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    del tasks_db[task_id]


@app.post("/tasks/{task_id}/complete", response_model=Task, tags=["tasks"])
def complete_task(task_id: int) -> dict:
    """Mark a task as completed."""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    tasks_db[task_id]["completed"] = True
    return tasks_db[task_id]


# ============================================================================
# Note Endpoints
# ============================================================================


@app.get("/notes", response_model=list[Note], tags=["notes"])
def list_notes(
    task_id: Optional[int] = Query(None, description="Filter by task ID"),
) -> list[dict]:
    """List all notes, optionally filtered by task."""
    notes = list(notes_db.values())

    if task_id is not None:
        notes = [n for n in notes if n["task_id"] == task_id]

    return notes


@app.post("/notes", response_model=Note, status_code=201, tags=["notes"])
def create_note(note: NoteCreate) -> dict:
    """Create a new note."""
    global note_id_counter

    # Validate task_id if provided
    if note.task_id is not None and note.task_id not in tasks_db:
        raise HTTPException(status_code=404, detail=f"Task {note.task_id} not found")

    new_note = {
        "id": note_id_counter,
        "content": note.content,
        "task_id": note.task_id,
        "created_at": datetime.now().isoformat(),
    }

    notes_db[note_id_counter] = new_note
    note_id_counter += 1

    return new_note


@app.get("/notes/{note_id}", response_model=Note, tags=["notes"])
def get_note(note_id: int) -> dict:
    """Get a specific note by ID."""
    if note_id not in notes_db:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
    return notes_db[note_id]


@app.delete("/notes/{note_id}", status_code=204, tags=["notes"])
def delete_note(note_id: int) -> None:
    """Delete a note."""
    if note_id not in notes_db:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
    del notes_db[note_id]


# ============================================================================
# Utility Endpoints
# ============================================================================


@app.get("/stats", tags=["utility"])
def get_stats() -> dict:
    """Get statistics about tasks and notes."""
    tasks = list(tasks_db.values())
    completed = sum(1 for t in tasks if t["completed"])

    return {
        "total_tasks": len(tasks),
        "completed_tasks": completed,
        "pending_tasks": len(tasks) - completed,
        "total_notes": len(notes_db),
        "tasks_by_priority": {
            "high": sum(1 for t in tasks if t["priority"] == "high"),
            "medium": sum(1 for t in tasks if t["priority"] == "medium"),
            "low": sum(1 for t in tasks if t["priority"] == "low"),
        },
    }


@app.get("/health", tags=["utility"])
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
