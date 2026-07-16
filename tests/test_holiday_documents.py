from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.auth import Role, User


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "holiday_upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "max_holiday_file_size_mb", 10)
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


def create_user_headers(db_session: Session, role_name: str) -> dict[str, str]:
    role = Role(name=role_name)
    user = User(
        first_name=role_name.title(),
        last_name="User",
        email=f"{role_name}@example.com",
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
    return create_user_headers(db_session, "admin")


@pytest.fixture()
def view_headers(db_session: Session):
    return create_user_headers(db_session, "view")


def upload_document(
    client: TestClient,
    headers: dict[str, str],
    filename: str,
    content: bytes,
    content_type: str,
):
    return client.post(
        "/api/holiday-documents",
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


def test_admin_can_upload_pdf(client: TestClient, admin_headers: dict[str, str]):
    response = upload_document(
        client,
        admin_headers,
        "holidays.pdf",
        b"%PDF-1.4\n%%EOF",
        "application/pdf",
    )

    assert response.status_code == 201
    assert response.json()["original_file_name"] == "holidays.pdf"


def test_admin_can_upload_docx(client: TestClient, admin_headers: dict[str, str]):
    response = upload_document(
        client,
        admin_headers,
        "holidays.docx",
        b"PK\x03\x04docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert response.status_code == 201
    assert response.json()["file_extension"] == "docx"


def test_admin_can_upload_xlsx(client: TestClient, admin_headers: dict[str, str]):
    response = upload_document(
        client,
        admin_headers,
        "holidays.xlsx",
        b"PK\x03\x04xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    assert response.status_code == 201
    assert response.json()["file_extension"] == "xlsx"


def test_admin_can_upload_image(client: TestClient, admin_headers: dict[str, str]):
    response = upload_document(
        client,
        admin_headers,
        "holidays.png",
        b"\x89PNG\r\n\x1a\nimage",
        "image/png",
    )

    assert response.status_code == 201
    assert response.json()["mime_type"] == "image/png"


def test_unsupported_file_is_rejected(client: TestClient, admin_headers: dict[str, str]):
    response = upload_document(
        client,
        admin_headers,
        "script.exe",
        b"MZ",
        "application/octet-stream",
    )

    assert response.status_code == 400


def test_file_over_10mb_is_rejected(client: TestClient, admin_headers: dict[str, str]):
    response = upload_document(
        client,
        admin_headers,
        "holidays.csv",
        b"a" * (10 * 1024 * 1024 + 1),
        "text/csv",
    )

    assert response.status_code == 413


def test_empty_file_is_rejected(client: TestClient, admin_headers: dict[str, str]):
    response = upload_document(
        client,
        admin_headers,
        "holidays.csv",
        b"",
        "text/csv",
    )

    assert response.status_code == 400


def test_view_role_cannot_upload(client: TestClient, view_headers: dict[str, str]):
    response = upload_document(
        client,
        view_headers,
        "holidays.csv",
        b"holiday,date",
        "text/csv",
    )

    assert response.status_code == 403


def test_authenticated_user_can_get_latest_document(
    client: TestClient,
    admin_headers: dict[str, str],
    view_headers: dict[str, str],
):
    upload_document(client, admin_headers, "holidays.csv", b"holiday,date", "text/csv")

    response = client.get("/api/holiday-documents/latest", headers=view_headers)

    assert response.status_code == 200
    assert response.json()["original_file_name"] == "holidays.csv"


def test_collection_list_endpoint_is_not_available(
    client: TestClient,
    view_headers: dict[str, str],
):
    response = client.get("/api/holiday-documents", headers=view_headers)

    assert response.status_code == 405


def test_pdf_view_endpoint_returns_inline_disposition(
    client: TestClient,
    admin_headers: dict[str, str],
):
    document = upload_document(
        client,
        admin_headers,
        "holidays.pdf",
        b"%PDF-1.4\n%%EOF",
        "application/pdf",
    ).json()

    response = client.get(
        f"/api/holiday-documents/{document['id']}/view",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert "inline" in response.headers["content-disposition"]


def test_download_endpoint_returns_attachment_disposition(
    client: TestClient,
    admin_headers: dict[str, str],
):
    document = upload_document(
        client,
        admin_headers,
        "holidays.pdf",
        b"%PDF-1.4\n%%EOF",
        "application/pdf",
    ).json()

    response = client.get(
        f"/api/holiday-documents/{document['id']}/download",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]


def test_original_filename_is_preserved_during_download(
    client: TestClient,
    admin_headers: dict[str, str],
):
    document = upload_document(
        client,
        admin_headers,
        "Company Holidays 2026.pdf",
        b"%PDF-1.4\n%%EOF",
        "application/pdf",
    ).json()

    response = client.get(
        f"/api/holiday-documents/{document['id']}/download",
        headers=admin_headers,
    )

    assert "Company%20Holidays%202026.pdf" in response.headers["content-disposition"]


def test_missing_document_returns_404(client: TestClient, admin_headers: dict[str, str]):
    response = client.get(
        "/api/holiday-documents/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_path_traversal_filename_is_sanitized(
    client: TestClient,
    admin_headers: dict[str, str],
):
    response = upload_document(
        client,
        admin_headers,
        "../../holidays.pdf",
        b"%PDF-1.4\n%%EOF",
        "application/pdf",
    )

    assert response.status_code == 201
    assert response.json()["original_file_name"] == "holidays.pdf"
