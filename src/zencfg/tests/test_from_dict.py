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
        param: int = 2

    class Config(ConfigBase):
        model: ModelConfig
        opt: OptimizerConfig = OptimizerConfig(_config_name="adamw", weight_decay=10)
        scheduler: SchedulerConfig = SchedulerConfig()

    data = {
        "opt.param": "10",
    }
    result = cfg_from_flat_dict(Config, data)
    assert result.opt._config_name == 'adamw', f"Expected 'adamw' but got {result}"
    assert result.opt.weight_decay == 0.01
    assert result.opt.param == 10




def test_no_subclass():
    class OptimizerConfig(ConfigBase):
        lr: float = 0.001

    class AdamW(OptimizerConfig):
        weight_decay: float = 0.01
        param: int = 2

    class Config(ConfigBase):
        model: ModelConfig
        opt: OptimizerConfig = OptimizerConfig()
        scheduler: SchedulerConfig = SchedulerConfig()

    data = {
        "model._config_name": "dit",
        "opt._config_name": "adamw",
        "opt.lr": "0.005",
        "opt.weight_decay": "0.1",
        "opt.param": "5",
    }
    cfg = cfg_from_flat_dict(Config, data, strict=True)

    assert cfg.opt._config_name == "adamw"
    assert cfg.opt.lr == 0.005
    assert cfg.opt.weight_decay == 0.1
    assert cfg.opt.param == 5


def test_untyped_fields_from_dict():
    """Test that fields without type hints are properly handled."""
    class ConfigWithUntyped(ConfigBase):
        typed_field: str = "default_typed"
        untyped_field = "default_untyped"
        another_untyped = 42

    data = {
        "typed_field": "new_typed_value",
        "untyped_field": "new_untyped_value", 
        "another_untyped": 100
    }
    
    cfg = cfg_from_flat_dict(ConfigWithUntyped, data, strict=True)
    assert cfg.typed_field == "new_typed_value"
    assert cfg.untyped_field == "new_untyped_value"
    assert cfg.another_untyped == 100
    
    # Test with partial data
    data_partial = {
        "typed_field": "partial_test",
        "untyped_field": "partial_untyped"
    }
    
    cfg_partial = cfg_from_flat_dict(ConfigWithUntyped, data_partial, strict=True)
    assert cfg_partial.typed_field == "partial_test"
    assert cfg_partial.untyped_field == "partial_untyped"
    assert cfg_partial.another_untyped == 42  # Should keep default


def test_untyped_fields_with_nested_config():
    """Test that untyped fields work correctly alongside nested ConfigBase fields."""
    class NestedConfig(ConfigBase):
        nested_param: str = "nested_default"
    
    class ConfigWithBoth(ConfigBase):
        nested: NestedConfig = NestedConfig()
        typed_field: int = 10
        untyped_field = "untyped_default"
    
    data = {
        "nested.nested_param": "new_nested_value",
        "typed_field": "20",  # Should parse to int
        "untyped_field": "new_untyped_value"
    }
    
    cfg = cfg_from_flat_dict(ConfigWithBoth, data, strict=True)
    assert cfg.nested.nested_param == "new_nested_value"
    assert cfg.typed_field == 20
    assert cfg.untyped_field == "new_untyped_value"


def test_internal_attributes_excluded():
    """Test that internal attributes like _registry are properly excluded from configuration."""
    class ConfigWithInternal(ConfigBase):
        public_field: str = "public"
        _registry = {"test": "should_be_excluded"}
    
    data = {"public_field": "new_value"}
    
    cfg = cfg_from_flat_dict(ConfigWithInternal, data, strict=True)
    assert cfg.public_field == "new_value"
    
    cfg_dict = cfg.to_dict()
    assert "_registry" not in cfg_dict
    assert "public_field" in cfg_dict