from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def use_local_email_provider():
    from app.core.config import settings

    previous_provider = settings.email_provider
    previous_api_key = settings.resend_api_key
    settings.email_provider = "local"
    settings.resend_api_key = None
    try:
        yield
    finally:
        settings.email_provider = previous_provider
        settings.resend_api_key = previous_api_key
