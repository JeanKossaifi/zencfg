"""Core configuration class.

ConfigBase is a thin layer over pydantic's BaseModel that adds the three things
ZenCFG is about:

1. A subclass registry: each direct child of ConfigBase is a config *category*
   (e.g. ModelConfig), and its subclasses can be selected by name at runtime
   via ``_config_name`` (e.g. ``--model cnnconfig`` on the command line).
2. Dotted-path overrides from flat dicts / the command line (see from_dict.py).
3. ``instantiate()``: build the actual object (model, optimizer, ...) described
   by a config through its ``_target_class``.

Validation, defaults (safely copied per instance), serialization and typing
are delegated to pydantic.
"""

import contextvars
import copy
import importlib
import inspect
import re
import textwrap
import types
import warnings
from functools import cached_property, lru_cache
from typing import Any, Callable, ClassVar, Dict, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, model_validator
from pydantic_core import PydanticUndefined

from .bunch import Bunch

# Union spelled either way: Union[X, Y] / Optional[X] or the PEP 604 form X | Y.
_UNION_ORIGINS = (Union, types.UnionType)

# pydantic error kinds that mean "wrong or missing key" rather than "bad value":
# ZenCFG reports those as ValueError, everything else as TypeError.
_KEY_ERROR_KINDS = {"missing", "extra_forbidden", "value_error", "no_such_attribute"}

# Tracks whether we are inside an outer validation: nested errors must stay
# ValidationErrors so pydantic can aggregate them across sibling fields;
# only the outermost call translates to ValueError/TypeError.
_inside_validation = contextvars.ContextVar("zencfg_inside_validation", default=False)


def _translate_validation_error(error: ValidationError) -> Exception:
    kinds = {err["type"] for err in error.errors()}
    if kinds & _KEY_ERROR_KINDS:
        return ValueError(str(error))
    return TypeError(str(error))


def is_configbase_type(tp: Any) -> bool:
    """Return True if 'tp' is a ConfigBase subclass or a Union that includes one."""
    if get_origin(tp) in _UNION_ORIGINS:
        return any(is_configbase_type(arg) for arg in get_args(tp))
    return isinstance(tp, type) and issubclass(tp, ConfigBase)


def _contains_configbase(tp: Any) -> bool:
    """Recursively check if a type involves ConfigBase, e.g. Dict[str, MyConfig]."""
    if is_configbase_type(tp):
        return True
    return any(_contains_configbase(arg) for arg in get_args(tp) if arg is not ...)


@lru_cache(maxsize=None)
def _type_adapter(field_type: Any) -> TypeAdapter:
    return TypeAdapter(field_type)


def parse_value_to_type(value: Any, field_type: Type, strict: bool = True, path: str = "") -> Any:
    """Parse a value to match its expected type.

    Strings are tried as JSON first (so "[4, 5]" can fill a List[int] field),
    then validated directly. Types involving ConfigBase are passed through:
    they are validated by the config machinery itself, not here.

    Parameters
    ----------
    value : Any
        The value to parse
    field_type : Type
        The expected type
    strict : bool
        If True, raises on conversion errors. If False, returns the original
        value when conversion fails.
    path : str
        Path in the config hierarchy, used for error messages

    Returns
    -------
    Any
        The parsed value

    Raises
    ------
    TypeError
        If value cannot be converted to the expected type and strict=True
    """
    origin = get_origin(field_type)
    args = get_args(field_type)

    # List[SomeConfig]: validate element-wise
    if origin is list and args and is_configbase_type(args[0]):
        if not isinstance(value, (list, tuple)):
            if strict:
                raise TypeError(
                    f"Value for field '{path}' must be a list of "
                    f"{getattr(args[0], '__name__', str(args[0]))}, got {type(value).__name__}")
            return value
        if isinstance(value, list) and all(isinstance(v, args[0]) for v in value):
            return value
        return [parse_value_to_type(v, args[0], strict=strict, path=f"{path}[{i}]")
                for i, v in enumerate(value)]

    # Direct ConfigBase types (or Unions including one)
    if is_configbase_type(field_type):
        if isinstance(value, field_type):
            return value
        if strict:
            raise TypeError(
                f"Value for field '{path}' must be an instance of "
                f"{getattr(field_type, '__name__', str(field_type))}")
        return value

    # Other generics containing ConfigBase (Dict[str, Config], Tuple[Config, ...]):
    # pass through, the config machinery validates them.
    if args and any(_contains_configbase(arg) for arg in args):
        return value

    adapter = _type_adapter(field_type)
    try:
        if isinstance(value, str):
            try:
                return adapter.validate_json(value)
            except Exception:
                pass  # not valid JSON for this type: validate the string itself
        return adapter.validate_python(value)
    except ValidationError as error:
        if strict:
            raise TypeError(
                f"Type Error during validation, got invalid value for field '{path}'. "
                f"Expected type {field_type}, but got {type(value).__name__}={value!r}\n{error}"
            ) from None
        return value


