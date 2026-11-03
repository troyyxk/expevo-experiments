from src.common import serialize_item


def test_canonical_serialization():
    a = serialize_item("topic", "hello world")
    b = serialize_item("topic", "hello world")
    assert a == b
    assert a == b'{"content":"hello world","topic":"topic"}'


def test_bytes_are_utf8():
    assert serialize_item("t", "é").decode("utf-8") == '{"content":"é","topic":"t"}'
