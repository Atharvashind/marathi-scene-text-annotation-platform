import uuid
from typing import List
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sql_delete

from backend.models import Project, Image, User
from backend.projects.schemas import ProjectCreate, ProjectUpdate, ProjectResponse


async def get_project_for_user(
    project_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Project:
    """
    Fetch a project that belongs to the authenticated user.
    Returns HTTP 403 (not 404) for any unauthorized or missing project
    to avoid leaking existence of other users' projects.
    """
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user.id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not found",
        )
    return project


async def _build_project_response(project: Project, db: AsyncSession) -> ProjectResponse:
    """Build ProjectResponse with image_count and approved_count."""
    count_result = await db.execute(
        select(
            func.count(Image.id).label("total"),
            func.count(Image.id).filter(Image.status == "Approved").label("approved"),
        ).where(Image.project_id == project.id)
    )
    row = count_result.one()
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        description=project.description,
        default_language=project.default_language,
        created_at=project.created_at,
        updated_at=project.updated_at,
        image_count=row.total or 0,
        approved_count=row.approved or 0,
    )


async def list_projects(user: User, db: AsyncSession) -> List[ProjectResponse]:
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user.id)
        .order_by(Project.updated_at.desc())
    )
    projects = result.scalars().all()
    return [await _build_project_response(p, db) for p in projects]


async def create_project(data: ProjectCreate, user: User, db: AsyncSession) -> ProjectResponse:
    project = Project(
        user_id=user.id,
        name=data.name,
        description=data.description,
        default_language=data.default_language,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return await _build_project_response(project, db)


async def get_project(project_id: uuid.UUID, user: User, db: AsyncSession) -> ProjectResponse:
    project = await get_project_for_user(project_id, user, db)
    return await _build_project_response(project, db)


async def update_project(
    project_id: uuid.UUID, data: ProjectUpdate, user: User, db: AsyncSession
) -> ProjectResponse:
    project = await get_project_for_user(project_id, user, db)
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.default_language is not None:
        project.default_language = data.default_language
    project.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(project)
    return await _build_project_response(project, db)


async def delete_project(project_id: uuid.UUID, user: User, db: AsyncSession) -> None:
    project = await get_project_for_user(project_id, user, db)
    await db.delete(project)
    await db.flush()
