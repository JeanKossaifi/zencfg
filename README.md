# ZenCFG

A Zen way to configure your Python packages while keeping your sanity.

## ⚡ Quick Start

```python
from zencfg import ConfigBase, make_config_from_cli

# Define base categories
class ModelConfig(ConfigBase):
    pass

class OptimizerConfig(ConfigBase):
    pass

# Define model architectures
class TransformerConfig(ModelConfig):
    layers: int = 12
    n_heads: int = 8

class CNNConfig(ModelConfig):
    channels: list[int] = [64, 128, 256]
    kernel_size: int = 3

# Define optimizers  
class AdamConfig(OptimizerConfig):
    lr: float = 1e-4
    weight_decay: float = 0.01

class SGDConfig(OptimizerConfig):
    lr: float = 1e-3
    momentum: float = 0.9

# Compose your experiment
class ExperimentConfig(ConfigBase):
    model: ModelConfig = TransformerConfig()
    optimizer: OptimizerConfig = AdamConfig()
    batch_size: int = 32

# Get config with command-line overrides
config = make_config_from_cli(ExperimentConfig)
```

Switch between architectures and tune their specific parameters:
```bash
# Switch to CNN with specific CNN parameters
python train.py --model cnnconfig --model.channels "[32,64,128]" --model.kernel_size 5

# Try SGD with momentum
python train.py --optimizer sgdconfig --optimizer.momentum 0.95 --batch_size 128

# Mix and match everything
python train.py --model transformerconfig --model.n_heads 16 --optimizer adamconfig --optimizer.weight_decay 0.001
```

## Why ZenCFG

ZenCFG (for *Zen ConFiGuration*), is the result of many iterations of trying pretty much every existing approach to Python configuration management systems and being satisfied by none of them. 

The key advantages of ZenCFG are:

### **1. Native Python Tooling**
Work with configs like any other Python code—inheritance, composition, and type hints provide familiar development patterns.
This also means full IDE support with autocomplete, refactoring safety, and type checking.

```python
class ModelConfig(ConfigBase):
    layers: int = 12  # IDE autocomplete and type checking
    learning_rate: float = 1e-4  # Runtime validation through type hints
```

### **2. Reduced Debugging Time** 
Catch configuration errors at startup with type safety and runtime validation, not hours into expensive training runs.

```python
config = ModelConfig(layers="invalid")  # ValidationError immediately!
# No more failed experiments due to config typos
```

### **3. Quick and Flexible Experimentation**
Override any nested parameter through intuitive command-line syntax without file editing. Switch between model architectures, optimizers, and their specific parameters in a single command.

```bash
# Switch architectures and tune their specific parameters
python train.py --model ditconfig --model.n_heads 16 --optimizer sgdconfig --optimizer.momentum 0.9
```

### **4. Zero Boilerplate**
Pure Python classes with no frameworks, no special syntax, and no additional dependencies. If you know Python, you know ZenCFG.

```python
from zencfg import make_config_from_cli
config = make_config_from_cli(MyConfig)  # That's it!
```

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
    opt: OptimizerConfig = OptimizerConfig(_config_name='adamw')
```

Note the `_config_name="adamw"`: this indicates that the default will be the AdamW class. 
You can create a subcategory by passing to the main category class the class name of the subcategory you want to create, 
through `_config_name`. 

The above is equivalent to explicitly creating an ADAMW optimizer:

```python
class Config(ConfigBase):
    model: ModelConfig
    opt: OptimizerConfig = AdamW(_config_name='adamw')
```

### Instantiating configurations

Your configurations are Python object: you can instantiate them:

```python
config = Config(model = ModelConfig(_config_name='dit', layers=24))
```

## Instantiating a configuration with optional values from the command line

The library also lets you override parameters from the configuration through the command line, 
using `make_config_from_cli`.

For instance, you can create a script `main.py` containing:
```python
from zencfg import make_config_from_cli

from YOUR_CONFIG_FILE import Config

config = make_config_from_cli(Config, strict=True)
```

You can then call your script via the command line. 
In that case, we simply use `.` to indicate nesting.

For instance, to instantiate the same config as above, you could simply do:
```bash
python main.py --model dit --model.layers 24
```

Or, equivalently, but more verbose (but perhaps also more explicitly):
```bash
python main.py --model._config_name dit --model.layers 24
```

You can switch between different config types and override their specific parameters:
```bash
# Switch optimizers with their specific parameters
python main.py --opt adamw --opt.weight_decay 0.001
python main.py --opt sgd --opt.momentum 0.9

# Mix model and optimizer changes
python main.py --model unet --model.conv "new_conv" --opt adamw --opt.weight_decay 0.01
```

## Export your configuration to dictionary

While you can directly use the configuration, you can also get a Python dictionary from a configuration instance, by simply using the `to_dict` method:

```python
config_dict = config.to_dict()

model_cfg = config_dict['model']

# You can access values as attributes too
optimizer_cfg = config_dict.opt
```

## Examples

For concrete examples, check the [`examples`](examples/) folder.
You can try running [`test_config`](examples/test_config.py) script.

## Gotchas

Note that we handle ConfigBase types differently. Consider the following scenario:
```python
class ModelConfig(ConfigBase):
    in_channels: int = 3
    out_channels: int = 1

class UNet(ModelConfig):
    layers: int = 10
    kernel: Tuple[int] = (3, 3)

class DiT(ModelConfig):
    layers: int = 10
    n_heads: int = 12

class Config(ConfigBase):
    some_param: str = 'whatever'
    model: ModelConfig = DiT(layers=4)
```

Now, if a user wants to override the number of layers through the command line to 6, they'd want to write:
```bash
python script.py --model.layers 6
```

We allow this and it will give you a DiT model with 6 layers. 

This is where the gotcha comes from: if you just instantiate the default type with layers=6, 
you would be instantiating a `ModelConfig`, **not** a DiT (which would also cause an error since ModelConfig does not have layers).

To fix this, we treat ConfigBase parameters differently: we first take the default value (here, DiT(layers=4)). 
Then, if the user passes a new `_config_name` (e.g. 'unet'), we discard those and use only users defaults.

Otherwise, if the user does **not** pass a `_config_name` (i.e. they want to use the default), then we use 
the same defaults (`DiT(layers=4)`), which is turned into a dict: `{'_config_name': 'dit', 'layers': 4}` and we update it 
with the values passed by the user. 

This causes the least surprises in general but you may want to be aware of this.
For example, back to our example, this will allow the users to get back a config that matches what they'd expect: 
 `{'_config_name': 'dit', 'layers': 6}`

## Questions or issues
This is very much a project in development that I wrote for myself and decided to share so others could easily reuse it for multiple projects, while knowing it is tested and actively developed!

If you have any questions or find any bugs, please open an issue, or better yet, a pull-request!
