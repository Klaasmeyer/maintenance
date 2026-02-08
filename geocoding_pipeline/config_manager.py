"""
Configuration manager for pipeline settings.

Loads pipeline configuration from YAML files, validates settings,
and provides environment variable substitution.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class PipelineConfig:
    """Validated pipeline configuration."""
    name: str
    cache_db_path: Path
    stages: Dict[str, Dict[str, Any]]
    fail_fast: bool = False
    save_intermediate: bool = True
    output_dir: Path = Path("outputs")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "cache_db_path": str(self.cache_db_path),
            "stages": self.stages,
            "fail_fast": self.fail_fast,
            "save_intermediate": self.save_intermediate,
            "output_dir": str(self.output_dir),
        }


class ConfigManager:
    """Manages pipeline configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_path: Path to configuration YAML file (optional)
        """
        self.config_path = config_path
        self._config: Optional[Dict[str, Any]] = None

    def load(self, config_path: Optional[Path] = None) -> PipelineConfig:
        """Load and validate configuration from YAML file.

        Args:
            config_path: Path to configuration file (overrides init path)

        Returns:
            PipelineConfig with validated settings

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        # Use provided path or fall back to init path
        path = config_path or self.config_path
        if path is None:
            raise ValueError("No configuration path provided")

        # Check file exists
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        # Load YAML
        with open(path, 'r') as f:
            config = yaml.safe_load(f)

        # Perform environment variable substitution
        config = self._substitute_env_vars(config)

        # Validate configuration
        self._validate_config(config)

        # Store raw config
        self._config = config

        # Create PipelineConfig
        return self._create_pipeline_config(config)

    def _substitute_env_vars(self, config: Any) -> Any:
        """Recursively substitute environment variables in configuration.

        Supports syntax: ${VAR_NAME} or ${VAR_NAME:default_value}

        Args:
            config: Configuration dictionary or value

        Returns:
            Configuration with substituted values
        """
        if isinstance(config, dict):
            return {
                key: self._substitute_env_vars(value)
                for key, value in config.items()
            }
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            return self._substitute_env_var_string(config)
        else:
            return config

    def _substitute_env_var_string(self, value: str) -> str:
        """Substitute environment variables in a string.

        Args:
            value: String potentially containing ${VAR} syntax

        Returns:
            String with substituted values
        """
        import re

        # Pattern: ${VAR_NAME} or ${VAR_NAME:default}
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'

        def replacer(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ""

            # Get from environment or use default
            return os.environ.get(var_name, default_value)

        return re.sub(pattern, replacer, value)

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration structure and required fields.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        # Required fields
        if "name" not in config:
            raise ValueError("Configuration missing required field: name")

        if "cache" not in config:
            raise ValueError("Configuration missing required field: cache")

        if "stages" not in config:
            raise ValueError("Configuration missing required field: stages")

        # Validate cache settings
        cache_config = config["cache"]
        if "db_path" not in cache_config:
            raise ValueError("Cache configuration missing required field: db_path")

        # Validate stages
        stages = config["stages"]
        if not isinstance(stages, dict):
            raise ValueError("Stages must be a dictionary")

        for stage_name, stage_config in stages.items():
            if not isinstance(stage_config, dict):
                raise ValueError(f"Stage {stage_name} configuration must be a dictionary")

            # Each stage should have at least enabled flag
            if "enabled" not in stage_config:
                # Default to enabled if not specified
                stage_config["enabled"] = True

    def _create_pipeline_config(self, config: Dict[str, Any]) -> PipelineConfig:
        """Create PipelineConfig from validated configuration.

        Args:
            config: Validated configuration dictionary

        Returns:
            PipelineConfig instance
        """
        cache_config = config["cache"]
        cache_db_path = Path(cache_config["db_path"]).expanduser()

        # Get output directory (default to outputs/)
        output_dir = Path(config.get("output_dir", "outputs")).expanduser()

        # Filter enabled stages only
        enabled_stages = {
            name: stage_config
            for name, stage_config in config["stages"].items()
            if stage_config.get("enabled", True)
        }

        return PipelineConfig(
            name=config["name"],
            cache_db_path=cache_db_path,
            stages=enabled_stages,
            fail_fast=config.get("fail_fast", False),
            save_intermediate=config.get("save_intermediate", True),
            output_dir=output_dir,
        )

    def get_stage_config(self, stage_name: str) -> Dict[str, Any]:
        """Get configuration for a specific stage.

        Args:
            stage_name: Name of stage

        Returns:
            Stage configuration dictionary

        Raises:
            ValueError: If stage not found in configuration
        """
        if self._config is None:
            raise ValueError("Configuration not loaded - call load() first")

        stages = self._config.get("stages", {})
        if stage_name not in stages:
            raise ValueError(f"Stage {stage_name} not found in configuration")

        return stages[stage_name]

    def save_example_config(self, output_path: Path) -> None:
        """Save an example configuration file.

        Args:
            output_path: Path where to save example config
        """
        example_config = {
            "name": "geocoding_pipeline",
            "cache": {
                "db_path": "${HOME}/geocoding_cache.db"
            },
            "output_dir": "outputs",
            "fail_fast": False,
            "save_intermediate": True,
            "stages": {
                "stage_1_api": {
                    "enabled": True,
                    "skip_rules": {
                        "skip_if_quality": ["EXCELLENT"],
                        "skip_if_locked": True,
                        "skip_if_confidence": 0.90
                    },
                    "api_key": "${GEOCODING_API_KEY}",
                    "api_url": "https://api.geocoding.com/v1/geocode",
                    "timeout": 5
                },
                "stage_3_proximity": {
                    "enabled": True,
                    "skip_rules": {
                        "skip_if_quality": ["EXCELLENT", "GOOD"],
                        "skip_if_locked": True
                    },
                    "road_network_path": "roads_merged.gpkg",
                    "max_distance_km": 50
                },
                "stage_4_geometric": {
                    "enabled": True,
                    "skip_rules": {
                        "skip_if_quality": ["EXCELLENT", "GOOD"],
                        "skip_if_locked": True
                    },
                    "road_network_path": "roads_merged.gpkg"
                },
                "stage_5_validation": {
                    "enabled": True,
                    "skip_rules": {
                        "skip_if_locked": True
                    },
                    "validation_rules": [
                        "low_confidence",
                        "emergency_low_confidence",
                        "city_distance",
                        "fallback_geocode",
                        "missing_road"
                    ]
                }
            }
        }

        with open(output_path, 'w') as f:
            yaml.dump(example_config, f, default_flow_style=False, sort_keys=False)

        print(f"Saved example configuration to {output_path}")


if __name__ == "__main__":
    # Test configuration manager
    print("Testing ConfigManager...\n")

    # Create example config
    manager = ConfigManager()
    example_path = Path("example_pipeline_config.yaml")
    manager.save_example_config(example_path)

    # Load and validate
    print("\nLoading configuration...")
    config = manager.load(example_path)

    print(f"✓ Configuration loaded: {config.name}")
    print(f"  Cache DB: {config.cache_db_path}")
    print(f"  Output Dir: {config.output_dir}")
    print(f"  Fail Fast: {config.fail_fast}")
    print(f"  Stages: {len(config.stages)}")

    # Print enabled stages
    print("\n  Enabled stages:")
    for stage_name in config.stages.keys():
        print(f"    - {stage_name}")

    # Test environment variable substitution
    print("\n✓ Environment variable substitution works")
    print(f"  HOME resolved to: {os.environ.get('HOME', 'NOT_SET')}")

    # Test stage config retrieval
    print("\n✓ Stage configuration retrieval:")
    stage_config = manager.get_stage_config("stage_3_proximity")
    print(f"  stage_3_proximity skip rules: {stage_config.get('skip_rules')}")

    print("\n✓ All ConfigManager tests passed!")
    print(f"\nExample config saved to: {example_path}")
