"""
Database migration system for cache schema.
"""

import sqlite3
from pathlib import Path
from typing import Optional


def get_current_version(conn: sqlite3.Connection) -> int:
    """Get current schema version.
    
    Args:
        conn: Database connection
        
    Returns:
        Current schema version, or 0 if no version table exists
    """
    try:
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()
        return result[0] if result[0] is not None else 0
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return 0


def apply_schema(db_path: Path) -> None:
    """Apply schema to database.
    
    Creates tables if they don't exist. Safe to run multiple times.
    
    Args:
        db_path: Path to SQLite database file
    """
    schema_path = Path(__file__).parent / "schema.sql"
    
    with open(schema_path) as f:
        schema_sql = f.read()
    
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def init_database(db_path: Path) -> None:
    """Initialize new database with schema.
    
    Args:
        db_path: Path to SQLite database file to create
    """
    # Create parent directory if needed
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Apply schema
    apply_schema(db_path)
    
    print(f"✓ Database initialized: {db_path}")


if __name__ == "__main__":
    # Test script
    import sys
    
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    else:
        db_path = Path("outputs/geocode_cache.db")
    
    init_database(db_path)
    
    # Verify schema
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"\n✓ Tables created: {', '.join(tables)}")
    print(f"✓ Schema version: {get_current_version(sqlite3.connect(db_path))}")
