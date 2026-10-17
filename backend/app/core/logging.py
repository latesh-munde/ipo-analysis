
import logging
import threading


class Logger:
    """Singleton facade for the application's logging infrastructure."""

    _instance: "Logger | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "Logger":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._configured = False

        return cls._instance

    def configure(self, level: str = "INFO") -> None:
        log_level = getattr(logging, level.upper(), None)

        if not isinstance(log_level, int):
            raise ValueError(f"Invalid logging level: {level}")

        with self._lock:
            if self._configured:
                logging.getLogger().setLevel(log_level)
                return

            logging.basicConfig(
                level=log_level,
                format=(
                    "%(asctime)s | %(levelname)s | "
                    "%(name)s | %(message)s"
                ),
            )

            self._configured = True

    def get_logger(self, name: str) -> logging.Logger:
        return logging.getLogger(name)


logger = Logger()
