"""Research Notes and Markdown Export REST API."""

import re

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedUser, get_current_user, get_db
from app.core.errors import NoteNotFoundError
from app.models.note import ResearchNote
from app.schemas.note import (
    NoteCreate,
    NoteExportResponse,
    NoteListResponse,
    NoteResponse,
    NoteUpdate,
)
from app.security.permissions import verify_ownership

router = APIRouter(prefix="/notes", tags=["Notes"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=NoteResponse)
async def create_note(
    body: NoteCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save an answer or research synthesis as a persistent note."""
    note = ResearchNote(
        owner_id=current_user.id,
        session_id=body.session_id,
        title=body.title,
        content=body.content,
        source_citations=body.source_citations or [],
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return NoteResponse.model_validate(note)


@router.get("", response_model=NoteListResponse)
async def list_notes(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all notes owned by user."""
    stmt = (
        select(ResearchNote)
        .where(ResearchNote.owner_id == current_user.id)
        .order_by(ResearchNote.updated_at.desc())
    )
    res = await db.execute(stmt)
    notes = res.scalars().all()
    items = [NoteResponse.model_validate(n) for n in notes]
    return NoteListResponse(total=len(items), items=items)


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get note details."""
    stmt = select(ResearchNote).where(ResearchNote.id == note_id)
    res = await db.execute(stmt)
    note = res.scalar_one_or_none()
    if not note:
        raise NoteNotFoundError(note_id)

    verify_ownership(note.owner_id, current_user.id, "research note")
    return NoteResponse.model_validate(note)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    body: NoteUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update title, content, or citations of a note."""
    stmt = select(ResearchNote).where(ResearchNote.id == note_id)
    res = await db.execute(stmt)
    note = res.scalar_one_or_none()
    if not note:
        raise NoteNotFoundError(note_id)

    verify_ownership(note.owner_id, current_user.id, "research note")

    if body.title is not None:
        note.title = body.title
    if body.content is not None:
        note.content = body.content
    if body.source_citations is not None:
        note.source_citations = body.source_citations

    await db.commit()
    await db.refresh(note)
    return NoteResponse.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a research note."""
    stmt = select(ResearchNote).where(ResearchNote.id == note_id)
    res = await db.execute(stmt)
    note = res.scalar_one_or_none()
    if not note:
        raise NoteNotFoundError(note_id)

    verify_ownership(note.owner_id, current_user.id, "research note")
    await db.delete(note)
    await db.commit()


@router.get("/{note_id}/export", response_model=NoteExportResponse)
async def export_note(
    note_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export note as publication-ready Markdown preserving all verified citations."""
    stmt = select(ResearchNote).where(ResearchNote.id == note_id)
    res = await db.execute(stmt)
    note = res.scalar_one_or_none()
    if not note:
        raise NoteNotFoundError(note_id)

    verify_ownership(note.owner_id, current_user.id, "research note")

    # Build Markdown with references section
    md_lines = [
        f"# {note.title}",
        "",
        f"*Exported from ORION AI Research Assistant on {note.updated_at.strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "---",
        "",
        "## Synthesis",
        "",
        note.content,
        "",
    ]

    if note.source_citations:
        md_lines.extend([
            "## Source References & Citations",
            "",
        ])
        for idx, cite in enumerate(note.source_citations):
            cid = cite.get("citation_id", f"cite:{idx+1}")
            fn = cite.get("filename", "Unknown Document")
            pages = cite.get("page_numbers", [])
            pg_str = f"Page {pages[0]}" if len(pages) == 1 else f"Pages {', '.join(str(p) for p in pages)}" if pages else "Page 1"
            excerpt = cite.get("excerpt", "").strip()

            md_lines.append(f"### [{cid}] {fn} ({pg_str})")
            if excerpt:
                md_lines.append(f"> \"{excerpt}\"")
            md_lines.append("")

    safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", note.title.lower())[:40]
    filename = f"orion_note_{safe_slug}.md"

    return NoteExportResponse(
        note_id=note.id,
        title=note.title,
        markdown_content="\n".join(md_lines),
        filename=filename,
    )
