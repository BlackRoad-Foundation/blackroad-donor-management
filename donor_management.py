"""
BlackRoad Donor Management - Donor Management and Fundraising Tracker
SQLite-backed system for nonprofits to manage donors, donations, campaigns.
"""

import sqlite3
import json
import uuid
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DonorType(str, Enum):
    INDIVIDUAL = "individual"
    CORPORATE = "corporate"
    FOUNDATION = "foundation"


class DonorTier(str, Enum):
    BRONZE = "bronze"      # < $1,000
    SILVER = "silver"      # $1,000 - $9,999
    GOLD = "gold"          # $10,000 - $49,999
    PLATINUM = "platinum"  # $50,000+


TIER_THRESHOLDS = {
    DonorTier.BRONZE: 0,
    DonorTier.SILVER: 1_000,
    DonorTier.GOLD: 10_000,
    DonorTier.PLATINUM: 50_000,
}


class DonationType(str, Enum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"


class DonationMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    CHECK = "check"
    WIRE = "wire"
    CRYPTO = "crypto"
    CASH = "cash"
    STOCK = "stock"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Donor:
    id: str
    name: str
    email: str
    phone: str = ""
    type: DonorType = DonorType.INDIVIDUAL
    tier: DonorTier = DonorTier.BRONZE
    total_given: float = 0.0
    campaigns: List[str] = field(default_factory=list)
    notes: str = ""
    assigned_to: str = ""
    address: str = ""
    tax_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_donation_at: Optional[str] = None


@dataclass
class Donation:
    id: str
    donor_id: str
    amount: float
    campaign: str
    type: DonationType = DonationType.ONE_TIME
    method: DonationMethod = DonationMethod.CREDIT_CARD
    acknowledged: bool = False
    tax_receipt_sent: bool = False
    received_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: str = ""
    reference_number: str = ""


@dataclass
class Campaign:
    id: str
    name: str
    goal: float
    start_date: str
    end_date: str
    description: str = ""
    status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

class DonorDatabase:
    def __init__(self, db_path: str = "donors.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS donors (
                    id              TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    email           TEXT UNIQUE NOT NULL,
                    phone           TEXT DEFAULT '',
                    type            TEXT DEFAULT 'individual',
                    tier            TEXT DEFAULT 'bronze',
                    total_given     REAL DEFAULT 0,
                    campaigns       TEXT DEFAULT '[]',
                    notes           TEXT DEFAULT '',
                    assigned_to     TEXT DEFAULT '',
                    address         TEXT DEFAULT '',
                    tax_id          TEXT DEFAULT '',
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL,
                    last_donation_at TEXT
                );

                CREATE TABLE IF NOT EXISTS donations (
                    id               TEXT PRIMARY KEY,
                    donor_id         TEXT NOT NULL REFERENCES donors(id),
                    amount           REAL NOT NULL,
                    campaign         TEXT NOT NULL,
                    type             TEXT DEFAULT 'one_time',
                    method           TEXT DEFAULT 'credit_card',
                    acknowledged     INTEGER DEFAULT 0,
                    tax_receipt_sent INTEGER DEFAULT 0,
                    received_at      TEXT NOT NULL,
                    notes            TEXT DEFAULT '',
                    reference_number TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS campaigns (
                    id          TEXT PRIMARY KEY,
                    name        TEXT UNIQUE NOT NULL,
                    goal        REAL NOT NULL DEFAULT 0,
                    start_date  TEXT NOT NULL,
                    end_date    TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status      TEXT DEFAULT 'active',
                    created_at  TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_don_donor ON donations(donor_id);
                CREATE INDEX IF NOT EXISTS idx_don_campaign ON donations(campaign);
                CREATE INDEX IF NOT EXISTS idx_donor_tier ON donors(tier);
            """)


# ---------------------------------------------------------------------------
# Donor Management Service
# ---------------------------------------------------------------------------

class DonorManagement:
    def __init__(self, db_path: str = "donors.db"):
        self.db = DonorDatabase(db_path)
        self.conn = self.db.conn

    # -----------------------------------------------------------------------
    # Campaign management
    # -----------------------------------------------------------------------

    def create_campaign(self, name: str, goal: float, start_date: str,
                        end_date: str, description: str = "") -> Campaign:
        c = Campaign(id=str(uuid.uuid4()), name=name, goal=goal,
                     start_date=start_date, end_date=end_date, description=description)
        with self.conn:
            self.conn.execute(
                "INSERT INTO campaigns (id, name, goal, start_date, end_date, description, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (c.id, c.name, c.goal, c.start_date, c.end_date,
                 c.description, c.status, c.created_at),
            )
        return c

    def get_campaign(self, name: str) -> Optional[Campaign]:
        row = self.conn.execute(
            "SELECT * FROM campaigns WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            return None
        return Campaign(id=row["id"], name=row["name"], goal=row["goal"],
                        start_date=row["start_date"], end_date=row["end_date"],
                        description=row["description"], status=row["status"],
                        created_at=row["created_at"])

    def list_campaigns(self) -> List[Campaign]:
        rows = self.conn.execute("SELECT * FROM campaigns ORDER BY start_date DESC").fetchall()
        return [Campaign(id=r["id"], name=r["name"], goal=r["goal"],
                         start_date=r["start_date"], end_date=r["end_date"],
                         description=r["description"], status=r["status"],
                         created_at=r["created_at"]) for r in rows]

    # -----------------------------------------------------------------------
    # Donor CRUD
    # -----------------------------------------------------------------------

    def add_donor(
        self,
        name: str,
        email: str,
        phone: str = "",
        donor_type: DonorType = DonorType.INDIVIDUAL,
        notes: str = "",
        assigned_to: str = "",
        address: str = "",
        tax_id: str = "",
    ) -> Donor:
        now = datetime.utcnow().isoformat()
        donor = Donor(
            id=str(uuid.uuid4()), name=name, email=email, phone=phone,
            type=donor_type, notes=notes, assigned_to=assigned_to,
            address=address, tax_id=tax_id, created_at=now, updated_at=now,
        )
        with self.conn:
            self.conn.execute(
                """INSERT INTO donors
                   (id, name, email, phone, type, tier, total_given, campaigns,
                    notes, assigned_to, address, tax_id, created_at, updated_at, last_donation_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (donor.id, donor.name, donor.email, donor.phone,
                 donor.type.value, donor.tier.value, donor.total_given,
                 json.dumps(donor.campaigns), donor.notes, donor.assigned_to,
                 donor.address, donor.tax_id, donor.created_at, donor.updated_at,
                 donor.last_donation_at),
            )
        return donor

    def get_donor(self, donor_id: str) -> Optional[Donor]:
        row = self.conn.execute(
            "SELECT * FROM donors WHERE id = ?", (donor_id,)
        ).fetchone()
        return self._row_to_donor(row) if row else None

    def get_donor_by_email(self, email: str) -> Optional[Donor]:
        row = self.conn.execute(
            "SELECT * FROM donors WHERE email = ?", (email,)
        ).fetchone()
        return self._row_to_donor(row) if row else None

    def list_donors(
        self,
        tier: Optional[DonorTier] = None,
        donor_type: Optional[DonorType] = None,
        assigned_to: Optional[str] = None,
    ) -> List[Donor]:
        query = "SELECT * FROM donors WHERE 1=1"
        params: List[Any] = []
        if tier:
            query += " AND tier = ?"
            params.append(tier.value)
        if donor_type:
            query += " AND type = ?"
            params.append(donor_type.value)
        if assigned_to:
            query += " AND assigned_to = ?"
            params.append(assigned_to)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_donor(r) for r in rows]

    # -----------------------------------------------------------------------
    # Donations
    # -----------------------------------------------------------------------

    def record_donation(
        self,
        donor_id: str,
        amount: float,
        campaign: str,
        donation_type: DonationType = DonationType.ONE_TIME,
        method: DonationMethod = DonationMethod.CREDIT_CARD,
        notes: str = "",
        reference_number: str = "",
        received_at: Optional[str] = None,
    ) -> Donation:
        """Record a donation and update donor totals and tier."""
        if not self.get_donor(donor_id):
            raise ValueError(f"Donor {donor_id} not found")
        now = received_at or datetime.utcnow().isoformat()
        donation = Donation(
            id=str(uuid.uuid4()), donor_id=donor_id, amount=amount,
            campaign=campaign, type=donation_type, method=method,
            notes=notes, reference_number=reference_number,
            received_at=now,
        )
        with self.conn:
            self.conn.execute(
                """INSERT INTO donations
                   (id, donor_id, amount, campaign, type, method, acknowledged,
                    tax_receipt_sent, received_at, notes, reference_number)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (donation.id, donation.donor_id, donation.amount, donation.campaign,
                 donation.type.value, donation.method.value, 0, 0,
                 donation.received_at, donation.notes, donation.reference_number),
            )
            # Update donor totals
            self.conn.execute(
                """UPDATE donors SET total_given = total_given + ?,
                   last_donation_at = ?, updated_at = ? WHERE id = ?""",
                (amount, now, now, donor_id),
            )
            # Add campaign to donor's campaign list
            donor = self.get_donor(donor_id)
            if donor and campaign not in donor.campaigns:
                new_campaigns = donor.campaigns + [campaign]
                self.conn.execute(
                    "UPDATE donors SET campaigns = ? WHERE id = ?",
                    (json.dumps(new_campaigns), donor_id),
                )
        self.upgrade_tier(donor_id)
        return donation

    def get_donation(self, donation_id: str) -> Optional[Donation]:
        row = self.conn.execute(
            "SELECT * FROM donations WHERE id = ?", (donation_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_donation(row)

    def list_donations(
        self,
        donor_id: Optional[str] = None,
        campaign: Optional[str] = None,
    ) -> List[Donation]:
        query = "SELECT * FROM donations WHERE 1=1"
        params: List[Any] = []
        if donor_id:
            query += " AND donor_id = ?"
            params.append(donor_id)
        if campaign:
            query += " AND campaign = ?"
            params.append(campaign)
        query += " ORDER BY received_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_donation(r) for r in rows]

    def acknowledge_donation(self, donation_id: str) -> Optional[Donation]:
        with self.conn:
            self.conn.execute(
                "UPDATE donations SET acknowledged = 1 WHERE id = ?", (donation_id,)
            )
        return self.get_donation(donation_id)

    def send_receipt(self, donation_id: str) -> Optional[Donation]:
        """Mark tax receipt as sent (simulated)."""
        with self.conn:
            self.conn.execute(
                "UPDATE donations SET tax_receipt_sent = 1, acknowledged = 1 WHERE id = ?",
                (donation_id,),
            )
        return self.get_donation(donation_id)

    # -----------------------------------------------------------------------
    # Tier management
    # -----------------------------------------------------------------------

    def upgrade_tier(self, donor_id: str) -> Optional[Donor]:
        """Recalculate and set donor tier based on total_given."""
        donor = self.get_donor(donor_id)
        if not donor:
            return None
        new_tier = self._calculate_tier(donor.total_given)
        if new_tier != donor.tier:
            with self.conn:
                self.conn.execute(
                    "UPDATE donors SET tier = ?, updated_at = ? WHERE id = ?",
                    (new_tier.value, datetime.utcnow().isoformat(), donor_id),
                )
        return self.get_donor(donor_id)

    def _calculate_tier(self, total_given: float) -> DonorTier:
        if total_given >= TIER_THRESHOLDS[DonorTier.PLATINUM]:
            return DonorTier.PLATINUM
        elif total_given >= TIER_THRESHOLDS[DonorTier.GOLD]:
            return DonorTier.GOLD
        elif total_given >= TIER_THRESHOLDS[DonorTier.SILVER]:
            return DonorTier.SILVER
        return DonorTier.BRONZE

    # -----------------------------------------------------------------------
    # Analytics
    # -----------------------------------------------------------------------

    def ltv(self, donor_id: str) -> Dict[str, Any]:
        """Lifetime value report for a donor."""
        donor = self.get_donor(donor_id)
        if not donor:
            raise ValueError(f"Donor {donor_id} not found")
        donations = self.list_donations(donor_id=donor_id)
        if not donations:
            return {"donor_id": donor_id, "name": donor.name, "ltv": 0,
                    "donation_count": 0, "average_gift": 0, "campaigns": []}
        avg = donor.total_given / len(donations)
        return {
            "donor_id": donor_id,
            "name": donor.name,
            "tier": donor.tier.value,
            "ltv": round(donor.total_given, 2),
            "donation_count": len(donations),
            "average_gift": round(avg, 2),
            "first_donation": donations[-1].received_at,
            "last_donation": donations[0].received_at,
            "campaigns": donor.campaigns,
        }

    def major_gifts(self, threshold: float = 10_000) -> List[Dict[str, Any]]:
        """Donors whose total giving exceeds threshold."""
        rows = self.conn.execute(
            "SELECT * FROM donors WHERE total_given >= ? ORDER BY total_given DESC",
            (threshold,),
        ).fetchall()
        donors = [self._row_to_donor(r) for r in rows]
        return [
            {
                "id": d.id,
                "name": d.name,
                "email": d.email,
                "type": d.type.value,
                "tier": d.tier.value,
                "total_given": d.total_given,
                "last_donation": d.last_donation_at,
            }
            for d in donors
        ]

    def campaign_summary(self, campaign_name: str) -> Dict[str, Any]:
        """Full summary for a specific fundraising campaign."""
        rows = self.conn.execute(
            """SELECT COUNT(*) as donor_count, SUM(amount) as total_raised,
               AVG(amount) as avg_gift, MAX(amount) as largest_gift,
               COUNT(CASE WHEN type='recurring' THEN 1 END) as recurring_count
               FROM donations WHERE campaign = ?""",
            (campaign_name,),
        ).fetchone()
        campaign = self.get_campaign(campaign_name)
        total_raised = rows["total_raised"] or 0
        goal = campaign.goal if campaign else 0
        return {
            "campaign": campaign_name,
            "goal": goal,
            "total_raised": round(total_raised, 2),
            "progress_pct": round(total_raised / goal * 100, 1) if goal else 0,
            "donor_count": rows["donor_count"],
            "average_gift": round(rows["avg_gift"] or 0, 2),
            "largest_gift": round(rows["largest_gift"] or 0, 2),
            "recurring_donors": rows["recurring_count"],
        }

    def retention_report(self) -> Dict[str, Any]:
        """Donor retention: who gave last year vs this year."""
        this_year = date.today().year
        last_year = this_year - 1
        this_year_donors = set(
            r[0] for r in self.conn.execute(
                "SELECT DISTINCT donor_id FROM donations WHERE strftime('%Y', received_at) = ?",
                (str(this_year),),
            ).fetchall()
        )
        last_year_donors = set(
            r[0] for r in self.conn.execute(
                "SELECT DISTINCT donor_id FROM donations WHERE strftime('%Y', received_at) = ?",
                (str(last_year),),
            ).fetchall()
        )
        retained = this_year_donors & last_year_donors
        lapsed = last_year_donors - this_year_donors
        new_donors = this_year_donors - last_year_donors
        return {
            "year": this_year,
            "retained_donors": len(retained),
            "lapsed_donors": len(lapsed),
            "new_donors": len(new_donors),
            "retention_rate": round(len(retained) / len(last_year_donors), 3)
            if last_year_donors else 0,
        }

    def tier_summary(self) -> Dict[str, Any]:
        rows = self.conn.execute(
            "SELECT tier, COUNT(*) as count, SUM(total_given) as total FROM donors GROUP BY tier"
        ).fetchall()
        return {r["tier"]: {"count": r["count"], "total_given": round(r["total"] or 0, 2)} for r in rows}

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _row_to_donor(self, row: sqlite3.Row) -> Donor:
        return Donor(
            id=row["id"], name=row["name"], email=row["email"], phone=row["phone"],
            type=DonorType(row["type"]), tier=DonorTier(row["tier"]),
            total_given=row["total_given"], campaigns=json.loads(row["campaigns"]),
            notes=row["notes"], assigned_to=row["assigned_to"],
            address=row["address"], tax_id=row["tax_id"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            last_donation_at=row["last_donation_at"],
        )

    def _row_to_donation(self, row: sqlite3.Row) -> Donation:
        return Donation(
            id=row["id"], donor_id=row["donor_id"], amount=row["amount"],
            campaign=row["campaign"], type=DonationType(row["type"]),
            method=DonationMethod(row["method"]),
            acknowledged=bool(row["acknowledged"]),
            tax_receipt_sent=bool(row["tax_receipt_sent"]),
            received_at=row["received_at"], notes=row["notes"],
            reference_number=row["reference_number"],
        )

    def close(self) -> None:
        self.conn.close()


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    import tempfile, os
    db_file = tempfile.mktemp(suffix=".db")
    dm = DonorManagement(db_file)

    print("\n=== Creating Campaigns ===")
    dm.create_campaign("Annual Fund 2025", 500_000, "2025-01-01", "2025-12-31",
                       "General operating support")
    dm.create_campaign("Capital Campaign", 2_000_000, "2025-03-01", "2026-06-30",
                       "New building fund")
    print("  Campaigns created")

    print("\n=== Adding Donors ===")
    alice = dm.add_donor("Alice Chen", "alice@donor.com", phone="555-1234",
                         donor_type=DonorType.INDIVIDUAL, assigned_to="Sarah")
    corp = dm.add_donor("Acme Corp", "giving@acme.com",
                        donor_type=DonorType.CORPORATE, tax_id="12-3456789")
    frank = dm.add_donor("Frank Williams Foundation", "frank@fwf.org",
                         donor_type=DonorType.FOUNDATION)
    print(f"  Added: {alice.name}, {corp.name}, {frank.name}")

    print("\n=== Recording Donations ===")
    dm.record_donation(alice.id, 500, "Annual Fund 2025", DonationMethod.CREDIT_CARD)
    dm.record_donation(alice.id, 1_500, "Annual Fund 2025", method=DonationMethod.CHECK)
    dm.record_donation(corp.id, 25_000, "Capital Campaign", method=DonationMethod.WIRE)
    d4 = dm.record_donation(frank.id, 100_000, "Capital Campaign",
                             method=DonationMethod.WIRE, donation_type=DonationType.RECURRING)
    print("  Donations recorded")

    print("\n=== Tier Check ===")
    alice_updated = dm.get_donor(alice.id)
    frank_updated = dm.get_donor(frank.id)
    print(f"  Alice: ${alice_updated.total_given:,.2f} → {alice_updated.tier.value}")
    print(f"  Frank: ${frank_updated.total_given:,.2f} → {frank_updated.tier.value}")

    print("\n=== Send Receipt ===")
    dm.send_receipt(d4.id)
    print("  Receipt sent")

    print("\n=== Major Gifts ===")
    major = dm.major_gifts(threshold=10_000)
    for m in major:
        print(f"  {m['name']}: ${m['total_given']:,.2f} ({m['tier']})")

    print("\n=== Campaign Summary ===")
    cs = dm.campaign_summary("Capital Campaign")
    print(f"  Raised: ${cs['total_raised']:,.2f} / ${cs['goal']:,.2f} ({cs['progress_pct']:.1f}%)")

    print("\n=== LTV ===")
    ltv = dm.ltv(alice.id)
    print(f"  {ltv['name']}: LTV=${ltv['ltv']:,.2f}, avg gift=${ltv['average_gift']:,.2f}")

    dm.close()
    os.unlink(db_file)
    print("\n✓ Demo complete")


if __name__ == "__main__":
    demo()
