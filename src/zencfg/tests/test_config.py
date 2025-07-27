import pytest
from typing import List, Union, Optional

from ..config import ConfigBase

def test_config():
    """Tests the ConfigBase class."""
    # Define a base Model config
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

    with pytest.raises(ValueError):
        c = Config()

    c = Config(model = ModelConfig(name='DIT', layers=24))
    assert c.model.name == "DIT"
    assert c.model.layers == 24

def test_type_validation():
    """Test that type validation works during attribute setting."""
    class TestConfig(ConfigBase):
        int_field: int = 1
        str_field: str = "test"
        float_field: float = 1.0
        list_field: List[int] = [1, 2, 3]

    # Test valid values
    cfg = TestConfig(int_field="2")  # Should convert string to int
    assert cfg.int_field == 2
    assert isinstance(cfg.int_field, int)

    cfg = TestConfig(float_field="2.5")  # Should convert string to float
    assert cfg.float_field == 2.5
    assert isinstance(cfg.float_field, float)

    cfg = TestConfig(list_field=["1", "2", "3"])  # Should convert strings to ints
    assert cfg.list_field == [1, 2, 3]
    assert all(isinstance(x, int) for x in cfg.list_field)

    # Test invalid values
    with pytest.raises(TypeError):
        TestConfig(int_field="not_an_int")
    with pytest.raises(TypeError):
        TestConfig(float_field="not_a_float")
    with pytest.raises(TypeError):
        TestConfig(list_field=["not_an_int"])


def test_list_of_configbase_default():
    """Test that a List[ConfigBase] with instantiated objects as default works (deep learning context)."""
    from typing import List, Optional
    class LayerConfig(ConfigBase):
        type: str  # e.g., 'conv', 'linear', 'relu'
        out_features: Optional[int] = None
        kernel_size: Optional[int] = None
        activation: Optional[str] = None
    class ModelConfig(ConfigBase):
        layers: List[LayerConfig] = [
            LayerConfig(type="conv", out_features=32, kernel_size=3, activation="relu"),
            LayerConfig(type="linear", out_features=10, activation="softmax")
        ]
        name: str = "MyNet"
    # Should not raise
    cfg = ModelConfig()
    assert isinstance(cfg.layers, list)
    assert isinstance(cfg.layers[0], LayerConfig)
    assert cfg.layers[0].type == "conv"
    assert cfg.layers[1].activation == "softmax"
    assert cfg.name == "MyNet"


def test_instantiate():
    """Test basic instantiate functionality with both string and callable targets."""
    
    # Test 1: String target
    class StringTargetConfig(ConfigBase):
        _target_class = "collections.namedtuple"
        typename: str = "Point"
        field_names: list = ['x', 'y']
    
    config1 = StringTargetConfig()
    Point = config1.instantiate()
    
    # Should create a namedtuple class
    assert callable(Point)
    point = Point(1, 2)
    assert point.x == 1
    assert point.y == 2
    
    # Test 2: Direct callable target
    class CallableTargetConfig(ConfigBase):
        _target_class = dict
        name: str = "test"
        value: int = 42
    
    config2 = CallableTargetConfig()
    result = config2.instantiate()
    
    # Should create a dict with the config parameters
    assert result == {"name": "test", "value": 42}
