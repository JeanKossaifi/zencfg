"""File-based configuration loading utilities."""

import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Type, Union, Optional, Dict
import importlib.util

from .config import ConfigBase


@contextmanager
def temporary_module_context(file_path: Path):
    """Temporarily register module hierarchy for relative imports.
    
    Creates a temporary module structure in sys.modules to enable relative
    imports within the config file, then cleans everything up afterward.
    """
    temp_modules = []
    saved_modules = {}
    original_path = sys.path.copy()
    added_to_path = False
    
    try:
        # Try to build module hierarchy relative to cwd
        try:
            relative_path = file_path.relative_to(Path.cwd())
            parts = relative_path.with_suffix('').parts
            
            # Register parent packages (e.g., for configs/models/exp.py: configs, configs.models)
            for i in range(len(parts) - 1):
                module_name = '.'.join(parts[:i+1])
                if module_name not in sys.modules:
                    # Create a temporary parent package
                    parent = types.ModuleType(module_name)
                    parent.__path__ = [str(Path.cwd() / '/'.join(parts[:i+1]))]
                    parent.__package__ = module_name
                    sys.modules[module_name] = parent
                    temp_modules.append(module_name)
                else:
                    # Save existing module to restore later
                    saved_modules[module_name] = sys.modules[module_name]
            
            module_name = '.'.join(parts)
            yield module_name, parts, False  # False = don't need sys.path help
            
        except ValueError:
            # File not relative to cwd - set up for external file
            # For external files, we need to add parent to sys.path for relative imports
            parent_dir = str(file_path.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
                added_to_path = True
            
            # Create a package context based on file's directory
            # This enables sibling imports (from .other import ...)
            module_name = file_path.stem
            
            # Register the parent directory as a package
            parent_package = f"_temp_pkg_{id(file_path)}"
            if parent_package not in sys.modules:
                pkg = types.ModuleType(parent_package)
                pkg.__path__ = [parent_dir]
                pkg.__package__ = parent_package
                sys.modules[parent_package] = pkg
                temp_modules.append(parent_package)
            
            # Module name within the package
            full_module_name = f"{parent_package}.{module_name}"
            yield full_module_name, [parent_package, module_name], True  # True = using sys.path
            
    finally:
        # Clean up temporary modules
        for name in temp_modules:
            sys.modules.pop(name, None)
        # Restore any saved modules
        for name, mod in saved_modules.items():
            sys.modules[name] = mod
        # Restore sys.path if we modified it
        if added_to_path:
            sys.path[:] = original_path


def extract_config_from_module(module, config_name: Optional[str] = None) -> Union[Type[ConfigBase], ConfigBase]:
    """Extract a ConfigBase class or instance from a loaded module.
    
    If config_name is specified, returns that specific item.
    Otherwise, auto-detects ConfigBase subclasses.
    """
    # If config_name specified, get it directly
    if config_name:
        try:
            config_item = getattr(module, config_name)
        except AttributeError:
            raise AttributeError(f"Config '{config_name}' not found in module")
            
        # Check if it's a class or instance
        if isinstance(config_item, type):
            if not issubclass(config_item, ConfigBase):
                raise TypeError(f"'{config_name}' is not a ConfigBase subclass")
            return config_item
        elif isinstance(config_item, ConfigBase):
            return config_item
        else:
            raise TypeError(f"'{config_name}' is neither a ConfigBase class nor instance")
    
    # Auto-detect ConfigBase classes
    config_classes = []
    config_instances = []
    
    for name in dir(module):
        if name.startswith('_'):
            continue
        try:
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, ConfigBase) and obj is not ConfigBase:
                # Check if defined in this module (not imported)
                if hasattr(obj, '__module__') and obj.__module__ == module.__name__:
                    config_classes.append(obj)
            elif isinstance(obj, ConfigBase):
                config_instances.append(obj)
        except:
            continue
    
    # Prefer classes over instances
    if config_classes:
        if len(config_classes) == 1:
            return config_classes[0]
        else:
            # Multiple classes - pick the most specific (deepest in hierarchy)
            return max(config_classes, key=lambda cls: len(cls.__mro__))
    elif config_instances:
        return config_instances[0]
    else:
        raise ValueError(f"No ConfigBase class or instance found in module")


def load_config_from_file(file_path: Union[str, Path], config_name: Optional[str] = None) -> Union[Type[ConfigBase], ConfigBase]:
    """Load a config class or instance from a file.
    
    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the Python file containing the config
    config_name : Optional[str]
        Name of the config to load. If None, auto-detects ConfigBase subclasses.
        
    Returns
    -------
    Union[Type[ConfigBase], ConfigBase]
        The config class or instance found in the file
        
    Notes
    -----
    This function temporarily registers the module hierarchy to enable relative
    imports within config files. The environment is fully cleaned up afterward.
    """
    file_path = Path(file_path).resolve()
    
    if not file_path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")
    
    # Use temporary module context for clean relative imports
    with temporary_module_context(file_path) as (module_name, parts, uses_syspath):
        # Try loading with proper module hierarchy (enables relative imports)
        if parts is not None:
            try:
                spec = importlib.util.spec_from_file_location(
                    module_name,
                    file_path,
                    submodule_search_locations=[str(file_path.parent)]
                )
                
                if spec is None or spec.loader is None:
                    raise ImportError(f"Could not create module spec for {file_path}")
                
                module = importlib.util.module_from_spec(spec)
                
                # Set package context for relative imports
                if len(parts) > 1:
                    module.__package__ = '.'.join(parts[:-1])
                else:
                    module.__package__ = None
                
                # Temporarily register the module
                sys.modules[module_name] = module
                try:
                    spec.loader.exec_module(module)
                    return extract_config_from_module(module, config_name)
                finally:
                    sys.modules.pop(module_name, None)
                    
            except (ImportError, AttributeError, ValueError) as e:
                # If using temp package failed, try without it
                if not uses_syspath:
                    # Fall back to simple loading for files under cwd
                    pass
                else:
                    # For external files, the error is real
                    raise
        
        # Fallback: Simple file loading (backward compatibility)
        # Only used when temp module context isn't helping
        if not uses_syspath:
            file_dir = str(file_path.parent)
            original_path = sys.path.copy()
            
            try:
                if file_dir not in sys.path:
                    sys.path.insert(0, file_dir)
                
                spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
                if spec is None or spec.loader is None:
                    raise ImportError(f"Could not load module from {file_path}")
                    
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                return extract_config_from_module(module, config_name)
                
            finally:
                # Restore original sys.path
                sys.path[:] = original_path 