from worker.anthropic_client import extract_json


def test_extract_json_plain():
    assert extract_json('[{"a": 1}]') == [{"a": 1}]


def test_extract_json_with_prose_and_fence():
    text = 'Sure, here you go:\n```json\n[{"start": 1.0, "end": 2.0}]\n```\nHope that helps!'
    assert extract_json(text) == [{"start": 1.0, "end": 2.0}]


def test_extract_json_object_with_prose():
    text = 'Here is the result: {"caption": "hi", "hashtags": ["#a"]}'
    assert extract_json(text) == {"caption": "hi", "hashtags": ["#a"]}
