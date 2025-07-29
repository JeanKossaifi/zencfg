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
        - str/Path: file path to load config from
    name : str, optional
        Required when source is a file path. Name of class/instance to load.
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
    >>> # From file
    >>> config = make_config("configs.py", "TrainingConfig", epochs=100)
    >>> config = make_config(Path("configs.py"), "TrainingConfig", epochs=100)
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
        # It's a file path - load and handle
        if name is None:
            raise ValueError("name parameter is required when loading from file")
        from .from_file import load_config_from_file
        loaded_item = load_config_from_file(str(source), name)
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
        Required when source is a file path. Name of class/instance to load.
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
    >>> # From file  
    >>> config = make_config_from_cli("configs.py", "TrainingConfig")
    >>> config = make_config_from_cli(Path("configs.py"), "TrainingConfig")
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
        # It's a file path - load and handle
        if name is None:
            raise ValueError("name parameter is required when loading from file")
        from .from_file import load_config_from_file
        loaded_item = load_config_from_file(str(source), name)
        return make_config_from_cli(loaded_item, strict=strict)  # Recursive call
        
    else:
        raise TypeError(f"Unsupported source type: {type(source)}. Expected ConfigBase class, instance, or file path.")
