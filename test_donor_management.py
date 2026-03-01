"""pytest tests for BlackRoad Donor Management"""
import pytest
from donor_management import (DonorManagement, DonorType, DonorTier,
                               DonationType, DonationMethod)


@pytest.fixture
def dm(tmp_path):
    d = DonorManagement(str(tmp_path / "test.db"))
    yield d
    d.close()


def test_add_donor(dm):
    d = dm.add_donor("Alice", "alice@test.com")
    assert d.id
    assert d.tier == DonorTier.BRONZE

def test_record_donation_updates_total(dm):
    d = dm.add_donor("Bob", "bob@test.com")
    dm.record_donation(d.id, 500, "Fund2025")
    updated = dm.get_donor(d.id)
    assert updated.total_given == 500

def test_tier_upgrade_to_silver(dm):
    d = dm.add_donor("Carol", "carol@test.com")
    dm.record_donation(d.id, 1_500, "Fund")
    updated = dm.get_donor(d.id)
    assert updated.tier == DonorTier.SILVER

def test_tier_upgrade_to_gold(dm):
    d = dm.add_donor("Dave", "dave@test.com")
    dm.record_donation(d.id, 15_000, "Capital")
    updated = dm.get_donor(d.id)
    assert updated.tier == DonorTier.GOLD

def test_tier_upgrade_to_platinum(dm):
    d = dm.add_donor("Eve", "eve@test.com")
    dm.record_donation(d.id, 60_000, "Capital")
    updated = dm.get_donor(d.id)
    assert updated.tier == DonorTier.PLATINUM

def test_send_receipt(dm):
    d = dm.add_donor("Frank", "frank@test.com")
    donation = dm.record_donation(d.id, 100, "Fund")
    result = dm.send_receipt(donation.id)
    assert result.tax_receipt_sent
    assert result.acknowledged

def test_ltv(dm):
    d = dm.add_donor("Grace", "grace@test.com")
    dm.record_donation(d.id, 200, "Fund")
    dm.record_donation(d.id, 300, "Capital")
    result = dm.ltv(d.id)
    assert result["ltv"] == 500
    assert result["donation_count"] == 2
    assert result["average_gift"] == 250

def test_major_gifts(dm):
    d = dm.add_donor("Henry", "henry@test.com")
    dm.record_donation(d.id, 25_000, "Capital")
    gifts = dm.major_gifts(threshold=10_000)
    assert len(gifts) == 1
    assert gifts[0]["name"] == "Henry"

def test_campaign_summary(dm):
    dm.create_campaign("Test Campaign", 10_000, "2025-01-01", "2025-12-31")
    d1 = dm.add_donor("I", "i@test.com")
    d2 = dm.add_donor("J", "j@test.com")
    dm.record_donation(d1.id, 1_000, "Test Campaign")
    dm.record_donation(d2.id, 2_000, "Test Campaign")
    summary = dm.campaign_summary("Test Campaign")
    assert summary["total_raised"] == 3_000
    assert summary["donor_count"] == 2
    assert summary["progress_pct"] == 30.0

def test_donor_campaigns_tracked(dm):
    d = dm.add_donor("K", "k@test.com")
    dm.record_donation(d.id, 100, "Campaign A")
    dm.record_donation(d.id, 100, "Campaign B")
    updated = dm.get_donor(d.id)
    assert "Campaign A" in updated.campaigns
    assert "Campaign B" in updated.campaigns

def test_tier_summary(dm):
    d = dm.add_donor("L", "l@test.com")
    dm.record_donation(d.id, 100, "Fund")
    summary = dm.tier_summary()
    assert "bronze" in summary

def test_list_by_tier(dm):
    d = dm.add_donor("M", "m@test.com")
    dm.record_donation(d.id, 15_000, "Capital")
    gold_donors = dm.list_donors(tier=DonorTier.GOLD)
    assert len(gold_donors) == 1

# ---------------------------------------------------------------------------
# Stripe integration tests
# ---------------------------------------------------------------------------

def test_stripe_method_exists():
    """DonationMethod.STRIPE must be a valid enum value."""
    from donor_management import DonationMethod
    assert DonationMethod.STRIPE == "stripe"