class _ConfigMeta(type(BaseModel)):
    """Let plain (un-annotated) class attributes behave like in a regular class.

    - A public data attribute without a type annotation becomes an ``Any``
      field (no validation), unless a parent class annotated it — then the
      inherited annotation governs and the value is just a new default.
    - Functions and descriptors stay methods/properties.
    - Other callables (callable instances, classes) stay inert class
      attributes, marked ClassVar so pydantic leaves them alone.
    """
    _METHOD_TYPES = (types.FunctionType, types.BuiltinFunctionType,
                     classmethod, staticmethod, property, cached_property)

    def __new__(mcs, name, bases, namespace, **kwargs):
        annotations = dict(namespace.get("__annotations__", {}))
        explicit = set(annotations)
        # Inherited field types, preferring pydantic's already-resolved
        # annotations (raw __annotations__ strings would re-resolve in the
        # wrong module under `from __future__ import annotations`).
        inherited = {}
        for base in bases:
            for klass in getattr(base, "__mro__", [base]):
                for attr, field in klass.__dict__.get("__pydantic_fields__", {}).items():
                    inherited.setdefault(attr, field.annotation)
                for attr, annotation in klass.__dict__.get("__annotations__", {}).items():
                    inherited.setdefault(attr, annotation)
        # re-annotating a field lifts it out of the untyped (no-parsing) set
        untyped = set().union(*(getattr(base, "__zencfg_untyped__", ()) for base in bases)) - explicit
        for attr, value in namespace.items():
            if (attr.startswith("_") or attr == "model_config" or attr in explicit
                    or isinstance(value, mcs._METHOD_TYPES) or hasattr(value, "__get__")):
                continue
            if attr in inherited:
                # a new default for an inherited field: keep the parent's type
                annotations[attr] = inherited[attr]
            elif callable(value):
                annotations[attr] = ClassVar[Any]
            else:
                annotations[attr] = Any
                untyped.add(attr)
        namespace["__annotations__"] = annotations
        namespace["__zencfg_untyped__"] = frozenset(untyped)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        # pydantic warns that a field "shadows an attribute" for every default
        # override, because our __getattr__ makes class-level field access
        # succeed. Re-emit only genuine shadows (a real attribute, e.g. a
        # method, found in a base class), and every unrelated warning.
        for caught_warning in caught:
            match = re.search(r'Field name "([^"]+)".*shadows an attribute',
                              str(caught_warning.message))
            genuine = match and any(match.group(1) in klass.__dict__
                                    for base in bases
                                    for klass in getattr(base, "__mro__", [base]))
            if match is None or genuine:
                warnings.warn_explicit(caught_warning.message, caught_warning.category,
                                       caught_warning.filename, caught_warning.lineno)
        return cls

    def __getattr__(cls, name):
        """Field defaults stay readable on the class, like regular attributes."""
        try:
            return super().__getattr__(name)
        except AttributeError:
            pass
        if not name.startswith("_"):
            field = cls.__dict__.get("__pydantic_fields__", {}).get(name)
            if field is not None and not field.is_required():
                default = field.get_default(call_default_factory=True)
                if default is not PydanticUndefined:
                    return default
        raise AttributeError(f"type object '{cls.__name__}' has no attribute '{name}'")


