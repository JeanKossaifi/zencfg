from ..bunch import Bunch

def test_bunch():
    """Test for Bunch
    
    We make sure that nested dicts are updated as desired
    """
    test = dict(a=dict(b=3, c=4), d=5)
    bunch = Bunch(test)
    assert bunch.a.b == 3
    assert bunch.a.c == 4
    assert bunch.d == 5

    # Make sure nested update works as expected:
    # By default we would loose the c in the dict
    bunch.update(dict(a=dict(b=5)))
    assert bunch.a.b == 5
    assert bunch.a.c == 4 #You still here?
