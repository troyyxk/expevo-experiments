import numpy as np

from src.refine import group_ids


def test_grouping_covers_exactly_once():
    ids = ["e3", "e1", "e2", "e4"]
    S = np.array([[10, 5, 1, 0], [5, 10, 1, 0], [1, 1, 10, 9], [0, 0, 9, 10]], float)
    groups = group_ids(ids, S, 5.0)
    flat = sorted(x for g in groups for x in g)
    assert flat == sorted(ids)
    assert all(len(g) >= 1 for g in groups)
    assert groups[0][0] == "e3"  # anchor first, stable order


def test_grouping_singletons_when_threshold_high():
    ids = ["a", "b", "c"]
    S = np.array([[10, 1, 0], [1, 10, 0], [0, 0, 10]], float)
    groups = group_ids(ids, S, 50.0)
    assert [len(g) for g in groups] == [1, 1, 1]
