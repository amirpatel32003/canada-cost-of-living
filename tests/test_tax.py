"""Take-home estimate: checked against figures published elsewhere and against the statutory maximums."""
import pytest

from pipeline.tax import ontario_health_premium, take_home

# Federal plus provincial income tax on $75,000 of employment income for 2026, as published in an
# independent province-by-province comparison (wealthnorth.ca, read November 2026).
PUBLISHED_TAX_ON_75K = {"AB": 12269, "BC": 11920, "SK": 13825, "MB": 14606, "ON": 12705,
                        "NB": 14529, "NS": 16207, "PE": 15315, "NL": 14894}


@pytest.mark.parametrize("province,expected", sorted(PUBLISHED_TAX_ON_75K.items()))
def test_income_tax_matches_published_figure(province, expected):
    assert take_home(75000, province)["income_tax"] == pytest.approx(expected, abs=1)


def test_quebec_is_within_ten_dollars_of_the_published_figure():
    assert take_home(75000, "QC")["income_tax"] == pytest.approx(15322, abs=10)


def test_payroll_maximums_outside_quebec():
    # CPP 4,230.45 + CPP2 416.00 + EI 1,123.07
    assert take_home(200000, "ON")["payroll"] == pytest.approx(5769.52, abs=0.01)


def test_payroll_maximums_in_quebec():
    # QPP 4,479.30 + QPP2 416.00 + EI 895.70 + QPIP 442.90
    assert take_home(200000, "QC")["payroll"] == pytest.approx(6233.90, abs=0.01)


def test_no_income_tax_under_the_basic_personal_amount():
    assert take_home(12000, "ON")["income_tax"] == 0


def test_net_rises_with_income_everywhere():
    for prov in list(PUBLISHED_TAX_ON_75K) + ["QC"]:
        nets = [take_home(i, prov)["net"] for i in range(10000, 400001, 5000)]
        assert all(b > a for a, b in zip(nets, nets[1:])), prov


def test_ontario_health_premium_steps():
    assert [ontario_health_premium(x) for x in (20000, 25000, 40000, 60000, 100000, 250000)] == [0, 300, 450, 600, 750, 900]
