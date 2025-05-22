from zencfg.from_dict import parse_value_to_type
from typing import List, Union

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
