"""Finance CRUD and summary tests."""

from tests.conftest import API


def test_category_and_transaction_flow(auth_client):
    # Category
    cat = auth_client.post(f"{API}/finance/categories", json={"name": "Salary", "type": "income"})
    assert cat.status_code == 200, cat.text
    assert cat.json()["data"]["type"] == "INCOME"
    category_id = cat.json()["data"]["id"]

    # Transaction with category snapshot
    txn = auth_client.post(
        f"{API}/finance/transactions",
        json={
            "type": "income",
            "amount": 5000000,
            "category_id": category_id,
            "transaction_date": "2026-06-01",
        },
    )
    assert txn.status_code == 200, txn.text
    assert txn.json()["data"]["category_name_snapshot"] == "Salary"
    assert txn.json()["data"]["currency"] == "IDR"


def test_transaction_amount_must_be_positive(auth_client):
    resp = auth_client.post(
        f"{API}/finance/transactions",
        json={"type": "expense", "amount": 0, "transaction_date": "2026-06-01"},
    )
    assert resp.status_code == 422


def test_monthly_summary(auth_client):
    auth_client.post(
        f"{API}/finance/transactions",
        json={"type": "income", "amount": 1000, "transaction_date": "2026-06-10"},
    )
    auth_client.post(
        f"{API}/finance/transactions",
        json={"type": "expense", "amount": 250, "transaction_date": "2026-06-15"},
    )
    # A transaction outside the month should be excluded.
    auth_client.post(
        f"{API}/finance/transactions",
        json={"type": "income", "amount": 999, "transaction_date": "2026-05-01"},
    )

    summary = auth_client.get(f"{API}/finance/summary", params={"year": 2026, "month": 6})
    assert summary.status_code == 200, summary.text
    data = summary.json()["data"]
    assert data["total_income"] == 1000
    assert data["total_expense"] == 250
    assert data["balance"] == 750
    assert data["transaction_count"] == 2
    assert data["currency"] == "IDR"


def test_finance_report_range_excludes_archived_periods(auth_client):
    auth_client.post(
        f"{API}/finance/transactions",
        json={"type": "income", "amount": 30000, "transaction_date": "2026-06-12"},
    )
    auth_client.post(
        f"{API}/finance/transactions",
        json={"type": "expense", "amount": 10000, "transaction_date": "2026-06-13"},
    )
    auth_client.post(
        f"{API}/finance/transactions",
        json={"type": "income", "amount": 20000, "transaction_date": "2023-10-05"},
    )

    report = auth_client.get(
        f"{API}/finance/report",
        params={"start": "2026-06-08", "end": "2026-06-14", "period_type": "week"},
    )
    assert report.status_code == 200, report.text
    data = report.json()["data"]
    assert data["period_type"] == "week"
    assert data["total_income"] == 30000
    assert data["total_expense"] == 10000
    assert data["balance"] == 20000
    assert data["transaction_count"] == 2
