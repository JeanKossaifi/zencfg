# ZenCFG

A Zen way to configure your Python packages.

## Why ZenCFG

ZenCFG (for *Zen ConFiGuration*), is the result of many iterations of trying pretty much every existing approach to Python configuration management systems and being satisfied by none of them. 

The key building principles of ZenCFG are:
* Pure Python code
* Minimal amound of code
* Minimally intrusive
* Intuitive

In practice, this means that you can define your configuration as Python classes (like dataclasses). 
You can specify the type of the parameters, and we use Pydantic to verify them.
You can trivially override any of the parameters through the command-line, with an intuitive interface.

It was built originally to configure and manage scripts for Deep Learning experiments, but you can use it for any Python project.
The examples I use are Deep Learning inspired.

## Install

Just clone the repository and install it, here in editable mode:

```bash
git clone https://github.com/JeanKossaifi/zencfg
cd zencfg
python -m pip install -e .
```

## Defining configurations

There are two main type of configurations: core configuration categories, and subcategories.

### Core configurations categories

Core categories are defined by inheriting **directly** from ConfigBase:

```python
# We define a Model core config
class ModelConfig(ConfigBase):
    version: str = "0.1.0"

# Another base class: optimizer configurations
class OptimizerConfig(ConfigBase):
    lr: float = 0.001
```

### SubCategories

Now that you have core categories, you can optionally instantiate this as subcategories. 
For instance, the different type of models you have, optimizers, etc.

To do this, simply inherit from your core category:
```python
class DiT(ModelConfig):
    layers: Union[int, List[int]] = 16

class Unet(ModelConfig):
    conv: str = "DISCO"

# Nested config.
class CompositeModel(ModelConfig):
    submodel: ModelConfig
    num_heads: int = 4

class AdamW(OptimizerConfig):
    weight_decay: float = 0.01
```

### Composing categories
You can have configuration objects as parameters in your config: 
for instance, our main configuration will contain a model and an optimizer.

```python
# Our main config is also a core category, and encapsulates a model and an optimizer
class Config(ConfigBase):
    model: ModelConfig
    opt: OptimizerConfig = OptimizerConfig(_name='adamw')
```

Note the `_name="adamw"`: this indicates that the default will be the AdamW class. 
You can create a subcategory by passing to the main category class the class name of the subcategory you want to create, 
through `_name`. 

The above is equivalent to explicitly creating an ADAMW optimizer:

```python
class Config(ConfigBase):
    model: ModelConfig
    opt: OptimizerConfig = AdamW(_name='adamw')
```


### Instantiating configurations

Your configurations are Python object: you can instantiate them:

```python
config = Config(model = ModelConfig(name='DIT', layers=24))
```

## Instantiating a configuration with optional values from the command line

The library also lets you override parameters from the configuration through the command line, 
using `cfg_from_flat_dict`.

For instance, you can create a script `main.py` containing:
```python
from zencfg import cfg_from_flat_dict

from YOUR_CONFIG_FILE import Config

config = cfg_from_flat_dict(Config, strict=True)
```

You can then call your script via the command line. 
In that case, we simply use `.` to indicate nesting.

For instance, to instantiate the same config as above, you could simply do:
```bash
python main.py --model._name DIT --model.layers 24
```

## Configuration to dictionary
You can directly get a Python dictionary from a configuration instance, simply use `to_dict`:

```python
config_dict = config.to_dict()

model_cfg = config_dict['model']

# You can access values as attributes too
optimizer_cfg = config_dict.opt
```

## Questions or issues
This is very much a project in development that I wrote for myself and decided to share so others could easily reuse it for multiple projects, while knowing it is tested and actively developed!

If you have any questions or find any bugs, please open an issue, or better yet, a pull-request!

