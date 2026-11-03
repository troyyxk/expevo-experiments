def upload_reduction(raw, dist):
    return 100 * (1 - dist / raw)


def test_upload_reduction_negative_is_kept():
    assert upload_reduction(100, 150) < 0


def test_storage_reduction():
    assert round(100 * (1 - 775 / 1000), 2) == 22.5
