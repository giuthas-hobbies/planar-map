import os
import yaml
from typing import Dict, Any


CONFIG_FILE = 'config.yaml'

DEFAULT_CONFIG: Dict[str, Any] = {
    'shortcuts': {
        'open_yaml': 'Ctrl+O',
        'create_node': 'Ctrl+N',
        'create_edge': 'Ctrl+E',
        'save_yaml': 'Ctrl+S',
        'delete_selected': 'Delete',
        'delete_selected_alt': 'Backspace',
        'edit_selected': 'Return',
        'export_graph': 'Ctrl+Shift+G',
        'export_markdown': 'Ctrl+Shift+M',
        'export_compilation': 'Ctrl+Shift+C',
        'edit_shortcuts': 'Ctrl+Shift+S'
    }
}


def load_config() -> Dict[str, Any]:
    """Loads the config file or creates it with defaults."""
    if not os.path.exists(path=CONFIG_FILE):
        save_config(config=DEFAULT_CONFIG)
        return DEFAULT_CONFIG

    with open(file=CONFIG_FILE, mode='r', encoding='utf-8') as f:
        config = yaml.safe_load(stream=f) or {}

    modified = False
    if 'shortcuts' not in config:
        config['shortcuts'] = {}

    for k, v in DEFAULT_CONFIG['shortcuts'].items():
        if k not in config['shortcuts']:
            config['shortcuts'][k] = v
            modified = True

    if modified:
        save_config(config=config)

    return config


def save_config(config: Dict[str, Any]) -> None:
    """Saves the configuration dictionary to the YAML file."""
    with open(file=CONFIG_FILE, mode='w', encoding='utf-8') as f:
        yaml.dump(data=config, stream=f, sort_keys=False)
