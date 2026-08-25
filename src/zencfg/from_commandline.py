"""Create configs with overrides from keyword arguments or the command line."""

import sys
from pathlib import Path
from typing import Optional, Type, Union

from .config import ConfigBase
from .from_dict import _deep_update, flat_dict_to_nested, make_config_from_flat_dict, make_config_from_nested_dict


def make_config(source: Union[Type[ConfigBase], ConfigBase, str, Path], name: Optional[str] = None, /, **overrides) -> ConfigBase:
    """Create a config instance from any source, with overrides.

    Parameters
    ----------
    source : Union[Type[ConfigBase], ConfigBase, str, Path]
        Source to create the config from:
        - ConfigBase class: instantiate it with the overrides
        - ConfigBase instance: apply the overrides to a copy
        - str/Path: path of a Python file to load the config from (requires name)
    name : str, optional
        Name of the class or instance to load, when source is a file path.
    **overrides
        Values to override in the config. Nested fields use dotted keys,
        passed via unpacking: ``make_config(cfg, **{"model.layers": 24})``.

    Returns
    -------
    ConfigBase
        Config instance with overrides applied.

    Examples
    --------
    >>> # From a class
    >>> config = make_config(TrainingConfig, batch_size=32)
    >>>
    >>> # From a file (name of the class or instance to load is required)
    >>> config = make_config("configs/experiment.py", "TrainingConfig", epochs=100)
    >>>
    >>> # From an instance
    >>> config = make_config(TrainingConfig(), learning_rate=0.001)
    """
    if isinstance(source, type) and issubclass(source, ConfigBase):
        return make_config_from_flat_dict(source, overrides)

    elif isinstance(source, ConfigBase):
        if not overrides:
            return source  # No changes needed
        merged = _deep_update(source.to_dict(), flat_dict_to_nested(dict(overrides)))
        return make_config_from_nested_dict(type(source), merged)

    elif isinstance(source, (str, Path)):
        if name is None:
            raise ValueError("name parameter is required when loading from a file")
        from .from_file import load_config_from_file

        source_path = Path(source).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Config file not found: {source}")
        loaded_item = load_config_from_file(source_path.parent, source_path.name, config_name=name)
        return make_config(loaded_item, **overrides)

    else:
        raise TypeError(f"Unsupported source type: {type(source)}. Expected ConfigBase class, instance, or file path.")


def _parse_cli_arguments(args) -> dict:
    """Parse ["--key", "value", "--key2=value2", ...] into {"key": value, ...}."""
    arg_dict = {}
    i = 0
    while i < len(args):
        arg = args[i]
        key = arg.lstrip('-') if isinstance(arg, str) else arg
        if not isinstance(arg, str) or not arg.startswith('-'):
            raise ValueError(
                f"Expected an argument name like --key, got '{arg}'. "
                "Arguments must be in pairs like: --model.layers 24 (or --model.layers=24)")
        if '=' in key:
            key, _, value = key.partition('=')
            i += 1
        else:
            if i + 1 >= len(args):
                raise ValueError(
                    f"Missing value for argument '--{key}'. "
                    "Arguments must be in pairs like: --model.layers 24 (or --model.layers=24)")
            value = args[i + 1]
            i += 2
        arg_dict[key] = value
    return arg_dict


def _cli_help_lines(config, prefix: str = "", seen: frozenset = frozenset()) -> list:
    """One help line per field (dotted paths for nested configs).

    `config` is a ConfigBase class or instance; with an instance, its current
    values are shown as the defaults (so `--model cnnconfig --help` shows the
    CNN fields). `seen` guards against self-referential configs.
    """
    from .from_dict import extract_configbase_member

    config_cls = config if isinstance(config, type) else type(config)
    lines = []
    for field_name, field in config_cls.model_fields.items():
        path = f"{prefix}{field_name}"
        if isinstance(config, type):
            value = field.default if not field.is_required() else None
        else:
            value = getattr(config, field_name)
        config_type = extract_configbase_member(field.annotation)
        if isinstance(config_type, type) and issubclass(config_type, ConfigBase):
            choices = [config_type._config_name, *config_type._registry]
            if isinstance(value, ConfigBase):
                default = value._config_name
            else:
                default = "required" if field.is_required() else repr(value)
            lines.append(f"  --{path} {{{', '.join(choices)}}}  (default: {default})")
            if config_type not in seen:
                lines.extend(_cli_help_lines(value if isinstance(value, ConfigBase) else config_type,
                                             prefix=f"{path}.", seen=seen | {config_type}))
        else:
            type_name = getattr(field.annotation, "__name__", str(field.annotation))
            default = repr(value) if not field.is_required() else "required"
            lines.append(f"  --{path} <{type_name}>  (default: {default})")
    return lines


