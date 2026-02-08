"""
Pydantic models for cache records.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class QualityTier(str, Enum):
    """Quality tier enumeration."""
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    REVIEW_NEEDED = "REVIEW_NEEDED"
    FAILED = "FAILED"


class ReviewPriority(str, Enum):
    """Review priority enumeration."""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GeocodeRecord(BaseModel):
    """Represents a geocoded ticket in the cache."""
    
    # Identification
    cache_id: Optional[int] = None
    ticket_number: str
    geocode_key: str
    
    # Input data
    street: Optional[str] = None
    intersection: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    ticket_type: Optional[str] = None
    duration: Optional[str] = None
    work_type: Optional[str] = None
    excavator: Optional[str] = None
    
    # Geocoding result
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    method: str
    approach: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)
    reasoning: Optional[str] = None
    error_message: Optional[str] = None
    
    # Quality metadata
    quality_tier: QualityTier
    review_priority: ReviewPriority = ReviewPriority.NONE
    validation_flags: List[str] = Field(default_factory=list)
    
    # Version tracking
    version: int = 1
    supersedes_cache_id: Optional[int] = None
    is_current: bool = True
    created_at: Optional[datetime] = None
    created_by_stage: Optional[str] = None
    
    # Reprocessing control
    locked: bool = False
    lock_reason: Optional[str] = None
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    
    # Extended metadata
    metadata: Optional[Dict[str, Any]] = None
    processing_time_ms: Optional[int] = None
    
    class Config:
        """Pydantic config."""
        use_enum_values = True
    
    @classmethod
    def from_db_row(cls, row: Any) -> "GeocodeRecord":
        """Create GeocodeRecord from database row.
        
        Args:
            row: sqlite3.Row object
            
        Returns:
            GeocodeRecord instance
        """
        import json
        
        return cls(
            cache_id=row["cache_id"],
            ticket_number=row["ticket_number"],
            geocode_key=row["geocode_key"],
            street=row["street"],
            intersection=row["intersection"],
            city=row["city"],
            county=row["county"],
            ticket_type=row["ticket_type"],
            duration=row["duration"],
            work_type=row["work_type"],
            excavator=row["excavator"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            method=row["method"],
            approach=row["approach"],
            confidence=row["confidence"],
            reasoning=row["reasoning"],
            error_message=row["error_message"],
            quality_tier=QualityTier(row["quality_tier"]),
            review_priority=ReviewPriority(row["review_priority"]) if row["review_priority"] else ReviewPriority.NONE,
            validation_flags=json.loads(row["validation_flags"]) if row["validation_flags"] else [],
            version=row["version"],
            supersedes_cache_id=row["supersedes_cache_id"],
            is_current=bool(row["is_current"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            created_by_stage=row["created_by_stage"],
            locked=bool(row["locked"]),
            lock_reason=row["lock_reason"],
            locked_at=datetime.fromisoformat(row["locked_at"]) if row["locked_at"] else None,
            locked_by=row["locked_by"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else None,
            processing_time_ms=row["processing_time_ms"],
        )


class CacheQuery(BaseModel):
    """Query parameters for cache lookups."""
    
    quality_tiers: Optional[List[QualityTier]] = None
    review_priorities: Optional[List[ReviewPriority]] = None
    min_confidence: Optional[float] = Field(None, ge=0, le=1)
    max_confidence: Optional[float] = Field(None, ge=0, le=1)
    locked: Optional[bool] = None
    limit: Optional[int] = None
    
    class Config:
        """Pydantic config."""
        use_enum_values = True
