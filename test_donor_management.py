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
