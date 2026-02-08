"""
Base class for all pipeline stages.

Provides common interface for processing tickets, checking cache,
and saving results with quality metadata.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import time

from cache.cache_manager import CacheManager
from cache.models import GeocodeRecord, QualityTier, ReviewPriority
from core.quality_assessment import QualityAssessor
from core.validation_rules import ValidationEngine
from core.reprocessing_rules import ReprocessingDecider


@dataclass
class StageResult:
    """Result of processing a single ticket through a stage."""
    ticket_number: str
    success: bool
    geocode_record: Optional[GeocodeRecord] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    error: Optional[str] = None
    processing_time_ms: int = 0


@dataclass
class StageStatistics:
    """Statistics for a stage run."""
    stage_name: str
    total_tickets: int = 0
    processed: int = 0
    skipped: int = 0
    succeeded: int = 0
    failed: int = 0
    improved: int = 0  # Quality tier increased
    total_time_ms: int = 0
    
    def add_result(self, result: StageResult) -> None:
        """Add a result to statistics."""
        self.total_tickets += 1
        self.total_time_ms += result.processing_time_ms
        
        if result.skipped:
            self.skipped += 1
        else:
            self.processed += 1
            if result.success:
                self.succeeded += 1
            else:
                self.failed += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stage_name": self.stage_name,
            "total_tickets": self.total_tickets,
            "processed": self.processed,
            "skipped": self.skipped,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "improved": self.improved,
            "avg_time_ms": self.total_time_ms / self.processed if self.processed > 0 else 0,
            "total_time_ms": self.total_time_ms,
        }


class BaseStage(ABC):
    """Abstract base class for pipeline stages."""
    
    def __init__(
        self,
        stage_name: str,
        cache_manager: CacheManager,
        config: Dict[str, Any],
    ):
        """Initialize stage.
        
        Args:
            stage_name: Unique name for this stage
            cache_manager: Cache manager instance
            config: Stage configuration from pipeline config
        """
        self.stage_name = stage_name
        self.cache_manager = cache_manager
        self.config = config
        
        # Initialize helper components
        self.quality_assessor = QualityAssessor()
        self.validation_engine = ValidationEngine()
        self.reprocessing_decider = ReprocessingDecider()
        
        # Statistics
        self.stats = StageStatistics(stage_name=stage_name)
    
    @abstractmethod
    def process_ticket(self, ticket_data: Dict[str, Any]) -> GeocodeRecord:
        """Process a single ticket and return geocode result.
        
        This is the main method that each stage must implement.
        
        Args:
            ticket_data: Dictionary with ticket fields
                Required: ticket_number, street, intersection, city, county
                Optional: ticket_type, duration, work_type, etc.
        
        Returns:
            GeocodeRecord with result (success or failure)
        
        Raises:
            Exception: If processing fails
        """
        pass
    
    def should_skip(self, ticket_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Check if ticket should be skipped based on cache and rules.
        
        Args:
            ticket_data: Ticket data dictionary
            
        Returns:
            Tuple of (should_skip: bool, reason: Optional[str])
        """
        ticket_number = ticket_data.get("ticket_number")
        if not ticket_number:
            return False, "No ticket number"
        
        # Check cache
        cached = self.cache_manager.get_current(ticket_number=ticket_number)
        if cached is None:
            return False, "Not in cache"
        
        # Check reprocessing rules
        should_skip, reason = self.reprocessing_decider.should_skip(
            record=cached,
            stage_name=self.stage_name,
            stage_config=self.config
        )
        
        return should_skip, reason
    
    def run(self, tickets: List[Dict[str, Any]]) -> List[StageResult]:
        """Run stage on list of tickets.
        
        Args:
            tickets: List of ticket data dictionaries
            
        Returns:
            List of StageResult
        """
        results = []
        
        for ticket_data in tickets:
            result = self.run_single(ticket_data)
            results.append(result)
            self.stats.add_result(result)
        
        return results
    
    def run_single(self, ticket_data: Dict[str, Any]) -> StageResult:
        """Run stage on a single ticket.
        
        Args:
            ticket_data: Ticket data dictionary
            
        Returns:
            StageResult
        """
        ticket_number = ticket_data.get("ticket_number", "UNKNOWN")
        start_time = time.time()
        
        # Check if should skip
        should_skip, skip_reason = self.should_skip(ticket_data)
        if should_skip:
            return StageResult(
                ticket_number=ticket_number,
                success=True,
                skipped=True,
                skip_reason=skip_reason,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
        
        # Process ticket
        try:
            geocode_record = self.process_ticket(ticket_data)
            
            # Assess quality
            geocode_record = self._assess_quality(geocode_record, ticket_data)
            
            # Save to cache
            self.cache_manager.set(geocode_record, self.stage_name)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            geocode_record.processing_time_ms = processing_time_ms
            
            return StageResult(
                ticket_number=ticket_number,
                success=True,
                geocode_record=geocode_record,
                skipped=False,
                processing_time_ms=processing_time_ms
            )
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create failed record
            geocode_record = GeocodeRecord(
                ticket_number=ticket_number,
                geocode_key=CacheManager.generate_geocode_key(
                    ticket_data.get("street", ""),
                    ticket_data.get("intersection", ""),
                    ticket_data.get("city", ""),
                    ticket_data.get("county", "")
                ),
                street=ticket_data.get("street"),
                intersection=ticket_data.get("intersection"),
                city=ticket_data.get("city"),
                county=ticket_data.get("county"),
                ticket_type=ticket_data.get("ticket_type"),
                duration=ticket_data.get("duration"),
                work_type=ticket_data.get("work_type"),
                method=self.stage_name,
                quality_tier=QualityTier.FAILED,
                review_priority=ReviewPriority.CRITICAL,
                error_message=str(e),
                processing_time_ms=processing_time_ms
            )
            
            # Save failed record to cache
            self.cache_manager.set(geocode_record, self.stage_name)
            
            return StageResult(
                ticket_number=ticket_number,
                success=False,
                geocode_record=geocode_record,
                error=str(e),
                processing_time_ms=processing_time_ms
            )
    
    def _assess_quality(
        self,
        record: GeocodeRecord,
        ticket_data: Dict[str, Any]
    ) -> GeocodeRecord:
        """Assess quality and add validation flags to record.
        
        Args:
            record: GeocodeRecord to assess
            ticket_data: Original ticket data
            
        Returns:
            Updated GeocodeRecord with quality assessment
        """
        # Calculate quality tier
        record.quality_tier = self.quality_assessor.calculate_quality_tier(
            confidence=record.confidence,
            method=record.method,
            approach=record.approach,
            validation_flags=record.validation_flags,
            ticket_type=record.ticket_type
        )
        
        # Run validation rules
        validation_results = self.validation_engine.validate(
            latitude=record.latitude,
            longitude=record.longitude,
            confidence=record.confidence,
            method=record.method,
            approach=record.approach,
            street=record.street,
            intersection=record.intersection,
            city=record.city,
            county=record.county,
            ticket_type=record.ticket_type
        )
        
        # Extract validation flags
        record.validation_flags = self.validation_engine.get_validation_flags(
            validation_results
        )
        
        # Calculate review priority
        record.review_priority = self.quality_assessor.calculate_review_priority(
            confidence=record.confidence,
            quality_tier=record.quality_tier,
            validation_flags=record.validation_flags,
            ticket_type=record.ticket_type,
            approach=record.approach
        )
        
        return record
    
    def get_statistics(self) -> StageStatistics:
        """Get stage statistics.
        
        Returns:
            StageStatistics
        """
        return self.stats
    
    def reset_statistics(self) -> None:
        """Reset statistics."""
        self.stats = StageStatistics(stage_name=self.stage_name)


if __name__ == "__main__":
    # Example usage (requires concrete implementation)
    print("BaseStage is an abstract class.")
    print("Create a concrete stage by inheriting from BaseStage")
    print("and implementing the process_ticket() method.")
