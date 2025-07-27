Examples
========

Here are practical examples showing ZenCFG in action for different scenarios.

Deep Learning Configuration
---------------------------

A sample deep learning experiment setup:

.. code-block:: python

   from zencfg import ConfigBase, make_config_from_cli
   from typing import List, Optional

   # Base categories
   class ModelConfig(ConfigBase):
       in_channels: int = 3
       out_channels: int = 100

   class OptimizerConfig(ConfigBase):
       lr: float = 1e-4 # they all have a lr

   # Model architectures
   class TransformerConfig(ModelConfig):
       layers: int = 12
       n_heads: int = 8
       dim: int = 512
       dropout: Optional[float] = 0.1

   class CNNConfig(ModelConfig):
       in_channels: int = 3
       out_channels: int = 1000
       features: List[int] = [64, 128, 256, 512]
       kernel_size: int = 3

   # Optimizers
   class AdamConfig(OptimizerConfig):
       lr: float = 1e-4
       weight_decay: float = 0.01
       betas: List[float] = [0.9, 0.999]

   class SGDConfig(OptimizerConfig):
       lr: float = 1e-3
       momentum: float = 0.9
       nesterov: bool = True

   # Main experiment config
   class ExperimentConfig(ConfigBase):
       model: ModelConfig = TransformerConfig()
       optimizer: OptimizerConfig = AdamConfig()
       batch_size: int = 32
       epochs: int = 100
       device: str = "cuda"
       mixed_precision: bool = True

   # Usage in your training script
   config = make_config_from_cli(ExperimentConfig)
   print(f"Training {config.model._config_name} for {config.epochs} epochs")


**Command line usage:**

Note how you can at the same time override the model and its parameters!

.. code-block:: bash

   # Quick experiments with different models
   python train.py --model transformerconfig --model.n_heads 16 --epochs 200
   python train.py --model cnnconfig --model.features "[32,64,128]" --batch_size 64
   
   # Optimizer comparisons  
   python train.py --optimizer adamconfig --optimizer.lr 2e-4
   python train.py --optimizer sgdconfig --optimizer.momentum 0.95

Configuration from Files
------------------------

For larger projects, organize configs in separate files:

**configs/models.py:**

.. code-block:: python

   from zencfg import ConfigBase

   class ModelConfig(ConfigBase):
       pass

   class ResNet50(ModelConfig):
       layers: int = 50
       pretrained: bool = True
       
   class EfficientNet(ModelConfig):
       variant: str = "b0"
       dropout: float = 0.2

**main.py:**

.. code-block:: python

   from zencfg import make_config_from_cli
   from configs.models import ModelConfig

   class Config(ConfigBase):
       model: ModelConfig = ResNet50()
       lr: float = 1e-3

   config = make_config_from_cli(Config)

Nested Configurations
---------------------

Handle complex nested structures elegantly:

.. code-block:: python

   class DataConfig(ConfigBase):
       batch_size: int = 32
       num_workers: int = 4

   class AugmentationConfig(ConfigBase):
       rotate: bool = True
       flip: bool = True
       brightness: float = 0.2

   class TrainingConfig(ConfigBase):
       data: DataConfig = DataConfig()
       augmentation: AugmentationConfig = AugmentationConfig()
       model: ModelConfig = TransformerConfig()
       epochs: int = 100

   config = make_config_from_cli(TrainingConfig)

**Override nested parameters:**

We use a flattened syntax to override nested parameters:

.. code-block:: bash

   python train.py --data.batch_size 128 --augmentation.brightness 0.5 --model.n_heads 12


Export and Inspect
------------------

Convert configurations to dictionaries for logging or serialization:

.. code-block:: python

   config = make_config_from_cli(ExperimentConfig)
   
   # Export to dictionary
   config_dict = config.to_dict()
   
   # Access nested values
   model_lr = config_dict['optimizer']['lr']
   
   # Pretty print configuration
   import json
   print(json.dumps(config_dict, indent=2))

Other considerations
--------------------

**1. Type Safety**
   Always use type hints when possible - they provide both IDE support and runtime validation. 
   You can use the `strict` parameter of `make_config_from_cli` to raise an error if a type conversion fails.

   You can also not provide any type hints but in that case, you will not get any runtime validation.

   .. code-block:: python

      class Config(ConfigBase):
          learning_rate: float = 1e-4  # ✅ Type-safe
          # learning_rate = 1e-4       # ❌ No type checking

**2. Meaningful Defaults**
   Set sensible defaults that work out of the box as much as possible:

   .. code-block:: python

      class ModelConfig(ConfigBase):
          hidden_size: int = 768      # Good default
          num_layers: int = 12        # Reasonable starting point


**3. Use Inheritance Wisely**
   Group related configurations for better organization:

   .. code-block:: python

      # Base categories
      class ModelConfig(ConfigBase): pass
      class DataConfig(ConfigBase): pass
      
      # Specific implementations
      class BERT(ModelConfig): ...
      class ImageDataset(DataConfig): ...

Check out the :doc:`advanced` guide for more advanced features.