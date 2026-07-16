from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.auth import Role, User, UserInvitation
from app.models.employee import Employee
from app.services.invitation_service import hash_invitation_token


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


@pytest.fixture()
def admin_headers(db_session: Session):
    role = Role(name="admin")
    user = User(
        first_name="Admin",
        last_name="User",
        email="admin@example.com",
        password_hash=hash_password("Admin@123"),
        is_active=True,
        roles=[role],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def employee_headers(db_session: Session):
    role = Role(name="employee")
    user = User(
        first_name="Employee",
        last_name="User",
        email="employee@example.com",
        password_hash=hash_password("Employee@123"),
        is_active=True,
        roles=[role],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def view_headers(db_session: Session):
    role = Role(name="view")
    user = User(
        first_name="View",
        last_name="User",
        email="view@example.com",
        password_hash=hash_password("View@123"),
        is_active=True,
        roles=[role],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def employee_payload(**overrides):
    payload = {
        "employee_id": "EMP-1001",
        "first_name": "Rahul",
        "last_name": "Sharma",
        "email": "rahul.sharma@teamflow.com",
        "date_of_birth": "1995-06-15",
    }
    payload.update(overrides)
    return payload


def test_admin_can_create_employee(client: TestClient, admin_headers: dict[str, str]):
    response = client.post(
        "/api/employees",
        json=employee_payload(),
        headers=admin_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["employee_id"] == "EMP-1001"
    assert data["email"] == "rahul.sharma@teamflow.com"
    assert "id" in data
    assert data["role"] == "view"
    assert data["account_status"] == "invited"
    assert data["invitation_sent"] is True


def test_admin_can_create_employee_with_admin_role(
    client: TestClient,
    admin_headers: dict[str, str],
):
    response = client.post(
        "/api/employees",
        json=employee_payload(role="admin"),
        headers=admin_headers,
    )

    assert response.status_code == 201
    assert response.json()["role"] == "admin"


def test_employee_create_creates_linked_invited_user(
    client: TestClient,
    db_session: Session,
    admin_headers: dict[str, str],
):
    response = client.post(
        "/api/employees",
        json=employee_payload(email="SHEETAL@EXAMPLE.COM"),
        headers=admin_headers,
    )

    assert response.status_code == 201
    employee = db_session.query(Employee).filter_by(employee_id="EMP-1001").one()
    user = db_session.query(User).filter_by(email="sheetal@example.com").one()
    invitation = db_session.query(UserInvitation).filter_by(user_id=user.id).one()

    assert employee.user_id == user.id
    assert employee.role == "view"
    assert user.role == "view"
    assert user.is_active is False
    assert user.account_status == "invited"
    assert invitation.token_hash
    assert invitation.token_hash not in response.text


def test_invited_user_cannot_login_before_password_setup(
    client: TestClient,
    admin_headers: dict[str, str],
):
    client.post("/api/employees", json=employee_payload(), headers=admin_headers)

    response = client.post(
        "/api/auth/login",
        json={"email": "rahul.sharma@teamflow.com", "password": "Whatever@123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Please set your password using the invitation email before logging in."
    )


def test_invitation_token_can_set_password_and_login(
    client: TestClient,
    db_session: Session,
    admin_headers: dict[str, str],
):
    client.post("/api/employees", json=employee_payload(), headers=admin_headers)
    invitation = db_session.query(UserInvitation).one()
    raw_token = "test-token"
    invitation.token_hash = hash_invitation_token(raw_token)
    db_session.commit()

    validate_response = client.get(f"/api/auth/invitations/validate?token={raw_token}")
    assert validate_response.status_code == 200
    assert validate_response.json()["email"] == "r***@teamflow.com"

    mismatch_response = client.post(
        "/api/auth/invitations/set-password",
        json={
            "token": raw_token,
            "password": "StrongPassword@123",
            "confirm_password": "OtherPassword@123",
        },
    )
    assert mismatch_response.status_code == 422

    weak_response = client.post(
        "/api/auth/invitations/set-password",
        json={
            "token": raw_token,
            "password": "password",
            "confirm_password": "password",
        },
    )
    assert weak_response.status_code == 422

    response = client.post(
        "/api/auth/invitations/set-password",
        json={
            "token": raw_token,
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123",
        },
    )
    assert response.status_code == 200

    db_session.refresh(invitation)
    user = db_session.query(User).filter_by(email="rahul.sharma@teamflow.com").one()
    assert invitation.used_at is not None
    assert user.is_active is True
    assert user.account_status == "active"

    reuse_response = client.get(f"/api/auth/invitations/validate?token={raw_token}")
    assert reuse_response.status_code == 400

    login_response = client.post(
        "/api/auth/login",
        json={"email": "rahul.sharma@teamflow.com", "password": "StrongPassword@123"},
    )
    assert login_response.status_code == 200


def test_admin_can_resend_invitation_and_revoke_previous_token(
    client: TestClient,
    db_session: Session,
    admin_headers: dict[str, str],
    view_headers: dict[str, str],
):
    created = client.post(
        "/api/employees",
        json=employee_payload(),
        headers=admin_headers,
    ).json()
    first_invitation = db_session.query(UserInvitation).one()

    forbidden_response = client.post(
        f"/api/employees/{created['id']}/resend-invitation",
        headers=view_headers,
    )
    assert forbidden_response.status_code == 403

    response = client.post(
        f"/api/employees/{created['id']}/resend-invitation",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["invitation_sent"] is True
    db_session.refresh(first_invitation)
    assert first_invitation.revoked_at is not None
    assert db_session.query(UserInvitation).count() == 2


def test_invalid_role_is_rejected(
    client: TestClient,
    admin_headers: dict[str, str],
):
    response = client.post(
        "/api/employees",
        json=employee_payload(role="owner"),
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_unauthenticated_user_cannot_create_employee(client: TestClient):
    response = client.post("/api/employees", json=employee_payload())

    assert response.status_code == 401


def test_duplicate_employee_id_is_rejected(
    client: TestClient,
    admin_headers: dict[str, str],
):
    client.post("/api/employees", json=employee_payload(), headers=admin_headers)

    response = client.post(
        "/api/employees",
        json=employee_payload(email="another@teamflow.com"),
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Employee ID already exists"


def test_duplicate_email_is_rejected(
    client: TestClient,
    admin_headers: dict[str, str],
):
    client.post("/api/employees", json=employee_payload(), headers=admin_headers)

    response = client.post(
        "/api/employees",
        json=employee_payload(employee_id="EMP-1002"),
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Employee email already exists"


def test_invalid_email_is_rejected(client: TestClient, admin_headers: dict[str, str]):
    response = client.post(
        "/api/employees",
        json=employee_payload(email="not-an-email"),
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_future_date_of_birth_is_rejected(
    client: TestClient,
    admin_headers: dict[str, str],
):
    future_date = date.today() + timedelta(days=1)

    response = client.post(
        "/api/employees",
        json=employee_payload(date_of_birth=future_date.isoformat()),
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_employee_list_returns_created_employees(
    client: TestClient,
    admin_headers: dict[str, str],
):
    client.post("/api/employees", json=employee_payload(), headers=admin_headers)

    response = client.get("/api/employees", headers=admin_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["employee_id"] == "EMP-1001"


def test_view_role_can_list_but_not_create_employees(
    client: TestClient,
    admin_headers: dict[str, str],
    view_headers: dict[str, str],
):
    client.post("/api/employees", json=employee_payload(), headers=admin_headers)

    list_response = client.get("/api/employees", headers=view_headers)
    create_response = client.post(
        "/api/employees",
        json=employee_payload(employee_id="EMP-1002", email="two@teamflow.com"),
        headers=view_headers,
    )

    assert list_response.status_code == 200
    assert create_response.status_code == 403


def test_employee_list_is_sorted_by_newest_first(
    client: TestClient,
    db_session: Session,
    admin_headers: dict[str, str],
):
    older = Employee(
        employee_id="EMP-1001",
        first_name="Older",
        last_name="Employee",
        email="older@teamflow.com",
        date_of_birth=date(1990, 1, 1),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = Employee(
        employee_id="EMP-1002",
        first_name="Newer",
        last_name="Employee",
        email="newer@teamflow.com",
        date_of_birth=date(1991, 1, 1),
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    db_session.add_all([older, newer])
    db_session.commit()

    response = client.get("/api/employees", headers=admin_headers)

    assert response.status_code == 200
    assert [employee["employee_id"] for employee in response.json()] == [
        "EMP-1002",
        "EMP-1001",
    ]


def test_admin_can_update_employee(client: TestClient, admin_headers: dict[str, str]):
    created = client.post(
        "/api/employees",
        json=employee_payload(),
        headers=admin_headers,
    ).json()

    response = client.patch(
        f"/api/employees/{created['id']}",
        json={"first_name": "Rohit", "email": "ROHIT.SHARMA@TEAMFLOW.COM"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Rohit"
    assert response.json()["email"] == "rohit.sharma@teamflow.com"


def test_admin_can_update_employee_role(
    client: TestClient,
    admin_headers: dict[str, str],
):
    created = client.post(
        "/api/employees",
        json=employee_payload(),
        headers=admin_headers,
    ).json()

    response = client.patch(
        f"/api/employees/{created['id']}",
        json={"role": "admin"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_unauthenticated_user_cannot_update_employee(client: TestClient):
    response = client.patch(
        "/api/employees/00000000-0000-0000-0000-000000000000",
        json={"first_name": "Rohit"},
    )

    assert response.status_code == 401


def test_non_admin_cannot_update_employee(
    client: TestClient,
    db_session: Session,
    admin_headers: dict[str, str],
    employee_headers: dict[str, str],
):
    created = client.post(
        "/api/employees",
        json=employee_payload(),
        headers=admin_headers,
    ).json()

    response = client.patch(
        f"/api/employees/{created['id']}",
        json={"first_name": "Rohit"},
        headers=employee_headers,
    )

    assert response.status_code == 403


def test_update_missing_employee_returns_404(
    client: TestClient,
    admin_headers: dict[str, str],
):
    response = client.patch(
        "/api/employees/00000000-0000-0000-0000-000000000000",
        json={"first_name": "Rohit"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_update_duplicate_employee_id_returns_409(
    client: TestClient,
    admin_headers: dict[str, str],
):
    first = client.post(
        "/api/employees",
        json=employee_payload(),
        headers=admin_headers,
    ).json()
    client.post(
        "/api/employees",
        json=employee_payload(employee_id="EMP-1002", email="two@teamflow.com"),
        headers=admin_headers,
    )

    response = client.patch(
        f"/api/employees/{first['id']}",
        json={"employee_id": "EMP-1002"},
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Employee ID already exists"


def test_update_duplicate_email_returns_409(
    client: TestClient,
    admin_headers: dict[str, str],
):
    first = client.post(
        "/api/employees",
        json=employee_payload(),
        headers=admin_headers,
    ).json()
    client.post(
        "/api/employees",
        json=employee_payload(employee_id="EMP-1002", email="two@teamflow.com"),
        headers=admin_headers,
    )

    response = client.patch(
        f"/api/employees/{first['id']}",
        json={"email": "two@teamflow.com"},
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Employee email already exists"


def test_update_can_keep_current_email_and_employee_id(
    client: TestClient,
    admin_headers: dict[str, str],
):
    created = client.post(
        "/api/employees",
        json=employee_payload(),
        headers=admin_headers,
    ).json()

    response = client.patch(
        f"/api/employees/{created['id']}",
        json={
            "employee_id": "EMP-1001",
            "email": "rahul.sharma@teamflow.com",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["employee_id"] == "EMP-1001"
    assert response.json()["email"] == "rahul.sharma@teamflow.com"


def test_update_future_date_of_birth_is_rejected(
    client: TestClient,
    admin_headers: dict[str, str],
):
    created = client.post(
        "/api/employees",
        json=employee_payload(),
        headers=admin_headers,
    ).json()
    future_date = date.today() + timedelta(days=1)

    response = client.patch(
        f"/api/employees/{created['id']}",
        json={"date_of_birth": future_date.isoformat()},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_admin_can_delete_employee(client: TestClient, admin_headers: dict[str, str]):
    created = client.post(
        "/api/employees",
        json=employee_payload(),
        headers=admin_headers,
    ).json()

    response = client.delete(f"/api/employees/{created['id']}", headers=admin_headers)

    assert response.status_code == 204


def test_unauthenticated_user_cannot_delete_employee(client: TestClient):
    response = client.delete("/api/employees/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 401


def test_deleted_employee_no_longer_appears_in_list(
    client: TestClient,
    admin_headers: dict[str, str],
):
    created = client.post(
        "/api/employees",
        json=employee_payload(),
        headers=admin_headers,
    ).json()

    client.delete(f"/api/employees/{created['id']}", headers=admin_headers)
    response = client.get("/api/employees", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_deleting_missing_employee_returns_404(
    client: TestClient,
    admin_headers: dict[str, str],
):
    response = client.delete(
        "/api/employees/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )

    assert response.status_code == 404
