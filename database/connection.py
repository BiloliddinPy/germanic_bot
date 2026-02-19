import sqlite3
from core.config import settings

def get_connection():
    """Returns a new sqlite3 connection to the configured database."""
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn
