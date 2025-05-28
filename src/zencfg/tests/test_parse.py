from zencfg.from_dict import parse_value_to_type
from typing import List, Union, Optional
import pytest

def test_parse_list_from_string():
    # Test with a list of integers
    result = parse_value_to_type("[4, 5]", Union[int, List[int]], strict=True, path="test")
    print(f"Result: {result}, Type: {type(result)}")
    assert isinstance(result, list)
    assert result == [4, 5]

    # Test with a single integer
    result = parse_value_to_type("42", Union[int, List[int]], strict=True, path="test")
    print(f"Result: {result}, Type: {type(result)}")
    assert isinstance(result, int)
    assert result == 42

def test_parse_optional():
    # Test with None value
    result = parse_value_to_type(None, Optional[float], strict=True, path="test")
    assert result is None

    # Test with valid float
    result = parse_value_to_type("1.5", Optional[float], strict=True, path="test")
    assert isinstance(result, float)
    assert result == 1.5

    # Test with invalid value
    with pytest.raises(TypeError):
        parse_value_to_type("not_a_float", Optional[float], strict=True, path="test")
