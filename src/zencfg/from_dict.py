import warnings
import logging
from typing import Any, Dict, get_type_hints, Union, get_origin, get_args
from pydantic import ValidationError, TypeAdapter

from .config import ConfigBase

logger = logging.getLogger(__name__)

# -------------------------------------------
# Utilities for detecting configbase in union
# -------------------------------------------
MISSING = object()  # sentinel


def is_configbase_type(tp: Any) -> bool:
    """
    Returns True if type 'tp' is a subclass of ConfigBase OR a Union that includes a ConfigBase subclass.
    """
    origin = get_origin(tp)
    if origin is Union:
        return any(
            isinstance(arg, type) and issubclass(arg, ConfigBase)
            for arg in get_args(tp)
        )
    else:
        return (isinstance(tp, type) and issubclass(tp, ConfigBase))

def extract_configbase_member(tp: Any) -> Any:
    """
    If 'tp' is Union[ConfigBase, NoneType], return ConfigBase.
    Otherwise return tp as-is.
    """
    origin = get_origin(tp)
    if origin is Union:
        for arg in get_args(tp):
            if isinstance(arg, type) and issubclass(arg, ConfigBase):
                return arg
    return tp

# -------------------------------------------
# Value parsing with Pydantic v2 TypeAdapter
# -------------------------------------------
def parse_value_to_type(raw_val: Any, expected_type: Any, strict: bool, path: str) -> Any:
    """
    Use Pydantic's TypeAdapter to parse 'raw_val' against its 'expected_type'.
    We add 'arbitrary_types_allowed=True' so it doesn't choke on ConfigBase classes.

    Note: path is the full nested key, passed only to print useful error messages.
    """
    adapter = TypeAdapter(
        expected_type,
        config={"arbitrary_types_allowed": True}  # Key fix for strict mode with custom classes
    )
    try:
        logger.debug(f"Parsing key={path} with type={expected_type}, raw_value={raw_val}")
        return adapter.validate_python(raw_val)
    except ValidationError as e:
        msg = f"Failed to parse key '{path}', with value={raw_val} and {expected_type=}. Full error: {e}"
        if strict:
            raise TypeError(msg) from e
        else:
            warnings.warn(msg)
            return raw_val

# -------------------------------------------
# Flatten -> Nested conversion
# -------------------------------------------
def update_nested_dict_from_flat(nested_dict, key, value, separator='.'):
    """Updates inplace a nested dict using a flattened key with nesting represented by a separator,
    for a single nested key (e.g. param1.subparam2.subsubparam3) and corresponding value.

    Parameters
    ----------
    nested_dict : dict
    key : str
        nested key of the form f"param1{separator}param2{separator}..."
    value : Object
    separator : str, default is '.'
    """
    keys = key.split(separator, 1)
    if len(keys) == 1:
        nested_dict[keys[0]] = value
    else:
        k, rest = keys
        # If k exists but is not a dict, convert current value to a dict 
        if k in nested_dict and not isinstance(nested_dict[k], dict):
            current_val = nested_dict[k]
            nested_dict[k] = {}  # Start fresh dict for nested values
            nested_dict[k]["_name"] = current_val  # Store original value as _name
        # Create dict if doesn't exist
        elif k not in nested_dict:
            nested_dict[k] = {}
        update_nested_dict_from_flat(nested_dict[k], rest, value, separator=separator)

def flat_dict_to_nested(flat_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a flat dictionary with dot notation to a nested dictionary."""
    sorted_items = sorted(flat_dict.items(), key=lambda x: len(x[0].split('.')))
    nested_dict = {}
    for key, value in sorted_items:
        update_nested_dict_from_flat(nested_dict, key, value)
    return nested_dict

def join_path(base: str, field_name: str) -> str:
    return field_name if not base else f"{base}.{field_name}"

# -------------------------------------------
# Build config from nested dict (top-down)
# -------------------------------------------
def cfg_from_nested_dict(config_cls: Any, nested_dict: Dict[str, Any], strict: bool,
                      path: str = "") -> Any:
    """
    Recursively build an instance of 'config_cls' from a nested dictionary.
    """
    logger.debug("Building config for '%s' at path='%s' with data=%r",
                 config_cls.__name__, path, nested_dict)

    # 1) Determine actual class to use
    if issubclass(config_cls, ConfigBase):
        name_val = nested_dict.get("_name", None)
        actual_cls = config_cls._get_subclass_by_name(name_val)
    else:
        actual_cls = config_cls

    # 2) Gather type hints & defaults
    type_hints = get_type_hints(actual_cls, include_extras=True)
    defaults = {}
    for attr_name in dir(actual_cls):
        if not attr_name.startswith("__"):
            val = getattr(actual_cls, attr_name)
            if not callable(val):
                defaults[attr_name] = val

    # 3) Validate unknown keys
    recognized_keys = set(type_hints.keys()) | {"_name"}
    for key in nested_dict:
        if key not in recognized_keys:
            full_path = join_path(path, key)
            raise ValueError(
                f"Unknown key '{full_path}' in {actual_cls.__name__}. "
                "Check for typos or remove unused config keys."
            )

    # 4) Build init_values
    init_values = {}
    for field_name, field_type in type_hints.items():
        full_path = join_path(path, field_name)

        if field_name in nested_dict:
            raw_val = nested_dict[field_name]
            if is_configbase_type(field_type):
                cb_type = extract_configbase_member(field_type)
                if not isinstance(raw_val, dict):
                    raise TypeError(
                        f"Value for ConfigBase field '{full_path}' must be a dict, got {type(raw_val)}"
                    )
                nested_val = cfg_from_nested_dict(cb_type, raw_val, strict, path=full_path)
                init_values[field_name] = nested_val
            else:
                parsed_val = parse_value_to_type(raw_val, field_type, strict, path=full_path)
                init_values[field_name] = parsed_val
        else:
            # Field not in nested_dict
            default_val = defaults.get(field_name, MISSING)
            if default_val is MISSING:
                if strict:
                    raise ValueError(
                        f"Missing required field '{field_name}' in {actual_cls.__name__} (strict mode)."
                    )
                else:
                    if is_configbase_type(field_type):
                        cb_type = extract_configbase_member(field_type)
                        init_values[field_name] = cb_type()  # use default ctor
                    else:
                        init_values[field_name] = None
            else:
                init_values[field_name] = default_val

    # 5) Instantiate
    instance = actual_cls.__new__(actual_cls)
    for k, v in init_values.items():
        setattr(instance, k, v)
    for k, v in defaults.items():
        if not hasattr(instance, k):
            setattr(instance, k, v)

    return instance


def cfg_from_flat_dict(config_cls: Any, flat_dict: Dict[str, Any], strict: bool = False) -> Any:
    """Instantiates a config class from a flat dictionary.
    
    Parameters
    ----------
    config_cls : ConfigBase
        The config class to instantiate.
    flat_dict : Dict[str, Any]
        "Flat" dict of the form {"key1": value1, "key2": value2, "key1.subkey": "value", ...}
        It's a single level dict (no nesting). Instead, the **keys** are nested using dots.
    strict : bool
        If True, raise a TypeError on parsing errors. Otherwise, log a warning.

    Returns
    -------
    ConfigBase
        An instance of 'config_cls' with values from 'flat_dict' with the loaded values.
    """
    nested = flat_dict_to_nested(flat_dict)
    return cfg_from_nested_dict(config_cls, nested, strict)

