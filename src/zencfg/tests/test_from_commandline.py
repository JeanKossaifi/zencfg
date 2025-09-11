import pytest
import tempfile
import os
from typing import List, Union

from ..config import ConfigBase
from ..from_commandline import make_config, make_config_from_cli


def test_make_config_from_class():
    """Test make_config with a class and overrides."""
    class TestConfig(ConfigBase):
        value: str = "default"
        number: int = 42
    
    # Test with no overrides
    config1 = make_config(TestConfig)
    assert config1.value == "default"
    assert config1.number == 42
    
    # Test with overrides
    config2 = make_config(TestConfig, value="modified", number=100)
    assert config2.value == "modified"
    assert config2.number == 100


def test_make_config_from_instance():
    """Test make_config with an instance and overrides."""
    class TestConfig(ConfigBase):
        value: str = "default"
        number: int = 42
    
    base_instance = TestConfig(value="instance_value", number=99)
    
    # Test with no overrides (should return same instance)
    config1 = make_config(base_instance)
    assert config1 is base_instance
    assert config1.value == "instance_value"
    assert config1.number == 99
    
    # Test with overrides (should return new instance)
    config2 = make_config(base_instance, value="overridden")
    assert config2 is not base_instance
    assert config2.value == "overridden"
    assert config2.number == 99  # Should preserve non-overridden values


def test_make_config_from_file():
    """Test make_config with a file path."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
from zencfg import ConfigBase

class TestConfig(ConfigBase):
    value: str = "file_default"
    number: int = 123

test_instance = TestConfig(value="file_instance", number=456)
''')
        temp_file = f.name
    
    try:
        # Test loading class with overrides
        config1 = make_config(temp_file, "TestConfig", value="file_override")
        assert config1.value == "file_override"
        assert config1.number == 123
        
        # Test loading instance with overrides
        config2 = make_config(temp_file, "test_instance", value="instance_override")
        assert config2.value == "instance_override"
        assert config2.number == 456
        
    finally:
        os.unlink(temp_file)


def test_make_config_from_file_requires_name():
    """Test that make_config requires a name when loading from a file."""
    import tempfile
    
    # Create a temporary config file
    temp_file = tempfile.mktemp(suffix='.py')
    try:
        with open(temp_file, 'w') as f:
            f.write('''
from zencfg import ConfigBase

class TestConfig(ConfigBase):
    value: str = "test"
    number: int = 42
''')
        
        # Should raise error when name is not provided
        with pytest.raises(ValueError, match="name parameter is required"):
            make_config(temp_file)  # No name provided
        
        # Works when name is provided explicitly
        config = make_config(temp_file, "TestConfig")
        assert config.value == "test"
        assert config.number == 42
        
    finally:
        os.unlink(temp_file)


def test_make_config_invalid_source():
    """Test that make_config raises error for invalid source types."""
    with pytest.raises(TypeError, match="Unsupported source type"):
        make_config(123)  # Invalid type


def test_make_config_from_cli_with_class(monkeypatch):
    """Test make_config_from_cli with a class."""
    monkeypatch.setattr("sys.argv", ['test', '--value', 'cli_value', '--number', '999'])
    
    class TestConfig(ConfigBase):
        value: str = "default"
        number: int = 42
    
    config = make_config_from_cli(TestConfig)
    assert config.value == "cli_value"
    assert config.number == 999


def test_make_config_from_cli_with_instance(monkeypatch):
    """Test make_config_from_cli with an instance."""
    monkeypatch.setattr("sys.argv", ['test', '--value', 'cli_override'])
    
    class TestConfig(ConfigBase):
        value: str = "default"
        number: int = 42
    
    base_instance = TestConfig(value="instance_value", number=100)
    config = make_config_from_cli(base_instance)
    
    assert config.value == "cli_override"  # Overridden by CLI
    assert config.number == 100  # Preserved from instance


def test_make_config_from_cli_with_file(monkeypatch):
    """Test make_config_from_cli with a file path."""
    monkeypatch.setattr("sys.argv", ['test', '--value', 'cli_file_override'])
    
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
from zencfg import ConfigBase

class TestConfig(ConfigBase):
    value: str = "file_default"
    number: int = 123
''')
        temp_file = f.name
    
    try:
        config = make_config_from_cli(temp_file, config_name="TestConfig")
        assert config.value == "cli_file_override"
        assert config.number == 123
        
    finally:
        os.unlink(temp_file)


def test_make_config_from_cli_requires_name(monkeypatch):
    """Test that make_config_from_cli requires a name when loading from a file."""
    import tempfile
    
    # Set up CLI args
    monkeypatch.setattr("sys.argv", ['test', '--value', 'modified', '--number', '100'])
    
    # Create a temporary config file
    temp_file = tempfile.mktemp(suffix='.py')
    try:
        with open(temp_file, 'w') as f:
            f.write('''
from zencfg import ConfigBase

class TestConfig(ConfigBase):
    value: str = "test"
    number: int = 42
''')
        
        # Should raise error when name is not provided
        with pytest.raises(ValueError, match="config_name is required"):
            make_config_from_cli(temp_file)  # No name provided
        
        # Works when name is provided
        config = make_config_from_cli(temp_file, config_name="TestConfig")
        assert config.value == "modified"  # CLI override
        assert config.number == 100  # CLI override
        
    finally:
        os.unlink(temp_file)


def test_make_config_from_cli_invalid_args(monkeypatch):
    """Test that make_config_from_cli raises error for odd number of args."""
    monkeypatch.setattr("sys.argv", ['test', '--value'])  # Missing value
    
    class TestConfig(ConfigBase):
        value: str = "default"
    
    with pytest.raises(ValueError, match="Arguments must be in pairs"):
        make_config_from_cli(TestConfig)