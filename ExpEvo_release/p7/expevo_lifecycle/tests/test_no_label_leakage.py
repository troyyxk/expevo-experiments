from src.run_interactions import SYSTEM_A, USER_A, parse_answer


def test_prompt_has_no_gold_field():
    text = (SYSTEM_A + USER_A).lower()
    assert "gold" not in text
    assert "correct option" not in text


def test_parse_answer_rejects_garbage():
    assert parse_answer("I am not sure") is None
    assert parse_answer('{"answer":"C","explanation":"x"}')[0] == "C"
