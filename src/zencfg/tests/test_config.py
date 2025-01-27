import pytest
from typing import List, Union

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
