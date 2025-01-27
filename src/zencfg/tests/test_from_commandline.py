from typing import List, Union

from ..config import ConfigBase
from ..from_commandline import cfg_from_commandline

def test_config_from_commandline(monkeypatch):
    """"Test for initializing configs from the command line"""
    monkeypatch.setattr("sys.argv", ['test', 
                                     '--model._name', 'CompositeModel',
                                     '--model.submodel._name', 'dit',
                                     '--model.submodel.layers', 16,
                                     '--opt._name', 'adamw'])

    class ModelConfig(ConfigBase):
        version: str = "0.1.0"

    # Is a ModelConfig
    class DiT(ModelConfig):
        layers: Union[int, List[int]] = 16

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
        model: ModelConfig
        opt: OptimizerConfig = AdamW()

    config = cfg_from_commandline(Config)
    assert config.model._name == "CompositeModel"
    assert config.model.submodel._name == "dit"
    assert config.model.submodel.layers == 16
    assert config.opt._name == "adamw"