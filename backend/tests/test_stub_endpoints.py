"""Tests documenting stub/placeholder endpoint behavior.

These tests assert the CURRENT not-implemented state. When features are built,
update these tests to verify real functionality. Each failing test = a backlog item.
"""


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


class TestTransactionStubs:
    """
    STATUS: IMPLEMENTED — manual transaction CRUD is live.
    These tests verify the authentication boundary of the implemented endpoints.
    Full functional coverage is in test_manual_transactions.py.
    """

    def test_create_requires_auth(self, client):
        response = client.post(
            "/api/v1/transactions/",
            json={
                "transaction_date": "2026-01-15",
                "amount": "29.99",
                "merchant_name": "CVS Pharmacy",
            },
        )
        assert response.status_code == 401

    def test_update_requires_auth(self, client):
        import uuid
        response = client.put(
            f"/api/v1/transactions/{uuid.uuid4()}",
            json={"amount": "10.00"},
        )
        assert response.status_code == 401

    def test_delete_requires_auth(self, client):
        import uuid
        response = client.delete(f"/api/v1/transactions/{uuid.uuid4()}")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


class TestCategoryStubs:
    """
    STATUS: PARTIALLY IMPLEMENTED (GET returns hardcoded list)
    TODO: Create Category model, implement CRUD, custom family categories
    """

    def test_list_returns_system_categories(self, client):
        response = client.get("/api/v1/categories/")
        assert response.status_code == 200
        categories = response.json()
        assert len(categories) == 5

        names = {c["name"] for c in categories}
        assert names == {
            "Medical Care",
            "Dental Care",
            "Vision Care",
            "Prescription Medications",
            "Over-the-Counter",
        }

        # All should be system categories and HSA-eligible
        for cat in categories:
            assert cat["is_system_category"] is True
            assert cat["is_hsa_eligible"] is True
            assert cat["family_id"] is None

    def test_create_returns_501(self, client):
        response = client.post(
            "/api/v1/categories/",
            json={"name": "Custom Category", "is_hsa_eligible": True},
        )
        assert response.status_code == 501

    def test_get_by_id_returns_404(self, client):
        response = client.get("/api/v1/categories/cat_medical")
        assert response.status_code == 404

    def test_update_returns_501(self, client):
        response = client.put(
            "/api/v1/categories/cat_medical",
            json={"name": "Updated", "is_hsa_eligible": True},
        )
        assert response.status_code == 501

    def test_delete_returns_501(self, client):
        response = client.delete("/api/v1/categories/cat_medical")
        assert response.status_code == 501
