"""
Statistics aggregator for ticket data analysis.

Generates aggregated statistics for:
- Time series analysis (tickets over time)
- Type distributions (breakdown by ticket type)
- Work type analysis
- Spatial distributions
- Cost projections
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
import numpy as np


class StatisticsAggregator:
    """Generate statistical summaries and aggregations of ticket data."""

    def __init__(self, output_dir: Path):
        """Initialize statistics aggregator.

        Args:
            output_dir: Directory for statistics output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_summary(
        self,
        tickets_df: pd.DataFrame,
        route_legs: Optional[List[str]] = None,
        output_name: str = "summary.json"
    ) -> Path:
        """Generate overall summary statistics.

        Args:
            tickets_df: DataFrame with ticket data
            route_legs: List of route leg names
            output_name: Output filename

        Returns:
            Path to JSON file with summary stats
        """
        summary = {
            'total_tickets': int(tickets_df.shape[0]),
            'date_range': {
                'start': None,
                'end': None,
                'days': None
            },
            'spatial': {
                'bounds': {
                    'west': float(tickets_df['longitude'].min()),
                    'south': float(tickets_df['latitude'].min()),
                    'east': float(tickets_df['longitude'].max()),
                    'north': float(tickets_df['latitude'].max())
                }
            }
        }

        # Date range analysis
        if 'created_at' in tickets_df.columns:
            dates = pd.to_datetime(tickets_df['created_at'], errors='coerce')
            valid_dates = dates.dropna()

            if len(valid_dates) > 0:
                min_date = valid_dates.min()
                max_date = valid_dates.max()

                summary['date_range'] = {
                    'start': min_date.isoformat(),
                    'end': max_date.isoformat(),
                    'days': (max_date - min_date).days
                }

        # Ticket type distribution
        if 'ticket_type' in tickets_df.columns:
            type_counts = tickets_df['ticket_type'].value_counts()
            summary['ticket_types'] = {
                str(k): int(v) for k, v in type_counts.items()
            }

        # Work type distribution (top 10)
        if 'work_type' in tickets_df.columns:
            work_counts = tickets_df['work_type'].value_counts().head(10)
            summary['work_types'] = {
                str(k): int(v) for k, v in work_counts.items()
            }

        # Route leg distribution
        if 'route_leg' in tickets_df.columns:
            leg_counts = tickets_df['route_leg'].value_counts()
            summary['route_legs'] = {
                str(k): int(v) for k, v in leg_counts.items()
            }

        # Quality metrics
        if 'confidence' in tickets_df.columns:
            summary['quality'] = {
                'avg_confidence': float(tickets_df['confidence'].mean()),
                'min_confidence': float(tickets_df['confidence'].min()),
                'max_confidence': float(tickets_df['confidence'].max())
            }

        # Generate timestamp
        summary['generated'] = datetime.now().isoformat()

        # Write to file
        output_path = self.output_dir / output_name
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)

        return output_path

    def generate_timeseries(
        self,
        tickets_df: pd.DataFrame,
        time_column: str = 'created_at',
        bin_type: str = 'monthly',  # 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
        output_name: str = "timeseries.json"
    ) -> Path:
        """Generate time series data showing tickets over time.

        Args:
            tickets_df: DataFrame with ticket data
            time_column: Column containing timestamps
            bin_type: Temporal binning
            output_name: Output filename

        Returns:
            Path to JSON file with time series data
        """
        # Convert to datetime
        tickets_df = tickets_df.copy()
        tickets_df[time_column] = pd.to_datetime(tickets_df[time_column], errors='coerce')
        tickets_df = tickets_df.dropna(subset=[time_column])

        # Set as index for resampling
        tickets_df = tickets_df.set_index(time_column)

        # Determine resample frequency (pandas 2.x uses ME/QE/YE for end-of-period)
        freq_map = {
            'daily': 'D',
            'weekly': 'W',
            'monthly': 'ME',  # Month-end (changed in pandas 2.x)
            'quarterly': 'QE',  # Quarter-end
            'yearly': 'YE'  # Year-end
        }
        freq = freq_map.get(bin_type, 'ME')

        # Resample and count
        timeseries = tickets_df.resample(freq).size()

        # Build time series data
        data = []
        for timestamp, count in timeseries.items():
            data.append({
                'date': timestamp.isoformat(),
                'count': int(count)
            })

        # Also include breakdown by ticket type if available
        series_by_type = {}
        if 'ticket_type' in tickets_df.columns:
            for ticket_type in tickets_df['ticket_type'].unique():
                if pd.notna(ticket_type):
                    type_series = tickets_df[tickets_df['ticket_type'] == ticket_type].resample(freq).size()
                    series_by_type[str(ticket_type)] = [
                        {'date': ts.isoformat(), 'count': int(cnt)}
                        for ts, cnt in type_series.items()
                    ]

        output_data = {
            'bin_type': bin_type,
            'total': data,
            'by_type': series_by_type,
            'generated': datetime.now().isoformat()
        }

        output_path = self.output_dir / output_name
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        return output_path

    def generate_type_distribution(
        self,
        tickets_df: pd.DataFrame,
        group_by: str = 'ticket_type',
        output_name: str = "type_distribution.json"
    ) -> Path:
        """Generate distribution breakdown by ticket type.

        Args:
            tickets_df: DataFrame with ticket data
            group_by: Column to group by
            output_name: Output filename

        Returns:
            Path to JSON file with distribution data
        """
        if group_by not in tickets_df.columns:
            raise ValueError(f"Column {group_by} not found in data")

        # Calculate counts and percentages
        counts = tickets_df[group_by].value_counts()
        total = counts.sum()

        distribution = []
        for category, count in counts.items():
            if pd.notna(category):
                distribution.append({
                    'category': str(category),
                    'count': int(count),
                    'percentage': float(count / total * 100)
                })

        output_data = {
            'group_by': group_by,
            'distribution': distribution,
            'total': int(total),
            'generated': datetime.now().isoformat()
        }

        output_path = self.output_dir / output_name
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        return output_path

    def generate_spatial_distribution(
        self,
        tickets_df: pd.DataFrame,
        group_by: str = 'route_leg',
        output_name: str = "spatial_distribution.json"
    ) -> Path:
        """Generate spatial distribution statistics.

        Args:
            tickets_df: DataFrame with ticket data
            group_by: Spatial grouping column (e.g., 'route_leg', 'county')
            output_name: Output filename

        Returns:
            Path to JSON file with spatial distribution
        """
        if group_by not in tickets_df.columns:
            raise ValueError(f"Column {group_by} not found in data")

        # Group by spatial entity
        groups = tickets_df.groupby(group_by)

        spatial_data = []
        for name, group in groups:
            if pd.notna(name):
                stats = {
                    'location': str(name),
                    'ticket_count': int(len(group)),
                    'bounds': {
                        'west': float(group['longitude'].min()),
                        'south': float(group['latitude'].min()),
                        'east': float(group['longitude'].max()),
                        'north': float(group['latitude'].max())
                    }
                }

                # Add ticket type breakdown
                if 'ticket_type' in group.columns:
                    type_counts = group['ticket_type'].value_counts()
                    stats['ticket_types'] = {
                        str(k): int(v) for k, v in type_counts.items()
                    }

                # Add average confidence if available
                if 'confidence' in group.columns:
                    stats['avg_confidence'] = float(group['confidence'].mean())

                spatial_data.append(stats)

        output_data = {
            'group_by': group_by,
            'locations': spatial_data,
            'generated': datetime.now().isoformat()
        }

        output_path = self.output_dir / output_name
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        return output_path

    def generate_osprey_summary(
        self,
        tickets_df: pd.DataFrame,
        route_gdf: Any,  # gpd.GeoDataFrame
        output_name: str = "osprey_summary.json"
    ) -> Path:
        """Generate summary optimized for Osprey Strike integration.

        Args:
            tickets_df: DataFrame with ticket data
            route_gdf: GeoDataFrame with route segments
            output_name: Output filename

        Returns:
            Path to JSON file with Osprey-specific summary
        """
        summary = {
            'project_overview': {
                'total_tickets': int(len(tickets_df)),
                'route_segments': int(len(route_gdf)),
            },
            'patrol_priorities': [],
            'high_risk_zones': [],
            'maintenance_schedule': {
                'weekly_checks': [],
                'monthly_checks': [],
                'quarterly_checks': []
            }
        }

        # Calculate patrol priorities per route segment
        for idx, route in route_gdf.iterrows():
            segment_name = route.get('name', f'Segment {idx}')

            # Find tickets near this segment
            # (Simplified - in production would use spatial join)
            if 'route_leg' in tickets_df.columns:
                segment_tickets = tickets_df[tickets_df['route_leg'] == segment_name]
                ticket_count = len(segment_tickets)

                # Calculate priority
                if ticket_count >= 50:
                    priority = 'HIGH'
                    frequency = 'weekly'
                elif ticket_count >= 20:
                    priority = 'MEDIUM'
                    frequency = 'monthly'
                else:
                    priority = 'LOW'
                    frequency = 'quarterly'

                summary['patrol_priorities'].append({
                    'segment': segment_name,
                    'priority': priority,
                    'ticket_count': ticket_count,
                    'recommended_frequency': frequency
                })

                # Add to maintenance schedule
                summary['maintenance_schedule'][f'{frequency}_checks'].append({
                    'segment': segment_name,
                    'ticket_count': ticket_count
                })

        # Identify high-risk zones (areas with emergency tickets)
        if 'ticket_type' in tickets_df.columns:
            emergency_tickets = tickets_df[tickets_df['ticket_type'] == 'Emergency']

            if len(emergency_tickets) > 0:
                # Group by location (simplified)
                if 'route_leg' in emergency_tickets.columns:
                    for leg, group in emergency_tickets.groupby('route_leg'):
                        if pd.notna(leg) and len(group) > 0:
                            summary['high_risk_zones'].append({
                                'location': str(leg),
                                'emergency_count': int(len(group)),
                                'requires_immediate_attention': len(group) >= 5
                            })

        summary['generated'] = datetime.now().isoformat()

        output_path = self.output_dir / output_name
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)

        return output_path


if __name__ == "__main__":
    print("Statistics Aggregator - Example Usage")
    print("="*50)
    print("""
    from kcci_maintenance.export import StatisticsAggregator

    aggregator = StatisticsAggregator(output_dir='exports/floydada/statistics')

    # Generate summary statistics
    aggregator.generate_summary(tickets_df)

    # Generate time series
    aggregator.generate_timeseries(tickets_df, bin_type='monthly')

    # Generate type distribution
    aggregator.generate_type_distribution(tickets_df, group_by='ticket_type')

    # Generate Osprey Strike summary
    aggregator.generate_osprey_summary(tickets_df, route_gdf)
    """)
