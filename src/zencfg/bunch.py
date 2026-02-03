class Bunch(dict):
    """A dict exposing its keys as attributes.
    
    .. warning::
       
       We override the default update function. 
       The new one updates each nested dict individually.
       This may be a surprising behaviour.
    
    Notes
    -----
    * At init, we explicitly go through each key, value pair to 
      make sure that a nested dict becomes a nested Bunch.
    * We override the update to make sure that a nested Bunch is 
      updated correctly. This may be a surprising behaviour.
    * String values 'None' or 'none' are automatically converted to Python None.
      This is useful when loading configs from files where None might be represented
      as a string.
      
    Examples
    --------
    >>> test = {'a': {'b': 3, 'c': 4}, 'd': 5}
    >>> bunch = Bunch(test)
    
    # Check what happens if we update an element with another dict:
    >>> bunch.update(dict(a=dict(b=5)))
    {'a': {'b': 5, 'c': 4}, 'd': 5}
    
    # Compare this with what happens if we update a regular dict:
    >>> test.update(dict(a=dict(b=5)))
    {'a': {'b': 5}, 'd': 5}
    
    # String 'None' is converted to Python None:
    >>> bunch = Bunch({'value': 'None'})
    >>> bunch.value is None
    True
    """
    __slots__ = () 

    def __init__(self, init=None):
        super().__init__()
        if init is None:
            init = {}
        for key, value in init.items():
            if isinstance(value, dict):
                value = Bunch(value)
            elif value is not None and (value == 'None' or value == 'none'):
                value = None
            self[key] = value

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__

    def update(self, mapping):
        """Update the Bunch with key-value pairs from mapping.
        
        Unlike dict.update(), this recursively updates nested dicts
        rather than replacing them entirely.
        
        Returns self for method chaining.
        """
        for key in mapping:
            value = mapping[key]
            if key in self and isinstance(value, dict):
                self[key].update(value)
            else:
                self[key] = value
        return self