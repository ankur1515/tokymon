from sensors import simulator


def test_distance_cycle():
    values = [simulator.read_distance_cm() for _ in range(4)]
    assert min(values) >= 30
    assert max(values) <= 50
