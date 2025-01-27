import pytest
from typing import List, Union

from ..config import ConfigBase
from ..from_dict import cfg_from_flat_dict, flat_dict_to_nested


class ModelConfig(ConfigBase):
    version: str = "0.1.0"

class DiT(ModelConfig):
    layers: Union[int, List[int]] = 16

class Unet(ModelConfig):
    conv: str = "DISCO"

class CompositeModel(ModelConfig):
    submodel: ModelConfig
    num_heads: int = 4

class OptimizerConfig(ConfigBase):
    lr: float = 0.001

class AdamW(OptimizerConfig):
    weight_decay: float = 0.01

class SchedulerConfig(ConfigBase):
    patience: float = 100

class Config(ConfigBase):
    model: ModelConfig
    opt: OptimizerConfig
    scheduler: SchedulerConfig = SchedulerConfig()

@pytest.fixture
def config_class():
    return Config


def test_simple_config(config_class):
    """
    Basic test showing how to build a config from dotted keys, using local classes.
    """
    data = {
        "model._name": "dit",
        "model.layers": "8",  # string, should parse to int
        "opt._name": "adamw",
        "opt.lr": "0.005", # should parse to float
        "opt.weight_decay": "0.1",
    }
    cfg = cfg_from_flat_dict(config_class, data, strict=True)

    # 'cfg.model' should be an instance of the DiT subclass
    assert cfg.model._name.lower() == "dit"
    assert cfg.model.version == "0.1.0"
    assert cfg.model.layers == 8

    # 'cfg.opt' should be AdamW
    assert cfg.opt._name == "adamw"
    assert cfg.opt.lr == 0.005
    assert cfg.opt.weight_decay == 0.1


def test_composite_style(config_class):
    """
    Another scenario: create a nested model (like a 'composite model' example).
    """
    data = {
        "model._name": "compositemodel",
        "model.submodel._name": "Unet",
        "model.submodel.conv": "Success",
        "opt._name": "adamw",
    }
    cfg = cfg_from_flat_dict(config_class, data)

    assert cfg.model.submodel._name.lower() == "unet"
    assert cfg.model.submodel.conv == "Success"
    assert cfg.opt._name == "adamw"
    assert isinstance(cfg.model, CompositeModel)
    assert isinstance(cfg.model.submodel, Unet)


def test_flat_dict_to_nested_simple():
    """
    Test that a straightforward dotted dictionary is converted into the correct nested structure.
    """
    data = {
        "model._name": "unet",
        "model.params.num_layers": 24,
        "model.params.dropout": 0.1,
        "optimizer.lr": 0.001,
    }
    expected = {
        "model": {
            "_name": "unet",
            "params": {
                "num_layers": 24,
                "dropout": 0.1,
            },
        },
        "optimizer": {
            "lr": 0.001,
        },
    }
    result = flat_dict_to_nested(data)
    assert result == expected, f"Expected {expected} but got {result}"


def test_flat_dict_to_nested_invalid():
    """
    Test that if a key conflicts with a non-dict in the path, we raise ValueError.
    """
    # Here, "model.params" is set to a string (not a dict),
    # but we also try to set "model.params.dropout".
    # This should trigger an error..."
    data = {
        "model.params": "not a dict",
        "model.params.dropout": 0.1,
    }
    with pytest.raises(ValueError):
        flat_dict_to_nested(data)
