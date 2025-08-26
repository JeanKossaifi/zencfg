import pytest
from typing import List, Union, Optional

from ..config import ConfigBase

# Helper classes for testing instantiate
class OptimizerLike:
    """Simulates an optimizer class that takes model parameters as first arg."""
    def __init__(self, params, lr=0.001, momentum=0.9):
        self.params = params
        self.lr = lr
        self.momentum = momentum
        
class ModelLike:
    """Simulates a model class with configuration parameters."""
    def __init__(self, in_features=10, out_features=2, bias=True):
        self.in_features = in_features
        self.out_features = out_features
        self.bias = bias

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
    """Test basic instantiate functionality with both string and class targets."""
    
    # Test 1: String target (fully qualified module path)
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
    
    # Test 2: Direct class target
    class ClassTargetConfig(ConfigBase):
        _target_class = dict  # Built-in class
        name: str = "test"
        value: int = 42
    
    config2 = ClassTargetConfig()
    result = config2.instantiate()
    
    # Should create a dict with the config parameters
    assert result == {"name": "test", "value": 42}
    
    # Test 3: Custom class target
    class ModelConfig(ConfigBase):
        _target_class = ModelLike  # Our test class
        in_features: int = 784
        out_features: int = 10
        bias: bool = False
    
    config3 = ModelConfig()
    model = config3.instantiate()
    
    assert model.in_features == 784
    assert model.out_features == 10
    assert model.bias == False


def test_instantiate_with_additional_args():
    """Test instantiate with additional positional arguments."""
    
    # Test 1: Using a class (like torch.optim.Adam) with positional args
    class OptimizerConfig(ConfigBase):
        _target_class = OptimizerLike  # This is a CLASS, not a function
        lr: float = 0.001
        momentum: float = 0.9
    
    config = OptimizerConfig(lr=0.002, momentum=0.95)
    fake_params = ["param1", "param2"]  # Simulating model.parameters()
    optimizer = config.instantiate(fake_params)
    
    # Verify the optimizer was created correctly
    assert optimizer.params == fake_params
    assert optimizer.lr == 0.002
    assert optimizer.momentum == 0.95
    
    # Test 2: Multiple positional arguments
    def create_object(a, b, c=3, d=4):
        return {"a": a, "b": b, "c": c, "d": d}
    
    class MultiArgConfig(ConfigBase):
        _target_class = create_object
        c: int = 30
        d: int = 40
    
    config2 = MultiArgConfig()
    result2 = config2.instantiate(1, 2)  # Provide required positional args
    
    assert result2 == {"a": 1, "b": 2, "c": 30, "d": 40}


def test_instantiate_with_kwargs_override():
    """Test that kwargs can override config parameters."""
    
    class ConfigurableClass:
        def __init__(self, param1=1, param2=2, param3=3):
            self.param1 = param1
            self.param2 = param2
            self.param3 = param3
    
    class OverrideConfig(ConfigBase):
        _target_class = ConfigurableClass
        param1: int = 10
        param2: int = 20
        param3: int = 30
    
    config = OverrideConfig()
    
    # Test 1: Override one parameter
    obj1 = config.instantiate(param2=200)
    assert obj1.param1 == 10
    assert obj1.param2 == 200  # Overridden by kwarg
    assert obj1.param3 == 30
    
    # Test 2: Override multiple parameters
    obj2 = config.instantiate(param1=100, param3=300)
    assert obj2.param1 == 100  # Overridden
    assert obj2.param2 == 20
    assert obj2.param3 == 300  # Overridden
    
    # Test 3: Add new parameters not in config
    obj3 = config.instantiate(param2=25)
    assert obj3.param2 == 25


def test_instantiate_mixed_args_kwargs():
    """Test instantiate with both positional and keyword arguments."""
    
    def create_mixed(required_arg, optional_arg=None, config_param=10, extra_param=20):
        return {
            "required": required_arg,
            "optional": optional_arg,
            "config": config_param,
            "extra": extra_param
        }
    
    class MixedConfig(ConfigBase):
        _target_class = create_mixed
        config_param: int = 100
        # Don't define extra_param in config
    
    config = MixedConfig()
    
    # Test with both args and kwargs
    result = config.instantiate("required_value", optional_arg="optional", extra_param=200)
    
    assert result["required"] == "required_value"
    assert result["optional"] == "optional"
    assert result["config"] == 100  # From config
    assert result["extra"] == 200  # From kwargs
