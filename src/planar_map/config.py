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
    """
    Load the default configuration from package resources.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the default shortcut and physics settings.
    """
    pkg = __package__ if __package__ else "planar_map"

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
    """
    Load the configuration from the working directory or user directory.

    If no configuration file exists, it creates one using the default
    settings. It also merges any missing default parameters into an
    existing configuration.

    Returns
    -------
    Dict[str, Any]
        The active configuration dictionary.
    """
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
        save_config(default_conf)
        return default_conf

    # Load existing user/cwd configuration
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}

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
        save_config(config)

    return config


def save_config(config: Dict[str, Any]) -> None:
    """
    Save the configuration dictionary to the active YAML file.

    Parameters
    ----------
    config : Dict[str, Any]
        The configuration dictionary to save.
    """
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, sort_keys=False)
