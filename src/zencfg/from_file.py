"""File-based configuration loading utilities."""

import sys
import types
import importlib.util
from contextlib import contextmanager
from pathlib import Path
from typing import Type, Union, Tuple
import uuid

from .config import ConfigBase


@contextmanager
def temporary_package_context(config_path: Path, module_parts: Tuple[str, ...]):
    """Create a temporary package structure for loading configs with relative imports.
    
    Parameters
    ----------
    config_path : Path
        The root directory of the config package
    module_parts : Tuple[str, ...]
        The module hierarchy (e.g., ('experiments', 'nlp', 'transformer'))
        
    Yields
    ------
    str
        The full module name to use for importing
    """
    # Generate unique namespace to avoid any conflicts
    unique_id = uuid.uuid4().hex[:8]
    base_package = f"_zencfg_temp_{unique_id}"
    
    # Track what we create for cleanup
    created_modules = []
    original_syspath = sys.path.copy()
    
    try:
        # Add config_path to sys.path for importing
        sys.path.insert(0, str(config_path))
        
        # Build the package hierarchy
        # For ('experiments', 'nlp', 'transformer'), create:
        # _zencfg_temp_xxx
        # _zencfg_temp_xxx.experiments
        # _zencfg_temp_xxx.experiments.nlp
        current_package = base_package
        current_path = config_path
        
        # Create base package
        base_module = types.ModuleType(base_package)
        base_module.__path__ = [str(config_path)]
        base_module.__package__ = base_package
        base_module.__file__ = None
        sys.modules[base_package] = base_module
        created_modules.append(base_package)
        
        # Create intermediate packages
        for i, part in enumerate(module_parts[:-1]):
            current_package = f"{current_package}.{part}"
            current_path = current_path / part
            
            package = types.ModuleType(current_package)
            package.__path__ = [str(current_path)]
            package.__package__ = current_package
            package.__file__ = None
            sys.modules[current_package] = package
            created_modules.append(current_package)
        
        # Full module name
        full_module_name = f"{base_package}.{'.'.join(module_parts)}"
        
        yield full_module_name, base_package
        
    finally:
        # Clean up sys.path
        sys.path[:] = original_syspath
        
        # Clean up all created modules and any submodules
        modules_to_remove = [
            name for name in sys.modules 
            if name.startswith(base_package)
        ]
        for name in modules_to_remove:
            sys.modules.pop(name, None)


def load_config_from_file(
    config_path: Union[str, Path],
    config_file: Union[str, Path],
    config_name: str
) -> Union[Type[ConfigBase], ConfigBase]:
    """Load a configuration from a Python file with full relative import support.
    
    This function loads configurations from Python files, properly handling
    relative imports within the config package structure. The config module
    is loaded in a temporary namespace to avoid conflicts with existing modules.
    
    Parameters
    ----------
    config_path : Union[str, Path]
        Root directory of your config package. This is where relative imports
        are resolved from. Use "." for configs in the current directory.
    config_file : Union[str, Path]
        Path to the config file relative to config_path.
        Can be a simple name ("config.py") or nested path ("models/bert.py").
    config_name : str
        Name of the ConfigBase class or instance to load from the file.
    
    Returns
    -------
    Union[Type[ConfigBase], ConfigBase]
        The loaded configuration class or instance.
    
    Raises
    ------
    FileNotFoundError
        If config_path/config_file doesn't exist
    ImportError
        If the file cannot be imported (e.g., syntax error, import error)
    AttributeError
        If config_name is not found in the file
    TypeError
        If config_name is not a ConfigBase class or instance
    ValueError
        If config_file is an absolute path
    
    Examples
    --------
    >>> # Simple config in current directory
    >>> config = load_config_from_file(".", "config.py", "MyConfig")
    >>> 
    >>> # Config in subdirectory
    >>> config = load_config_from_file("configs/", "base.py", "BaseConfig")
    >>> 
    >>> # Nested config with relative imports
    >>> config = load_config_from_file(
    ...     config_path="configs/",
    ...     config_file="experiments/nlp/transformer.py",
    ...     config_name="TransformerConfig"
    ... )
    >>> # This file can use: from ...base import BaseConfig
    >>> 
    >>> # Using Path objects
    >>> from pathlib import Path
    >>> config = load_config_from_file(
    ...     config_path=Path("project/configs"),
    ...     config_file=Path("models") / "bert.py",
    ...     config_name="BertConfig"
    ... )
    
    Notes
    -----
    The config file is executed as Python code. Only load configs from
    trusted sources. Module-level code in the config will execute with
    full permissions. The module namespace is temporary and will be cleaned
    up, but any side effects (file I/O, environment changes) will persist.
    
    **Implementation Details:**
    
    The function creates a temporary package structure in `sys.modules` using
    a unique namespace (`_zencfg_temp_<uuid>`). This approach ensures:
    
    - Relative imports are resolved correctly based on the package structure
    - No permanent modifications to `sys.path` or `sys.modules`
    - Complete cleanup after config loading
    - No conflicts with existing modules in the application
    """
    # Convert to Path objects and validate
    config_path = Path(config_path).resolve()
    config_file = Path(config_file)
    
    # Validate config_file is relative
    if config_file.is_absolute():
        raise ValueError(
            f"config_file must be relative to config_path, got absolute path: {config_file}"
        )
    
    # Check that the file exists
    full_path = config_path / config_file
    if not full_path.exists():
        raise FileNotFoundError(f"Config file not found: {full_path}")
    
    if not full_path.is_file():
        raise ValueError(f"Path is not a file: {full_path}")
    
    # Build module hierarchy from config_file
    # "experiments/nlp/transformer.py" -> ("experiments", "nlp", "transformer")
    module_parts = config_file.with_suffix('').parts
    
    # Use temporary package context for clean loading
    with temporary_package_context(config_path, module_parts) as (full_module_name, base_package):
        # Create module spec
        spec = importlib.util.spec_from_file_location(
            full_module_name,
            full_path,
            submodule_search_locations=[]
        )
        
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create module spec for {full_path}")
        
        # Create the module
        module = importlib.util.module_from_spec(spec)
        
        # Set the proper package for relative imports
        if len(module_parts) > 1:
            # e.g., _zencfg_temp_xxx.experiments.nlp for transformer.py
            module.__package__ = '.'.join([base_package] + list(module_parts[:-1]))
        else:
            # Single file at root level
            module.__package__ = base_package
        
        # Register in sys.modules before executing
        sys.modules[full_module_name] = module
        
        try:
            # Execute the module
            spec.loader.exec_module(module)
            
            # Extract the config
            try:
                config_item = getattr(module, config_name)
            except AttributeError:
                available = [
                    name for name in dir(module) 
                    if not name.startswith('_')
                ]
                raise AttributeError(
                    f"Config '{config_name}' not found in {config_file}. "
                    f"Available items: {', '.join(available[:5])}"
                    f"{'...' if len(available) > 5 else ''}"
                )
            
            # Validate it's a ConfigBase
            if isinstance(config_item, type) and issubclass(config_item, ConfigBase):
                return config_item
            elif isinstance(config_item, ConfigBase):
                return config_item
            else:
                raise TypeError(
                    f"'{config_name}' must be a ConfigBase class or instance, "
                    f"got {type(config_item).__name__}"
                )
                
        finally:
            # Module cleanup is handled by the context manager
            pass