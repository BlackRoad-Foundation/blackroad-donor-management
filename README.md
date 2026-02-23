# BlackRoad Donor Management

> Donor management and fundraising tracker — SQLite-backed, zero-dependency Python.

## Features

- **Donors** — individual / corporate / foundation with tier tracking (bronze → platinum)
- **Donations** — one-time and recurring, multiple payment methods
- **Tax Receipts** — track acknowledgements and tax receipt delivery
- **Campaigns** — goal tracking, progress reporting
- **Analytics** — LTV, major gifts, campaign summary, tier breakdown, retention report

## Tier Thresholds

| Tier | Lifetime Giving |
|------|----------------|
| Bronze | < $1,000 |
| Silver | $1,000 – $9,999 |
| Gold | $10,000 – $49,999 |
| Platinum | $50,000+ |

## Quick Start

```python
from donor_management import DonorManagement, DonorType, DonationMethod

dm = DonorManagement("donors.db")

dm.create_campaign("Annual Fund 2025", 500_000, "2025-01-01", "2025-12-31")

donor = dm.add_donor("Alice Chen", "alice@co.com",
                     donor_type=DonorType.INDIVIDUAL, assigned_to="Sarah")

donation = dm.record_donation(donor.id, 5_000, "Annual Fund 2025",
                               method=DonationMethod.CHECK)
dm.send_receipt(donation.id)

print(dm.ltv(donor.id))
print(dm.major_gifts(threshold=1_000))
print(dm.campaign_summary("Annual Fund 2025"))
```

## Running Tests

```bash
pip install pytest
pytest test_donor_management.py -v
```
