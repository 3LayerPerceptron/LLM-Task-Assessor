from backend.src.config import settings


async def test_always_passes() -> None:
    assert True, "if every other test failed, at leat you have me"


async def test_environment() -> None:
    assert settings.ENVIRONMENT == "test", "tests can only been run in testing env"


async def test_logging_configuration() -> None:
    assert settings.LOG_LEVEL == "DEBUG", "log level should be DEBUG in testing env"
    assert len(
        settings.LOG_HANDLERS) >= 1, "there should be at least one log handler configured"


async def test_moodle_configuration(config) -> None:
    assert config.username != "user", "moodle username should not be empty in test config"
    assert config.password != "pass", "moodle password should not be empty in test config"
    assert config.base_url != "moodle.example.com", "moodle base URL should not be empty in test config"
    assert config.service == "moodle_mobile_app", "moodle service should be set to moodle_mobile_app in test config"


async def test_database_uri() -> None:
    assert settings.DATABASE_URI == "sqlite+aiosqlite:///:memory:", "in testing environment, database should be sqlite in-memory"
