"""
Cache manager for geocoding results with versioning support.
"""

import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from cache.models import GeocodeRecord, CacheQuery, QualityTier, ReviewPriority
from cache.migrations import apply_schema


class CacheManager:
    """Manages persistent cache of geocoding results."""
    
    def __init__(self, db_path: Path):
        """Initialize cache manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        # Create parent directory
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Apply schema
        apply_schema(self.db_path)
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            isolation_level="DEFERRED"
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_current(
        self, 
        ticket_number: Optional[str] = None,
        geocode_key: Optional[str] = None
    ) -> Optional[GeocodeRecord]:
        """Get current (latest) geocode for a ticket.
        
        Args:
            ticket_number: Ticket identifier
            geocode_key: Geocode key (hash of location fields)
            
        Returns:
            GeocodeRecord if found, None otherwise
        """
        if not ticket_number and not geocode_key:
            raise ValueError("Must provide ticket_number or geocode_key")
        
        with self._get_connection() as conn:
            if ticket_number:
                row = conn.execute(
                    """SELECT * FROM geocode_cache 
                       WHERE ticket_number = ? AND is_current = 1""",
                    (ticket_number,)
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT * FROM geocode_cache 
                       WHERE geocode_key = ? AND is_current = 1""",
                    (geocode_key,)
                ).fetchone()
            
            return GeocodeRecord.from_db_row(row) if row else None
    
    def set(
        self,
        record: GeocodeRecord,
        stage_name: str
    ) -> int:
        """Save geocode result, creating new version if changed.
        
        Args:
            record: GeocodeRecord to save
            stage_name: Name of stage creating this record
            
        Returns:
            cache_id of saved record
        """
        # Check if there's a current version
        current = self.get_current(ticket_number=record.ticket_number)
        
        with self._get_connection() as conn:
            if current:
                # Mark old version as not current
                conn.execute(
                    "UPDATE geocode_cache SET is_current = 0 WHERE cache_id = ?",
                    (current.cache_id,)
                )
                new_version = current.version + 1
                supersedes_id = current.cache_id
            else:
                new_version = 1
                supersedes_id = None
            
            # Insert new version
            cursor = conn.execute(
                """INSERT INTO geocode_cache (
                    ticket_number, geocode_key,
                    street, intersection, city, county,
                    ticket_type, duration, work_type, excavator,
                    latitude, longitude, method, approach,
                    confidence, reasoning, error_message,
                    quality_tier, review_priority, validation_flags,
                    version, supersedes_cache_id, is_current,
                    created_by_stage, locked, lock_reason,
                    metadata_json, processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.ticket_number,
                    record.geocode_key,
                    record.street,
                    record.intersection,
                    record.city,
                    record.county,
                    record.ticket_type,
                    record.duration,
                    record.work_type,
                    record.excavator,
                    record.latitude,
                    record.longitude,
                    record.method,
                    record.approach,
                    record.confidence,
                    record.reasoning,
                    record.error_message,
                    record.quality_tier.value if isinstance(record.quality_tier, QualityTier) else record.quality_tier,
                    record.review_priority.value if isinstance(record.review_priority, ReviewPriority) else record.review_priority,
                    json.dumps(record.validation_flags) if record.validation_flags else None,
                    new_version,
                    supersedes_id,
                    1,  # is_current
                    stage_name,
                    record.locked,
                    record.lock_reason,
                    json.dumps(record.metadata) if record.metadata else None,
                    record.processing_time_ms,
                )
            )
            return cursor.lastrowid
    
    def get_version_history(
        self, 
        ticket_number: str
    ) -> List[GeocodeRecord]:
        """Get all versions of geocode for a ticket.
        
        Args:
            ticket_number: Ticket identifier
            
        Returns:
            List of GeocodeRecord ordered by version (newest first)
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM geocode_cache 
                   WHERE ticket_number = ? 
                   ORDER BY version DESC""",
                (ticket_number,)
            ).fetchall()
            
            return [GeocodeRecord.from_db_row(row) for row in rows]
    
    def lock(
        self,
        ticket_number: str,
        reason: str,
        locked_by: str = "human_review"
    ) -> None:
        """Lock a geocode to prevent reprocessing.
        
        Args:
            ticket_number: Ticket to lock
            reason: Why this is locked
            locked_by: Who locked it
        """
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE geocode_cache 
                   SET locked = 1, 
                       lock_reason = ?,
                       locked_at = CURRENT_TIMESTAMP,
                       locked_by = ?
                   WHERE ticket_number = ? AND is_current = 1""",
                (reason, locked_by, ticket_number)
            )
    
    def unlock(self, ticket_number: str) -> None:
        """Unlock a geocode to allow reprocessing.
        
        Args:
            ticket_number: Ticket to unlock
        """
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE geocode_cache 
                   SET locked = 0,
                       lock_reason = NULL,
                       locked_at = NULL,
                       locked_by = NULL
                   WHERE ticket_number = ? AND is_current = 1""",
                (ticket_number,)
            )
    
    def query(self, query: CacheQuery) -> List[GeocodeRecord]:
        """Query cache with filters.
        
        Args:
            query: CacheQuery with filter criteria
            
        Returns:
            List of matching GeocodeRecord
        """
        conditions = ["is_current = 1"]
        params = []
        
        if query.quality_tiers:
            placeholders = ",".join("?" * len(query.quality_tiers))
            conditions.append(f"quality_tier IN ({placeholders})")
            params.extend([t.value if isinstance(t, QualityTier) else t for t in query.quality_tiers])
        
        if query.review_priorities:
            placeholders = ",".join("?" * len(query.review_priorities))
            conditions.append(f"review_priority IN ({placeholders})")
            params.extend([p.value if isinstance(p, ReviewPriority) else p for p in query.review_priorities])
        
        if query.min_confidence is not None:
            conditions.append("confidence >= ?")
            params.append(query.min_confidence)
        
        if query.max_confidence is not None:
            conditions.append("confidence <= ?")
            params.append(query.max_confidence)
        
        if query.locked is not None:
            conditions.append("locked = ?")
            params.append(1 if query.locked else 0)
        
        where_clause = " AND ".join(conditions)
        sql = f"SELECT * FROM geocode_cache WHERE {where_clause}"
        
        if query.limit:
            sql += f" LIMIT {query.limit}"
        
        with self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [GeocodeRecord.from_db_row(row) for row in rows]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dict with statistics
        """
        with self._get_connection() as conn:
            stats = {}
            
            # Total records
            stats["total_records"] = conn.execute(
                "SELECT COUNT(*) FROM geocode_cache WHERE is_current = 1"
            ).fetchone()[0]
            
            # Quality tier breakdown
            tier_counts = conn.execute(
                """SELECT quality_tier, COUNT(*) as count 
                   FROM geocode_cache 
                   WHERE is_current = 1 
                   GROUP BY quality_tier"""
            ).fetchall()
            stats["quality_tiers"] = {row[0]: row[1] for row in tier_counts}
            
            # Average confidence by tier
            avg_conf = conn.execute(
                """SELECT quality_tier, AVG(confidence) as avg_conf
                   FROM geocode_cache 
                   WHERE is_current = 1 AND confidence IS NOT NULL
                   GROUP BY quality_tier"""
            ).fetchall()
            stats["avg_confidence_by_tier"] = {row[0]: row[1] for row in avg_conf}
            
            # Locked count
            stats["locked_count"] = conn.execute(
                "SELECT COUNT(*) FROM geocode_cache WHERE is_current = 1 AND locked = 1"
            ).fetchone()[0]
            
            # Total versions
            stats["total_versions"] = conn.execute(
                "SELECT COUNT(*) FROM geocode_cache"
            ).fetchone()[0]
            
            return stats
    
    @staticmethod
    def generate_geocode_key(
        street: str,
        intersection: str,
        city: str,
        county: str
    ) -> str:
        """Generate deterministic key for geocode lookup.
        
        Args:
            street: Street name
            intersection: Intersection name
            city: City name
            county: County name
            
        Returns:
            SHA256 hash of normalized location
        """
        # Normalize to uppercase and concatenate
        key_string = f"{street}|{intersection}|{city}|{county}".upper()
        return hashlib.sha256(key_string.encode()).hexdigest()


