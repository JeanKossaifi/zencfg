"""File-based configuration loading utilities."""

import hashlib
import importlib.util
import sys
import types
from pathlib import Path
from typing import Type, Union

from .config import ConfigBase


def _ensure_package(name: str, path: Path, parent: str = "") -> str:
    """Make sure package `name` exists in sys.modules; return its full name."""
    full_name = f"{parent}.{name}" if parent else name
    if full_name not in sys.modules:
        package = types.ModuleType(full_name)
        package.__path__ = [str(path)]
        package.__package__ = full_name
        sys.modules[full_name] = package
    return full_name


def _load_module(module_name: str, package: str, full_path: Path, config_path: Path):
    """Import the config file as `module_name`, keeping it in sys.modules."""
    spec = importlib.util.spec_from_file_location(module_name, full_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create module spec for {full_path}")

    module = importlib.util.module_from_spec(spec)
    module.__package__ = package
    sys.modules[module_name] = module
    # Allow absolute imports of sibling modules while the config file executes
    sys.path.insert(0, str(config_path))
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    finally:
        try:
            sys.path.remove(str(config_path))
        except ValueError:
            pass  # the config file itself removed it
    module.__zencfg_mtime__ = full_path.stat().st_mtime
    return module


def load_config_from_file(
    config_path: Union[str, Path],
    config_file: Union[str, Path],
    config_name: str
) -> Union[Type[ConfigBase], ConfigBase]:
    """Load a configuration from a Python file, with relative import support.

    The file is imported as a regular module under a stable, path-derived
    name, so that:

    - relative imports inside the config package work,
    - loading the same file twice returns the same classes (isinstance and
      the subclass registry stay consistent),
    - loaded configs can be pickled within the process (e.g. inside a
      torch.save checkpoint). Unpickling in a *different* process requires
      the config classes to be importable there; for that, keep configs in
      an importable module of your project instead of loading from file.

    If the file changed on disk since it was loaded, it is reloaded.

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
        If the file cannot be imported (e.g. syntax error, import error)
    AttributeError
        If config_name is not found in the file
    TypeError
        If config_name is not a ConfigBase class or instance
    ValueError
        If config_file is an absolute path

    Examples
    --------
    >>> # Simple config in the current directory
    >>> config = load_config_from_file(".", "config.py", "MyConfig")
    >>>
    >>> # Nested config with relative imports
    >>> config = load_config_from_file(
    ...     config_path="configs/",
    ...     config_file="experiments/nlp/transformer.py",
    ...     config_name="TransformerConfig"
    ... )
    >>> # That file can use: from ...base import BaseConfig

    Notes
    -----
    The config file is executed as Python code. Only load configs from
    trusted sources: module-level code in the config will execute with
    full permissions.
    """
    config_path = Path(config_path).resolve()
    config_file = Path(config_file)

    if config_file.is_absolute():
        raise ValueError(
            f"config_file must be relative to config_path, got absolute path: {config_file}")

    full_path = config_path / config_file
    if not full_path.exists():
        raise FileNotFoundError(f"Config file not found: {full_path}")
    if not full_path.is_file():
        raise ValueError(f"Path is not a file: {full_path}")

    # Stable module hierarchy derived from the paths:
    # configs/experiments/nlp/transformer.py ->
    #   _zencfg_<digest>.experiments.nlp.transformer
    digest = hashlib.md5(str(config_path).encode()).hexdigest()[:8]
    package = _ensure_package(f"_zencfg_{digest}", config_path)
    current_path = config_path
    module_parts = config_file.with_suffix('').parts
    for part in module_parts[:-1]:
        current_path = current_path / part
        package = _ensure_package(part, current_path, package)
    module_name = f"{package}.{module_parts[-1]}"

    module = sys.modules.get(module_name)
    if module is None or getattr(module, "__zencfg_mtime__", None) != full_path.stat().st_mtime:
        module = _load_module(module_name, package, full_path, config_path)

    try:
        config_item = getattr(module, config_name)
    except AttributeError:
        available = [name for name in dir(module) if not name.startswith('_')]
        raise AttributeError(
            f"Config '{config_name}' not found in {config_file}. "
            f"Available items: {', '.join(available[:5])}"
            f"{'...' if len(available) > 5 else ''}") from None

    if isinstance(config_item, type) and issubclass(config_item, ConfigBase):
        return config_item
    if isinstance(config_item, ConfigBase):
        return config_item
    raise TypeError(
        f"'{config_name}' must be a ConfigBase class or instance, "
        f"got {type(config_item).__name__}")
