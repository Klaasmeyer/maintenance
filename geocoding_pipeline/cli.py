#!/usr/bin/env python3
"""
Geocoding Pipeline CLI

Command-line interface for running the geocoding pipeline with various options.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd

from pipeline import Pipeline
from cache.cache_manager import CacheManager
from config_manager import ConfigManager
from stages.stage_3_proximity import Stage3ProximityGeocoder
from stages.stage_5_validation import Stage5Validation
from stages.stage_6_enrichment import Stage6Enrichment
from utils.ticket_loader import TicketLoader


def main():
    parser = argparse.ArgumentParser(
        description="Geocoding Pipeline - Process 811 tickets with intelligent caching and quality assessment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run pipeline on single CSV file
  %(prog)s tickets.csv --output results.csv

  # Run pipeline on directory structure (tickets/[county]/[year]/)
  %(prog)s projects/floydada/tickets --output results.csv

  # Use custom configuration
  %(prog)s tickets.csv --config my_config.yaml

  # Generate review queue only
  %(prog)s tickets.csv --review-queue-only --output review.csv

  # Export existing cache results
  %(prog)s --export-cache results.csv

  # Show cache statistics
  %(prog)s --stats
        """
    )

    # Input/Output options
    parser.add_argument(
        'input_file',
        nargs='?',
        type=Path,
        help='Input CSV/Excel file or directory with ticket data (supports tickets/[county]/[year]/ structure)'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output CSV file for results (default: pipeline_results_TIMESTAMP.csv)'
    )
    parser.add_argument(
        '-r', '--review-queue',
        type=Path,
        help='Output CSV file for review queue (default: review_queue_TIMESTAMP.csv)'
    )

    # Configuration options
    parser.add_argument(
        '-c', '--config',
        type=Path,
        help='Pipeline configuration YAML file (default: use built-in config)'
    )
    parser.add_argument(
        '--cache-db',
        type=Path,
        default=Path('outputs/pipeline_cache.db'),
        help='Cache database path (default: outputs/pipeline_cache.db)'
    )
    parser.add_argument(
        '--roads',
        type=Path,
        default=Path('roads_merged.gpkg'),
        help='Road network GeoPackage file (default: roads_merged.gpkg)'
    )

    # Pipeline behavior
    parser.add_argument(
        '--skip-stage3',
        action='store_true',
        help='Skip proximity geocoding stage (Stage 3)'
    )
    parser.add_argument(
        '--skip-stage5',
        action='store_true',
        help='Skip validation stage (Stage 5)'
    )
    parser.add_argument(
        '--skip-stage6',
        action='store_true',
        help='Skip enrichment stage (Stage 6)'
    )
    parser.add_argument(
        '--force-reprocess',
        action='store_true',
        help='Force reprocessing of all tickets (ignore cache)'
    )
    parser.add_argument(
        '--fail-fast',
        action='store_true',
        help='Stop pipeline on first error'
    )

    # Review queue options
    parser.add_argument(
        '--review-priority',
        nargs='+',
        choices=['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
        default=['CRITICAL', 'HIGH', 'MEDIUM'],
        help='Review priorities to include (default: CRITICAL HIGH MEDIUM)'
    )
    parser.add_argument(
        '--review-queue-only',
        action='store_true',
        help='Only generate review queue from existing cache (no geocoding)'
    )

    # Cache operations
    parser.add_argument(
        '--export-cache',
        type=Path,
        metavar='OUTPUT',
        help='Export all cache records to CSV and exit'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show cache statistics and exit'
    )
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Clear all cache records (WARNING: destructive!)'
    )

    # Output options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Minimal output (errors only)'
    )
    parser.add_argument(
        '--no-progress',
        action='store_true',
        help='Disable progress indicators'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.input_file and not args.export_cache and not args.stats and not args.clear_cache:
        parser.error("input_file is required unless using --export-cache, --stats, or --clear-cache")

    # Initialize cache manager
    args.cache_db.parent.mkdir(parents=True, exist_ok=True)
    cache_manager = CacheManager(str(args.cache_db))

    # Handle cache operations
    if args.clear_cache:
        if not args.quiet:
            print("⚠️  WARNING: This will delete all cached records!")
            response = input("Are you sure? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return 0
        # Clear cache (delete database and recreate)
        args.cache_db.unlink(missing_ok=True)
        cache_manager = CacheManager(str(args.cache_db))
        print("✅ Cache cleared")
        return 0

    if args.stats:
        show_statistics(cache_manager, args.quiet)
        return 0

    if args.export_cache:
        export_cache(cache_manager, args.export_cache, args.quiet)
        return 0

    # Handle review queue only
    if args.review_queue_only:
        generate_review_queue_only(cache_manager, args, args.quiet)
        return 0

    # Validate input file
    if not args.input_file.exists():
        print(f"❌ Error: Input file not found: {args.input_file}", file=sys.stderr)
        return 1

    if args.roads and not args.roads.exists():
        print(f"❌ Error: Road network file not found: {args.roads}", file=sys.stderr)
        return 1

    # Load configuration
    if args.config:
        config_manager = ConfigManager(args.config)
        config = config_manager.load()
        pipeline_config = config.to_dict()
    else:
        # Use default config
        pipeline_config = {
            'name': 'geocoding_pipeline_cli',
            'fail_fast': args.fail_fast,
            'save_intermediate': True,
        }

    # Load tickets
    if not args.quiet:
        print(f"📊 Loading tickets from {args.input_file}...")

    try:
        # Use TicketLoader to support both files and directory structures
        loader = TicketLoader(normalize_columns=True)
        df = loader.load(args.input_file)

        if not args.quiet:
            # Show loading summary
            if '_source_file' in df.columns:
                num_files = df['_source_file'].nunique()
                if num_files > 1:
                    print(f"   Loaded {len(df)} tickets from {num_files} file(s)")
                else:
                    print(f"   Loaded {len(df)} tickets")
            else:
                print(f"   Loaded {len(df)} tickets")

        # Prepare tickets for pipeline
        tickets = loader.prepare_tickets(df)

    except Exception as e:
        print(f"❌ Error loading tickets: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"   Loaded {len(tickets)} tickets")

    # Create pipeline
    pipeline = Pipeline(cache_manager, pipeline_config)

    # Add stages
    if not args.skip_stage3:
        stage3_config = {
            'road_network_path': str(args.roads),
            'skip_rules': {
                'skip_if_quality': [] if args.force_reprocess else ['EXCELLENT', 'GOOD'],
                'skip_if_locked': True,
            }
        }
        stage3 = Stage3ProximityGeocoder(cache_manager, stage3_config)
        pipeline.add_stage(stage3)
        if not args.quiet:
            print("✅ Added Stage 3: Proximity Geocoding")

    if not args.skip_stage5:
        stage5_config = {
            'validation_rules': [
                'low_confidence',
                'emergency_low_confidence',
                'city_distance',
                'fallback_geocode',
                'missing_road',
            ],
            'skip_rules': {
                'skip_if_locked': True,
            }
        }
        stage5 = Stage5Validation(cache_manager, stage5_config)
        pipeline.add_stage(stage5)
        if not args.quiet:
            print("✅ Added Stage 5: Validation")

    if not args.skip_stage6 and args.config:
        # Stage 6 requires config file with jurisdiction settings
        if 'stages' in pipeline_config and 'stage_6_enrichment' in pipeline_config['stages']:
            stage6_config = pipeline_config['stages']['stage_6_enrichment']
            stage6 = Stage6Enrichment(cache_manager, stage6_config)
            pipeline.add_stage(stage6)
            if not args.quiet:
                print("✅ Added Stage 6: Enrichment")

    # Run pipeline
    if not args.quiet:
        print("\n🚀 Running pipeline...")

    result = pipeline.run(tickets)

    if not args.quiet:
        print(f"\n✅ Pipeline complete!")
        print(f"   Succeeded: {result.total_succeeded}/{result.total_tickets}")
        print(f"   Failed: {result.total_failed}/{result.total_tickets}")

    # Generate outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Export results
    if args.output:
        output_path = args.output
    else:
        output_path = Path(f'pipeline_results_{timestamp}.csv')

    count = pipeline.export_results(output_path)
    if not args.quiet:
        print(f"\n📁 Exported {count} results to {output_path}")

    # Generate review queue
    if args.review_queue:
        review_path = args.review_queue
    else:
        review_path = Path(f'review_queue_{timestamp}.csv')

    review_count = pipeline.generate_review_queue(
        review_path,
        priority_filter=args.review_priority
    )
    if not args.quiet:
        print(f"📁 Generated review queue with {review_count} tickets at {review_path}")

    return 0


def show_statistics(cache_manager, quiet=False):
    """Show cache statistics."""
    stats = cache_manager.get_statistics()

    print("\n" + "="*60)
    print("📊 Cache Statistics")
    print("="*60)
    print(f"Total Records:     {stats['total_records']}")
    print(f"Total Versions:    {stats['total_versions']}")
    print(f"Locked Records:    {stats['locked_count']}")
    print()
    print("Quality Distribution:")
    for tier, count in sorted(stats['quality_tiers'].items()):
        percentage = count / stats['total_records'] * 100 if stats['total_records'] > 0 else 0
        print(f"  {tier:20s}: {count:4d} ({percentage:5.1f}%)")

    if 'avg_confidence_by_tier' in stats:
        print()
        print("Average Confidence by Tier:")
        for tier, conf in sorted(stats['avg_confidence_by_tier'].items()):
            print(f"  {tier:20s}: {conf:.1%}")
    print("="*60)


def export_cache(cache_manager, output_path, quiet=False):
    """Export all cache records to CSV."""
    from cache.models import CacheQuery

    query = CacheQuery()
    records = cache_manager.query(query)

    if not records:
        print("⚠️  No records in cache to export")
        return

    import csv
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "ticket_number", "latitude", "longitude", "confidence",
            "quality_tier", "review_priority", "method", "approach",
            "street", "intersection", "city", "county"
        ])
        writer.writeheader()

        for record in records:
            writer.writerow({
                "ticket_number": record.ticket_number,
                "latitude": record.latitude,
                "longitude": record.longitude,
                "confidence": record.confidence,
                "quality_tier": record.quality_tier.value if hasattr(record.quality_tier, 'value') else record.quality_tier,
                "review_priority": record.review_priority.value if hasattr(record.review_priority, 'value') else record.review_priority,
                "method": record.method,
                "approach": record.approach,
                "street": record.street,
                "intersection": record.intersection,
                "city": record.city,
                "county": record.county,
            })

    if not quiet:
        print(f"✅ Exported {len(records)} records to {output_path}")


def generate_review_queue_only(cache_manager, args, quiet=False):
    """Generate review queue from existing cache."""
    from cache.models import CacheQuery, ReviewPriority

    review_priorities = [ReviewPriority(p) for p in args.review_priority]
    query = CacheQuery(review_priority=review_priorities)
    records = cache_manager.query(query)

    if not records:
        print("⚠️  No records found with specified priorities")
        return

    # Sort by priority
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    records.sort(
        key=lambda r: priority_order.get(
            r.review_priority.value if hasattr(r.review_priority, 'value') else r.review_priority,
            4
        )
    )

    # Output path
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if args.review_queue:
        output_path = args.review_queue
    else:
        output_path = Path(f'review_queue_{timestamp}.csv')

    # Write to CSV
    import csv
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "ticket_number", "review_priority", "quality_tier",
            "confidence", "latitude", "longitude",
            "street", "intersection", "city", "county"
        ])
        writer.writeheader()

        for record in records:
            writer.writerow({
                "ticket_number": record.ticket_number,
                "review_priority": record.review_priority.value if hasattr(record.review_priority, 'value') else record.review_priority,
                "quality_tier": record.quality_tier.value if hasattr(record.quality_tier, 'value') else record.quality_tier,
                "confidence": f"{record.confidence:.2%}" if record.confidence else "",
                "latitude": record.latitude,
                "longitude": record.longitude,
                "street": record.street,
                "intersection": record.intersection,
                "city": record.city,
                "county": record.county,
            })

    if not quiet:
        print(f"✅ Generated review queue with {len(records)} tickets at {output_path}")


if __name__ == '__main__':
    sys.exit(main())
