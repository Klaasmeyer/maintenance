"""
Ticket data loader utilities.

Supports loading tickets from:
- Single CSV/Excel files
- Hierarchical directory structures: tickets/[county]/[year]/[files]
- Multiple files combined into a single dataset
"""

import logging
from pathlib import Path
from typing import List, Union, Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


class TicketLoader:
    """Loads ticket data from various sources and formats."""

    SUPPORTED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}

    def __init__(self, normalize_columns: bool = True):
        """Initialize ticket loader.

        Args:
            normalize_columns: Whether to normalize column names (default: True)
        """
        self.normalize_columns = normalize_columns

    def load(self, path: Union[str, Path]) -> pd.DataFrame:
        """Load tickets from a file or directory structure.

        Args:
            path: Path to a single file or directory containing ticket files

        Returns:
            DataFrame with all ticket data

        Raises:
            FileNotFoundError: If path doesn't exist
            ValueError: If no valid ticket files found
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Ticket path not found: {path}")

        if path.is_file():
            # Single file
            return self._load_file(path)
        elif path.is_dir():
            # Directory structure
            return self._load_directory(path)
        else:
            raise ValueError(f"Invalid path type: {path}")

    def _load_directory(self, directory: Path) -> pd.DataFrame:
        """Load all ticket files from a directory structure.

        Supports hierarchical structures like:
        - tickets/[county]/[year]/[files]
        - tickets/[year]/[files]
        - tickets/[files]

        Args:
            directory: Root directory containing ticket files

        Returns:
            Combined DataFrame from all files

        Raises:
            ValueError: If no valid files found
        """
        # Find all ticket files recursively
        ticket_files = []
        for ext in self.SUPPORTED_EXTENSIONS:
            ticket_files.extend(directory.rglob(f"*{ext}"))

        # Filter out hidden files and system files
        ticket_files = [
            f for f in ticket_files
            if not any(part.startswith('.') for part in f.parts)
        ]

        if not ticket_files:
            raise ValueError(f"No ticket files found in {directory}")

        logger.info(f"Found {len(ticket_files)} ticket file(s) in {directory}")

        # Load and combine all files
        dfs = []
        for file_path in sorted(ticket_files):
            try:
                df = self._load_file(file_path)
                # Add metadata columns to track source
                df['_source_file'] = str(file_path.relative_to(directory))
                df['_source_county'] = self._extract_county(file_path, directory)
                df['_source_year'] = self._extract_year(file_path, directory)

                dfs.append(df)
                logger.info(f"  ✓ Loaded {len(df)} tickets from {file_path.name}")
            except Exception as e:
                logger.warning(f"  ⚠ Failed to load {file_path.name}: {e}")
                continue

        if not dfs:
            raise ValueError(f"No valid ticket data loaded from {directory}")

        # Combine all DataFrames
        combined_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Combined total: {len(combined_df)} tickets from {len(dfs)} file(s)")

        return combined_df

    def _load_file(self, file_path: Path) -> pd.DataFrame:
        """Load a single ticket file (CSV or Excel).

        Args:
            file_path: Path to ticket file

        Returns:
            DataFrame with ticket data

        Raises:
            ValueError: If file format not supported
        """
        ext = file_path.suffix.lower()

        if ext == '.csv':
            df = pd.read_csv(file_path)
        elif ext in {'.xlsx', '.xls'}:
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        # Normalize column names if requested
        if self.normalize_columns:
            df = self._normalize_columns(df)

        return df

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to standard format.

        Maps various column name formats to standard names:
        - 'Number', 'ticket_number', 'Ticket Number' -> 'ticket_number'
        - 'County', 'county' -> 'county'
        - etc.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with normalized column names
        """
        # Column mapping: {standard_name: [possible_variants]}
        column_mapping = {
            'ticket_number': ['Number', 'ticket_number', 'Ticket Number', 'TicketNumber'],
            'county': ['County', 'county'],
            'city': ['City', 'city'],
            'street': ['Street', 'street', 'Address'],
            'intersection': ['Intersection', 'intersection', 'Cross Street', 'CrossStreet'],
            'ticket_type': ['Ticket Type', 'ticket_type', 'Type'],
            'duration': ['Duration', 'duration', 'Work Duration'],
            'work_type': ['Nature of Work', 'work_type', 'Work Type', 'WorkType'],
            'excavator': ['Excavator', 'excavator', 'Company'],
            'state': ['State', 'state'],
            'zip': ['Zip', 'zip', 'Zip Code', 'ZipCode'],
        }

        # Create reverse mapping for actual renaming
        rename_map = {}
        for standard_name, variants in column_mapping.items():
            for variant in variants:
                if variant in df.columns:
                    rename_map[variant] = standard_name
                    break  # Use first match only

        if rename_map:
            df = df.rename(columns=rename_map)
            logger.debug(f"Normalized columns: {rename_map}")

        return df

    def _extract_county(self, file_path: Path, base_dir: Path) -> str:
        """Extract county name from file path structure.

        Looks for county name in directory structure:
        - tickets/[county]/[year]/file.csv -> county name
        - tickets/[year]/file.csv -> None

        Args:
            file_path: Path to file
            base_dir: Base directory (tickets root)

        Returns:
            County name or empty string
        """
        try:
            relative_path = file_path.relative_to(base_dir)
            parts = relative_path.parts

            # If structure has at least 3 parts: county/year/file.csv
            if len(parts) >= 3:
                return parts[0].title()  # Capitalize first letter
            # If structure has 2 parts: year/file.csv (no county)
            elif len(parts) == 2:
                # Check if first part looks like a year
                if parts[0].isdigit() and len(parts[0]) == 4:
                    return ""
                else:
                    # Assume it's a county
                    return parts[0].title()
            else:
                return ""
        except ValueError:
            return ""

    def _extract_year(self, file_path: Path, base_dir: Path) -> str:
        """Extract year from file path structure.

        Looks for year (4-digit number) in directory structure:
        - tickets/[county]/[year]/file.csv -> year
        - tickets/[year]/file.csv -> year

        Args:
            file_path: Path to file
            base_dir: Base directory (tickets root)

        Returns:
            Year string or empty string
        """
        try:
            relative_path = file_path.relative_to(base_dir)
            parts = relative_path.parts

            # Look for 4-digit year in path parts
            for part in parts:
                if part.isdigit() and len(part) == 4:
                    return part

            return ""
        except ValueError:
            return ""

    def prepare_tickets(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Prepare tickets DataFrame for pipeline processing.

        Converts DataFrame to list of ticket dictionaries with standard fields.

        Args:
            df: DataFrame with ticket data

        Returns:
            List of ticket dictionaries
        """
        tickets = []
        for _, row in df.iterrows():
            ticket = {
                'ticket_number': str(row.get('ticket_number', row.get('Number', ''))),
                'county': row.get('county', row.get('County', '')),
                'city': row.get('city', row.get('City', '')),
                'street': row.get('street', row.get('Street', '')),
                'intersection': row.get('intersection', row.get('Intersection', '')),
                'ticket_type': row.get('ticket_type', row.get('Ticket Type')),
                'duration': row.get('duration', row.get('Duration')),
                'work_type': row.get('work_type', row.get('Nature of Work')),
                'excavator': row.get('excavator', row.get('Excavator')),
            }

            # Add source metadata if available
            if '_source_file' in df.columns:
                ticket['_source_file'] = row.get('_source_file', '')
            if '_source_county' in df.columns:
                ticket['_source_county'] = row.get('_source_county', '')
            if '_source_year' in df.columns:
                ticket['_source_year'] = row.get('_source_year', '')

            tickets.append(ticket)

        return tickets


def load_tickets(
    path: Union[str, Path],
    normalize_columns: bool = True,
) -> pd.DataFrame:
    """Convenience function to load tickets.

    Args:
        path: Path to file or directory
        normalize_columns: Whether to normalize column names

    Returns:
        DataFrame with ticket data
    """
    loader = TicketLoader(normalize_columns=normalize_columns)
    return loader.load(path)


if __name__ == "__main__":
    # Test the ticket loader
    print("TicketLoader - Test Mode\n")

    # Test 1: Load from directory structure
    test_dirs = [
        Path("projects/floydada/tickets"),
        Path("projects/wink/tickets"),
    ]

    for test_dir in test_dirs:
        if test_dir.exists():
            print(f"\n{'='*70}")
            print(f"Testing: {test_dir}")
            print('='*70)

            try:
                loader = TicketLoader(normalize_columns=True)
                df = loader.load(test_dir)

                print(f"\n✓ Loaded {len(df)} tickets")
                print(f"  Columns: {list(df.columns)}")

                if '_source_file' in df.columns:
                    print(f"\n  Source files:")
                    for source_file in df['_source_file'].unique():
                        count = len(df[df['_source_file'] == source_file])
                        print(f"    - {source_file}: {count} tickets")

                if '_source_county' in df.columns and '_source_year' in df.columns:
                    print(f"\n  County/Year breakdown:")
                    for county in df['_source_county'].unique():
                        if county:
                            county_df = df[df['_source_county'] == county]
                            for year in county_df['_source_year'].unique():
                                count = len(county_df[county_df['_source_year'] == year])
                                print(f"    - {county} {year}: {count} tickets")

                # Test prepare_tickets
                tickets = loader.prepare_tickets(df.head(3))
                print(f"\n  Sample ticket:")
                for key, value in tickets[0].items():
                    if not key.startswith('_'):
                        print(f"    {key}: {value}")

            except Exception as e:
                print(f"  ❌ Error: {e}")
                import traceback
                traceback.print_exc()

    print("\n" + "="*70)
    print("✓ TicketLoader test complete")
