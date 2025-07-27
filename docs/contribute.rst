Contributing
============

Development Setup
-----------------

Clone and install in editable mode:

.. code-block:: bash

   git clone https://github.com/jeankossaifi/zencfg
   cd zencfg
   pip install -e .

Run tests:

.. code-block:: bash

   python -m pytest src/zencfg/tests/

Build documentation:

.. code-block:: bash

   cd docs
   sphinx-build -b html . _build/html

Internal Implementation
-----------------------

These functions are used internally by ZenCFG. They're documented here for contributors and advanced users who want to understand how the library works.

parse_value_to_type
~~~~~~~~~~~~~~~~~~~

Converts values to their expected types using Pydantic validation.

.. autofunction:: zencfg.config.parse_value_to_type

is_configbase_type
~~~~~~~~~~~~~~~~~~

Checks if a type is a ConfigBase subclass or Union containing ConfigBase.

.. autofunction:: zencfg.config.is_configbase_type

gather_defaults
~~~~~~~~~~~~~~~

Collects default values from a class and its inheritance hierarchy.

.. autofunction:: zencfg.config.gather_defaults

Contributing Guidelines
-----------------------

- Follow existing code style
- Add tests for new features
- Update documentation as needed
- Open an issue before major changes 