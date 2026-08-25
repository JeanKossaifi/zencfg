"""Build config instances from flat (dotted-key) or nested dictionaries."""

from typing import Any, Dict, get_args, get_origin

from pydantic import ValidationError

from .config import (ConfigBase, _UNION_ORIGINS, _dump_value, _holds_config_instances,
                     _translate_validation_error)
from .config import is_configbase_type, parse_value_to_type  # noqa: F401 (re-exported)


def extract_configbase_member(tp: Any) -> Any:
    """If 'tp' is a Union including a ConfigBase subclass (e.g. Optional[MyConfig]
    or MyConfig | None), return that subclass. Otherwise return tp as-is."""
    if get_origin(tp) in _UNION_ORIGINS:
        for arg in get_args(tp):
            if isinstance(arg, type) and issubclass(arg, ConfigBase):
                return arg
    return tp


# -------------------------------------------
# Flat -> nested conversion
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
        # A previous plain value for k (e.g. "--model dit") was the config name
        if k in nested_dict and not isinstance(nested_dict[k], dict):
            nested_dict[k] = {"_config_name": nested_dict[k]}
        elif k not in nested_dict:
            nested_dict[k] = {}
        update_nested_dict_from_flat(nested_dict[k], rest, value, separator=separator)


def flat_dict_to_nested(flat_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a flat dictionary with dot notation to a nested dictionary."""
    sorted_items = sorted(flat_dict.items(), key=lambda item: len(item[0].split('.')))
    nested_dict = {}
    for key, value in sorted_items:
        update_nested_dict_from_flat(nested_dict, key, value)
    return nested_dict


# -------------------------------------------
# Build config from nested dict
# -------------------------------------------
def _is_config_dump(value: Any) -> bool:
    """A dict produced by ConfigBase.to_dict(), recognizable by '_config_name'."""
    return isinstance(value, dict) and isinstance(value.get("_config_name"), str)


def _config_names_match(base: dict, override: dict) -> bool:
    override_name = override.get("_config_name")
    if override_name is None:
        return True
    if not isinstance(override_name, str):
        raise ValueError(
            f"'_config_name' must be a string, got {type(override_name).__name__}: {override_name!r}")
    return override_name.lower() == base["_config_name"].lower()


def _deep_update(base: Any, override: Any) -> Any:
    """Merge override into a config dump (or a dict containing config dumps).

    Only config dumps are merged; plain dict values are replaced like any
    other value. A bare string overriding a config dump selects a subclass by
    name; selecting a different '_config_name' than base replaces base
    entirely, since values from another subclass would not make sense.
    """
    if _is_config_dump(base) and isinstance(override, str):
        override = {"_config_name": override}
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override
    if _is_config_dump(base):
        if not _config_names_match(base, override):
            return dict(override)
    elif not any(_is_config_dump(v) for v in base.values()):
        return override  # plain dict value: replace, don't merge
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(value, (dict, str)):
            merged[key] = _deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


def _prepare_values(config_cls: type, data: Dict[str, Any], strict: bool) -> Dict[str, Any]:
    """Prepare a nested dict for validation against config_cls.

    For ConfigBase fields, a bare name string is normalized to
    {"_config_name": name} and the user's values are merged into the field's
    default instance (see the README "Gotchas" section: overriding a parameter
    keeps the default subclass and its other values, while selecting a new
    '_config_name' starts fresh). Unless strict, missing required ConfigBase
    fields are filled with the category's defaults. String parsing and
    validation are handled by ConfigBase itself.
    """
    actual_cls = config_cls._get_subclass_by_name(data.get("_config_name"))
    prepared = {}
    for key, value in data.items():
        field = actual_cls.model_fields.get(key)
        config_type = extract_configbase_member(field.annotation) if field else None
        if isinstance(config_type, type) and issubclass(config_type, ConfigBase):
            if isinstance(value, str):
                value = {"_config_name": value}
            if isinstance(value, dict):
                if isinstance(field.default, ConfigBase):
                    value = _deep_update(field.default.to_dict(), value)
                value = _prepare_values(config_type, value, strict)
        elif (field is not None and isinstance(value, dict)
                and isinstance(field.default, dict) and _holds_config_instances(field.default)):
            # dotted overrides into a Dict[str, SomeConfig] field merge into
            # the default's entries instead of replacing the whole mapping
            value = _deep_update(_dump_value(field.default), value)
        prepared[key] = value

    if not strict:
        for name, field in actual_cls.model_fields.items():
            if name in prepared or not field.is_required():
                continue
            config_type = extract_configbase_member(field.annotation)
            if isinstance(config_type, type) and issubclass(config_type, ConfigBase):
                prepared[name] = _prepare_values(config_type, {}, strict)
    return prepared


def make_config_from_nested_dict(config_cls: Any, nested_dict: Dict[str, Any],
                                 strict: bool = False, path: str = "") -> Any:
    """Build a config instance from a nested dictionary.

    Creates an instance of config_cls (or the subclass selected by a
    "_config_name" entry) using values from nested_dict, recursively for nested
    ConfigBase fields.

    For ConfigBase fields with an instance default, user values are merged into
    that default: overriding a parameter keeps the default subclass and its
    other values, while passing a new "_config_name" starts fresh from the
    selected subclass's own defaults.

    Parameters
    ----------
    config_cls : type
        The ConfigBase subclass to instantiate.
    nested_dict : dict
        Nested dictionary of values. ConfigBase fields accept either a dict of
        values or a bare string (treated as the "_config_name").
    strict : bool, default=False
        If True, missing required ConfigBase fields raise a ValueError.
        If False (default), they are filled with the category's defaults.
        Value validation is always on in both modes.
    path : str, optional
        Kept for backward compatibility; error messages carry full paths.

    Returns
    -------
    Instance of config_cls (or selected subclass) with the given values.

    Raises
    ------
    ValueError
        On unknown keys, unknown "_config_name" values, or missing required fields.
    TypeError
        On values that cannot be validated against the field's type.
    """
    if not (isinstance(config_cls, type) and issubclass(config_cls, ConfigBase)):
        raise TypeError(f"config_cls must be a ConfigBase subclass, got {config_cls!r}")
    prepared = _prepare_values(config_cls, nested_dict, strict)
    try:
        return config_cls.model_validate(prepared)
    except ValidationError as error:
        raise _translate_validation_error(error) from None


def make_config_from_flat_dict(config_cls: Any, flat_dict: Dict[str, Any],
                               strict: bool = False) -> Any:
    """Instantiates a config class from a flat dictionary.

    Parameters
    ----------
    config_cls : ConfigBase
        The config class to instantiate.
    flat_dict : Dict[str, Any]
        "Flat" dict of the form {"key1": value1, "key1.subkey": value2, ...}:
        a single-level dict whose **keys** encode nesting with dots.
    strict : bool, default=False
        If True, missing required ConfigBase fields raise a ValueError.
        If False (default), they are filled with the category's defaults.
        Value validation is always on in both modes.

    Returns
    -------
    ConfigBase
        An instance of 'config_cls' with the loaded values.
    """
    nested = flat_dict_to_nested(flat_dict)
    return make_config_from_nested_dict(config_cls, nested, strict)
