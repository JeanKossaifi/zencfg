import pytest
import tempfile
import os
from pathlib import Path
from typing import List

from ..config import ConfigBase
from ..from_file import cfg_from_file


def test_cfg_from_file():
    """Test loading config from file."""
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
        # Test simple loading
        ExperimentConfig = cfg_from_file(temp_file, 'TestExperimentConfig')
        config = ExperimentConfig()
        
        assert config.batch_size == 32
        assert config.model.layers == 12
        assert config.model.n_heads == 8
        
        # Test that it's a proper ConfigBase subclass
        assert issubclass(ExperimentConfig, ConfigBase)
        
    finally:
        os.unlink(temp_file)


def test_cfg_from_file_invalid_class():
    """Test that loading non-ConfigBase classes raises an error."""
    # Create a temporary file with a non-ConfigBase class
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
class NotAConfig:
    pass
""")
        temp_file = f.name
    
    try:
        with pytest.raises(TypeError, match="is not a ConfigBase subclass"):
            cfg_from_file(temp_file, 'NotAConfig')
    finally:
        os.unlink(temp_file)


def test_cfg_from_file_missing_class():
    """Test that loading non-existent class raises an error."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
from zencfg import ConfigBase

class TestConfig(ConfigBase):
    pass
""")
        temp_file = f.name
    
    try:
        with pytest.raises(AttributeError):
            cfg_from_file(temp_file, 'NonExistentConfig')
    finally:
        os.unlink(temp_file) 