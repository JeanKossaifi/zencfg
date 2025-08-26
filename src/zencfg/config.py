from typing import Any, Dict, Type, Union, List, get_origin, get_args, Optional, Callable
import importlib
import inspect
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
    # Handle AutoConfig sentinel - pass through without validation
    if isinstance(value, AutoConfig):
        return value
        
    origin = get_origin(field_type)
    args = get_args(field_type)

    # Handle List[...] of ConfigBase
    if origin in (list, List) and args and is_configbase_type(args[0]):
        if isinstance(value, list) and all(isinstance(v, args[0]) for v in value):
            return value
        # Otherwise, try to parse each element
        return [parse_value_to_type(v, args[0], strict=strict, path=f"{path}[{i}]") for i, v in enumerate(value)]

    # Handle direct ConfigBase types or Unions containing ConfigBase
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


class AutoConfig:
    """Sentinel indicating a field should be automatically configured with the latest instance of its type."""
    
    def __init__(self, default_class=None, required: bool = False):
        """
        Parameters
        ----------
        default_class : type, optional
            Class to instantiate if no instance of the field type exists.
            If None, uses the field type itself.
        required : bool, default=False
            If True, raises error if no instance exists and no default_class provided.
            If False, creates a default instance when needed.
        """
        self.default_class = default_class
        self.required = required