class ConfigBase(BaseModel, metaclass=_ConfigMeta):
    """Base class for all config objects.

    **Defining configs**: subclass ConfigBase for each configuration *category*
    (e.g. ModelConfig), then subclass the category for each concrete choice
    (e.g. CNNConfig, TransformerConfig). Fields are plain annotated class
    attributes with optional defaults.

    **Selecting a subclass by name**: every subclass is registered under its
    lowercase class name. Passing ``_config_name`` selects the subclass::

        opt: OptimizerConfig = OptimizerConfig(_config_name="adamw")

    The same works from dicts and the command line (``--opt adamw``).

    **Validation**: values are validated (and coerced when unambiguous) against
    the field's type hint, at construction and on attribute assignment.
    Unknown field names raise a ValueError, invalid values a TypeError.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
        arbitrary_types_allowed=True,
    )

    # Value equality (from pydantic) with identity hash: two equal configs can
    # coexist in a set, and configs remain usable as dict keys, like before.
    __hash__ = object.__hash__

    _registry: ClassVar[dict] = {}
    _config_name: ClassVar[str] = "configbase"
    _target_class: ClassVar[Any] = None  # optional target for instantiate()

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        """Register subclasses by lowercase class name.

        Direct children of ConfigBase are categories and get their own registry;
        deeper subclasses register into their category's registry.
        """
        super().__pydantic_init_subclass__(**kwargs)
        parent = cls.__bases__[0]
        cls._config_name = cls.__name__.lower()
        if parent is ConfigBase:
            cls._registry = {}
        elif issubclass(parent, ConfigBase):
            parent._registry[cls._config_name] = cls

    @classmethod
    def _get_subclass_by_name(cls, config_name: Optional[str]) -> Type["ConfigBase"]:
        """Return the registered subclass for `config_name` (falsy name: cls itself)."""
        if not config_name:
            return cls
        if not isinstance(config_name, str):
            raise ValueError(f"'_config_name' must be a string, "
                             f"got {type(config_name).__name__}: {config_name!r}")
        config_name = config_name.lower()
        if config_name == cls._config_name:
            return cls
        if config_name in cls._registry:
            return cls._registry[config_name]
        raise ValueError(
            f"Unknown subclass '{config_name}' for class '{cls.__name__}', "
            f"should be one of: {list(dict.fromkeys([cls._config_name, *cls._registry]))}")

    def __new__(cls, **data):
        """If '_config_name' is passed, create the corresponding subclass instead."""
        config_name = data.get("_config_name")
        if config_name:
            cls = cls._get_subclass_by_name(config_name)
        return super().__new__(cls)

    def __init__(self, /, **data: Any):
        data.pop("_config_name", None)
        # Defaults holding config instances are copied per instance, so
        # mutating one config never leaks into another. (Because configs are
        # hashable, pydantic reuses the validated default object across
        # instances instead of copying it.)
        injected = []
        for name, field in type(self).model_fields.items():
            if name not in data and _holds_config_instances(field.default):
                try:
                    data[name] = copy.deepcopy(field.default)
                except Exception:
                    continue  # not copyable: leave the default to pydantic
                injected.append(name)
        try:
            super().__init__(**data)
        except ValidationError as error:
            if _inside_validation.get():
                raise  # let the outer validation aggregate errors across fields
            raise _translate_validation_error(error) from None
        # injected defaults are still defaults, not explicitly-set fields
        self.__pydantic_fields_set__.difference_update(injected)

    def __setattr__(self, name: str, value: Any):
        try:
            super().__setattr__(name, self._coerce_string(name, value))
        except ValidationError as error:
            raise _translate_validation_error(error) from None

    @classmethod
    def _coerce_string(cls, name: str, value: Any) -> Any:
        """Leniently parse a string value for field `name` (JSON first), so
        e.g. "8" or "[4, 5]" can fill typed fields. Non-strings, unknown fields
        and un-annotated fields pass through; validation stays in charge."""
        field = cls.model_fields.get(name)
        if field is None or not isinstance(value, str) or name in cls.__zencfg_untyped__:
            return value
        return parse_value_to_type(value, field.annotation, strict=False, path=name)

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch_by_config_name(cls, data: Any, handler):
        """When validating a dict (or a bare name string), honor '_config_name'
        and leniently parse string values against their field types."""
        if isinstance(data, str):
            data = {"_config_name": data}
        if isinstance(data, dict):
            if "_config_name" in data:
                config_name = data["_config_name"]
                data = {key: value for key, value in data.items() if key != "_config_name"}
                target = cls._get_subclass_by_name(config_name)
                if not issubclass(target, cls):
                    valid = dict.fromkeys([cls._config_name] + [
                        n for n, c in cls._registry.items() if issubclass(c, cls)])
                    raise ValueError(f"'{config_name}' is not a {cls.__name__}, "
                                     f"should be one of: {list(valid)}")
                if target is not cls:
                    return target.model_validate(data)
            data = {key: cls._coerce_string(key, value) for key, value in data.items()}
        token = _inside_validation.set(True)
        try:
            return handler(data)
        finally:
            _inside_validation.reset(token)

    # ------------------------------------------------------------------
    # Instantiation of the target class
    # ------------------------------------------------------------------
    def _resolve_target_class(self) -> Optional[Callable]:
        """Resolve _target_class to an actual callable (importing it if a string)."""
        target = type(self)._target_class
        if target is None or callable(target):
            return target
        if isinstance(target, str):
            if "." not in target:
                raise ValueError(
                    f"String target class '{target}' must be a fully qualified name "
                    f"(e.g., 'torch.nn.Linear')")
            module_name, _, attr = target.rpartition(".")
            try:
                module = importlib.import_module(module_name)
            except ImportError as error:
                raise ImportError(f"Could not import module '{module_name}': {error}") from error
            try:
                return getattr(module, attr)
            except AttributeError:
                raise AttributeError(f"Module '{module_name}' has no attribute '{attr}'") from None
        raise TypeError(f"_target_class must be a callable or string, got {type(target)}")

    def _recursive_instantiate(self, value: Any) -> Any:
        """Instantiate nested configs (in lists, tuples and dicts too)."""
        if isinstance(value, ConfigBase):
            if type(value)._target_class is not None:
                return value.instantiate(recursive=True)
            return value
        if isinstance(value, list):
            return [self._recursive_instantiate(v) for v in value]
        if isinstance(value, tuple):
            return tuple(self._recursive_instantiate(v) for v in value)
        if isinstance(value, dict):
            return {k: self._recursive_instantiate(v) for k, v in value.items()}
        return value

    def instantiate(self, *args, recursive: bool = True, **kwargs) -> Any:
        """Instantiate the target class with the config's fields as arguments.

        Creates an instance of ``_target_class`` (a class/callable, or its fully
        qualified name as a string), passing every config field as a keyword
        argument. Nested configs that define their own ``_target_class`` are
        instantiated too (including inside lists, tuples and dicts), unless
        ``recursive=False``.

        Parameters
        ----------
        *args : tuple
            Additional positional arguments, passed before the config fields
            (e.g. ``optimizer_config.instantiate(model.parameters())``).
        recursive : bool, default=True
            Recursively instantiate nested configs that define _target_class.
        **kwargs : dict
            Additional keyword arguments; they override config fields with the
            same name.

        Returns
        -------
        Any
            An instance of the target class.

        Examples
        --------
        >>> class LinearConfig(ConfigBase):
        ...     _target_class = "torch.nn.Linear"
        ...     in_features: int = 784
        ...     out_features: int = 10
        >>> model = LinearConfig().instantiate()  # torch.nn.Linear(in_features=784, out_features=10)

        Or override the method entirely for full control:

        >>> class CustomConfig(ConfigBase):
        ...     param1: int = 42
        ...     def instantiate(self, *args, **kwargs):
        ...         return MyCustomClass(self.param1, *args, **kwargs)
        """
        target_class = self._resolve_target_class()
        if target_class is None:
            raise NotImplementedError(
                f"{type(self).__name__} must either define _target_class "
                f"or override the instantiate() method")

        params = {name: getattr(self, name) for name in type(self).model_fields}
        params.update(kwargs)
        if recursive:
            params = {name: self._recursive_instantiate(value) for name, value in params.items()}

        try:
            return target_class(*args, **params)
        except TypeError as error:
            target_name = getattr(target_class, "__name__", str(target_class))
            try:
                accepted = list(inspect.signature(target_class).parameters)
                hint = f"\n  Parameters accepted by {target_name}: {accepted}"
            except (TypeError, ValueError):
                hint = ""
            raise TypeError(
                f"Failed to instantiate {target_name}"
                f"{' with positional args ' + repr(list(args)) if args else ''}"
                f" with parameters {sorted(params)}.{hint}\n"
                f"  Original error: {error}") from error

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self, flatten: bool = False, parent_key: str = "") -> Dict[str, Any]:
        """Dictionary representation of this config (nested, or flattened with dotted keys).

        The result always includes '_config_name' entries, so it can be fed back
        to make_config / make_config_from_flat_dict and rebuild the exact same
        config, subclass choices included.
        """
        if flatten:
            prefix = f"{parent_key}." if parent_key else ""
            flat = {f"{prefix}_config_name": self._config_name}
            for name in type(self).model_fields:
                value = getattr(self, name)
                if isinstance(value, ConfigBase):
                    flat.update(value.to_dict(flatten=True, parent_key=f"{prefix}{name}"))
                else:
                    flat[f"{prefix}{name}"] = _dump_value(value)
            return Bunch(flat)

        nested = {"_config_name": self._config_name}
        for name in type(self).model_fields:
            nested[name] = _dump_value(getattr(self, name))
        return Bunch(nested)

    def __repr__(self) -> str:
        field_names = type(self).model_fields
        if not field_names:
            return f"{type(self).__name__}()"
        lines = [textwrap.indent(f"{name}={getattr(self, name)!r},", "  ")
                 for name in field_names]
        return f"{type(self).__name__}(\n" + "\n".join(lines) + "\n)"

    def __str__(self) -> str:
        return self.__repr__()


def _holds_config_instances(value: Any) -> bool:
    """True if value is a ConfigBase instance or a container holding one."""
    if isinstance(value, ConfigBase):
        return True
    if isinstance(value, (list, tuple, set)):
        return any(_holds_config_instances(v) for v in value)
    if isinstance(value, dict):
        return any(_holds_config_instances(v) for v in value.values())
    return False


def _dump_value(value: Any) -> Any:
    """Recursively convert ConfigBase objects (in containers too) to dicts."""
    if isinstance(value, ConfigBase):
        return value.to_dict()
    if isinstance(value, list):
        return [_dump_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_dump_value(v) for v in value)
    if isinstance(value, dict):
        return {k: _dump_value(v) for k, v in value.items()}
    return value
