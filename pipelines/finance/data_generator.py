#!/usr/bin/env python3
"""Generate synthetic finance data for all finance use cases (including GST).

Produces realistic CSV/JSON/XLSX files for GST reconciliation, TDS reconciliation,
statutory audit, internal audit, bookkeeping, ROC compliance, tax advisory,
litigation support, forensic analytics, and training use cases.

Usage:
    python3 -m pipelines.finance.data_generator --output-dir experiments/finance_run/data
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import string
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCOUNT_HEADS = [
    ("1000", "Cash & Bank"), ("1100", "Accounts Receivable"), ("1200", "Inventory"),
    ("1300", "Prepaid Expenses"), ("1400", "Fixed Assets"), ("2000", "Accounts Payable"),
    ("2100", "Short-term Borrowings"), ("2200", "Provisions"), ("2300", "Tax Payable"),
    ("3000", "Share Capital"), ("3100", "Reserves & Surplus"), ("4000", "Sales Revenue"),
    ("4100", "Other Income"), ("5000", "Cost of Goods Sold"), ("5100", "Employee Benefits"),
    ("5200", "Rent & Utilities"), ("5300", "Depreciation"), ("5400", "Interest Expense"),
    ("5500", "Professional Fees"), ("5600", "Travelling Expenses"),
]

TDS_SECTIONS = [
    ("194A", "Interest other than securities", 10.0),
    ("194C", "Payment to contractors", 1.0),
    ("194H", "Commission/Brokerage", 5.0),
    ("194I", "Rent", 10.0),
    ("194J", "Professional/Technical fees", 10.0),
    ("192", "Salary", 0.0),  # Slab-based
    ("194B", "Lottery winnings", 30.0),
    ("194D", "Insurance commission", 5.0),
]

COMPANY_NAMES = [
    "Reliance Industries Ltd", "Tata Consultancy Services", "Infosys Ltd",
    "Wipro Ltd", "HCL Technologies", "Bajaj Auto Ltd", "Larsen & Toubro",
    "Mahindra & Mahindra", "Sun Pharma Industries", "Titan Company Ltd",
    "Asian Paints Ltd", "Kotak Mahindra Bank", "HDFC Bank", "ICICI Bank",
    "Adani Enterprises", "Bharti Airtel", "Maruti Suzuki", "Ultratech Cement",
    "Hindustan Unilever", "ITC Limited",
]

VENDOR_NAMES = [
    "Sharma & Associates", "Patel Legal Services", "Kumar IT Solutions",
    "Singh Transport Co.", "Reddy Consulting", "Mehta Stationery Supplies",
    "Jain Maintenance Services", "Agarwal Catering", "Verma Security",
    "Nair Advertising Agency", "Iyer Tax Consultants", "Das Courier Services",
    "Mukherjee Architects", "Rao Cloud Services", "Chopra HR Solutions",
]

EMPLOYEE_NAMES = [
    "Amit Sharma", "Priya Patel", "Rahul Gupta", "Sneha Singh", "Vikram Kumar",
    "Anjali Reddy", "Suresh Mehta", "Kavita Jain", "Raj Verma", "Deepa Nair",
    "Karthik Iyer", "Pooja Das", "Arjun Mukherjee", "Neha Rao", "Manish Chopra",
    "Sanjay Tiwari", "Ritu Saxena", "Gaurav Mishra", "Swati Bose", "Anil Choudhary",
]


def _random_pan() -> str:
    return "".join(random.choices(string.ascii_uppercase, k=5)) + \
           "".join(random.choices(string.digits, k=4)) + random.choice(string.ascii_uppercase)


def _random_tan() -> str:
    return "".join(random.choices(string.ascii_uppercase, k=4)) + \
           "".join(random.choices(string.digits, k=5)) + random.choice(string.ascii_uppercase)


def _random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 1)))


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_trial_balance(period_count: int) -> list[dict]:
    rows = []
    for code, name in ACCOUNT_HEADS:
        for p in range(1, period_count + 1):
            fy = f"FY2024-25" if p == 1 else f"FY2023-24"
            opening = round(random.uniform(10000, 5000000), 2)
            debit = round(random.uniform(0, opening * 0.3), 2)
            credit = round(random.uniform(0, opening * 0.3), 2)
            closing = round(opening + debit - credit, 2)
            rows.append({
                "account_code": code, "account_name": name, "fiscal_year": fy,
                "opening_balance": opening, "debit_total": debit,
                "credit_total": credit, "closing_balance": closing,
            })
    return rows


def generate_tds_26as(count: int) -> list[dict]:
    rows = []
    for i in range(count):
        section, desc, rate = random.choice(TDS_SECTIONS)
        amount = round(random.uniform(5000, 500000), 2)
        tds = round(amount * rate / 100, 2) if rate > 0 else round(amount * random.uniform(0.05, 0.3), 2)
        rows.append({
            "entry_id": f"26AS-{i+1:05d}",
            "deductor_tan": _random_tan(),
            "deductor_name": random.choice(COMPANY_NAMES),
            "section": section, "section_desc": desc,
            "transaction_date": _random_date(date(2024, 4, 1), date(2025, 3, 31)).isoformat(),
            "amount_paid": amount, "tds_deducted": tds, "tds_deposited": tds,
            "quarter": random.choice(["Q1", "Q2", "Q3", "Q4"]),
            "status": random.choice(["Matched", "Matched"] * 4 + ["Unmatched"]),
        })
    return rows


def generate_tds_register(count: int) -> list[dict]:
    rows = []
    for i in range(count):
        section, desc, rate = random.choice(TDS_SECTIONS)
        amount = round(random.uniform(5000, 500000), 2)
        tds = round(amount * rate / 100, 2) if rate > 0 else round(amount * random.uniform(0.05, 0.3), 2)
        rows.append({
            "entry_id": f"TDS-{i+1:05d}",
            "deductee_pan": _random_pan(),
            "deductee_name": random.choice(VENDOR_NAMES + EMPLOYEE_NAMES),
            "section": section, "invoice_no": f"INV-{random.randint(10000,99999)}",
            "payment_date": _random_date(date(2024, 4, 1), date(2025, 3, 31)).isoformat(),
            "amount_paid": amount, "tds_deducted": tds,
            "challan_no": f"CHL-{random.randint(100000,999999)}",
            "challan_date": _random_date(date(2024, 4, 7), date(2025, 4, 7)).isoformat(),
            "quarter": random.choice(["Q1", "Q2", "Q3", "Q4"]),
        })
    return rows


def generate_challan_register(count: int) -> list[dict]:
    rows = []
    for i in range(count):
        rows.append({
            "challan_no": f"CHL-{random.randint(100000,999999)}",
            "bsr_code": f"{random.randint(1000000,9999999)}",
            "deposit_date": _random_date(date(2024, 4, 7), date(2025, 4, 7)).isoformat(),
            "section": random.choice(TDS_SECTIONS)[0],
            "amount": round(random.uniform(1000, 200000), 2),
            "interest": round(random.uniform(0, 5000), 2),
            "penalty": 0.0 if random.random() > 0.1 else round(random.uniform(100, 10000), 2),
            "bank_name": random.choice(["SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "PNB"]),
        })
    return rows


def generate_journal_entries(count: int) -> list[dict]:
    rows = []
    for i in range(count):
        acc_code, acc_name = random.choice(ACCOUNT_HEADS)
        amount = round(random.uniform(100, 1000000), 2)
        is_round = random.random() < 0.1  # 10% round amounts
        if is_round:
            amount = round(amount / 1000) * 1000
        hour = random.randint(0, 23)
        is_odd_hour = hour < 6 or hour > 22
        user = f"user{random.randint(100,999)}"
        dt = _random_date(date(2024, 4, 1), date(2025, 3, 31))
        is_period_end = dt.day >= 28
        rows.append({
            "je_id": f"JE-{i+1:06d}",
            "date": dt.isoformat(), "time": f"{hour:02d}:{random.randint(0,59):02d}:00",
            "account_code": acc_code, "account_name": acc_name,
            "debit": amount if random.random() > 0.5 else 0.0,
            "credit": 0.0 if random.random() > 0.5 else amount,
            "narration": f"Entry for {acc_name}",
            "user": user, "approved_by": f"user{random.randint(100,999)}",
            "is_round_amount": is_round, "is_odd_hour": is_odd_hour,
            "is_period_end": is_period_end,
        })
    return rows


def generate_invoice_register(count: int) -> list[dict]:
    rows = []
    for i in range(count):
        vendor = random.choice(VENDOR_NAMES)
        amount = round(random.uniform(1000, 500000), 2)
        rows.append({
            "invoice_id": f"AP-INV-{i+1:05d}",
            "vendor_name": vendor, "vendor_pan": _random_pan(),
            "invoice_date": _random_date(date(2024, 4, 1), date(2025, 3, 31)).isoformat(),
            "due_date": _random_date(date(2024, 4, 15), date(2025, 4, 15)).isoformat(),
            "amount": amount,
            "gst_amount": round(amount * 0.18, 2),
            "total": round(amount * 1.18, 2),
            "status": random.choice(["Paid", "Paid", "Paid", "Pending", "Overdue"]),
            "payment_date": _random_date(date(2024, 4, 5), date(2025, 3, 31)).isoformat() if random.random() > 0.2 else "",
        })
    return rows


def generate_payment_log(count: int) -> list[dict]:
    rows = []
    for i in range(count):
        vendor = random.choice(VENDOR_NAMES)
        amount = round(random.uniform(1000, 500000), 2)
        dt = _random_date(date(2024, 4, 1), date(2025, 3, 31))
        hour = random.randint(0, 23)
        rows.append({
            "payment_id": f"PAY-{i+1:06d}",
            "date": dt.isoformat(), "time": f"{hour:02d}:{random.randint(0,59):02d}:00",
            "vendor_name": vendor,
            "amount": amount,
            "payment_mode": random.choice(["NEFT", "RTGS", "Cheque", "UPI", "Cash"]),
            "approved_by": f"user{random.randint(100,999)}",
            "reference_no": f"REF-{random.randint(100000,999999)}",
            "is_weekend": dt.weekday() >= 5,
        })
    return rows


def generate_vendor_master() -> list[dict]:
    vendors = []
    for v in VENDOR_NAMES:
        pan = _random_pan()
        vendors.append({
            "vendor_id": f"V-{len(vendors)+1:03d}",
            "vendor_name": v, "pan": pan,
            "bank_account": f"{random.randint(10000000000,99999999999)}",
            "ifsc": f"HDFC{random.randint(1000000,9999999)}",
            "address": f"{random.randint(1,999)} MG Road, {random.choice(['Mumbai','Delhi','Bangalore','Chennai'])}",
            "status": random.choice(["Active"] * 9 + ["Blacklisted"]),
        })
    return vendors


def generate_employee_master() -> list[dict]:
    employees = []
    for e in EMPLOYEE_NAMES:
        employees.append({
            "emp_id": f"EMP-{len(employees)+1:03d}",
            "name": e, "pan": _random_pan(),
            "department": random.choice(["Finance", "Engineering", "HR", "Sales", "Operations"]),
            "bank_account": f"{random.randint(10000000000,99999999999)}",
            "ifsc": f"ICIC{random.randint(1000000,9999999)}",
            "designation": random.choice(["Manager", "Analyst", "Senior Associate", "Director", "VP"]),
        })
    return employees


def generate_bank_statement(count: int) -> list[dict]:
    rows = []
    balance = round(random.uniform(100000, 5000000), 2)
    for i in range(count):
        dt = date(2024, 4, 1) + timedelta(days=i // 3)
        amount = round(random.uniform(500, 200000), 2)
        is_credit = random.random() > 0.5
        if is_credit: balance += amount
        else: balance -= amount
        rows.append({
            "txn_id": f"TXN-{i+1:06d}",
            "date": dt.isoformat(),
            "description": random.choice([
                "NEFT from client", "RTGS to vendor", "Salary credit", "Rent payment",
                "Cheque deposit", "Interest credit", "Service charge", "Tax payment",
            ]),
            "debit": 0.0 if is_credit else amount,
            "credit": amount if is_credit else 0.0,
            "balance": round(balance, 2),
            "reference": f"REF-{random.randint(100000,999999)}",
            "cleared": random.choice(["Yes", "Yes", "Yes", "No"]),
        })
    return rows


def generate_compliance_calendar() -> list[dict]:
    filings = [
        ("DIR-3 KYC", "Annual", "2024-09-30"), ("MGT-14", "Event-based", ""),
        ("AOC-4", "Annual", "2024-10-30"), ("MGT-7", "Annual", "2024-11-29"),
        ("ADT-1", "Annual", "2024-10-14"), ("DPT-3", "Annual", "2024-06-30"),
        ("MSME-1", "Half-yearly", "2024-10-31"), ("BEN-2", "Event-based", ""),
        ("GST-3B", "Monthly", ""), ("TDS Return 26Q", "Quarterly", ""),
    ]
    rows = []
    for form, freq, deadline in filings:
        rows.append({
            "form_name": form, "frequency": freq,
            "due_date": deadline if deadline else _random_date(date(2024, 4, 1), date(2025, 3, 31)).isoformat(),
            "status": random.choice(["Filed", "Filed", "Pending", "Overdue"]),
            "filed_date": _random_date(date(2024, 4, 1), date(2025, 3, 31)).isoformat() if random.random() > 0.3 else "",
            "entity": "Demo Pvt Ltd",
        })
    return rows


def generate_ground_truth(journal_entries: list[dict], tds_26as: list[dict], tds_register: list[dict]) -> list[dict]:
    findings = []
    for je in journal_entries:
        if je.get("is_round_amount") and je.get("is_odd_hour"):
            findings.append({"finding_id": f"GT-{len(findings)+1:04d}", "type": "suspicious_je",
                             "reference_id": je["je_id"], "expected_action": "investigate"})
        if je.get("is_period_end") and je.get("is_round_amount"):
            findings.append({"finding_id": f"GT-{len(findings)+1:04d}", "type": "period_end_round_entry",
                             "reference_id": je["je_id"], "expected_action": "review"})
        if len(findings) > 50:
            break
    # TDS mismatches
    mismatch_count = min(len(tds_26as), len(tds_register)) // 10
    for i in range(mismatch_count):
        findings.append({"finding_id": f"GT-{len(findings)+1:04d}", "type": "tds_mismatch",
                         "reference_id": tds_26as[i]["entry_id"], "expected_action": "reconcile"})
    return findings[:80]


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana",
    "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
    "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh",
    "23": "Madhya Pradesh", "24": "Gujarat", "27": "Maharashtra",
    "29": "Karnataka", "32": "Kerala", "33": "Tamil Nadu",
    "36": "Telangana", "37": "Andhra Pradesh",
}

HSN_CODES = [
    ("8471", "Computers & peripherals"),
    ("8517", "Telecom equipment"),
    ("3004", "Medicaments"),
    ("7308", "Iron/steel structures"),
    ("8544", "Insulated wire/cable"),
    ("9403", "Furniture"),
    ("4819", "Packaging / cartons"),
    ("3926", "Plastic articles"),
    ("8481", "Valves & taps"),
    ("7318", "Screws, bolts, nuts"),
    ("6802", "Worked stone"),
    ("3923", "Plastic containers"),
    ("8504", "Transformers"),
    ("2710", "Petroleum oils"),
    ("7210", "Flat-rolled steel"),
]

TAX_RATES = [5.0, 12.0, 18.0, 28.0]
DEFAULT_TAX_RATE = 18.0

BUSINESS_NAMES = [
    "Sharma Enterprises", "Patel Trading Co.", "Gupta Industries",
    "Singh Manufacturing", "Kumar Electronics", "Reddy Suppliers",
    "Mehta Hardware", "Jain Chemicals", "Agarwal Plastics",
    "Verma Steel Works", "Nair Components", "Iyer IT Solutions",
    "Das Packaging", "Mukherjee Textiles", "Rao Pharmaceuticals",
    "Chopra Logistics", "Malhotra Furniture", "Bhatt Electricals",
    "Sinha Auto Parts", "Pillai Marine Supplies", "Thakur Cement",
    "Saxena Paper Mills", "Mishra Agro Products", "Bose Electronics",
    "Choudhary Oil Co.", "Tiwari Construction", "Pandey Polymers",
    "Rajput Metal Works", "Kapoor Textiles", "Bansal Food Products",
    "Dutta Machinery", "Ghosh Chemicals", "Sethi Imports",
    "Kaur Exports", "Rathore Mining", "Kulkarni Engineering",
    "Deshmukh Pharma", "Hegde Software", "Nambiar Agritech",
    "Menon Trading House",
]

MISMATCH_TYPES = [
    "amount",       # taxable value differs
    "missing_erp",  # in GSTR but not in ERP
    "missing_gstr", # in ERP but not in GSTR
    "hsn",          # HSN code mismatch
    "tax_rate",     # tax rate differs
    "date",         # invoice date differs
    "gstin_typo",   # GSTIN has a typo in one source
]


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class Supplier:
    gstin: str
    legal_name: str
    trade_name: str
    state_code: str
    status: str = "Active"


@dataclass
class Invoice:
    invoice_no: str
    supplier_gstin: str
    supplier_name: str
    invoice_date: str
    taxable_value: float
    hsn_code: str
    hsn_desc: str
    tax_rate: float
    cgst: float
    sgst: float
    igst: float
    period: str
    is_inter_state: bool = False


@dataclass
class MismatchRecord:
    invoice_no: str
    mismatch_type: str
    erp_value: str
    gstr_value: str
    supplier_gstin: str


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def _random_gstin(state_code: str) -> str:
    """Generate a plausible GSTIN."""
    pan_chars = "".join(random.choices(string.ascii_uppercase, k=5))
    pan_digits = "".join(random.choices(string.digits, k=4))
    pan = f"{pan_chars}{pan_digits}"
    entity = random.choice(string.ascii_uppercase)
    suffix = random.choice(string.ascii_uppercase + string.digits)
    check = random.choice(string.ascii_uppercase + string.digits)
    return f"{state_code}{pan}{entity}{suffix}{check}"


def generate_suppliers(count: int) -> list[Supplier]:
    """Generate `count` unique suppliers with random GSTINs."""
    used_names = set()
    suppliers: list[Supplier] = []
    state_codes = list(STATES.keys())
    names = list(BUSINESS_NAMES)
    random.shuffle(names)

    for i in range(count):
        state = random.choice(state_codes)
        if i < len(names):
            name = names[i]
        else:
            name = f"Enterprise_{i + 1:03d}"
        if name in used_names:
            name = f"{name} ({state})"
        used_names.add(name)
        gstin = _random_gstin(state)
        trade = name.split()[0] + " " + random.choice(["Pvt Ltd", "LLP", "& Sons", "Corp"])
        suppliers.append(Supplier(
            gstin=gstin,
            legal_name=name,
            trade_name=trade,
            state_code=state,
            status=random.choice(["Active"] * 9 + ["Suspended"]),
        ))
    return suppliers


def _filing_periods(count: int, start_year: int = 2024, start_month: int = 4) -> list[str]:
    """Generate `count` consecutive monthly filing periods like '042024'."""
    periods = []
    m, y = start_month, start_year
    for _ in range(count):
        periods.append(f"{m:02d}{y}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return periods


def generate_invoices(
    suppliers: list[Supplier],
    total_invoices: int,
    periods: list[str],
    own_state: str = "27",
) -> list[Invoice]:
    """Generate purchase invoices spread across suppliers and periods."""
    invoices: list[Invoice] = []
    inv_counter = 1

    for _ in range(total_invoices):
        supplier = random.choice(suppliers)
        period = random.choice(periods)
        month = int(period[:2])
        year = int(period[2:])
        day = random.randint(1, 28)
        inv_date = date(year, month, day)

        hsn_code, hsn_desc = random.choice(HSN_CODES)
        tax_rate = random.choice(TAX_RATES)
        taxable = round(random.uniform(5000, 500000), 2)

        is_inter = supplier.state_code != own_state
        if is_inter:
            igst = round(taxable * tax_rate / 100, 2)
            cgst = sgst = 0.0
        else:
            half = tax_rate / 2
            cgst = round(taxable * half / 100, 2)
            sgst = round(taxable * half / 100, 2)
            igst = 0.0

        inv_no = f"INV-{year}{month:02d}-{inv_counter:05d}"
        inv_counter += 1

        invoices.append(Invoice(
            invoice_no=inv_no,
            supplier_gstin=supplier.gstin,
            supplier_name=supplier.legal_name,
            invoice_date=inv_date.isoformat(),
            taxable_value=taxable,
            hsn_code=hsn_code,
            hsn_desc=hsn_desc,
            tax_rate=tax_rate,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            period=period,
            is_inter_state=is_inter,
        ))

    return invoices


def inject_mismatches(
    invoices: list[Invoice],
    mismatch_rate: float = 0.15,
) -> tuple[list[Invoice], list[Invoice], list[MismatchRecord]]:
    """Create ERP and GSTR versions with mismatches."""
    erp: list[Invoice] = []
    gstr: list[Invoice] = []
    mismatches: list[MismatchRecord] = []

    n_mismatch = int(len(invoices) * mismatch_rate)
    mismatch_indices = set(random.sample(range(len(invoices)), min(n_mismatch, len(invoices))))

    for idx, inv in enumerate(invoices):
        if idx not in mismatch_indices:
            erp.append(inv)
            gstr.append(inv)
            continue

        mtype = random.choice(MISMATCH_TYPES)

        if mtype == "amount":
            factor = random.uniform(0.85, 1.15)
            gstr_taxable = round(inv.taxable_value * factor, 2)
            erp.append(inv)
            gstr_inv = Invoice(**{**inv.__dict__})
            gstr_inv.taxable_value = gstr_taxable
            if gstr_inv.is_inter_state:
                gstr_inv.igst = round(gstr_taxable * inv.tax_rate / 100, 2)
            else:
                half = inv.tax_rate / 2
                gstr_inv.cgst = round(gstr_taxable * half / 100, 2)
                gstr_inv.sgst = round(gstr_taxable * half / 100, 2)
            gstr.append(gstr_inv)
            mismatches.append(MismatchRecord(
                inv.invoice_no, "amount_mismatch",
                str(inv.taxable_value), str(gstr_taxable), inv.supplier_gstin,
            ))

        elif mtype == "missing_erp":
            gstr.append(inv)
            mismatches.append(MismatchRecord(
                inv.invoice_no, "missing_in_erp",
                "(absent)", str(inv.taxable_value), inv.supplier_gstin,
            ))

        elif mtype == "missing_gstr":
            erp.append(inv)
            mismatches.append(MismatchRecord(
                inv.invoice_no, "missing_in_gstr",
                str(inv.taxable_value), "(absent)", inv.supplier_gstin,
            ))

        elif mtype == "hsn":
            erp.append(inv)
            alt_hsn, alt_desc = random.choice(
                [(h, d) for h, d in HSN_CODES if h != inv.hsn_code]
            )
            gstr_inv = Invoice(**{**inv.__dict__})
            gstr_inv.hsn_code = alt_hsn
            gstr_inv.hsn_desc = alt_desc
            gstr.append(gstr_inv)
            mismatches.append(MismatchRecord(
                inv.invoice_no, "hsn_mismatch",
                inv.hsn_code, alt_hsn, inv.supplier_gstin,
            ))

        elif mtype == "tax_rate":
            erp.append(inv)
            alt_rate = random.choice([r for r in TAX_RATES if r != inv.tax_rate])
            gstr_inv = Invoice(**{**inv.__dict__})
            gstr_inv.tax_rate = alt_rate
            if gstr_inv.is_inter_state:
                gstr_inv.igst = round(inv.taxable_value * alt_rate / 100, 2)
            else:
                half = alt_rate / 2
                gstr_inv.cgst = round(inv.taxable_value * half / 100, 2)
                gstr_inv.sgst = round(inv.taxable_value * half / 100, 2)
            gstr.append(gstr_inv)
            mismatches.append(MismatchRecord(
                inv.invoice_no, "tax_rate_mismatch",
                str(inv.tax_rate), str(alt_rate), inv.supplier_gstin,
            ))

        elif mtype == "date":
            erp.append(inv)
            orig = date.fromisoformat(inv.invoice_date)
            shift = random.choice([-5, -3, -1, 1, 3, 5, 10])
            new_date = orig + timedelta(days=shift)
            gstr_inv = Invoice(**{**inv.__dict__})
            gstr_inv.invoice_date = new_date.isoformat()
            gstr.append(gstr_inv)
            mismatches.append(MismatchRecord(
                inv.invoice_no, "date_mismatch",
                inv.invoice_date, new_date.isoformat(), inv.supplier_gstin,
            ))

        elif mtype == "gstin_typo":
            erp.append(inv)
            gstin = list(inv.supplier_gstin)
            pos = random.randint(5, len(gstin) - 1)
            gstin[pos] = random.choice(string.ascii_uppercase + string.digits)
            bad_gstin = "".join(gstin)
            gstr_inv = Invoice(**{**inv.__dict__})
            gstr_inv.supplier_gstin = bad_gstin
            gstr.append(gstr_inv)
            mismatches.append(MismatchRecord(
                inv.invoice_no, "gstin_mismatch",
                inv.supplier_gstin, bad_gstin, inv.supplier_gstin,
            ))

    return erp, gstr, mismatches


# ---------------------------------------------------------------------------
# CSV Writers
# ---------------------------------------------------------------------------

_PURCHASE_COLS = [
    "invoice_no", "supplier_gstin", "supplier_name", "invoice_date",
    "taxable_value", "cgst", "sgst", "igst", "hsn_code", "tax_rate", "period",
]

_GSTR2B_COLS = [
    "supplier_gstin", "invoice_no", "invoice_date", "taxable_value",
    "igst", "cgst", "sgst", "hsn_code", "filing_period",
]

_SALES_COLS = [
    "invoice_no", "buyer_gstin", "buyer_name", "invoice_date",
    "taxable_value", "cgst", "sgst", "igst", "hsn_code", "tax_rate", "period",
]

_GSTR1_COLS = [
    "buyer_gstin", "invoice_no", "invoice_date", "taxable_value",
    "igst", "cgst", "sgst", "hsn_code", "filing_period",
]

_SUPPLIER_COLS = ["gstin", "legal_name", "trade_name", "state_code", "status"]


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _invoice_to_purchase_row(inv: Invoice) -> dict[str, Any]:
    return {
        "invoice_no": inv.invoice_no,
        "supplier_gstin": inv.supplier_gstin,
        "supplier_name": inv.supplier_name,
        "invoice_date": inv.invoice_date,
        "taxable_value": inv.taxable_value,
        "cgst": inv.cgst,
        "sgst": inv.sgst,
        "igst": inv.igst,
        "hsn_code": inv.hsn_code,
        "tax_rate": inv.tax_rate,
        "period": inv.period,
    }


def _invoice_to_gstr2b_row(inv: Invoice) -> dict[str, Any]:
    return {
        "supplier_gstin": inv.supplier_gstin,
        "invoice_no": inv.invoice_no,
        "invoice_date": inv.invoice_date,
        "taxable_value": inv.taxable_value,
        "igst": inv.igst,
        "cgst": inv.cgst,
        "sgst": inv.sgst,
        "hsn_code": inv.hsn_code,
        "filing_period": inv.period,
    }


def _invoice_to_sales_row(inv: Invoice) -> dict[str, Any]:
    return {
        "invoice_no": inv.invoice_no,
        "buyer_gstin": inv.supplier_gstin,
        "buyer_name": inv.supplier_name,
        "invoice_date": inv.invoice_date,
        "taxable_value": inv.taxable_value,
        "cgst": inv.cgst,
        "sgst": inv.sgst,
        "igst": inv.igst,
        "hsn_code": inv.hsn_code,
        "tax_rate": inv.tax_rate,
        "period": inv.period,
    }


def _invoice_to_gstr1_row(inv: Invoice) -> dict[str, Any]:
    return {
        "buyer_gstin": inv.supplier_gstin,
        "invoice_no": inv.invoice_no,
        "invoice_date": inv.invoice_date,
        "taxable_value": inv.taxable_value,
        "igst": inv.igst,
        "cgst": inv.cgst,
        "sgst": inv.sgst,
        "hsn_code": inv.hsn_code,
        "filing_period": inv.period,
    }


# ---------------------------------------------------------------------------
# Main generation orchestrator
# ---------------------------------------------------------------------------

@dataclass
class GstGenerationResult:
    output_dir: Path
    supplier_count: int
    purchase_count: int
    sales_count: int
    gstr2b_count: int
    gstr1_count: int
    mismatch_count: int
    files: list[str] = field(default_factory=list)


def _gst_generate_all(
    output_dir: Path,
    *,
    supplier_count: int = 30,
    invoice_count: int = 200,
    period_count: int = 3,
    mismatch_rate: float = 0.15,
    seed: int | None = None,
) -> GstGenerationResult:
    """Generate all GST dummy data files under output_dir."""
    if seed is not None:
        random.seed(seed)

    output_dir.mkdir(parents=True, exist_ok=True)

    suppliers = generate_suppliers(supplier_count)
    _write_csv(
        output_dir / "supplier_master.csv",
        _SUPPLIER_COLS,
        [asdict(s) for s in suppliers],
    )

    periods = _filing_periods(period_count)
    base_purchases = generate_invoices(suppliers, invoice_count, periods)
    erp_purchases, gstr2b_invoices, purchase_mismatches = inject_mismatches(
        base_purchases, mismatch_rate,
    )

    purchase_count = _write_csv(
        output_dir / "erp_purchase_register.csv",
        _PURCHASE_COLS,
        [_invoice_to_purchase_row(i) for i in erp_purchases],
    )
    gstr2b_count = _write_csv(
        output_dir / "gstr2b_returns.csv",
        _GSTR2B_COLS,
        [_invoice_to_gstr2b_row(i) for i in gstr2b_invoices],
    )

    sales_count_target = int(invoice_count * 0.6)
    base_sales = generate_invoices(suppliers, sales_count_target, periods)
    erp_sales, gstr1_invoices, sales_mismatches = inject_mismatches(
        base_sales, mismatch_rate,
    )

    sales_count = _write_csv(
        output_dir / "erp_sales_register.csv",
        _SALES_COLS,
        [_invoice_to_sales_row(i) for i in erp_sales],
    )
    gstr1_count = _write_csv(
        output_dir / "gstr1_returns.csv",
        _GSTR1_COLS,
        [_invoice_to_gstr1_row(i) for i in gstr1_invoices],
    )

    all_mismatches = purchase_mismatches + sales_mismatches
    _write_csv(
        output_dir / "ground_truth_mismatches.csv",
        ["invoice_no", "mismatch_type", "erp_value", "gstr_value", "supplier_gstin"],
        [asdict(m) for m in all_mismatches],
    )

    meta = {
        "supplier_count": supplier_count,
        "invoice_count": invoice_count,
        "period_count": period_count,
        "periods": periods,
        "mismatch_rate": mismatch_rate,
        "purchase_invoices": purchase_count,
        "sales_invoices": sales_count,
        "gstr2b_records": gstr2b_count,
        "gstr1_records": gstr1_count,
        "total_mismatches": len(all_mismatches),
        "mismatch_breakdown": {},
    }
    for m in all_mismatches:
        meta["mismatch_breakdown"][m.mismatch_type] = (
            meta["mismatch_breakdown"].get(m.mismatch_type, 0) + 1
        )
    (output_dir / "data_manifest.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8",
    )

    files = [
        "supplier_master.csv",
        "erp_purchase_register.csv",
        "gstr2b_returns.csv",
        "erp_sales_register.csv",
        "gstr1_returns.csv",
        "ground_truth_mismatches.csv",
        "data_manifest.json",
    ]

    return GstGenerationResult(
        output_dir=output_dir,
        supplier_count=supplier_count,
        purchase_count=purchase_count,
        sales_count=sales_count,
        gstr2b_count=gstr2b_count,
        gstr1_count=gstr1_count,
        mismatch_count=len(all_mismatches),
        files=files,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------

@dataclass
class GenerationResult:
    output_dir: Path
    trial_balance_count: int
    tds_26as_count: int
    tds_register_count: int
    journal_entry_count: int
    invoice_count: int
    bank_txn_count: int
    ground_truth_count: int
    files: list[str] = field(default_factory=list)


def generate_all(
    output_dir: Path,
    *,
    tds_count: int = 150,
    journal_count: int = 300,
    invoice_count: int = 200,
    payment_count: int = 180,
    bank_txn_count: int = 250,
    challan_count: int = 60,
    period_count: int = 2,
    seed: int | None = None,
) -> GenerationResult:
    if seed is not None:
        random.seed(seed)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Trial balance
    tb = generate_trial_balance(period_count)
    _write_csv(output_dir / "trial_balance.csv",
               ["account_code", "account_name", "fiscal_year", "opening_balance",
                "debit_total", "credit_total", "closing_balance"], tb)

    # TDS
    tds26 = generate_tds_26as(tds_count)
    _write_csv(output_dir / "tds_certificates_26as.csv",
               ["entry_id", "deductor_tan", "deductor_name", "section", "section_desc",
                "transaction_date", "amount_paid", "tds_deducted", "tds_deposited",
                "quarter", "status"], tds26)

    tds_reg = generate_tds_register(tds_count)
    _write_csv(output_dir / "tds_deducted_register.csv",
               ["entry_id", "deductee_pan", "deductee_name", "section", "invoice_no",
                "payment_date", "amount_paid", "tds_deducted", "challan_no",
                "challan_date", "quarter"], tds_reg)

    challans = generate_challan_register(challan_count)
    _write_csv(output_dir / "challan_register.csv",
               ["challan_no", "bsr_code", "deposit_date", "section", "amount",
                "interest", "penalty", "bank_name"], challans)

    # Journal entries
    jes = generate_journal_entries(journal_count)
    _write_csv(output_dir / "journal_entries.csv",
               ["je_id", "date", "time", "account_code", "account_name", "debit", "credit",
                "narration", "user", "approved_by", "is_round_amount", "is_odd_hour",
                "is_period_end"], jes)

    # Invoice & payment
    invoices = generate_invoice_register(invoice_count)
    _write_csv(output_dir / "invoice_register.csv",
               ["invoice_id", "vendor_name", "vendor_pan", "invoice_date", "due_date",
                "amount", "gst_amount", "total", "status", "payment_date"], invoices)

    payments = generate_payment_log(payment_count)
    _write_csv(output_dir / "payment_log.csv",
               ["payment_id", "date", "time", "vendor_name", "amount", "payment_mode",
                "approved_by", "reference_no", "is_weekend"], payments)

    # Master data
    vendors = generate_vendor_master()
    _write_csv(output_dir / "vendor_master.csv",
               ["vendor_id", "vendor_name", "pan", "bank_account", "ifsc", "address", "status"],
               vendors)

    employees = generate_employee_master()
    _write_csv(output_dir / "employee_master.csv",
               ["emp_id", "name", "pan", "department", "bank_account", "ifsc", "designation"],
               employees)

    # Bank statement
    bank = generate_bank_statement(bank_txn_count)
    _write_csv(output_dir / "bank_statement.csv",
               ["txn_id", "date", "description", "debit", "credit", "balance", "reference",
                "cleared"], bank)

    # Compliance calendar
    compliance = generate_compliance_calendar()
    _write_csv(output_dir / "compliance_calendar.csv",
               ["form_name", "frequency", "due_date", "status", "filed_date", "entity"],
               compliance)

    # Ground truth
    gt = generate_ground_truth(jes, tds26, tds_reg)
    _write_csv(output_dir / "ground_truth_anomalies.csv",
               ["finding_id", "type", "reference_id", "expected_action"], gt)

    files = [
        "trial_balance.csv", "tds_certificates_26as.csv", "tds_deducted_register.csv",
        "challan_register.csv", "journal_entries.csv", "invoice_register.csv",
        "payment_log.csv", "vendor_master.csv", "employee_master.csv",
        "bank_statement.csv", "compliance_calendar.csv", "ground_truth_anomalies.csv",
        "data_manifest.json",
    ]
    _write_json(output_dir / "data_manifest.json", {
        "domain": "finance",
        "tds_count": tds_count, "journal_count": journal_count,
        "invoice_count": invoice_count, "bank_txn_count": bank_txn_count,
        "ground_truth_count": len(gt), "files": files,
    })

    return GenerationResult(
        output_dir=output_dir, trial_balance_count=len(tb),
        tds_26as_count=len(tds26), tds_register_count=len(tds_reg),
        journal_entry_count=len(jes), invoice_count=len(invoices),
        bank_txn_count=len(bank), ground_truth_count=len(gt), files=files,
    )



def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic finance data")
    parser.add_argument("--output-dir", default="experiments/finance_run/data")
    parser.add_argument("--tds-count", type=int, default=150)
    parser.add_argument("--journal-count", type=int, default=300)
    parser.add_argument("--invoice-count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    result = generate_all(Path(args.output_dir), tds_count=args.tds_count,
                          journal_count=args.journal_count, invoice_count=args.invoice_count,
                          seed=args.seed)
    print(f"Generated finance data in {result.output_dir}/")
    print(f"  Trial balance rows: {result.trial_balance_count}")
    print(f"  TDS 26AS entries: {result.tds_26as_count}")
    print(f"  Journal entries: {result.journal_entry_count}")
    print(f"  Ground truth: {result.ground_truth_count}")


# ---------------------------------------------------------------------------
# GST data generation — delegates to gst_recon sub-module
# Tasks with "data_generator": "generate_gst_data" in task_bank.py call this.
# ---------------------------------------------------------------------------

def generate_gst_data(
    output_dir: Path,
    *,
    supplier_count: int = 30,
    invoice_count: int = 150,
    period_count: int = 3,
    mismatch_rate: float = 0.15,
    seed: int | None = None,
):
    """Generate GST-specific synthetic data."""
    return _gst_generate_all(
        output_dir,
        supplier_count=supplier_count,
        invoice_count=invoice_count,
        period_count=period_count,
        mismatch_rate=mismatch_rate,
        seed=seed,
    )


if __name__ == "__main__":
    main()
