"""Tests for deprecated functions."""

import pytest
from typing import List, Union

from ..config import ConfigBase
from ..deprecated import cfg_from_commandline


def test_config_from_commandline(monkeypatch):
    """"Test for initializing configs from the command line"""
    monkeypatch.setattr("sys.argv", ['test', 
                                     '--model._config_name', 'CompositeModel',
                                     '--model.submodel._config_name', 'dit',
                                     '--model.submodel.layers', 16,
                                     '--opt._config_name', 'adamw'])

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
    # _config_name reports the class name; selection is case-insensitive
    assert config.model._config_name == "CompositeModel"
    assert isinstance(config.model, CompositeModel)
    assert config.model.submodel._config_name == "DiT"
    assert config.model.submodel.layers == 16
    assert config.opt._config_name == "AdamW"