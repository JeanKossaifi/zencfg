import pytest
import tempfile
import os
from pathlib import Path
from typing import List

from ..config import ConfigBase
from ..from_file import load_config_from_file


def test_load_config_from_file():
    """Test basic config loading from file."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
from zencfg import ConfigBase

class TestModelConfig(ConfigBase):
    layers: int = 12
    n_heads: int = 8

class TestExperimentConfig(ConfigBase):
    model: TestModelConfig = TestModelConfig()
    batch_size: int = 32
""")
        temp_file = f.name
    
    try:
        # Test loading with new API
        temp_path = Path(temp_file)
        ExperimentConfig = load_config_from_file(
            temp_path.parent, 
            temp_path.name, 
            'TestExperimentConfig'
        )
        config = ExperimentConfig()
        
        assert config.batch_size == 32
        assert config.model.layers == 12
        assert config.model.n_heads == 8
        assert issubclass(ExperimentConfig, ConfigBase)
        
    finally:
        os.unlink(temp_file)


def test_load_config_from_file_invalid_class():
    """Test that loading non-ConfigBase classes raises an error."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
class NotAConfig:
    pass
""")
        temp_file = f.name
    
    try:
        with pytest.raises(TypeError, match="must be a ConfigBase class or instance"):
            temp_path = Path(temp_file)
            load_config_from_file(temp_path.parent, temp_path.name, 'NotAConfig')
    finally:
        os.unlink(temp_file)


def test_load_config_from_file_missing_class():
    """Test that loading non-existent class raises an error."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
from zencfg import ConfigBase

class TestConfig(ConfigBase):
    pass
""")
        temp_file = f.name
    
    try:
        with pytest.raises(AttributeError):
            temp_path = Path(temp_file)
            load_config_from_file(temp_path.parent, temp_path.name, 'NonExistentConfig')
    finally:
        os.unlink(temp_file)