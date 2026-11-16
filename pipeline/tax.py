"""Take-home pay estimate for one employee, by province, for the 2026 tax year.

Covers federal and provincial income tax, CPP or QPP (including the second tier), EI and QPIP, with the
basic personal amounts, the Canada employment amount and the credits for CPP and EI. It also covers the
Ontario surtax and health premium, the Quebec abatement and Quebec's deduction for workers.

It leaves out RRSP and other deductions, refundable benefits, and the low-income tax reductions several
provinces offer, so it overstates tax at low incomes. The parameters live in tax_2026.json and the page
runs the same formula in JavaScript from the same file.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PARAMS_PATH = Path(__file__).with_name("tax_2026.json")


@lru_cache(maxsize=1)
def params() -> dict:
    return json.loads(PARAMS_PATH.read_text(encoding="utf-8"))


def bracket_tax(amount: float, brackets: list) -> float:
    tax, low = 0.0, 0.0
    for high, rate in brackets:
        if high is None or amount <= high:
            return tax + max(0.0, amount - low) * rate
        tax += (high - low) * rate
        low = high
    return tax


def ontario_health_premium(taxable: float) -> float:
    if taxable <= 20000:
        return 0.0
    if taxable <= 36000:
        return min(300.0, 0.06 * (taxable - 20000))
    if taxable <= 48000:
        return min(450.0, 300 + 0.06 * (taxable - 36000))
    if taxable <= 72000:
        return min(600.0, 450 + 0.25 * (taxable - 48000))
    if taxable <= 200000:
        return min(750.0, 600 + 0.25 * (taxable - 72000))
    return min(900.0, 750 + 0.25 * (taxable - 200000))


def take_home(income: float, province: str) -> dict:
    """Annual figures for one person with `income` of employment income in `province`."""
    p = params()
    fed, pay, prov = p["federal"], p["payroll"], p["provinces"][province]
    quebec = province == "QC"

    pensionable = max(0.0, min(income, pay["ympe"]) - pay["cpp_exemption"])
    pension = pensionable * (pay["qpp_rate"] if quebec else pay["cpp_rate"])
    enhanced = pensionable * pay["enhanced_rate"]            # deducted from income
    pension_base = pension - enhanced                         # earns a credit
    pension2 = max(0.0, min(income, pay["yampe"]) - pay["ympe"]) * pay["cpp2_rate"]
    ei = min(income, pay["ei_max_earnings"]) * (pay["ei_rate_quebec"] if quebec else pay["ei_rate"])
    qpip = min(income, pay["qpip_max_earnings"]) * pay["qpip_rate"] if quebec else 0.0

    taxable = max(0.0, income - enhanced - pension2)

    if income <= fed["bpa_phase_start"]:
        bpa = fed["bpa_max"]
    else:
        span = fed["bpa_phase_end"] - fed["bpa_phase_start"]
        bpa = max(fed["bpa_min"], fed["bpa_max"] - (fed["bpa_max"] - fed["bpa_min"]) * (income - fed["bpa_phase_start"]) / span)
    low_fed = fed["brackets"][0][1]
    credits = bpa + min(fed["employment_amount"], income) + pension_base + ei + qpip
    federal = max(0.0, bracket_tax(taxable, fed["brackets"]) - low_fed * credits)
    if quebec:
        federal *= 1 - fed["quebec_abatement"]

    low = prov["brackets"][0][1]
    if quebec:
        worker = min(prov["worker_deduction_max"], prov["worker_deduction_rate"] * income)
        provincial = max(0.0, bracket_tax(max(0.0, taxable - worker), prov["brackets"]) - low * prov["bpa"])
    else:
        prov_bpa = prov["bpa"]
        if "bpa_phase_start" in prov and income > prov["bpa_phase_start"]:
            span = prov["bpa_phase_end"] - prov["bpa_phase_start"]
            prov_bpa = max(0.0, prov_bpa * (1 - (income - prov["bpa_phase_start"]) / span))
        provincial = max(0.0, bracket_tax(taxable, prov["brackets"]) - low * (prov_bpa + pension_base + ei))
    if "surtax" in prov:
        provincial += sum(rate * max(0.0, provincial - threshold) for threshold, rate in prov["surtax"])
    if prov.get("health_premium"):
        provincial += ontario_health_premium(taxable)

    payroll = pension + pension2 + ei + qpip
    return {
        "income": income, "federal_tax": federal, "provincial_tax": provincial,
        "income_tax": federal + provincial, "payroll": payroll, "net": income - federal - provincial - payroll,
    }
