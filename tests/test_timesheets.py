from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.auth import Role, User
from app.models.employee import Employee
from app.models.project import Project

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def headers_for(db: Session, role_name: str, email: str) -> dict[str, str]:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        role = Role(name=role_name)
        db.add(role)
        db.flush()
    user = User(
        first_name=role_name.title(),
        last_name="User",
        email=email,
        password_hash=hash_password("Password@123"),
        is_active=True,
        account_status="active",
        roles=[role],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.fixture()
def admin_headers(db_session: Session):
    return headers_for(db_session, "admin", "admin@example.com")


@pytest.fixture()
def view_headers(db_session: Session):
    return headers_for(db_session, "view", "rahul@example.com")


@pytest.fixture()
def employee(db_session: Session):
    employee = Employee(
        employee_id="EMP-1001",
        first_name="Rahul",
        last_name="Sharma",
        email="rahul@example.com",
        date_of_birth=date(1995, 1, 1),
        role="view",
    )
    other = Employee(
        employee_id="EMP-1002",
        first_name="Priya",
        last_name="Patel",
        email="priya@example.com",
        date_of_birth=date(1996, 1, 1),
        role="view",
    )
    db_session.add_all([employee, other])
    db_session.commit()
    db_session.refresh(employee)
    db_session.refresh(other)
    return employee


@pytest.fixture()
def projects(db_session: Session, employee: Employee):
    active = Project(
        project_code="TF-001",
        project_name="WorkPilot",
        project_status="active",
        start_date=date(2026, 7, 1),
        end_date=None,
        assignees=[employee],
    )
    active_two = Project(
        project_code="TF-004",
        project_name="HireMind",
        project_status="active",
        start_date=date(2026, 7, 1),
        end_date=None,
        assignees=[employee],
    )
    inactive = Project(
        project_code="TF-002",
        project_name="Inactive",
        project_status="completed",
        start_date=date(2026, 7, 1),
        end_date=None,
        assignees=[employee],
    )
    unassigned = Project(
        project_code="TF-003",
        project_name="Unassigned",
        project_status="active",
        start_date=date(2026, 7, 1),
        end_date=None,
    )
    db_session.add_all([active, active_two, inactive, unassigned])
    db_session.commit()
    for project in [active, active_two, inactive, unassigned]:
        db_session.refresh(project)
    return active, inactive, unassigned, active_two


def save_payload(project_id: str, **overrides):
    payload = {
        "week_start": "2026-07-13",
        "entries": [
            {
                "project_id": project_id,
                "work_date": "2026-07-13",
                "hours": "8",
                "notes": "Module work",
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_employee_can_save_draft_with_exactly_8_hours(
    client: TestClient,
    view_headers: dict[str, str],
    projects: tuple[Project, Project, Project],
):
    response = client.put(
        "/api/timesheets/week",
        json=save_payload(str(projects[0].id)),
        headers=view_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert response.json()["daily_totals"]["2026-07-13"] == "8.00"


def test_daily_total_above_8_hours_is_rejected(
    client: TestClient,
    view_headers: dict[str, str],
    projects: tuple[Project, Project, Project],
):
    response = client.put(
        "/api/timesheets/week",
        json=save_payload(
            str(projects[0].id),
            entries=[
                {"project_id": str(projects[0].id), "work_date": "2026-07-13", "hours": "5"},
                {"project_id": str(projects[3].id), "work_date": "2026-07-13", "hours": "3.5"},
            ],
        ),
        headers=view_headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "DAILY_HOURS_EXCEEDED"


def test_duplicate_project_same_day_is_rejected(
    client: TestClient,
    view_headers: dict[str, str],
    projects: tuple[Project, Project, Project],
):
    response = client.put(
        "/api/timesheets/week",
        json=save_payload(
            str(projects[0].id),
            entries=[
                {"project_id": str(projects[0].id), "work_date": "2026-07-13", "hours": "5"},
                {"project_id": str(projects[0].id), "work_date": "2026-07-13", "hours": "2"},
            ],
        ),
        headers=view_headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "This project has already been added for this date."


def test_full_week_update_replaces_existing_entries_without_duplicate_conflict(
    client: TestClient,
    view_headers: dict[str, str],
    projects: tuple[Project, Project, Project],
):
    entries = [
        {"project_id": str(projects[0].id), "work_date": "2026-07-13", "hours": "4"},
        {"project_id": str(projects[3].id), "work_date": "2026-07-13", "hours": "4"},
        {"project_id": str(projects[0].id), "work_date": "2026-07-14", "hours": "4"},
        {"project_id": str(projects[3].id), "work_date": "2026-07-14", "hours": "4"},
    ]
    first = client.put(
        "/api/timesheets/week",
        json=save_payload(str(projects[0].id), entries=entries),
        headers=view_headers,
    )
    second = client.put(
        "/api/timesheets/week",
        json=save_payload(
            str(projects[0].id),
            entries=[
                {**entries[0], "notes": "updated"},
                {**entries[1], "notes": "updated"},
                {**entries[2], "notes": "updated"},
                {**entries[3], "notes": "updated"},
            ],
        ),
        headers=view_headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(second.json()["entries"]) == 4


def test_blank_rows_are_not_saved_and_weekend_entries_are_rejected(
    client: TestClient,
    view_headers: dict[str, str],
    projects: tuple[Project, Project, Project],
):
    blank_response = client.put(
        "/api/timesheets/week",
        json=save_payload(
            str(projects[0].id),
            entries=[
                {"project_id": None, "work_date": None, "hours": None, "notes": ""},
            ],
        ),
        headers=view_headers,
    )
    weekend_response = client.put(
        "/api/timesheets/week",
        json=save_payload(
            str(projects[0].id),
            entries=[
                {"project_id": str(projects[0].id), "work_date": "2026-07-18", "hours": "4"},
            ],
        ),
        headers=view_headers,
    )

    assert blank_response.status_code == 200
    assert blank_response.json()["entries"] == []
    assert weekend_response.status_code == 422
    assert weekend_response.json()["detail"] == "Weekend entries are not allowed"


def test_future_week_save_is_rejected(
    client: TestClient,
    view_headers: dict[str, str],
    projects: tuple[Project, Project, Project],
):
    response = client.put(
        "/api/timesheets/week",
        json=save_payload(str(projects[0].id), week_start="2099-01-05", entries=[
            {"project_id": str(projects[0].id), "work_date": "2099-01-05", "hours": "1"}
        ]),
        headers=view_headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Future-week timesheets cannot be created or edited"


def test_unassigned_and_inactive_projects_are_rejected(
    client: TestClient,
    view_headers: dict[str, str],
    projects: tuple[Project, Project, Project],
):
    inactive = client.put(
        "/api/timesheets/week",
        json=save_payload(str(projects[1].id)),
        headers=view_headers,
    )
    unassigned = client.put(
        "/api/timesheets/week",
        json=save_payload(str(projects[2].id)),
        headers=view_headers,
    )

    assert inactive.status_code == 422
    assert unassigned.status_code == 403


def test_submit_makes_timesheet_read_only_and_admin_can_approve(
    client: TestClient,
    view_headers: dict[str, str],
    admin_headers: dict[str, str],
    projects: tuple[Project, Project, Project],
):
    created = client.put(
        "/api/timesheets/week",
        json=save_payload(str(projects[0].id), entries=[
            {"project_id": str(projects[0].id), "work_date": "2026-07-13", "hours": "7.5"}
        ]),
        headers=view_headers,
    ).json()
    submitted = client.post(f"/api/timesheets/{created['id']}/submit", headers=view_headers)
    edit_response = client.put(
        "/api/timesheets/week",
        json=save_payload(str(projects[0].id)),
        headers=view_headers,
    )
    approved = client.post(f"/api/timesheets/{created['id']}/approve", headers=admin_headers)

    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    assert edit_response.status_code == 409
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


def test_admin_can_reject_and_employee_can_restore_to_draft(
    client: TestClient,
    view_headers: dict[str, str],
    admin_headers: dict[str, str],
    projects: tuple[Project, Project, Project],
):
    created = client.put(
        "/api/timesheets/week",
        json=save_payload(str(projects[0].id)),
        headers=view_headers,
    ).json()
    client.post(f"/api/timesheets/{created['id']}/submit", headers=view_headers)
    rejected = client.post(
        f"/api/timesheets/{created['id']}/reject",
        json={"reason": "Please correct Friday hours."},
        headers=admin_headers,
    )
    restored = client.put(
        "/api/timesheets/week",
        json=save_payload(str(projects[0].id), entries=[
            {"project_id": str(projects[0].id), "work_date": "2026-07-14", "hours": "4"}
        ]),
        headers=view_headers,
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert restored.status_code == 200
    assert restored.json()["status"] == "draft"


def test_admin_summary_counts_statuses_and_hours(
    client: TestClient,
    view_headers: dict[str, str],
    admin_headers: dict[str, str],
    projects: tuple[Project, Project, Project],
):
    created = client.put(
        "/api/timesheets/week",
        json=save_payload(str(projects[0].id), entries=[
            {"project_id": str(projects[0].id), "work_date": "2026-07-13", "hours": "6"}
        ]),
        headers=view_headers,
    ).json()
    client.post(f"/api/timesheets/{created['id']}/submit", headers=view_headers)

    response = client.get(
        "/api/timesheets/summary?week_start=2026-07-13",
        headers=admin_headers,
    )
    forbidden = client.get(
        "/api/timesheets/summary?week_start=2026-07-13",
        headers=view_headers,
    )

    assert response.status_code == 200
    assert response.json()["total_timesheets"] == 1
    assert response.json()["submitted"] == 1
    assert response.json()["total_logged_hours"] == "6.00"
    assert forbidden.status_code == 403
