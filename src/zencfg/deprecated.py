"""Deprecated functions for backward compatibility.

This module contains deprecated functions that will be removed in a future version.
Use the new make_config and make_config_from_cli functions instead.
"""

import warnings
from typing import Type

from .from_commandline import make_config_from_cli
from .config import ConfigBase


def cfg_from_commandline(config_class: Type[ConfigBase], strict: bool = False) -> ConfigBase:
    """Takes a Config class and returns an instance of it, with values updated from command line.
    
    .. deprecated:: 1.0.0
        Use ``make_config_from_cli()`` instead.
    """
    warnings.warn(
        "cfg_from_commandline is deprecated. Use make_config_from_cli() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return make_config_from_cli(config_class, strict=strict) 