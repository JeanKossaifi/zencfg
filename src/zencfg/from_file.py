"""File-based configuration loading utilities."""

import sys
from pathlib import Path
from typing import Type, Union
import importlib.util

from .config import ConfigBase


def load_config_from_file(file_path: Union[str, Path], config_name: str) -> Union[Type[ConfigBase], ConfigBase]:
    """Load a config class or instance from a file."""
    file_path = Path(file_path).resolve()
    
    if not file_path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")
    
    # Add file directory to Python path temporarily
    file_dir = str(file_path.parent)
    original_path = sys.path.copy()
    
    try:
        if file_dir not in sys.path:
            sys.path.insert(0, file_dir)
        
        # Import the module
        module_name = file_path.stem
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {file_path}")
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Get the config class or instance
        try:
            config_item = getattr(module, config_name)
        except AttributeError:
            raise AttributeError(f"Config '{config_name}' not found in {file_path}")
        
        # Check if it's a class or instance
        if isinstance(config_item, type):
            if not issubclass(config_item, ConfigBase):
                raise TypeError(f"'{config_name}' is not a ConfigBase subclass")
            return config_item
        elif isinstance(config_item, ConfigBase):
            return config_item
        else:
            raise TypeError(f"'{config_name}' is neither a ConfigBase class nor instance")
        
    finally:
        # Restore original sys.path
        sys.path[:] = original_path 