Advanced Usage
==============

Inheritance Patterns
--------------------

.. code-block:: python

   class BaseConfig(ConfigBase):
       version: str = "1.0.0"
       debug: bool = False

   class ModelConfig(BaseConfig):
       dim: int = 512
       dropout: float = 0.1

   class TransformerConfig(ModelConfig):
       n_heads: int = 8
       n_layers: int = 12

   # All configs inherit version and debug from BaseConfig
   config = TransformerConfig()
   assert config.version == "1.0.0"
   assert config.dim == 512
   assert config.n_heads == 8


Type Validation
---------------

.. code-block:: python

   class AdvancedConfig(ConfigBase):
       # Union types with automatic selection
       layers: Union[int, List[int]] = 12
       
       # Optional fields with None handling
       checkpoint_path: Optional[Path] = None
       
       # Complex nested structures
       hyperparams: dict = {"lr": 0.001, "weight_decay": 0.01}

   # Usage examples
   config = AdvancedConfig(
       layers="[12, 24, 48]",  # String to list conversion
       checkpoint_path="/path/to/checkpoint.pt",  # String to Path
       hyperparams={"lr": "0.0001"}  # Partial dict update
   )


Serialization
-------------

You can export your configs to different formats.

.. code-block:: python

   class ExportableConfig(ConfigBase):
       model: ModelConfig = TransformerConfig()
       optimizer: OptimizerConfig = AdamW()
       training: dict = {"epochs": 100, "batch_size": 32}

   config = ExportableConfig()

   # Export to different formats
   flat_dict = config.to_dict(flatten=True)
   nested_dict = config.to_dict(flatten=False)
   
   # Import from dictionary
   new_config = make_config_from_flat_dict(ExportableConfig, flat_dict)
   new_config_nested = make_config_from_nested_dict(ExportableConfig, nested_dict) 

Note that this could be easily extended to other formats.


Auto-Discovery Pattern
-----------------------

For modular applications and plugin architectures, you can use automatic instance discovery to wire up configurations without explicit imports.

.. note::
   **Best Practice**: Define config classes in importable modules (not main scripts) and ensure content modules are imported to create instances.

Basic Auto-Discovery
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from zencfg import ConfigBase, AutoConfig

   class DatabaseConfig(ConfigBase):
       host: str = "localhost"
       port: int = 5432

   class AppConfig(ConfigBase):
       database: DatabaseConfig = AutoConfig()  # Uses latest DatabaseConfig instance

   # Create instance anywhere - it becomes available automatically
   prod_db = DatabaseConfig(host="prod-db.example.com")
   
   # AutoConfig finds the prod_db instance
   config = AppConfig()
   print(config.database.host)  # "prod-db.example.com"

Modular Configuration Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**configs/database.py:**

.. code-block:: python

   from zencfg import ConfigBase

   class DatabaseConfig(ConfigBase):
       host: str = "localhost"
       port: int = 5432
       username: str
       password: str

   # This instance automatically becomes available
   prod_db = DatabaseConfig(
       host="prod-db.example.com",
       username="app_user",
       password="secret123"
   )

**configs/cache.py:**

.. code-block:: python

   from zencfg import ConfigBase

   class CacheConfig(ConfigBase):
       host: str = "localhost"
       port: int = 6379
       password: str = ""

   # This instance automatically becomes available
   redis_cache = CacheConfig(
       host="redis.example.com",
       password="redis_secret"
   )

**main.py:**

.. code-block:: python

   from zencfg import ConfigBase, AutoConfig, make_config_from_cli

   # Import to create the instances
   import configs.database
   import configs.cache

   class AppConfig(ConfigBase):
       database: DatabaseConfig = AutoConfig()  # Automatically uses prod_db
       cache: CacheConfig = AutoConfig()        # Automatically uses redis_cache
       debug: bool = False
       port: int = 8000

   # The database and cache are automatically wired up!
   config = make_config_from_cli(AppConfig)
   print(f"Database: {config.database.host}:{config.database.port}")
   print(f"Cache: {config.cache.host}:{config.cache.port}")

Advanced AutoConfig Options
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class AppConfig(ConfigBase):
       # Use latest instance, or create default if none exists
       database: DatabaseConfig = AutoConfig()
       
       # Use specific default class if no instances exist
       cache: CacheConfig = AutoConfig(default_class=RedisCacheConfig)
       
       # Require an instance to exist (raises error if not found)
       auth: AuthConfig = AutoConfig(required=True)

This pattern is perfect for:

- **Plugin architectures** where modules self-register
- **Microservice configurations** with modular components  
- **Environment-specifin setups** where different modules load different configs
- **Large applications** with loosely coupled configuration modules