def _print_cli_help(source, args) -> None:
    """Print available fields; selections already on the command line are applied."""
    config_cls = source if isinstance(source, type) else type(source)
    try:
        arg_dict = _parse_cli_arguments([a for a in args if a not in ("-h", "--help")])
        if isinstance(source, ConfigBase):
            merged = _deep_update(source.to_dict(), flat_dict_to_nested(arg_dict))
            resolved = make_config_from_nested_dict(config_cls, merged)
        else:
            resolved = make_config_from_flat_dict(config_cls, arg_dict)
    except Exception:
        resolved = source  # help must never fail: fall back to the defaults
    print(f"Usage: {Path(sys.argv[0]).name} [--field value ...]")
    print(f"\nFields of {config_cls.__name__} (nested fields use dots, "
          f"subclasses are selected by name):\n")
    print("\n".join(_cli_help_lines(resolved)))


def make_config_from_cli(
    config_or_path: Union[Type[ConfigBase], ConfigBase, str, Path],
    config_file: Optional[Union[str, Path]] = None,
    config_name: Optional[str] = None,
    *,
    strict: bool = False
) -> ConfigBase:
    """Create a config instance with command-line argument overrides.

    Arguments are read from sys.argv as ``--key value`` or ``--key=value``
    pairs, where nested fields use dots (``--model.layers 24``) and subclasses
    are selected by name (``--model cnnconfig``). Passing ``--help`` prints the
    available fields and exits.

    This function supports two usage patterns:

    1. Pass a ConfigBase class or instance directly
    2. Load from a file, using the same API as load_config_from_file

    Parameters
    ----------
    config_or_path : Union[Type[ConfigBase], ConfigBase, str, Path]
        Either:
        - A ConfigBase class or instance to apply CLI overrides to
        - A config_path root directory (when config_file is also provided)
        - A single file path (when config_file is None)
    config_file : Union[str, Path], optional
        If provided, config_or_path is treated as the root directory and this
        is the file's path relative to it (matching load_config_from_file).
    config_name : str, optional
        Name of the class or instance to load. Required when loading from file.
    strict : bool, default=False
        Kept for backward compatibility; validation is always on.

    Returns
    -------
    ConfigBase
        Config instance with command-line overrides applied.

    Examples
    --------
    >>> # From a class
    >>> config = make_config_from_cli(TrainingConfig)
    >>>
    >>> # From a file, relative to a config root directory
    >>> config = make_config_from_cli(
    ...     "configs/",
    ...     config_file="experiments/main.py",
    ...     config_name="MainConfig",
    ... )
    >>>
    >>> # From a single file path
    >>> config = make_config_from_cli("configs/experiment.py", config_name="TrainingConfig")
    """
    args = sys.argv[1:]  # Skip the script name
    help_requested = any(arg in ("-h", "--help") for arg in args if isinstance(arg, str))
    if not help_requested:
        arg_dict = _parse_cli_arguments(args)

    # File given relative to a config root directory
    if config_file is not None:
        if config_name is None:
            raise ValueError("config_name is required when loading from file")
        from .from_file import load_config_from_file

        loaded_item = load_config_from_file(config_or_path, config_file, config_name=config_name)
        return make_config_from_cli(loaded_item, strict=strict)

    source = config_or_path

    if isinstance(source, (str, Path)):
        if config_name is None:
            raise ValueError("config_name is required when loading from a file")
        from .from_file import load_config_from_file

        source_path = Path(source).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Config file not found: {source}")
        loaded_item = load_config_from_file(source_path.parent, source_path.name, config_name=config_name)
        return make_config_from_cli(loaded_item, strict=strict)

    if not (isinstance(source, ConfigBase)
            or (isinstance(source, type) and issubclass(source, ConfigBase))):
        raise TypeError(f"Unsupported config_or_path type: {type(source)}. "
                        "Expected ConfigBase class, instance, or file path.")

    if help_requested:
        _print_cli_help(source, args)
        sys.exit(0)

    if isinstance(source, ConfigBase):
        # Merge CLI overrides into the instance's current values
        merged = _deep_update(source.to_dict(), flat_dict_to_nested(arg_dict))
        return make_config_from_nested_dict(type(source), merged, strict=strict)

    return make_config_from_flat_dict(source, arg_dict, strict=strict)
