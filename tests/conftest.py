from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from adfc_nc.config import Settings
from adfc_nc.nextcloud.users import User


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        admin_user="admin",
        admin_password="secret",
        state_dir=tmp_path / "state",
    )


@pytest.fixture
def user() -> User:
    return User(
        id="jdoe",
        display_name="Jane Doe",
        email="jane@example.org",
        enabled=True,
        last_login=datetime(2026, 10, 1, 12, 0, tzinfo=ZoneInfo("Europe/Berlin")),
        group_ids=("admins",),
        group_names=("Administratoren",),
    )
