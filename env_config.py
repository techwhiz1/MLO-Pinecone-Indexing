import os

from dotenv import load_dotenv


load_dotenv()


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Add it to .env or export it before running."
        )
    return value


def postgres_config(prefix: str) -> dict:
    return {
        "dbname": required_env(f"{prefix}_DB_NAME"),
        "user": required_env(f"{prefix}_DB_USER"),
        "password": required_env(f"{prefix}_DB_PASSWORD"),
        "host": required_env(f"{prefix}_DB_HOST"),
        "port": int(required_env(f"{prefix}_DB_PORT")),
    }
