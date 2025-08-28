import sys
import warnings
from typing import Type, Union, Optional, Any
from pathlib import Path

from .from_dict import make_config_from_flat_dict
from .config import ConfigBase


def make_config(source: Union[Type[ConfigBase], ConfigBase, str, Path], name: Optional[str] = None, /, **overrides) -> ConfigBase:
    """Create a config instance from any source with overrides.
    
    Parameters
    ----------
    source : Union[Type[ConfigBase], ConfigBase, str, Path]
        Source to create config from:
        - ConfigBase class: instantiate with overrides
        - ConfigBase instance: apply overrides to copy
        - str/Path: file path to load config from (auto-detects class if name not provided)
    name : str, optional
        Name of class/instance to load from file. If None, auto-detects ConfigBase subclass.
    **overrides
        Keyword arguments to override in the config
        
    Returns
    -------
    ConfigBase
        Config instance with overrides applied
        
    Examples
    --------
    >>> # From class
    >>> config = make_config(TrainingConfig, batch_size=32)
    >>> 
    >>> # From file - name is now optional!
    >>> config = make_config("configs/experiment.py", epochs=100)  # Auto-detects
    >>> config = make_config("configs.py", "TrainingConfig", epochs=100)  # Explicit
    >>>
    >>> # From instance
    >>> base = TrainingConfig()
    >>> config = make_config(base, learning_rate=0.001)
    """
    if isinstance(source, type) and issubclass(source, ConfigBase):
        # It's a class - instantiate with overrides
        return source(**overrides)
        
    elif isinstance(source, ConfigBase):
        # It's an instance - apply overrides
        if not overrides:
            return source  # No changes needed
        current_dict = source.to_dict(flatten=True)
        current_dict.update({k: str(v) for k, v in overrides.items()})  # Convert to strings for make_config_from_flat_dict
        return make_config_from_flat_dict(source.__class__, current_dict)
        
    elif isinstance(source, (str, Path)):
        # It's a file path - name is required
        if name is None:
            raise ValueError("name parameter is required when loading from a file")
        from .from_file import load_config_from_file
        
        # Parse the source path to separate config_path and config_file
        source_path = Path(source).resolve()
        if source_path.is_file():
            # Use parent directory as config_path, filename as config_file
            config_path = source_path.parent
            config_file = source_path.name
        else:
            raise FileNotFoundError(f"Config file not found: {source}")
        
        loaded_item = load_config_from_file(config_path, config_file, config_name=name)
        return make_config(loaded_item, **overrides)  # Recursive call
        
    else:
        raise TypeError(f"Unsupported source type: {type(source)}. Expected ConfigBase class, instance, or file path.")


def make_config_from_cli(source: Union[Type[ConfigBase], ConfigBase, str, Path], name: Optional[str] = None, /, strict: bool = False) -> ConfigBase:
    """Create a config instance with command-line argument overrides.
    
    Parameters
    ----------
    source : Union[Type[ConfigBase], ConfigBase, str, Path]
        Source to create config from (class, instance, or file path)
    name : str, optional
        Name of class/instance to load from file. If None, auto-detects ConfigBase subclass.
    strict : bool, default=False
        If True, raises errors on type conversion failures
        
    Returns
    -------
    ConfigBase
        Config instance with command-line overrides applied
        
    Examples
    --------
    >>> # From class
    >>> config = make_config_from_cli(TrainingConfig)
    >>>
    >>> # From file - name is now optional!
    >>> config = make_config_from_cli("configs/experiment.py")  # Auto-detects
    >>> config = make_config_from_cli("configs.py", "TrainingConfig")  # Explicit
    """
    args = sys.argv[1:]  # Skip the script name

    if len(args) % 2 != 0:
        raise ValueError("Arguments must be in pairs like: --model._config_name MyModel --model.layers 24")

    # Build arg dict from command line
    arg_dict = {}
    for i in range(0, len(args), 2):
        key = args[i].lstrip('-')
        arg_dict[key] = args[i + 1]

    if isinstance(source, type) and issubclass(source, ConfigBase):
        # It's a class - create instance with CLI overrides
        return make_config_from_flat_dict(source, arg_dict, strict=strict)
        
    elif isinstance(source, ConfigBase):
        # It's an instance - merge CLI overrides with existing values
        current_dict = source.to_dict(flatten=True)
        current_dict.update(arg_dict)  # CLI args override existing values
        return make_config_from_flat_dict(source.__class__, current_dict, strict=strict)
        
    elif isinstance(source, (str, Path)):
        # It's a file path - name is required
        if name is None:
            raise ValueError("name parameter is required when loading from a file")
        from .from_file import load_config_from_file
        
        # Parse the source path to separate config_path and config_file
        source_path = Path(source).resolve()
        if source_path.is_file():
            # Use parent directory as config_path, filename as config_file
            config_path = source_path.parent
            config_file = source_path.name
        else:
            raise FileNotFoundError(f"Config file not found: {source}")
        
        loaded_item = load_config_from_file(config_path, config_file, config_name=name)
        return make_config_from_cli(loaded_item, strict=strict)  # Recursive call
        
    else:
        raise TypeError(f"Unsupported source type: {type(source)}. Expected ConfigBase class, instance, or file path.")
