from app.core.logging import Logger


def test_logger_is_singleton() -> None:
    first = Logger()
    second = Logger()

    assert first is second
