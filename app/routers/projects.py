import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin, require_any_role
from app.models.auth import User
from app.schemas.auth import ErrorResponse
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(
    tags=["projects"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List projects",
    description="Return all projects sorted by creation date descending.",
)
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role("admin", "view")),
) -> list[ProjectResponse]:
    return ProjectService(db).list_projects(current_user)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project",
)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role("admin", "view")),
) -> ProjectResponse:
    return ProjectService(db).get_project(project_id, current_user)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
    description="Create a new project. Admin access is required.",
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ProjectResponse:
    return ProjectService(db).create_project(payload)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project",
    description="Update an existing project. Admin access is required.",
)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ProjectResponse:
    return ProjectService(db).update_project(project_id, payload)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Delete an existing project. Admin access is required.",
)
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> Response:
    ProjectService(db).delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
