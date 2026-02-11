"""
Project path resolution utilities.

Provides functions to resolve project-based directory structures
supporting the new multi-project architecture.
"""

from pathlib import Path
from typing import Literal, Dict

# Type for resource types
ResourceType = Literal['tickets', 'route', 'utilities', 'permitting']


def resolve_project_path(
    project_name: str,
    resource_type: ResourceType,
    base_dir: Path = Path("projects")
) -> Path:
    """Resolve path for a project resource.

    Args:
        project_name: Name of the project (e.g., "wink", "floydada")
        resource_type: Type of resource (tickets, route, utilities, permitting)
        base_dir: Base directory for projects (default: "projects")

    Returns:
        Path to the resource directory

    Examples:
        >>> resolve_project_path("wink", "tickets")
        Path("projects/wink/tickets")

        >>> resolve_project_path("floydada", "route")
        Path("projects/floydada/route")
    """
    project_root = base_dir / project_name
    resource_path = project_root / resource_type

    return resource_path


def get_project_config(
    project_name: str,
    base_dir: Path = Path("projects")
) -> Dict[str, Path]:
    """Get all standard paths for a project.

    Args:
        project_name: Name of the project
        base_dir: Base directory for projects (default: "projects")

    Returns:
        Dictionary with all resource paths

    Example:
        >>> config = get_project_config("wink")
        >>> config["tickets"]
        Path("projects/wink/tickets")
        >>> config["route"]
        Path("projects/wink/route")
    """
    project_root = base_dir / project_name

    return {
        "root": project_root,
        "tickets": project_root / "tickets",
        "route": project_root / "route",
        "utilities": project_root / "utilities",
        "permitting": project_root / "permitting",
    }


def resolve_project_file(
    project_name: str,
    resource_type: ResourceType,
    filename: str,
    base_dir: Path = Path("projects")
) -> Path:
    """Resolve full path to a specific file in a project resource.

    Args:
        project_name: Name of the project
        resource_type: Type of resource
        filename: Name of the file
        base_dir: Base directory for projects (default: "projects")

    Returns:
        Full path to the file

    Example:
        >>> resolve_project_file("wink", "tickets", "wink-intersection.csv")
        Path("projects/wink/tickets/wink-intersection.csv")
    """
    resource_path = resolve_project_path(project_name, resource_type, base_dir)
    return resource_path / filename


def validate_project_structure(
    project_name: str,
    base_dir: Path = Path("projects")
) -> Dict[str, bool]:
    """Check which resource directories exist for a project.

    Args:
        project_name: Name of the project
        base_dir: Base directory for projects (default: "projects")

    Returns:
        Dictionary indicating which directories exist

    Example:
        >>> validate_project_structure("wink")
        {'root': True, 'tickets': True, 'route': True, 'utilities': True, 'permitting': True}
    """
    config = get_project_config(project_name, base_dir)

    return {
        name: path.exists()
        for name, path in config.items()
    }


if __name__ == "__main__":
    # Test the utilities
    print("Testing project path resolution utilities\n")

    # Test resolve_project_path
    print("Test 1: resolve_project_path")
    path = resolve_project_path("wink", "tickets")
    print(f"  wink/tickets -> {path}")

    path = resolve_project_path("floydada", "route")
    print(f"  floydada/route -> {path}")

    # Test get_project_config
    print("\nTest 2: get_project_config")
    config = get_project_config("wink")
    print(f"  Wink project paths:")
    for name, path in config.items():
        print(f"    {name}: {path}")

    # Test resolve_project_file
    print("\nTest 3: resolve_project_file")
    file_path = resolve_project_file("wink", "tickets", "wink-intersection.csv")
    print(f"  wink tickets CSV -> {file_path}")

    # Test validate_project_structure
    print("\nTest 4: validate_project_structure")
    structure = validate_project_structure("wink")
    print(f"  Wink project structure:")
    for name, exists in structure.items():
        status = "✓" if exists else "✗"
        print(f"    {status} {name}")

    print("\n✓ All tests completed!")
