from touch_sensor import classify_hit


def test_light_hit():
    label, level = classify_hit(50)
    assert level == 1
    assert "轻" in label


def test_medium_hit():
    label, level = classify_hit(150)
    assert level == 2
    assert "中" in label


def test_heavy_hit():
    label, level = classify_hit(250)
    assert level == 3
    assert "重" in label


def test_boundary_medium():
    label, level = classify_hit(100)
    assert level == 2


def test_boundary_heavy():
    label, level = classify_hit(200)
    assert level == 3
