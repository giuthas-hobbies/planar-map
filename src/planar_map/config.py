import os
import yaml
from pathlib import Path
from importlib import resources
from typing import Dict, Any


# Define paths for the working directory and the user directory
CWD_CONFIG = Path(os.getcwd()) / "config.yaml"
USER_DIR = Path(os.path.expanduser(path="~/.planar-map"))
USER_CONFIG = USER_DIR / "config.yaml"

# Global reference to wherever we end up saving/loading the config
CONFIG_FILE: Path = CWD_CONFIG


def get_default_config() -> Dict[str, Any]:
    """Loads the default configuration from package resources."""
    # Note: Replace 'your_package_name' with your actual package name folder
    # if you are running this outside of a standard module context.
    pkg = __package__ if __package__ else "your_package_name"

    try:
        # For Python 3.9+
        yaml_str = resources.files(anchor=pkg).joinpath(
            "default_config.yaml"
        ).read_text(encoding="utf-8")
    except AttributeError:
        # Fallback for Python 3.8 and below
        yaml_str = resources.read_text(
            package=pkg,
            resource="default_config.yaml",
            encoding="utf-8"
        )

    return yaml.safe_load(stream=yaml_str) or {}


def load_config() -> Dict[str, Any]:
    """Loads config from cwd or ~/.planar-map, or creates from default."""
    global CONFIG_FILE

    # Decide which path to use
    if CWD_CONFIG.exists():
        CONFIG_FILE = CWD_CONFIG
    else:
        CONFIG_FILE = USER_CONFIG
        if not USER_DIR.exists():
            USER_DIR.mkdir(parents=True, exist_ok=True)

    default_conf = get_default_config()

    # If neither file exists, create the user config from defaults
    if not CONFIG_FILE.exists():
        save_config(config=default_conf)
        return default_conf

    # Load existing user/cwd configuration
    with open(file=CONFIG_FILE, mode='r', encoding='utf-8') as f:
        config = yaml.safe_load(stream=f) or {}

    # Merge missing defaults into the loaded config safely
    modified = False
    for section in ['shortcuts', 'physics']:
        if section not in config:
            config[section] = {}

        for k, v in default_conf.get(section, {}).items():
            if k not in config[section]:
                config[section][k] = v
                modified = True

    # Save automatically if we had to inject missing missing parameters
    if modified:
        save_config(config=config)

    return config


def save_config(config: Dict[str, Any]) -> None:
    """Saves the configuration dictionary to the chosen YAML file."""
    with open(file=CONFIG_FILE, mode='w', encoding='utf-8') as f:
        yaml.dump(data=config, stream=f, sort_keys=False)
