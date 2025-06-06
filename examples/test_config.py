from zencfg import ConfigBase, cfg_from_commandline
from typing import Union, List, Optional
from pathlib import Path

"""
This example script shows how to define a config class with nested configurations.

You can try running this script with the following command:
```bash 
python test_config.py --model compositemodel --model.submodel DIT
```
"""


class ModelConfig(ConfigBase):
    version: str = "0.1.0"

# Is a ModelConfig
class DiT(ModelConfig):
    layers: Union[int, List[int]] = [16, 8]
    version: str = '2.0.0'
    dropout: Optional[float] = None

class Unet(ModelConfig):
    conv: str = "DISCO"

# Nested config.
class CompositeModel(ModelConfig):
    submodel: ModelConfig
    num_heads: int = 4

# Another base class: optimizer configurations
class OptimizerConfig(ConfigBase):
    lr: float = 0.001

class AdamW(OptimizerConfig):
    weight_decay: float = 0.01

class Config(ConfigBase):
    model: ModelConfig = DiT()
    opt: OptimizerConfig = AdamW()
    path: Union[str, Path, None] = None

if __name__ == "__main__":
    c = cfg_from_commandline(Config, strict=True)
    print(c)
    print(c.to_dict())

    # You could also explicitly instantiate the config:
    # c = Config(model = ModelConfig(_name='DIT', layers=24))
