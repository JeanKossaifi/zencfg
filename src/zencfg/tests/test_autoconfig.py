"""Tests for AutoConfig functionality."""

import pytest
from ..config import ConfigBase, AutoConfig


def test_autoconfig_basic():
    """Test basic AutoConfig functionality with existing instances."""
    class DatabaseConfig(ConfigBase):
        host: str = "localhost"
    
    class AppConfig(ConfigBase):
        database: DatabaseConfig = AutoConfig()
    
    # Create instance - should auto-register
    db = DatabaseConfig(host="prod.db")
    
    # AutoConfig should find the registered instance
    config = AppConfig()
    assert config.database.host == "prod.db"
    assert config.database is db


def test_autoconfig_with_default_class():
    """Test AutoConfig with default_class parameter."""
    class DatabaseConfig(ConfigBase):
        host: str = "localhost"
    
    class CustomDatabaseConfig(DatabaseConfig):
        host: str = "custom.db"
    
    class AppConfig(ConfigBase):
        database: DatabaseConfig = AutoConfig(default_class=CustomDatabaseConfig)
    
    # No instances exist - should create CustomDatabaseConfig
    config = AppConfig()
    assert config.database.host == "custom.db"
    assert isinstance(config.database, CustomDatabaseConfig)


def test_autoconfig_fallback_to_field_type():
    """Test AutoConfig creates instance of field type when no instances exist."""
    class DatabaseConfig(ConfigBase):
        host: str = "localhost"
    
    class AppConfig(ConfigBase):
        database: DatabaseConfig = AutoConfig()
    
    # No instances exist - should create DatabaseConfig
    config = AppConfig()
    assert config.database.host == "localhost"
    assert isinstance(config.database, DatabaseConfig)


def test_autoconfig_required_error():
    """Test AutoConfig raises error when required=True and no instances exist."""
    class DatabaseConfig(ConfigBase):
        host: str = "localhost"
    
    class AppConfig(ConfigBase):
        database: DatabaseConfig = AutoConfig(required=True)
    
    # Should raise error since no instances exist
    with pytest.raises(ValueError, match="No instance of DatabaseConfig found for AutoConfig field"):
        AppConfig()


def test_autoconfig_latest_wins():
    """Test that AutoConfig uses the latest instance."""
    class DatabaseConfig(ConfigBase):
        host: str = "localhost"
    
    class AppConfig(ConfigBase):
        database: DatabaseConfig = AutoConfig()
    
    # Create first instance
    db1 = DatabaseConfig(host="first.db")
    config1 = AppConfig()
    assert config1.database.host == "first.db"
    
    # Create second instance - should become the latest
    db2 = DatabaseConfig(host="second.db")
    config2 = AppConfig()
    assert config2.database.host == "second.db"
    assert config2.database is db2