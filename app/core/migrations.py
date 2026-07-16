from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import Settings, settings


def run_pending_migrations() -> None:
    if not settings.run_migrations_on_startup:
        return
    if settings.database_url == Settings.model_fields["database_url"].default:
        return

    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    alembic_config = Config(str(alembic_ini))
    alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_config, "head")
