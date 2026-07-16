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
from app.models.project import ProjectAssignee

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


def create_user_headers(db_session: Session, role_name: str, email: str) -> dict[str, str]:
    role = db_session.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        role = Role(name=role_name)
        db_session.add(role)
        db_session.flush()
    user = User(
        first_name=role_name.title(),
        last_name="User",
        email=email,
        password_hash=hash_password("Password@123"),
        is_active=True,
        roles=[role],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.fixture()
def admin_headers(db_session: Session):
    return create_user_headers(db_session, "admin", "admin@example.com")


@pytest.fixture()
def employees(db_session: Session):
    first = Employee(
        employee_id="EMP-1001",
        first_name="Rahul",
        last_name="Sharma",
        email="rahul@example.com",
        date_of_birth=date(1995, 1, 1),
        role="view",
    )
    second = Employee(
        employee_id="EMP-1002",
        first_name="Priya",
        last_name="Patel",
        email="priya@example.com",
        date_of_birth=date(1996, 1, 1),
        role="view",
    )
    third = Employee(
        employee_id="EMP-1003",
        first_name="Aman",
        last_name="Singh",
        email="aman@example.com",
        date_of_birth=date(1997, 1, 1),
        role="view",
    )
    db_session.add_all([first, second, third])
    db_session.commit()
    for employee in [first, second, third]:
        db_session.refresh(employee)
    return [first, second, third]


@pytest.fixture()
def rahul_headers(db_session: Session):
    return create_user_headers(db_session, "view", "rahul@example.com")


@pytest.fixture()
def priya_headers(db_session: Session):
    return create_user_headers(db_session, "view", "priya@example.com")


def project_payload(employee_ids: list[str], **overrides):
    payload = {
        "project_code": "tf-001",
        "project_name": "TeamFlow",
        "project_status": "active",
        "assignee_ids": employee_ids,
        "start_date": "2026-07-15",
        "end_date": "2026-12-31",
    }
    payload.update(overrides)
    return payload


def test_admin_can_create_project_with_multiple_assignees(
    client: TestClient,
    admin_headers: dict[str, str],
    employees: list[Employee],
):
    response = client.post(
        "/api/projects",
        json=project_payload([str(employees[0].id), str(employees[1].id)]),
        headers=admin_headers,
    )

    assert response.status_code == 201
    assert response.json()["project_code"] == "TF-001"
    assert response.json()["project_status"] == "active"
    assert len(response.json()["assignees"]) == 2


def test_duplicate_project_code_is_rejected(
    client: TestClient,
    admin_headers: dict[str, str],
    employees: list[Employee],
):
    client.post(
        "/api/projects",
        json=project_payload([str(employees[0].id)]),
        headers=admin_headers,
    )
    response = client.post(
        "/api/projects",
        json=project_payload([str(employees[1].id)], project_name="Other"),
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_invalid_status_and_date_are_rejected(
    client: TestClient,
    admin_headers: dict[str, str],
    employees: list[Employee],
):
    bad_status = client.post(
        "/api/projects",
        json=project_payload([str(employees[0].id)], project_status="planning"),
        headers=admin_headers,
    )
    bad_date = client.post(
        "/api/projects",
        json=project_payload(
            [str(employees[0].id)],
            start_date="2026-12-31",
            end_date="2026-07-15",
        ),
        headers=admin_headers,
    )

    assert bad_status.status_code == 422
    assert bad_date.status_code == 422


def test_invalid_employee_id_is_rejected(
    client: TestClient,
    admin_headers: dict[str, str],
):
    response = client.post(
        "/api/projects",
        json=project_payload(["00000000-0000-0000-0000-000000000000"]),
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_duplicate_assignee_ids_are_deduped(
    client: TestClient,
    admin_headers: dict[str, str],
    employees: list[Employee],
):
    response = client.post(
        "/api/projects",
        json=project_payload([str(employees[0].id), str(employees[0].id)]),
        headers=admin_headers,
    )

    assert response.status_code == 201
    assert len(response.json()["assignees"]) == 1


def test_view_user_sees_only_assigned_projects(
    client: TestClient,
    admin_headers: dict[str, str],
    employees: list[Employee],
    rahul_headers: dict[str, str],
):
    assigned = client.post(
        "/api/projects",
        json=project_payload([str(employees[0].id)], project_code="TF-001"),
        headers=admin_headers,
    ).json()
    other = client.post(
        "/api/projects",
        json=project_payload([str(employees[1].id)], project_code="TF-002"),
        headers=admin_headers,
    ).json()

    list_response = client.get("/api/projects", headers=rahul_headers)
    assigned_response = client.get(f"/api/projects/{assigned['id']}", headers=rahul_headers)
    other_response = client.get(f"/api/projects/{other['id']}", headers=rahul_headers)

    assert [project["project_code"] for project in list_response.json()] == ["TF-001"]
    assert assigned_response.status_code == 200
    assert other_response.status_code == 403


def test_view_user_cannot_mutate_projects(
    client: TestClient,
    employees: list[Employee],
    rahul_headers: dict[str, str],
):
    response = client.post(
        "/api/projects",
        json=project_payload([str(employees[0].id)]),
        headers=rahul_headers,
    )

    assert response.status_code == 403


def test_admin_can_update_status_and_assignees(
    client: TestClient,
    admin_headers: dict[str, str],
    employees: list[Employee],
    rahul_headers: dict[str, str],
    priya_headers: dict[str, str],
):
    created = client.post(
        "/api/projects",
        json=project_payload([str(employees[0].id)]),
        headers=admin_headers,
    ).json()

    response = client.patch(
        f"/api/projects/{created['id']}",
        json={
            "project_status": "completed",
            "assignee_ids": [str(employees[1].id)],
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["project_status"] == "completed"
    assert [assignee["employee_id"] for assignee in response.json()["assignees"]] == [
        "EMP-1002"
    ]
    assert client.get(f"/api/projects/{created['id']}", headers=rahul_headers).status_code == 403
    assert client.get(f"/api/projects/{created['id']}", headers=priya_headers).status_code == 200


def test_deleting_project_removes_assignments(
    client: TestClient,
    db_session: Session,
    admin_headers: dict[str, str],
    employees: list[Employee],
):
    created = client.post(
        "/api/projects",
        json=project_payload([str(employees[0].id)]),
        headers=admin_headers,
    ).json()

    response = client.delete(f"/api/projects/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert list(db_session.scalars(select(ProjectAssignee)).all()) == []
