import numpy as np

from y4cdata.fields import celsius, cloud_percent, rain_rate


def test_rain_is_the_mean_rate_over_the_interval_and_never_negative():
    now, prev = np.array([0.006, 0.0010]), np.array([0.003, 0.0011])  # metres; packing noise in the second
    assert np.allclose(rain_rate(now, prev, 3), [1.0, 0.0])


def test_six_hour_steps_divide_by_six():
    assert np.allclose(rain_rate(np.array([0.012]), np.array([0.0]), 6), [2.0])


def test_kelvin_to_celsius():
    assert np.allclose(celsius(np.array([273.15, 233.15])), [0.0, -40.0])


def test_cloud_fraction_to_percent_stays_in_range():
    assert np.allclose(cloud_percent(np.array([0.0, 0.5, 1.0000001, -0.0000001])), [0, 50, 100, 0])
