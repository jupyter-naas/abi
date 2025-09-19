from src import secret

def requirements():
    # Postgres Configuration
    POSTGRES_USER = secret.get('POSTGRES_USER')
    POSTGRES_PASSWORD = secret.get('POSTGRES_PASSWORD')
    POSTGRES_DBNAME = secret.get('POSTGRES_DBNAME')
    POSTGRES_HOST = secret.get('POSTGRES_HOST')
    POSTGRES_PORT = secret.get('POSTGRES_PORT')
    if POSTGRES_USER and POSTGRES_PASSWORD and POSTGRES_DBNAME and POSTGRES_HOST and POSTGRES_PORT:
        return True
    return False