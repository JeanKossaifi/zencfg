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

class LAMB(OptimizerConfig):
    lamb_param: float = 0.01

class SchedulerConfig(ConfigBase):
    patience: float = 100

class Config(ConfigBase):
    model: ModelConfig
    opt: OptimizerConfig = OptimizerConfig(_config_name="adamw")
    scheduler: SchedulerConfig = SchedulerConfig()

@pytest.fixture
def config_class():
    return Config


def test_simple_config_from_dict(config_class):
    """
    Basic test showing how to build a config from dotted keys, using local classes.
    """
    data = {
        "model._config_name": "dit",
        "model.layers": "8",  # string, should parse to int
        "opt._config_name": "adamw",
        "opt.lr": "0.005", # should parse to float
        "opt.weight_decay": "0.1",
    }
    cfg = cfg_from_flat_dict(config_class, data, strict=True)

    # 'cfg.model' should be an instance of the DiT subclass
    assert cfg.model._config_name.lower() == "dit"
    assert cfg.model.version == "0.1.0"
    assert cfg.model.layers == 8

    # 'cfg.opt' should be AdamW
    assert cfg.opt._config_name == "adamw"
    assert cfg.opt.lr == 0.005
    assert cfg.opt.weight_decay == 0.1


def test_composite_style_from_dict(config_class):
    """
    Another scenario: create a nested model (like a 'composite model' example).
    """
    data = {
        "model._config_name": "compositemodel",
        "model.submodel._config_name": "Unet",
        "model.submodel.conv": "Success",
        "opt._config_name": "adamw",
    }
    cfg = cfg_from_flat_dict(config_class, data)

    assert cfg.model.submodel._config_name.lower() == "unet"
    assert cfg.model.submodel.conv == "Success"
    assert cfg.opt._config_name == "adamw"
    assert isinstance(cfg.model, CompositeModel)
    assert isinstance(cfg.model.submodel, Unet)
    
    # Check that we didn't ALSO add some other model parameters
    cfg = cfg.to_dict()
    for param, value in cfg.model.items():
        if param == '_config_name':
            assert (value.lower() != 'dit')
    for param, value in cfg.model.submodel.items():
        if param == '_config_name':
            assert (value.lower() != 'dit')

def test_invalid_keys_from_dict(config_class):
    """
    Test that if a key conflicts with a non-dict in the path, we raise ValueError.
    """
    data = {
        "model.params": "DOesn't exist",
        "model.version": '0.1.2',
    }
    with pytest.raises(ValueError):
        cfg_from_flat_dict(config_class, data)

    # Just a wrong name
    data = {
        "model": "NOT A MODEL",
        "model.version": '0.1.2',
    }
    with pytest.raises(ValueError):
        cfg_from_flat_dict(config_class, data)

    # Right name, wrong parameter
    data = {
        "model": "DIT",
        "model.unexistant_param": 'DOES NOT EXIST',
    }
    with pytest.raises(ValueError):
        cfg_from_flat_dict(config_class, data)


def test_flat_dict_to_nested_simple():
    """
    Test that a straightforward dotted dictionary is converted into the correct nested structure.
    """
    data = {
        "model._config_name": "unet",
        "model.params.num_layers": 24,
        "model.params.dropout": 0.1,
        "optimizer.lr": 0.001,
    }
    expected = {
        "model": {
            "_config_name": "unet",
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


def test_preserve_config_defaults_args(config_class):
    """
    That's a tricky one: for ConfigBase type, we want to 
    **add** users' parameters to the existing default parameters. 
    
    Otherwise, if user just change parameters, but not _config_name, 
    they expect to get a class with the same defaults as the original class.
    But they'd instead get the base class.
    """
    class OptimizerConfig(ConfigBase):
        lr: float = 0.001

    class AdamW(OptimizerConfig):
        weight_decay: float = 0.01

    class Config(ConfigBase):
        model: ModelConfig
        opt: OptimizerConfig = OptimizerConfig(_config_name="adamw")
        scheduler: SchedulerConfig = SchedulerConfig()

    data = {
        "opt.weight_decay": "10",
    }
    result = cfg_from_flat_dict(Config, data)
    assert result.opt._config_name == 'adamw', f"Expected 'adamw' but got {result}"


