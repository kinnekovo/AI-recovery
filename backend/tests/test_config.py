import os
import unittest

from app.core.config import get_settings


class SettingsTest(unittest.TestCase):
    def tearDown(self) -> None:
        for key in ("DATABASE_URL", "DATABASE_CONNECT_TIMEOUT_SECONDS", "PRONUNCIATION_SHADOW_MODE"):
            os.environ.pop(key, None)
        get_settings.cache_clear()

    def test_postgres_database_url_adds_connect_timeout(self) -> None:
        os.environ["DATABASE_URL"] = "postgresql+psycopg://user:pass@localhost:5432/app"
        os.environ["DATABASE_CONNECT_TIMEOUT_SECONDS"] = "7"
        get_settings.cache_clear()

        self.assertEqual(
            get_settings().effective_database_url,
            "postgresql+psycopg://user:pass@localhost:5432/app?connect_timeout=7",
        )

    def test_existing_database_connect_timeout_is_preserved(self) -> None:
        os.environ["DATABASE_URL"] = "postgresql+psycopg://user:pass@localhost:5432/app?connect_timeout=3"
        get_settings.cache_clear()

        self.assertEqual(
            get_settings().effective_database_url,
            "postgresql+psycopg://user:pass@localhost:5432/app?connect_timeout=3",
        )

    def test_pronunciation_shadow_mode_can_be_disabled(self) -> None:
        os.environ["PRONUNCIATION_SHADOW_MODE"] = "false"
        get_settings.cache_clear()

        self.assertFalse(get_settings().pronunciation_shadow_mode)


if __name__ == "__main__":
    unittest.main()
