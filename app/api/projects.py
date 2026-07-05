from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.core.response import created, ok
from app.db import get_db
from app.models.auth import Project, User
from app.schemas.auth import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


async def _get_project_or_404(project_id: str, org_id: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id, Project.org_id == org_id))
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project")
    return project


@router.get("")
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.org_id == current_user.org_id))
    projects = result.scalars().all()
    return ok([ProjectOut.model_validate(p).model_dump(mode="json") for p in projects])


@router.post("", status_code=201)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(org_id=current_user.org_id, name=body.name, description=body.description)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return created(ProjectOut.model_validate(project).model_dump(mode="json"))


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_or_404(project_id, current_user.org_id, db)
    return ok(ProjectOut.model_validate(project).model_dump(mode="json"))


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_or_404(project_id, current_user.org_id, db)
    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    await db.commit()
    await db.refresh(project)
    return ok(ProjectOut.model_validate(project).model_dump(mode="json"))


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_or_404(project_id, current_user.org_id, db)
    await db.delete(project)
    await db.commit()