if __name__ == "__main__":
    # Test script
    from pathlib import Path
    
    # Create test cache
    cache = CacheManager(Path("outputs/test_cache.db"))
    
    # Create test record
    test_record = GeocodeRecord(
        ticket_number="TEST123",
        geocode_key=CacheManager.generate_geocode_key(
            "CR 426", "CR 432", "Pyote", "Ward"
        ),
        street="CR 426",
        intersection="CR 432",
        city="Pyote",
        county="Ward",
        latitude=31.5401,
        longitude=-103.1293,
        method="PROXIMITY_BASED",
        approach="closest_point",
        confidence=0.85,
        reasoning="Test geocode",
        quality_tier=QualityTier.GOOD,
    )
    
    # Save record
    cache_id = cache.set(test_record, "test_stage")
    print(f"✓ Created record with cache_id: {cache_id}")
    
    # Retrieve record
    retrieved = cache.get_current(ticket_number="TEST123")
    print(f"✓ Retrieved record: {retrieved.ticket_number} @ {retrieved.latitude}, {retrieved.longitude}")
    
    # Get statistics
    stats = cache.get_statistics()
    print(f"✓ Cache statistics: {stats}")
    
    # Clean up
    Path("outputs/test_cache.db").unlink()
    print(f"✓ Test complete")
