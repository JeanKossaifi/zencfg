Quick Start Guide
=================

Installation
------------

First install the library your favourite way. Either directly from PyPI:

.. code-block:: bash

   pip install zencfg

Or from the source code:

.. code-block:: bash

   git clone https://github.com/JeanKossaifi/zencfg
   cd zencfg
   pip install -e . # Editable install


Define Your Configuration
-------------------------

Start by creating configuration classes using inheritance and type hints:

.. code-block:: python

   from zencfg import ConfigBase, make_config_from_cli

   # Define base categories
   class ModelConfig(ConfigBase):
       in_channels: int = 3
       out_channels: int = 1

   class OptimizerConfig(ConfigBase):
       lr: float = 1e-4

These base configurations are then used to define specific implementations, that you can quickly switch between.

For instance, let's define Configurations for a Transformer and a CNN, as well as a simple SGD and an Adam optimizer.

.. code-block:: python

   # Define specific implementations
   class TransformerConfig(ModelConfig):
       layers: int = 12
       n_heads: int = 8
       dropout: float = 0.1

   class CNNConfig(ModelConfig):
       channels: list[int] = [64, 128, 256]
       kernel_size: int = 3

   class AdamConfig(OptimizerConfig):
       weight_decay: float = 0.01
       # Uses the default lr from the base class

   class SGDConfig(OptimizerConfig):
       lr: float = 1e-3
       momentum: float = 0.9
       nesterov: bool = True

   # Compose your main configuration
   class ExperimentConfig(ConfigBase):
       model: ModelConfig = TransformerConfig()
       optimizer: OptimizerConfig = AdamConfig()
       batch_size: int = 32
       epochs: int = 100


Use in Your Scripts
-------------------


Using your newly defined configurations is as simple as calling the make_config function. 

``make_config_from_cli`` function.
This will automatically parse the command line arguments and return a configuration instance.

.. code-block:: python

   # Get configuration with command-line overrides
   config = make_config_from_cli(ExperimentConfig)
   
   # Use your config
   print(f"Training {config.model._config_name} with {config.optimizer._config_name}")
   print(f"Batch size: {config.batch_size}, Epochs: {config.epochs}")


Command Line Usage
------------------

Run your scripts with flexible parameter overrides:

.. code-block:: bash

   # Switch architectures
   python train.py --model cnnconfig --model.channels "[32,64,128]"
   
   # Change optimizers
   python train.py --optimizer adamconfig --optimizer.weight_decay 0.001
   
   # Mix and match everything
   python train.py --model transformerconfig --model.n_heads 16 --batch_size 64

Your configurations are now **type-safe**, **IDE-friendly**, and **command-line ready**.

Loading from Files
------------------

For larger projects, you can organize configurations in separate files:


.. code-block:: python

   from zencfg import make_config_from_cli, cfg_from_file
   from pathlib import Path

   path_to_config = Path("configs/experiment.py")
   # Option 1: Load class and use make_config_from_cli, by passing the path to the file and the class name
   ExperimentConfig = cfg_from_file(path_to_config, "ExperimentConfig")
   # Optionally, you can override specific parameters from the command line:
   config = make_config_from_cli(ExperimentConfig)

   # Option 2: Direct loading with make_config_from_cli
   config = make_config_from_cli("configs/experiment.py", "ExperimentConfig")

   # Both approaches support command-line overrides
   # python main.py --model.layers 24 --batch_size 64

The main difference: `cfg_from_file` returns the class for reuse, while `make_config_from_cli` directly creates an instance.

Next Steps
----------

- Check out :doc:`examples` for more complex scenarios
- Read the :doc:`api` documentation for advanced features
- Explore :doc:`advanced` topics for power users
   