class ConfigBase:
    """Base class for all config objects, instanciates a new ConfigBase object.
        
    **Class creation**
    We manually enable inheritance of class-level attributes (see notes for detail).
    You can specify which configuration (sub)-class you actually want to create by passing a `"_config_name"` key in kwargs.
    The subclass with that `_config_name` will be instantiated instead of the `BaseConfig`.
    
    **Class hierarchy**
    Each direct descendent from ConfigBase will have a _registry attribute and track their children.
    In other words, for each main configuration category, create one subclass.
    Each config instance in this category should inherit from that subclass.        
        
    **Auto-discovery**
    ConfigBase automatically tracks the latest instance of each config type.
    Use `AutoConfig()` as a default value to automatically populate fields with the latest instance.
        
    Notes
    -----
    **AutoConfig best practices**: For reliable auto-discovery, define config classes in 
    importable modules (not in main scripts). Content modules creating instances must be 
    imported to execute their code and register instances.
    
    **Recommended structure**:
        - Define classes in: ``models/config.py`` or similar importable modules
        - Create instances in: ``content/*.py`` or configuration modules  
        - Import content modules in: ``main.py`` or package ``__init__.py``
        - Avoid defining config classes directly in main scripts (causes class identity issues)
    
    **Attribute inheritance**: Note that by default, attributes are **not** inherited since they
    are class-level attributes, not actual constructor parameters.
    By default, Python does not automatically copy class attributes into 
    instance attributes at ``__init__`` time. 
    
    To fix this, we manually collect the defaults:

    * gather_defaults(cls):
        * walk the entire Method Resolution Order (MRO), from the root (object) 
          up to the child class, collecting all fields that are not private or callable.
        * Because we do ``for base in reversed(cls.__mro__):``, 
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
    _latest_instances = {} # Dict[Type, "ConfigBase"] = {} - Auto-discovery registry
    _config_name: str = "configbase"
    _target_class: Optional[Union[str, Callable]] = None  # Optional target for instantiation

    def _resolve_target_class(self) -> Optional[Callable]:
        """Resolve _target_class to an actual callable.
        
        Returns
        -------
        Optional[Callable]
            The resolved target class/function, or None if _target_class is not set
            
        Raises
        ------
        ImportError
            If the target class cannot be imported
        AttributeError
            If the target class cannot be found in the module
        """
        if not hasattr(self, '_target_class') or self._target_class is None:
            return None
            
        target = self._target_class
        
        # Check if it's a bound method and extract the underlying function
        # This happens when a function is assigned as a class attribute
        if hasattr(target, '__self__') and hasattr(target, '__func__'):
            # It's a bound method, get the underlying function
            target = target.__func__
        
        # If it's already a callable, return it
        if callable(target):
            return target
            
        # If it's a string, try to import it
        if isinstance(target, str):
            if '.' not in target:
                raise ValueError(f"String target class '{target}' must be a fully qualified name (e.g., 'torch.nn.Linear')")
                
            module_name, class_name = target.rsplit('.', 1)
            try:
                module = importlib.import_module(module_name)
                return getattr(module, class_name)
            except ImportError as e:
                raise ImportError(f"Could not import module '{module_name}': {e}")
            except AttributeError as e:
                raise AttributeError(f"Module '{module_name}' has no attribute '{class_name}': {e}")
        
        raise TypeError(f"_target_class must be a callable or string, got {type(target)}")

    def _extract_config_params(self) -> Dict[str, Any]:
        """Extract configuration parameters for instantiation.
        
        Only excludes essential ZenCFG internal attributes. Everything else
        (including private attributes and callables) is passed to the target class.
        
        Returns
        -------
        Dict[str, Any]
            Dictionary of parameter names and values
        """
        params = {}
        
        # Only exclude the essential ZenCFG internals
        zencfg_internals = {'_registry', '_config_name', '_target_class'}
        
        for name, value in vars(self).items():
            if name in zencfg_internals:
                continue
            # Include everything else - let the target class decide what it wants
            params[name] = value
        
        return params

    def instantiate(self, *args, **kwargs) -> Any:
        """Instantiate the target class with config parameters and optional additional arguments.
        
        This method creates an instance of the class specified in _target_class
        using the configuration parameters as constructor arguments, along with any
        additional positional or keyword arguments provided.
        
        Only the current config is instantiated - nested ConfigBase objects
        are passed as-is (not recursively instantiated).
        
        Parameters
        ----------
        *args : tuple
            Additional positional arguments to pass to the target class constructor.
            These are passed before the config parameters.
        **kwargs : dict
            Additional keyword arguments to pass to the target class constructor.
            These override any config parameters with the same name.
            
        Returns
        -------
        Any
            An instance of the target class
            
        Raises
        ------
        NotImplementedError
            If _target_class is not set and this method is not overridden
        ImportError
            If the target class cannot be imported
        TypeError
            If the target class cannot be instantiated with the given parameters
            
        Examples
        --------
        You can specify the target class as a class directly or as a string:

        .. code-block:: python

            >>> class LinearConfig(ConfigBase):
            ...     _target_class = "torch.nn.Linear"
            ...     in_features: int = 784
            ...     out_features: int = 10
            >>> config = LinearConfig()
            >>> model = config.instantiate()  # Creates torch.nn.Linear(in_features=784, out_features=10)
        
        With additional arguments (e.g., for optimizers):

        .. code-block:: python

            >>> class OptimizerConfig(ConfigBase):
            ...     _target_class = "torch.optim.Adam"
            ...     lr: float = 0.001
            ...     betas: tuple = (0.9, 0.999)
            >>> config = OptimizerConfig()
            >>> optimizer = config.instantiate(model.parameters())  # Pass model.parameters() as first arg
        
        Override config parameters with kwargs:

        .. code-block:: python

            >>> config = LinearConfig(out_features=10)
            >>> model = config.instantiate(out_features=20)  # kwargs override config values
            >>> # Creates torch.nn.Linear(in_features=784, out_features=20)
        
        Alternatively, you can customize the instantiate method:

        .. code-block:: python

            >>> class CustomConfig(ConfigBase):
            ...     param1: int = 42
            ...     def instantiate(self, *args, **kwargs):
            ...         return MyCustomClass(self.param1, *args, **kwargs)
            >>> config = CustomConfig()
            >>> obj = config.instantiate(additional_param="test")

        """
        target_class = self._resolve_target_class()
        
        if target_class is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} must either define _target_class or override the instantiate() method"
            )
        
        # Extract parameters from config
        params = self._extract_config_params()
        
        # Merge with kwargs (kwargs override config params)
        merged_params = {**params, **kwargs}
        
        # Try to instantiate
        try:
            return target_class(*args, **merged_params)
        except TypeError as e:
            # Get the signature for better error messages
            try:
                sig = inspect.signature(target_class)
                available_params = list(sig.parameters.keys())
                provided_params = list(params.keys())
                
                raise TypeError(
                    f"Cannot instantiate {target_class.__name__} with provided parameters.\n"
                    f"Available parameters: {available_params}\n"
                    f"Provided parameters: {provided_params}\n"
                    f"Original error: {e}"
                )
            except Exception:
                # If we can't get signature info, just re-raise original error
                raise e

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
        
        # Auto-register this instance as the latest for its type
        ConfigBase._latest_instances[self.__class__] = self
        
        # Resolve any AutoConfig fields
        self._resolve_auto_fields()

    def _resolve_auto_fields(self):
        """Replace AutoConfig sentinels with the latest instances."""
        from typing import get_type_hints
        type_hints = get_type_hints(self.__class__)
        
        for field_name, field_type in type_hints.items():
            current_value = getattr(self, field_name, None)
            
            if isinstance(current_value, AutoConfig):
                if current_value.default_class:
                    # When default_class is specified, only use latest instance if it matches
                    latest_instance = self._latest_instances.get(current_value.default_class)
                    if latest_instance:
                        setattr(self, field_name, latest_instance)
                    else:
                        # Create instance of specified default class
                        default_instance = current_value.default_class()
                        setattr(self, field_name, default_instance)
                else:
                    # No default_class specified, use latest of field_type
                    latest_instance = self._latest_instances.get(field_type)
                    
                    if latest_instance:
                        setattr(self, field_name, latest_instance)
                    elif not current_value.required:
                        # Create instance of the field type itself
                        try:
                            default_instance = field_type()
                            setattr(self, field_name, default_instance)
                        except Exception as e:
                            if current_value.required:
                                raise ValueError(
                                    f"Could not create default instance of {field_type.__name__} "
                                    f"for field '{field_name}': {e}"
                                )
                            # If not required and can't create default, leave as AutoConfig
                    else:
                        raise ValueError(
                            f"No instance of {field_type.__name__} found for AutoConfig field '{field_name}'. "
                            f"Ensure the module creating {field_type.__name__} instances is imported. "
                            f"If classes are defined in your main script, consider moving them to a separate module."
                        )

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