def test_record_donation_with_stripe_charge_id(dm):
    """Storing a stripe_charge_id round-trips through the DB correctly."""
    d = dm.add_donor("N", "n@test.com")
    donation = dm.record_donation(
        d.id, 100, "Fund",
        method=DonationMethod.STRIPE,
        stripe_charge_id="pi_test_abc123",
    )
    assert donation.stripe_charge_id == "pi_test_abc123"
    assert donation.method == DonationMethod.STRIPE
    fetched = dm.get_donation(donation.id)
    assert fetched.stripe_charge_id == "pi_test_abc123"

def test_process_stripe_payment_missing_package(dm):
    """process_stripe_payment raises ImportError when stripe is not installed."""
    import sys, unittest.mock
    d = dm.add_donor("O", "o@test.com")
    with unittest.mock.patch.dict(sys.modules, {"stripe": None}):
        with pytest.raises(ImportError, match="stripe"):
            dm.process_stripe_payment(
                donor_id=d.id,
                amount_cents=5000,
                campaign="Fund",
                payment_method_id="pm_test",
                stripe_api_key="sk_test_fake",
            )

def test_process_stripe_payment_mocked(dm):
    """process_stripe_payment records donation using mocked Stripe SDK."""
    import unittest.mock
    d = dm.add_donor("P", "p@test.com")
    fake_intent = {"id": "pi_mock_xyz789"}
    mock_stripe = unittest.mock.MagicMock()
    mock_stripe.PaymentIntent.create.return_value = fake_intent

    import sys
    with unittest.mock.patch.dict(sys.modules, {"stripe": mock_stripe}):
        donation = dm.process_stripe_payment(
            donor_id=d.id,
            amount_cents=7500,
            campaign="Annual Fund 2025",
            payment_method_id="pm_test_card",
            stripe_api_key="sk_test_fake",
        )

    assert donation.amount == 75.0
    assert donation.stripe_charge_id == "pi_mock_xyz789"
    assert donation.method == DonationMethod.STRIPE
    updated = dm.get_donor(d.id)
    assert updated.total_given == 75.0

# ---------------------------------------------------------------------------
# End-to-end scenario
# ---------------------------------------------------------------------------

def test_e2e_full_donor_lifecycle(dm):
    """E2E: create campaign → add donor → donate via Stripe → receipt → analytics."""
    import unittest.mock

    # 1. Campaign
    dm.create_campaign("E2E Campaign", 50_000, "2025-01-01", "2025-12-31")

    # 2. Donor
    donor = dm.add_donor(
        "Test Donor", "e2e@test.com",
        phone="555-0000",
        donor_type=DonorType.INDIVIDUAL,
        assigned_to="TestRep",
    )
    assert donor.tier == DonorTier.BRONZE

    # 3. Non-Stripe donation brings donor to Silver
    dm.record_donation(donor.id, 1_200, "E2E Campaign", method=DonationMethod.CHECK)
    assert dm.get_donor(donor.id).tier == DonorTier.SILVER

    # 4. Stripe donation via mocked SDK
    fake_intent = {"id": "pi_e2e_stripe_001"}
    mock_stripe = unittest.mock.MagicMock()
    mock_stripe.PaymentIntent.create.return_value = fake_intent
    import sys
    with unittest.mock.patch.dict(sys.modules, {"stripe": mock_stripe}):
        stripe_don = dm.process_stripe_payment(
            donor_id=donor.id,
            amount_cents=900000,  # $9,000 → pushes total to $10,200 → Gold
            campaign="E2E Campaign",
            payment_method_id="pm_e2e_card",
            stripe_api_key="sk_test_fake",
        )
    assert stripe_don.stripe_charge_id == "pi_e2e_stripe_001"
    assert dm.get_donor(donor.id).tier == DonorTier.GOLD

    # 5. Receipt
    receipt = dm.send_receipt(stripe_don.id)
    assert receipt.tax_receipt_sent
    assert receipt.acknowledged

    # 6. LTV analytics
    ltv = dm.ltv(donor.id)
    assert ltv["ltv"] == 10_200.0
    assert ltv["donation_count"] == 2
    assert "E2E Campaign" in ltv["campaigns"]

    # 7. Campaign summary
    summary = dm.campaign_summary("E2E Campaign")
    assert summary["total_raised"] == 10_200.0
    assert summary["progress_pct"] == pytest.approx(20.4, rel=1e-2)

    # 8. Retention report runs without error
    report = dm.retention_report()
    assert "year" in report
