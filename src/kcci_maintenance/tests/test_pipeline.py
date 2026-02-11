"""
Unit tests for pipeline orchestration.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import Pipeline, PipelineResult
from cache.cache_manager import CacheManager
from cache.models import GeocodeRecord, QualityTier, ReviewPriority
from stages.base_stage import BaseStage


class MockStage(BaseStage):
    """Mock stage for testing."""

    def __init__(self, stage_name, cache_manager, config, success_rate=1.0):
        super().__init__(stage_name, cache_manager, config)
        self.success_rate = success_rate
        self.processed_tickets = []

    def process_ticket(self, ticket_data):
        """Mock process that always succeeds."""
        self.processed_tickets.append(ticket_data["ticket_number"])

        # Simulate failure based on success rate
        import random
        if random.random() > self.success_rate:
            raise Exception("Simulated failure")

        return GeocodeRecord(
            ticket_number=ticket_data["ticket_number"],
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
            latitude=31.5,
            longitude=-103.1,
            confidence=0.85,
            method=self.stage_name,
            approach="mock",
            quality_tier=QualityTier.GOOD,
            review_priority=ReviewPriority.NONE,
        )


@pytest.fixture
def cache_manager(tmp_path):
    """Create a temporary cache manager for testing."""
    db_path = tmp_path / "test_pipeline.db"
    return CacheManager(str(db_path))


@pytest.fixture
def pipeline_config():
    """Create a pipeline configuration."""
    return {
        "name": "test_pipeline",
        "fail_fast": False,
        "save_intermediate": True,
    }


@pytest.fixture
def sample_tickets():
    """Create sample tickets for testing."""
    return [
        {
            "ticket_number": f"TEST{i:03d}",
            "street": "Main St",
            "intersection": "1st Ave",
            "city": "Test City",
            "county": "Test County",
        }
        for i in range(5)
    ]


def test_pipeline_initialization(cache_manager, pipeline_config):
    """Test pipeline initialization."""
    pipeline = Pipeline(cache_manager, pipeline_config)
    assert pipeline.pipeline_name == "test_pipeline"
    assert pipeline.fail_fast is False
    assert len(pipeline.stages) == 0


def test_pipeline_add_stage(cache_manager, pipeline_config):
    """Test adding stages to pipeline."""
    pipeline = Pipeline(cache_manager, pipeline_config)

    stage1 = MockStage("stage_1", cache_manager, {})
    stage2 = MockStage("stage_2", cache_manager, {})

    pipeline.add_stage(stage1)
    pipeline.add_stage(stage2)

    assert len(pipeline.stages) == 2
    assert pipeline.stages[0].stage_name == "stage_1"
    assert pipeline.stages[1].stage_name == "stage_2"


def test_pipeline_run_single_stage(cache_manager, pipeline_config, sample_tickets):
    """Test running pipeline with single stage."""
    pipeline = Pipeline(cache_manager, pipeline_config)
    stage = MockStage("test_stage", cache_manager, {})
    pipeline.add_stage(stage)

    result = pipeline.run(sample_tickets)

    assert result.total_tickets == 5
    assert result.total_succeeded == 5
    assert result.total_failed == 0
    assert len(result.stage_statistics) == 1


def test_pipeline_run_multiple_stages(cache_manager, pipeline_config, sample_tickets):
    """Test running pipeline with multiple stages."""
    pipeline = Pipeline(cache_manager, pipeline_config)

    stage1 = MockStage("stage_1", cache_manager, {"skip_rules": {}})
    stage2 = MockStage("stage_2", cache_manager, {"skip_rules": {}})

    pipeline.add_stage(stage1)
    pipeline.add_stage(stage2)

    result = pipeline.run(sample_tickets)

    assert result.total_tickets == 5
    assert len(result.stage_statistics) == 2


def test_pipeline_skip_logic(cache_manager, pipeline_config, sample_tickets):
    """Test that stages skip already-processed tickets."""
    pipeline = Pipeline(cache_manager, pipeline_config)

    # Stage 1 processes all tickets
    stage1 = MockStage("stage_1", cache_manager, {
        "skip_rules": {"skip_if_quality": []}
    })

    # Stage 2 should skip GOOD quality tickets
    stage2 = MockStage("stage_2", cache_manager, {
        "skip_rules": {"skip_if_quality": ["EXCELLENT", "GOOD"]}
    })

    pipeline.add_stage(stage1)
    pipeline.add_stage(stage2)

    result = pipeline.run(sample_tickets)

    # Stage 1 should process all 5
    assert result.stage_statistics[0].processed == 5

    # Stage 2 should skip all 5 (since stage 1 created GOOD quality)
    assert result.stage_statistics[1].skipped == 5


def test_pipeline_statistics(cache_manager, pipeline_config, sample_tickets):
    """Test pipeline statistics calculation."""
    pipeline = Pipeline(cache_manager, pipeline_config)
    stage = MockStage("test_stage", cache_manager, {})
    pipeline.add_stage(stage)

    result = pipeline.run(sample_tickets)

    # Check result structure
    assert isinstance(result, PipelineResult)
    assert result.total_tickets == 5
    assert result.total_time_ms > 0
    assert result.start_time != ""
    assert result.end_time != ""

    # Check stage statistics
    stats = result.stage_statistics[0]
    assert stats.stage_name == "test_stage"
    assert stats.total_tickets == 5
    assert stats.succeeded == 5


def test_pipeline_to_dict(cache_manager, pipeline_config, sample_tickets):
    """Test converting pipeline result to dictionary."""
    pipeline = Pipeline(cache_manager, pipeline_config)
    stage = MockStage("test_stage", cache_manager, {})
    pipeline.add_stage(stage)

    result = pipeline.run(sample_tickets)
    result_dict = result.to_dict()

    assert isinstance(result_dict, dict)
    assert "total_tickets" in result_dict
    assert "total_succeeded" in result_dict
    assert "stages" in result_dict
    assert len(result_dict["stages"]) == 1


def test_pipeline_export_results(cache_manager, pipeline_config, sample_tickets, tmp_path):
    """Test exporting pipeline results to CSV."""
    pipeline = Pipeline(cache_manager, pipeline_config)
    stage = MockStage("test_stage", cache_manager, {})
    pipeline.add_stage(stage)

    # Run pipeline
    result = pipeline.run(sample_tickets)

    # Export results
    output_path = tmp_path / "results.csv"
    count = pipeline.export_results(output_path)

    assert count == 5
    assert output_path.exists()

    # Check CSV content
    with open(output_path, 'r') as f:
        content = f.read()
        assert "ticket_number" in content
        assert "TEST000" in content


def test_pipeline_generate_review_queue(cache_manager, pipeline_config, tmp_path):
    """Test generating human review queue."""
    pipeline = Pipeline(cache_manager, pipeline_config)

    # Create tickets with different review priorities
    tickets = [
        {"ticket_number": f"TEST{i:03d}", "street": "Main", "intersection": "1st",
         "city": "City", "county": "County"}
        for i in range(3)
    ]

    # Create a stage that produces different priorities
    class VariedPriorityStage(BaseStage):
        def process_ticket(self, ticket_data):
            priorities = [ReviewPriority.CRITICAL, ReviewPriority.HIGH, ReviewPriority.MEDIUM]
            idx = int(ticket_data["ticket_number"][-1])
            return GeocodeRecord(
                ticket_number=ticket_data["ticket_number"],
                geocode_key="key",
                latitude=31.5,
                longitude=-103.1,
                confidence=0.5 - idx * 0.1,
                method=self.stage_name,
                quality_tier=QualityTier.REVIEW_NEEDED,
                review_priority=priorities[idx],
            )

    stage = VariedPriorityStage("test_stage", cache_manager, {})
    pipeline.add_stage(stage)

    # Run pipeline
    result = pipeline.run(tickets)

    # Generate review queue
    output_path = tmp_path / "review_queue.csv"
    count = pipeline.generate_review_queue(output_path)

    assert count == 3
    assert output_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
