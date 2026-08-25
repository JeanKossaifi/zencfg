class Bunch(dict):
    """A dict exposing its keys as attributes.

    Nested dicts are converted to Bunches, both at creation and on assignment,
    so attribute access works at any depth.

    .. warning::

       Unlike ``dict.update``, :meth:`update` merges nested dicts recursively
       instead of replacing them.

    Examples
    --------
    >>> bunch = Bunch({'a': {'b': 3, 'c': 4}, 'd': 5})
    >>> bunch.a.b
    3

    # update merges nested dicts instead of replacing them:
    >>> bunch.update({'a': {'b': 5}})
    {'a': {'b': 5, 'c': 4}, 'd': 5}
    """
    __slots__ = ()

    def __init__(self, init=None):
        super().__init__()
        for key, value in (init or {}).items():
            self[key] = value

    def __setitem__(self, key, value):
        if isinstance(value, dict):
            value = Bunch(value)  # convert (and copy) nested dicts, at any depth
        super().__setitem__(key, value)

    def __setattr__(self, key, value):
        self[key] = value

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None

    def update(self, mapping):
        """Update with key-value pairs from mapping, merging nested dicts recursively.

        Returns self for method chaining.
        """
        for key, value in mapping.items():
            if isinstance(value, dict) and isinstance(self.get(key), dict):
                self[key].update(value)
            else:
                self[key] = value
        return self
