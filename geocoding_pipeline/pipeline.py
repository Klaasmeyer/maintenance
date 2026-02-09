"""
Pipeline orchestrator for running geocoding stages in sequence.

The Pipeline loads configuration, initializes the cache, and runs each stage
on input tickets in order, tracking statistics and handling errors.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import time
import json
from datetime import datetime

from cache.cache_manager import CacheManager
from cache.models import GeocodeRecord, QualityTier
from stages.base_stage import BaseStage, StageResult, StageStatistics


@dataclass
class PipelineResult:
    """Result of running the entire pipeline."""
    pipeline_id: str
    total_tickets: int
    total_succeeded: int
    total_failed: int
    total_skipped: int
    total_time_ms: int
    stage_statistics: List[StageStatistics] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pipeline_id": self.pipeline_id,
            "total_tickets": self.total_tickets,
            "total_succeeded": self.total_succeeded,
            "total_failed": self.total_failed,
            "total_skipped": self.total_skipped,
            "total_time_ms": self.total_time_ms,
            "avg_time_ms": self.total_time_ms / self.total_tickets if self.total_tickets > 0 else 0,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "stages": [stage.to_dict() for stage in self.stage_statistics],
        }


class Pipeline:
    """Orchestrates geocoding pipeline stages."""

    def __init__(
        self,
        cache_manager: CacheManager,
        config: Dict[str, Any],
    ):
        """Initialize pipeline.

        Args:
            cache_manager: Cache manager instance
            config: Pipeline configuration dictionary
        """
        self.cache_manager = cache_manager
        self.config = config
        self.stages: List[BaseStage] = []

        # Pipeline configuration
        self.pipeline_name = config.get("name", "geocoding_pipeline")
        self.fail_fast = config.get("fail_fast", False)
        self.save_intermediate = config.get("save_intermediate", True)

    def add_stage(self, stage: BaseStage) -> None:
        """Add a stage to the pipeline.

        Args:
            stage: Stage instance to add
        """
        self.stages.append(stage)

    def run(
        self,
        tickets: List[Dict[str, Any]],
        pipeline_id: Optional[str] = None
    ) -> PipelineResult:
        """Run all stages on tickets in sequence.

        Args:
            tickets: List of ticket data dictionaries
            pipeline_id: Optional pipeline run ID (generated if not provided)

        Returns:
            PipelineResult with overall statistics
        """
        # Generate pipeline ID if not provided
        if pipeline_id is None:
            pipeline_id = f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        start_time = time.time()
        start_time_str = datetime.now().isoformat()

        print(f"\n{'='*80}")
        print(f"Starting Pipeline: {self.pipeline_name}")
        print(f"Pipeline ID: {pipeline_id}")
        print(f"Tickets: {len(tickets)}")
        print(f"Stages: {len(self.stages)}")
        print(f"{'='*80}\n")

        # Record pipeline run in database (optional)
        try:
            self._record_pipeline_run(
                pipeline_id=pipeline_id,
                config=self.config,
                ticket_count=len(tickets)
            )
        except Exception as e:
            print(f"⚠️  Warning: Could not record pipeline run to database: {e}")
            print(f"   Continuing with pipeline execution...")

        # Run each stage
        stage_statistics = []
        for stage in self.stages:
            print(f"Running stage: {stage.stage_name}")
            print(f"-" * 80)

            # Reset stage statistics
            stage.reset_statistics()

            # Run stage on all tickets
            stage_start = time.time()
            stage_results = stage.run(tickets)
            stage_time_ms = int((time.time() - stage_start) * 1000)

            # Get statistics
            stats = stage.get_statistics()
            stage_statistics.append(stats)

            # Print stage summary
            print(f"  Processed: {stats.processed}/{stats.total_tickets}")
            print(f"  Succeeded: {stats.succeeded}")
            print(f"  Skipped: {stats.skipped}")
            print(f"  Failed: {stats.failed}")
            print(f"  Time: {stage_time_ms}ms ({stats.to_dict()['avg_time_ms']:.1f}ms avg)")
            print()

            # Check fail_fast
            if self.fail_fast and stats.failed > 0:
                print(f"⚠️  Stopping pipeline: fail_fast=True and {stats.failed} tickets failed")
                break

        # Calculate overall statistics
        total_time_ms = int((time.time() - start_time) * 1000)
        end_time_str = datetime.now().isoformat()

        # Count unique tickets (some may be processed by multiple stages)
        unique_tickets = set(ticket["ticket_number"] for ticket in tickets)

        # Get final results from cache
        final_results = self._get_final_results(list(unique_tickets))

        result = PipelineResult(
            pipeline_id=pipeline_id,
            total_tickets=len(unique_tickets),
            total_succeeded=len([r for r in final_results if r.quality_tier != QualityTier.FAILED]),
            total_failed=len([r for r in final_results if r.quality_tier == QualityTier.FAILED]),
            total_skipped=sum(s.skipped for s in stage_statistics),
            total_time_ms=total_time_ms,
            stage_statistics=stage_statistics,
            start_time=start_time_str,
            end_time=end_time_str,
        )

        # Print final summary
        self._print_summary(result)

        # Update pipeline run status (optional)
        try:
            self._update_pipeline_run(
                pipeline_id=pipeline_id,
                status="completed",
                results=result.to_dict()
            )
        except Exception as e:
            print(f"⚠️  Warning: Could not update pipeline run status: {e}")

        return result

    def _record_pipeline_run(
        self,
        pipeline_id: str,
        config: Dict[str, Any],
        ticket_count: int
    ) -> None:
        """Record pipeline run start in database.

        Args:
            pipeline_id: Pipeline run ID
            config: Pipeline configuration
            ticket_count: Number of tickets to process
        """
        with self.cache_manager._get_connection() as conn:
            conn.execute("""
                INSERT INTO pipeline_history (
                    pipeline_id,
                    start_time,
                    status,
                    config,
                    ticket_count
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                pipeline_id,
                datetime.now().isoformat(),
                "running",
                json.dumps(config),
                ticket_count
            ))
            conn.commit()

    def _update_pipeline_run(
        self,
        pipeline_id: str,
        status: str,
        results: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update pipeline run status in database.

        Args:
            pipeline_id: Pipeline run ID
            status: Pipeline status (running/completed/failed)
            results: Optional results dictionary
        """
        with self.cache_manager._get_connection() as conn:
            conn.execute("""
                UPDATE pipeline_history
                SET end_time = ?,
                    status = ?,
                    results = ?
                WHERE pipeline_id = ?
            """, (
                datetime.now().isoformat(),
                status,
                json.dumps(results) if results else None,
                pipeline_id
            ))
            conn.commit()

    def _get_final_results(self, ticket_numbers: List[str]) -> List[GeocodeRecord]:
        """Get final results for tickets from cache.

        Args:
            ticket_numbers: List of ticket numbers

        Returns:
            List of GeocodeRecords
        """
        results = []
        for ticket_number in ticket_numbers:
            record = self.cache_manager.get_current(ticket_number=ticket_number)
            if record:
                results.append(record)
        return results

    def _print_summary(self, result: PipelineResult) -> None:
        """Print pipeline summary.

        Args:
            result: PipelineResult
        """
        print(f"\n{'='*80}")
        print(f"Pipeline Complete: {self.pipeline_name}")
        print(f"{'='*80}")
        print(f"Total Tickets: {result.total_tickets}")
        print(f"Succeeded: {result.total_succeeded} ({result.total_succeeded/result.total_tickets*100:.1f}%)")
        print(f"Failed: {result.total_failed} ({result.total_failed/result.total_tickets*100:.1f}%)")
        print(f"Total Time: {result.total_time_ms}ms ({result.total_time_ms/result.total_tickets:.1f}ms avg)")
        print(f"{'='*80}\n")

    def export_results(
        self,
        output_path: Path,
        quality_filter: Optional[List[QualityTier]] = None
    ) -> int:
        """Export pipeline results to CSV.

        Args:
            output_path: Path to output CSV file
            quality_filter: Optional list of quality tiers to filter

        Returns:
            Number of records exported
        """
        import csv

        # Query cache for records
        from cache.models import CacheQuery

        if quality_filter:
            query = CacheQuery(quality_tier=quality_filter)
        else:
            query = CacheQuery()

        records = self.cache_manager.query(query)

        # Write to CSV
        with open(output_path, 'w', newline='') as f:
            if not records:
                return 0

            # Write header
            writer = csv.DictWriter(f, fieldnames=[
                "ticket_number", "geocode_key", "latitude", "longitude",
                "confidence", "method", "approach", "quality_tier",
                "review_priority", "validation_flags", "street", "intersection",
                "city", "county", "ticket_type", "created_at", "created_by_stage"
            ])
            writer.writeheader()

            # Write records
            for record in records:
                writer.writerow({
                    "ticket_number": record.ticket_number,
                    "geocode_key": record.geocode_key,
                    "latitude": record.latitude,
                    "longitude": record.longitude,
                    "confidence": record.confidence,
                    "method": record.method,
                    "approach": record.approach,
                    "quality_tier": record.quality_tier.value if hasattr(record.quality_tier, 'value') else record.quality_tier,
                    "review_priority": record.review_priority.value if hasattr(record.review_priority, 'value') else record.review_priority,
                    "validation_flags": ",".join(record.validation_flags) if record.validation_flags else "",
                    "street": record.street,
                    "intersection": record.intersection,
                    "city": record.city,
                    "county": record.county,
                    "ticket_type": record.ticket_type,
                    "created_at": record.created_at,
                    "created_by_stage": record.created_by_stage,
                })

        print(f"Exported {len(records)} records to {output_path}")
        return len(records)

    def generate_review_queue(
        self,
        output_path: Path,
        priority_filter: Optional[List[str]] = None
    ) -> int:
        """Generate human review queue CSV.

        Args:
            output_path: Path to output CSV file
            priority_filter: Optional list of priorities to filter (e.g., ["HIGH", "CRITICAL"])

        Returns:
            Number of records in review queue
        """
        import csv
        from cache.models import CacheQuery, ReviewPriority

        # Query for records needing review
        if priority_filter:
            review_priorities = [ReviewPriority(p) for p in priority_filter]
        else:
            # Default to all non-NONE priorities
            review_priorities = [
                ReviewPriority.LOW,
                ReviewPriority.MEDIUM,
                ReviewPriority.HIGH,
                ReviewPriority.CRITICAL
            ]

        query = CacheQuery(review_priority=review_priorities)
        records = self.cache_manager.query(query)

        # Sort by priority (CRITICAL first)
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        records.sort(
            key=lambda r: priority_order.get(
                r.review_priority.value if hasattr(r.review_priority, 'value') else r.review_priority,
                4
            )
        )

        # Write to CSV
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "ticket_number", "review_priority", "quality_tier",
                "confidence", "validation_flags", "latitude", "longitude",
                "street", "intersection", "city", "county",
                "method", "approach", "created_at"
            ])
            writer.writeheader()

            for record in records:
                writer.writerow({
                    "ticket_number": record.ticket_number,
                    "review_priority": record.review_priority.value if hasattr(record.review_priority, 'value') else record.review_priority,
                    "quality_tier": record.quality_tier.value if hasattr(record.quality_tier, 'value') else record.quality_tier,
                    "confidence": f"{record.confidence:.2%}" if record.confidence else "",
                    "validation_flags": ",".join(record.validation_flags) if record.validation_flags else "",
                    "latitude": record.latitude,
                    "longitude": record.longitude,
                    "street": record.street,
                    "intersection": record.intersection,
                    "city": record.city,
                    "county": record.county,
                    "method": record.method,
                    "approach": record.approach,
                    "created_at": record.created_at,
                })

        print(f"Generated review queue with {len(records)} tickets at {output_path}")
        return len(records)


if __name__ == "__main__":
    # Example usage
    print("Pipeline is a class - use it by instantiating and adding stages.")
    print("\nExample:")
    print("  pipeline = Pipeline(cache_manager, config)")
    print("  pipeline.add_stage(Stage1API(cache_manager, config))")
    print("  pipeline.add_stage(Stage3Proximity(cache_manager, config))")
    print("  result = pipeline.run(tickets)")
