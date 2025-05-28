from typing import Any, Dict, Type, Union, List, get_origin, get_args
from pydantic import TypeAdapter, ValidationError

from .bunch import Bunch


def is_configbase_type(tp: Any) -> bool:
    """
    Returns True if type 'tp' is a subclass of ConfigBase OR a Union that includes a ConfigBase subclass.
    """
    origin = get_origin(tp)
    def is_configbase(cls):
        return isinstance(cls, type) and any(base.__name__ == 'ConfigBase' for base in cls.__mro__)
    if origin is Union:
        return any(is_configbase(arg) for arg in get_args(tp))
    else:
        return is_configbase(tp)

def parse_value_to_type(value: Any, field_type: Type, strict: bool = True, path: str = "") -> Any:
    """Parse a value to match its expected type.
    
    Parameters
    ----------
    value : Any
        The value to parse
    field_type : Type
        The expected type
    strict : bool
        If True, raises on type conversion errors. If False, falls back to original value if conversion fails.
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
    # Handle ConfigBase types
    if is_configbase_type(field_type):
        if isinstance(value, field_type):
            return value
        if strict:
            raise TypeError(f"Value for field '{path}' must be an instance of {getattr(field_type, '__name__', str(field_type))}")
        return value

    adapter = TypeAdapter(field_type)
    try:
        if isinstance(value, str):
            try:
                return adapter.validate_json(value)
            except Exception:
                pass  # Fall back to validate_python if JSON parsing fails
        return adapter.validate_python(value)
    except ValidationError as e:
        if strict:
            # Add value and type info to Pydantic's error message, with truncation
            raise TypeError(
                f"Invalid value for field '{path}' (got {type(value).__name__} = {str(value)[:100]}):\n{str(e)}"
            )
        return value


def gather_defaults(cls) -> dict:
    """
    Gather all default (class-level) fields from the entire MRO, 
    ensuring that child classes override parent defaults if present.
    Returns a dictionary of {field_name: default_value}.
    """
    defaults = {}
    # We iterate over the MRO from base -> child, so child overrides if repeated
    for base in reversed(cls.__mro__):
        if base is object:
            continue  # skip Python's built-in object
        for k, v in vars(base).items():
            if not k.startswith('_') and not callable(v):
                defaults[k] = v

    return defaults


class ConfigBase:
    """Base class for all config objects, instanciates a new ConfigBase object.
        
    **Class creation**
    We manually enable inheritance of class-level attributes by, see notes for detail.
    You can specify which class you actually want to create by passing a "_config_config_name" key in kwargs.
    The subclass with that _config_name will be instantiated instead of the BaseConfig.
    
    **Class hierarchy**
    Each direct descendent from ConfigBase will have a _registry attribute and track their children.
    In other words, for each main config category, create one subclass.
    Each config instance in this category should inherit from that subclass.        
        
    Notes
    -----
    Note that by default, attributes are **not** inherited since they
    are class-level attributes, not actual constructor parameters.
    By default, Python does not automatically copy class attributes into 
    instance attributes at __init__ time. 
    
    To fix this, we manually collect the defaults: 
    * gather_defaults(cls):
        * walk the entire Method Resolution Order (MRO), from the root (object) 
          up to the child class, collecting all fields that are not private or callable.
        * Because we do for base in reversed(cls.__mro__):, 
          we effectively start from the oldest parent 
          (like Checkpoint) and end at the child (CheckpointSubclass),
          so the child can override any fields if it redefines them.
    * __init__: 
        * We call gather_defaults(type(self)) to get all inherited fields.
        * Check for any missing required fields (not in defaults).
        * Assign defaults to self.
        * Then override with any passed-in kwargs, including name.
    """
    _registry = {} # Dict[str, Type["ConfigBase"]] = {}
    _config_name: str = "configbase"

    def __setattr__(self, name: str, value: Any) -> None:
        """Override attribute setting to validate types."""
        if name in self.__annotations__:
            field_type = self.__annotations__[name]
            # Include class name in the path for better error messages
            path = f"{self.__class__.__name__}.{name}"
            value = parse_value_to_type(value, field_type, strict=True, path=path)
        super().__setattr__(name, value)

    def __init__(self, **kwargs):
        # Gather default values for optional class attributes
        all_defaults = gather_defaults(type(self))

        # Check that required attributes (no default) are provided by the user
        for name, field_type in self.__annotations__.items():
            if name not in all_defaults and name not in kwargs:
                raise ValueError(f"Missing required field '{name}', of type '{field_type}'")
            # # We could also instantiate ConfigBase subclasses here:
            # if (
            #     name not in all_defaults 
            #     and isinstance(field_type, type)
            #     and issubclass(field_type, ConfigBase)
            # ):
            #     all_defaults[name] = field_type()

        # First assign default values to all attributes
        for k, v in all_defaults.items():
            setattr(self, k, v)

        # Then override with values provided by the user
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses by lowercase class name."""
        super().__init_subclass__(**kwargs)
        parent = cls.__bases__[0]
        cls_name = cls.__name__.lower()
        cls._config_name = cls_name
        if parent is ConfigBase:
            cls._registry = {}
        elif issubclass(parent, ConfigBase):
            parent._registry[cls_name] = cls

    @classmethod
    def _get_subclass_by_name(cls, config_name: str) -> Type["ConfigBase"]:
        """Return a registered subclass based on `name` if available, else return `cls` itself."""
        if not config_name:
            return cls
        config_name = config_name.lower()
        if config_name == cls._config_name:
            return cls
        if config_name in cls._registry:
            return cls._registry[config_name]
        else:
            raise ValueError(f"Unknown subclass '{config_name=}' for class '{cls.__name__}'"
                             f" should be one: {list(cls._registry.keys())})")
    
    def __new__(cls, **kwargs):
        """Intercept creation. If "_config_name" is in kwargs, pick the correct subclass."""
        config_name = kwargs.get("_config_name", None)
        if config_name:    
            # Is there a known subclass with that name?
            subcls = cls._get_subclass_by_name(config_name)
            if subcls is not cls:
                # we found a different subclass, so create that instead
                return super(ConfigBase, subcls).__new__(subcls)
        # else: normal creation
        return super().__new__(cls)

    def __repr__(self) -> str:
        """Custom repr showing meaningful attributes."""
        cls_name = self.__class__.__name__
        attrs = {
            name: value for name, value in vars(self).items()
            if not name.startswith('__') and not callable(value) and value is not None
        }
        if not attrs:
            return f"{cls_name}()"

        attrs_str = ', \n'.join(f"{name}={value!r}" for name, value in attrs.items())
        return f"{cls_name}({attrs_str})"

    def to_dict(self, flatten: bool = False, parent_key: str = "") -> Dict[str, Any]:
        """
        Returns a dictionary representation of this config (either nested or flattened).
        """
        result = {}
        for attr_name, value in vars(self).items():
            if attr_name.startswith('__') or callable(value):
                continue

            if isinstance(value, ConfigBase):
                # Recurse into sub-config
                if flatten:
                    sub_dict = value.to_dict(flatten=True)
                    for k2, v2 in sub_dict.items():
                        full_key = f"{attr_name}.{k2}"
                        if parent_key:
                            full_key = f"{parent_key}.{full_key}"
                        result[full_key] = v2
                else:
                    result[attr_name] = value.to_dict(flatten=False)
            else:
                # Non-ConfigBase attribute: just add to the dict
                if flatten:
                    full_key = attr_name if not parent_key else f"{parent_key}.{attr_name}"
                    result[full_key] = value
                else:
                    result[attr_name] = value

        return Bunch(result)
