#!/usr/bin/env python3
"""
ZenCFG Example: Nested Configuration with Inheritance

This example demonstrates how to create complex nested configurations
with inheritance and command-line overrides.

Usage:
    python test_config.py --model compositemodel --model.submodel DIT
"""

from zencfg import ConfigBase, make_config_from_cli, make_config
from typing import Union, List, Optional
from pathlib import Path


class ModelConfig(ConfigBase):
    """Base class for all model configurations."""
    version: str = "0.1.0"


class DiT(ModelConfig):
    """Diffusion Transformer model configuration."""
    layers: Union[int, List[int]] = [16, 8]
    version: str = '2.0.0'
    dropout: Optional[float] = None


class UNet(ModelConfig):
    """UNet model configuration."""
    conv: str = "DISCO"


class CompositeModel(ModelConfig):
    """Composite model that contains other models."""
    submodel: ModelConfig
    num_heads: int = 4


class OptimizerConfig(ConfigBase):
    """Base class for optimizer configurations."""
    lr: float = 0.001


class AdamW(OptimizerConfig):
    """AdamW optimizer configuration."""
    weight_decay: float = 0.01


class ExperimentConfig(ConfigBase):
    """Complete experiment configuration."""
    model: ModelConfig = DiT()
    optimizer: OptimizerConfig = AdamW()
    checkpoint_path: Union[str, Path, None] = None
    other_param = 'NOTYPE'  # No type annotation


if __name__ == "__main__":
    # Load configuration with command-line overrides
    config = make_config_from_cli(ExperimentConfig, strict=True)
    
    # Alternative: create config with overrides
    # config = make_config(ExperimentConfig, other_param='MODIFIED')
    # config = make_config('configs.py', 'ExperimentConfig', epochs=200)
    # config = make_config(existing_instance, other_param='UPDATED')
    
    print("Configuration loaded successfully!")
    print(f"Model: {config.model._config_name}")
    print(f"Optimizer: {config.optimizer._config_name}")
    print(f"Learning rate: {config.optimizer.lr}")
    
    # Show the full configuration as dictionary
    print("\nFull configuration:")
    print(config.to_dict())
