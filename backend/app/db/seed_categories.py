"""Seed default HSA-eligible expense categories"""

from sqlalchemy.orm import Session
from app.models.category import ExpenseCategory

# IRS-qualified HSA expense categories
DEFAULT_CATEGORIES = [
    # Medical Services
    {
        "name": "Doctor Visits",
        "description": "Primary care, specialist visits, consultations",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Hospital Services",
        "description": "Inpatient care, emergency room, surgery",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Lab Tests & Diagnostics",
        "description": "Blood work, X-rays, MRI, CT scans, ultrasounds",
        "is_hsa_eligible": True,
        "parent": None,
    },
    # Dental Care
    {
        "name": "Dental Care",
        "description": "Routine cleanings, fillings, extractions, root canals",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Orthodontics",
        "description": "Braces, retainers, aligners",
        "is_hsa_eligible": True,
        "parent": None,
    },
    # Vision Care
    {
        "name": "Vision Care",
        "description": "Eye exams, prescription glasses, contact lenses",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Eye Surgery",
        "description": "LASIK, cataract surgery, corrective procedures",
        "is_hsa_eligible": True,
        "parent": None,
    },
    # Prescriptions & Medical Supplies
    {
        "name": "Prescription Medications",
        "description": "Prescribed drugs and medications",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Over-the-Counter Medications",
        "description": "OTC drugs with prescription (post-2020)",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Medical Supplies",
        "description": "Bandages, crutches, thermometers, blood pressure monitors",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Diabetes Supplies",
        "description": "Test strips, glucose monitors, insulin",
        "is_hsa_eligible": True,
        "parent": None,
    },
    # Therapy & Mental Health
    {
        "name": "Mental Health Services",
        "description": "Therapy, counseling, psychiatric care",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Physical Therapy",
        "description": "Rehabilitation, occupational therapy, speech therapy",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Chiropractic Care",
        "description": "Chiropractic adjustments and treatments",
        "is_hsa_eligible": True,
        "parent": None,
    },
    # Reproductive Health
    {
        "name": "Pregnancy & Childbirth",
        "description": "Prenatal care, delivery, postpartum care",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Birth Control",
        "description": "Prescription contraceptives",
        "is_hsa_eligible": True,
        "parent": None,
    },
    # Medical Equipment
    {
        "name": "Medical Equipment",
        "description": "Wheelchairs, walkers, hospital beds, CPAP machines",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Hearing Aids",
        "description": "Hearing aids and batteries",
        "is_hsa_eligible": True,
        "parent": None,
    },
    # Insurance
    {
        "name": "Insurance Premiums",
        "description": "Qualified health insurance premiums (limited circumstances)",
        "is_hsa_eligible": True,
        "parent": None,
    },
    # Other Common Expenses
    {
        "name": "Ambulance Services",
        "description": "Emergency transport",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Home Health Care",
        "description": "In-home nursing, aide services",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Smoking Cessation",
        "description": "Programs and medications to quit smoking",
        "is_hsa_eligible": True,
        "parent": None,
    },
    {
        "name": "Weight Loss Programs",
        "description": "Medically prescribed weight loss programs for specific diseases",
        "is_hsa_eligible": True,
        "parent": None,
    },
    # Non-HSA Eligible (for reference)
    {
        "name": "Cosmetic Procedures",
        "description": "Elective cosmetic surgery (not medically necessary)",
        "is_hsa_eligible": False,
        "parent": None,
    },
    {
        "name": "Vitamins & Supplements",
        "description": "General health vitamins (unless prescribed for specific condition)",
        "is_hsa_eligible": False,
        "parent": None,
    },
    {
        "name": "Gym Membership",
        "description": "General fitness (unless prescribed for specific condition)",
        "is_hsa_eligible": False,
        "parent": None,
    },
]


def seed_default_categories(db: Session) -> list[ExpenseCategory]:
    """
    Seed default HSA expense categories

    Args:
        db: Database session

    Returns:
        List of created categories
    """
    categories = []

    # Check if system categories already exist
    existing_count = db.query(ExpenseCategory).filter(
        ExpenseCategory.is_system_category == True
    ).count()

    if existing_count > 0:
        print(f"System categories already exist ({existing_count} found). Skipping seed.")
        return []

    # Create all categories
    for cat_data in DEFAULT_CATEGORIES:
        category = ExpenseCategory(
            family_id=None,  # System category (not family-specific)
            name=cat_data["name"],
            description=cat_data["description"],
            is_hsa_eligible=cat_data["is_hsa_eligible"],
            parent_category_id=None,  # No parent hierarchy for now (can add later)
            is_system_category=True,  # Mark as system category
        )
        db.add(category)
        categories.append(category)

    db.commit()

    print(f"Seeded {len(categories)} default expense categories")
    return categories


def seed_categories_if_needed(db: Session):
    """
    Check and seed categories if not already present

    This function can be called during app startup to ensure
    default categories are available.
    """
    try:
        seed_default_categories(db)
    except Exception as e:
        print(f"Error seeding categories: {e}")
        db.rollback()
        raise
