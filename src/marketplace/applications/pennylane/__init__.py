from src import secret

def requirements():
    # Postgres Configuration
    PENNYLANE_API_KEY = secret.get('PENNYLANE_API_KEY')
    if PENNYLANE_API_KEY:
        return True
    return False