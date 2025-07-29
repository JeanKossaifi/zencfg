API Reference
=============

Core Classes
------------

ConfigBase
~~~~~~~~~~

The main configuration class that provides inheritance, type validation, and serialization capabilities.

.. autoclass:: zencfg.ConfigBase
   :members:
   :undoc-members:
   :show-inheritance:

Bunch
~~~~~

A dictionary-like object that exposes its keys as attributes, with special handling for nested updates.
This is what we return when we use the ``config.to_dict()`` method.

.. autoclass:: zencfg.bunch.Bunch
   :members:
   :undoc-members:
   :show-inheritance:


Loading and Instantiating Configurations
----------------------------------------

make_config
~~~~~~~~~~~

Create a config instance from any source:
- ConfigBase class: instantiate with optional overrides
- ConfigBase instance: apply overrides to a copy of instance
- File path (str or Path): load a configuration class or instance from a file

.. autofunction:: zencfg.make_config


make_config_from_cli
~~~~~~~~~~~~~~~~~~~~

Override any parameters of a configuration via the command-line argument. 
The configuration to load can be given as class, instance, or file.

.. autofunction:: zencfg.make_config_from_cli

make_config_from_flat_dict
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a configuration instance from a flat dictionary (with dot notation to signify nested keys).

.. autofunction:: zencfg.make_config_from_flat_dict

make_config_from_nested_dict
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a configuration instance from a nested dictionary structure.

.. autofunction:: zencfg.make_config_from_nested_dict

load_config_from_file
~~~~~~~~~~~~~~~~~~~~

Load a configuration class or instance from a Python file.

.. autofunction:: zencfg.load_config_from_file

Deprecated Functions
--------------------

.. warning::

   The following functions are deprecated and will be removed in a future version.

cfg_from_commandline
~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 1.0.0
   Use :func:`make_config_from_cli` instead.

Parse command-line arguments and create a configuration instance.

.. autofunction:: zencfg.cfg_from_commandline
