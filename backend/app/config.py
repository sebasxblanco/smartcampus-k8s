import os


def database_url() -> str:
    """URL de la base de datos, leída siempre de variables de entorno.

    DATABASE_URL tiene prioridad (los tests la usan para apuntar a SQLite).
    Si no está, se construye la de PostgreSQL con las variables DB_*.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("DB_USER", "smartcampus")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "smartcampus")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


APP_ENV = os.getenv("APP_ENV", "development")
