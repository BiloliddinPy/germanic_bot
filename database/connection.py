import sqlite3
from pathlib import Path
from core.config import settings

def get_connection():
    """Returns a new sqlite3 connection to the configured database."""
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn
