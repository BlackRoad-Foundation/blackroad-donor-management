# BlackRoad Donor Management

[![PyPI version](https://img.shields.io/pypi/v/blackroad-donor-management.svg)](https://pypi.org/project/blackroad-donor-management/)
[![Python](https://img.shields.io/pypi/pyversions/blackroad-donor-management.svg)](https://pypi.org/project/blackroad-donor-management/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/BlackRoad-Foundation/blackroad-donor-management/actions/workflows/python-package.yml/badge.svg)](https://github.com/BlackRoad-Foundation/blackroad-donor-management/actions)

> **Production-ready donor management and fundraising CRM for nonprofits.**  
> SQLite-backed · Stripe-integrated · Zero mandatory dependencies · Python 3.9+

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Installation](#installation)
   - [pip (recommended)](#pip-recommended)
   - [Stripe extra](#stripe-extra)
   - [Development install](#development-install)
4. [Quick Start](#quick-start)
5. [Stripe Integration](#stripe-integration)
   - [Setup](#setup)
   - [Charging a card](#charging-a-card)
6. [API Reference](#api-reference)
   - [DonorManagement](#donormanagement)
   - [Campaigns](#campaigns)
   - [Donors](#donors)
   - [Donations](#donations)
   - [Analytics](#analytics)
7. [Data Model](#data-model)
   - [Enums](#enums)
   - [Tier Thresholds](#tier-thresholds)
   - [Donor fields](#donor-fields)
   - [Donation fields](#donation-fields)
   - [Campaign fields](#campaign-fields)
8. [Running Tests](#running-tests)
9. [Contributing](#contributing)
10. [License](#license)

---

## Overview

**BlackRoad Donor Management** is a lightweight, self-contained Python library that gives nonprofits a full donor CRM backed by SQLite. It tracks individual, corporate, and foundation donors; records one-time and recurring gifts; manages fundraising campaigns; calculates lifetime value; and integrates with **Stripe** for card-present and online payments — all with no required external dependencies.

---

## Features

| Category | Capability |
|---|---|
| **Donors** | Individual / corporate / foundation with automatic tier promotion |
| **Donations** | One-time & recurring gifts; 7 payment methods including Stripe |
| **Tax Receipts** | Track acknowledgements and tax receipt delivery |
| **Campaigns** | Goal tracking and real-time progress reporting |
| **Analytics** | LTV, major-gift reports, campaign summaries, tier breakdowns, retention |
| **Stripe** | Native `process_stripe_payment()` — charge → record → tier-upgrade in one call |
| **Portable** | Single SQLite file; no server, no Docker, no configuration required |

---

## Installation

### pip (recommended)

```bash
pip install blackroad-donor-management
```

### Stripe extra

To enable the `process_stripe_payment()` helper, install the optional Stripe dependency:

```bash
pip install "blackroad-donor-management[stripe]"
```

### Development install

```bash
git clone https://github.com/BlackRoad-Foundation/blackroad-donor-management.git
cd blackroad-donor-management
pip install -e ".[dev]"
```

---

## Quick Start

```python
from donor_management import DonorManagement, DonorType, DonationMethod

dm = DonorManagement("donors.db")

# Create a campaign
dm.create_campaign("Annual Fund 2025", 500_000, "2025-01-01", "2025-12-31")

# Add a donor
donor = dm.add_donor(
    "Alice Chen", "alice@example.com",
    donor_type=DonorType.INDIVIDUAL,
    assigned_to="Sarah",
)

# Record a donation by check
donation = dm.record_donation(
    donor.id, 5_000, "Annual Fund 2025",
    method=DonationMethod.CHECK,
)

# Send the tax receipt
dm.send_receipt(donation.id)

# Analytics
print(dm.ltv(donor.id))
print(dm.major_gifts(threshold=1_000))
print(dm.campaign_summary("Annual Fund 2025"))
```

---

## Stripe Integration

### Setup

1. Install the Stripe extra: `pip install "blackroad-donor-management[stripe]"`
2. Obtain your Stripe secret key from the [Stripe Dashboard](https://dashboard.stripe.com/apikeys).
3. Collect a `PaymentMethod` ID (`pm_…`) on your frontend using [Stripe.js](https://stripe.com/docs/js).

### Charging a card

```python
from donor_management import DonorManagement, DonorType

dm = DonorManagement("donors.db")

donor = dm.add_donor("Bob Smith", "bob@example.com", donor_type=DonorType.INDIVIDUAL)

# amount_cents is in the smallest currency unit (cents for USD)
donation = dm.process_stripe_payment(
    donor_id=donor.id,
    amount_cents=10_000,          # $100.00
    campaign="Annual Fund 2025",
    payment_method_id="pm_...",   # from Stripe.js on your frontend
    stripe_api_key="sk_live_...", # keep this secret — never expose in client code
)

print(donation.stripe_charge_id)  # pi_3...
print(donation.amount)            # 100.0
```

> **Security note:** Never embed your Stripe **secret** key (`sk_…`) in client-side code. Store it in an environment variable and pass it at runtime.

---

## API Reference

### DonorManagement

```python
DonorManagement(db_path: str = "donors.db")
```

Opens (or creates) a SQLite database at `db_path`. Thread-safe for read-heavy workloads; use one instance per thread for write-heavy scenarios.

---

### Campaigns

#### `create_campaign`

```python
create_campaign(
    name: str,
    goal: float,
    start_date: str,   # "YYYY-MM-DD"
    end_date: str,     # "YYYY-MM-DD"
    description: str = "",
) -> Campaign
```

#### `get_campaign`

```python
get_campaign(name: str) -> Optional[Campaign]
```

#### `list_campaigns`

```python
list_campaigns() -> List[Campaign]
```

---

### Donors

#### `add_donor`

```python
add_donor(
    name: str,
    email: str,
    phone: str = "",
    donor_type: DonorType = DonorType.INDIVIDUAL,
    notes: str = "",
    assigned_to: str = "",
    address: str = "",
    tax_id: str = "",
) -> Donor
```

#### `get_donor`

```python
get_donor(donor_id: str) -> Optional[Donor]
```

#### `get_donor_by_email`

```python
get_donor_by_email(email: str) -> Optional[Donor]
```

#### `list_donors`

```python
list_donors(
    tier: Optional[DonorTier] = None,
    donor_type: Optional[DonorType] = None,
    assigned_to: Optional[str] = None,
) -> List[Donor]
```

---

### Donations

#### `record_donation`

```python
record_donation(
    donor_id: str,
    amount: float,
    campaign: str,
    donation_type: DonationType = DonationType.ONE_TIME,
    method: DonationMethod = DonationMethod.CREDIT_CARD,
    notes: str = "",
    reference_number: str = "",
    received_at: Optional[str] = None,  # ISO-8601; defaults to utcnow
    stripe_charge_id: str = "",
) -> Donation
```

Automatically recalculates and persists the donor's tier after recording.

#### `process_stripe_payment`

```python
process_stripe_payment(
    donor_id: str,
    amount_cents: int,
    campaign: str,
    payment_method_id: str,
    stripe_api_key: str,
    donation_type: DonationType = DonationType.ONE_TIME,
    notes: str = "",
    currency: str = "usd",
) -> Donation
```

Creates a confirmed Stripe `PaymentIntent` then calls `record_donation` internally. Requires `pip install "blackroad-donor-management[stripe]"`.

#### `get_donation`

```python
get_donation(donation_id: str) -> Optional[Donation]
```

#### `list_donations`

```python
list_donations(
    donor_id: Optional[str] = None,
    campaign: Optional[str] = None,
) -> List[Donation]
```

#### `acknowledge_donation`

```python
acknowledge_donation(donation_id: str) -> Optional[Donation]
```

#### `send_receipt`

```python
send_receipt(donation_id: str) -> Optional[Donation]
```

Marks `acknowledged = True` and `tax_receipt_sent = True`.

---

### Analytics

#### `ltv`

```python
ltv(donor_id: str) -> Dict[str, Any]
```

Returns lifetime-value summary: `ltv`, `donation_count`, `average_gift`, `first_donation`, `last_donation`, `campaigns`.

#### `major_gifts`

```python
major_gifts(threshold: float = 10_000) -> List[Dict[str, Any]]
```

Returns all donors whose `total_given` exceeds `threshold`, ordered descending.

#### `campaign_summary`

```python
campaign_summary(campaign_name: str) -> Dict[str, Any]
```

Returns `total_raised`, `goal`, `progress_pct`, `donor_count`, `average_gift`, `largest_gift`, `recurring_donors`.

#### `retention_report`

```python
retention_report() -> Dict[str, Any]
```

Compares giving between the current and prior calendar year: `retained_donors`, `lapsed_donors`, `new_donors`, `retention_rate`.

#### `tier_summary`

```python
tier_summary() -> Dict[str, Any]
```

Returns per-tier donor counts and total giving.

---

## Data Model

### Enums

| Enum | Values |
|---|---|
| `DonorType` | `INDIVIDUAL`, `CORPORATE`, `FOUNDATION` |
| `DonorTier` | `BRONZE`, `SILVER`, `GOLD`, `PLATINUM` |
| `DonationType` | `ONE_TIME`, `RECURRING` |
| `DonationMethod` | `CREDIT_CARD`, `CHECK`, `WIRE`, `CRYPTO`, `CASH`, `STOCK`, `STRIPE` |

### Tier Thresholds

| Tier | Lifetime Giving |
|---|---|
| Bronze | < $1,000 |
| Silver | $1,000 – $9,999 |
| Gold | $10,000 – $49,999 |
| Platinum | $50,000+ |

Tiers are recalculated automatically every time a donation is recorded.

### Donor fields

| Field | Type | Description |
|---|---|---|
| `id` | `str` | UUID primary key |
| `name` | `str` | Full name |
| `email` | `str` | Unique email address |
| `phone` | `str` | Phone number |
| `type` | `DonorType` | Individual / corporate / foundation |
| `tier` | `DonorTier` | Auto-calculated from `total_given` |
| `total_given` | `float` | Cumulative lifetime donations |
| `campaigns` | `List[str]` | Campaign names the donor has given to |
| `notes` | `str` | Internal notes |
| `assigned_to` | `str` | Staff member responsible |
| `address` | `str` | Mailing address |
| `tax_id` | `str` | EIN or SSN for receipting |
| `created_at` | `str` | ISO-8601 timestamp |
| `updated_at` | `str` | ISO-8601 timestamp |
| `last_donation_at` | `str \| None` | ISO-8601 timestamp of most recent gift |

### Donation fields

| Field | Type | Description |
|---|---|---|
| `id` | `str` | UUID primary key |
| `donor_id` | `str` | FK → Donor |
| `amount` | `float` | Gift amount in dollars |
| `campaign` | `str` | Campaign name |
| `type` | `DonationType` | One-time or recurring |
| `method` | `DonationMethod` | Payment method |
| `acknowledged` | `bool` | Whether gift has been acknowledged |
| `tax_receipt_sent` | `bool` | Whether tax receipt has been issued |
| `received_at` | `str` | ISO-8601 timestamp |
| `notes` | `str` | Internal notes |
| `reference_number` | `str` | Check number, wire ref, etc. |
| `stripe_charge_id` | `str` | Stripe `PaymentIntent` ID (`pi_…`) |

### Campaign fields

| Field | Type | Description |
|---|---|---|
| `id` | `str` | UUID primary key |
| `name` | `str` | Unique campaign name |
| `goal` | `float` | Fundraising goal in dollars |
| `start_date` | `str` | `YYYY-MM-DD` |
| `end_date` | `str` | `YYYY-MM-DD` |
| `description` | `str` | Campaign description |
| `status` | `str` | `active` or `closed` |
| `created_at` | `str` | ISO-8601 timestamp |

---

## Running Tests

```bash
pip install "blackroad-donor-management[dev]"
pytest test_donor_management.py -v
```

The test suite covers unit tests, Stripe mocked integration tests, and a full end-to-end donor lifecycle scenario.

---

## Contributing

1. Fork the repository and create a feature branch.
2. Make your changes with tests.
3. Run `pytest test_donor_management.py -v` to confirm all tests pass.
4. Open a pull request against `main`.

Please follow the existing code style (type hints, docstrings on public methods).

---

## License

[MIT](LICENSE) © BlackRoad Foundation

