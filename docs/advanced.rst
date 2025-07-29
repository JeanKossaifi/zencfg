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
