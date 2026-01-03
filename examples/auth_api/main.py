"""Simple Notes API with JWT authentication for testing OMCP dynamic auth.

This API demonstrates:
- JWT authentication with multiple users
- User-specific data (each user only sees their notes)
- CRUD operations

Run: uvicorn examples.auth_api.main:app --reload --port 8080
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# =============================================================================
# Configuration
# =============================================================================

# Secret key for JWT signing (in production, use a secure secret)
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# =============================================================================
# Models
# =============================================================================


class User(BaseModel):
    """User model."""

    id: str
    username: str
    email: str
    role: str = "user"


class Note(BaseModel):
    """Note model."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    title: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NoteCreate(BaseModel):
    """Request body for creating a note."""

    title: str
    content: str


class NoteUpdate(BaseModel):
    """Request body for updating a note."""

    title: str | None = None
    content: str | None = None


class TokenResponse(BaseModel):
    """Response for token generation."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User


class UserInfo(BaseModel):
    """Current user info response."""

    user: User
    token_expires_at: datetime


# =============================================================================
# In-Memory Database
# =============================================================================

# Test users (password is same as username for simplicity)
USERS: dict[str, User] = {
    "alice": User(id="user-1", username="alice", email="alice@example.com", role="admin"),
    "bob": User(id="user-2", username="bob", email="bob@example.com", role="user"),
    "charlie": User(id="user-3", username="charlie", email="charlie@example.com", role="user"),
}

# Notes database: note_id -> Note
notes_db: dict[str, Note] = {}


def seed_data():
    """Seed initial notes for testing."""
    global notes_db

    seed_notes = [
        Note(
            id="note-1",
            user_id="user-1",
            title="Alice's Project Plan",
            content="1. Design architecture\n2. Implement core features\n3. Write tests",
        ),
        Note(
            id="note-2",
            user_id="user-1",
            title="Meeting Notes",
            content="Discussed Q4 roadmap with the team. Action items pending.",
        ),
        Note(
            id="note-3",
            user_id="user-2",
            title="Bob's TODO List",
            content="- Buy groceries\n- Call mom\n- Finish report",
        ),
        Note(
            id="note-4",
            user_id="user-2",
            title="Recipe Ideas",
            content="Try making pasta carbonara this weekend.",
        ),
        Note(
            id="note-5",
            user_id="user-3",
            title="Charlie's Reading List",
            content="1. Clean Code\n2. Design Patterns\n3. The Pragmatic Programmer",
        ),
    ]

    for note in seed_notes:
        notes_db[note.id] = note


# =============================================================================
# JWT Utilities
# =============================================================================


def create_token(user: User) -> tuple[str, datetime]:
    """Create a JWT token for a user."""
    expires_at = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {
        "sub": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "exp": expires_at,
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# =============================================================================
# Authentication
# =============================================================================

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    """Extract and validate the current user from JWT token."""
    payload = decode_token(credentials.credentials)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
        )

    # Reconstruct user from token claims
    return User(
        id=user_id,
        username=payload.get("username", "unknown"),
        email=payload.get("email", ""),
        role=payload.get("role", "user"),
    )


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Notes API",
    description="A simple notes API with JWT authentication for testing OMCP dynamic auth",
    version="1.0.0",
)


@app.on_event("startup")
async def startup():
    """Seed data on startup."""
    seed_data()


# =============================================================================
# Auth Endpoints (for getting tokens)
# =============================================================================


@app.post(
    "/auth/token",
    response_model=TokenResponse,
    tags=["auth"],
    operation_id="get_token",
    summary="Get access token",
    description="Get a JWT access token for a test user. Username and password are the same (e.g., alice/alice).",
)
async def get_token(username: str, password: str) -> TokenResponse:
    """Authenticate and get a JWT token."""
    # Simple auth: password = username
    if username not in USERS or password != username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    user = USERS[username]
    token, expires_at = create_token(user)

    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRY_HOURS * 3600,
        user=user,
    )


@app.get(
    "/auth/users",
    response_model=list[str],
    tags=["auth"],
    operation_id="list_users",
    summary="List test users",
    description="List available test usernames (password = username)",
)
async def list_users() -> list[str]:
    """List available test users."""
    return list(USERS.keys())


# =============================================================================
# User Endpoints
# =============================================================================


@app.get(
    "/me",
    response_model=UserInfo,
    tags=["user"],
    operation_id="get_me",
    summary="Get current user",
    description="Get information about the currently authenticated user",
)
async def get_me(
    user: Annotated[User, Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> UserInfo:
    """Get current user info."""
    payload = decode_token(credentials.credentials)
    expires_at = datetime.fromtimestamp(payload["exp"])

    return UserInfo(user=user, token_expires_at=expires_at)


# =============================================================================
# Notes Endpoints
# =============================================================================


@app.get(
    "/notes",
    response_model=list[Note],
    tags=["notes"],
    operation_id="list_notes",
    summary="List my notes",
    description="Get all notes belonging to the current user",
)
async def list_notes(
    user: Annotated[User, Depends(get_current_user)],
) -> list[Note]:
    """List all notes for the current user."""
    return [note for note in notes_db.values() if note.user_id == user.id]


@app.post(
    "/notes",
    response_model=Note,
    status_code=status.HTTP_201_CREATED,
    tags=["notes"],
    operation_id="create_note",
    summary="Create a note",
    description="Create a new note for the current user",
)
async def create_note(
    note_data: NoteCreate,
    user: Annotated[User, Depends(get_current_user)],
) -> Note:
    """Create a new note."""
    note = Note(
        user_id=user.id,
        title=note_data.title,
        content=note_data.content,
    )
    notes_db[note.id] = note
    return note


@app.get(
    "/notes/{note_id}",
    response_model=Note,
    tags=["notes"],
    operation_id="get_note",
    summary="Get a note",
    description="Get a specific note by ID (must belong to current user)",
)
async def get_note(
    note_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> Note:
    """Get a specific note."""
    note = notes_db.get(note_id)

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if note.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this note")

    return note


@app.put(
    "/notes/{note_id}",
    response_model=Note,
    tags=["notes"],
    operation_id="update_note",
    summary="Update a note",
    description="Update a note (must belong to current user)",
)
async def update_note(
    note_id: str,
    note_data: NoteUpdate,
    user: Annotated[User, Depends(get_current_user)],
) -> Note:
    """Update a note."""
    note = notes_db.get(note_id)

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if note.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this note")

    if note_data.title is not None:
        note.title = note_data.title
    if note_data.content is not None:
        note.content = note_data.content
    note.updated_at = datetime.utcnow()

    notes_db[note_id] = note
    return note


@app.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["notes"],
    operation_id="delete_note",
    summary="Delete a note",
    description="Delete a note (must belong to current user)",
)
async def delete_note(
    note_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a note."""
    note = notes_db.get(note_id)

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if note.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this note")

    del notes_db[note_id]


# =============================================================================
# Stats Endpoint (Admin only)
# =============================================================================


@app.get(
    "/stats",
    tags=["admin"],
    operation_id="get_stats",
    summary="Get system stats",
    description="Get system statistics (admin only)",
)
async def get_stats(
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get system stats (admin only)."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return {
        "total_users": len(USERS),
        "total_notes": len(notes_db),
        "notes_per_user": {
            username: len([n for n in notes_db.values() if n.user_id == u.id])
            for username, u in USERS.items()
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
