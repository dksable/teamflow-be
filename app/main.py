from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.migrations import run_pending_migrations
from app.routers import auth, dashboard, employees, health, holiday_documents, projects, timesheets


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_pending_migrations()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(dashboard.router, prefix="/api/dashboard")
app.include_router(employees.router, prefix="/api/employees")
app.include_router(holiday_documents.router, prefix="/api/holiday-documents")
app.include_router(projects.router, prefix="/api/projects")
app.include_router(timesheets.router, prefix="/api/timesheets")


@app.exception_handler(OperationalError)
def database_operational_error_handler(_request, _exc: OperationalError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database is temporarily unavailable. Please try again.",
        },
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "TeamFlow API"}
