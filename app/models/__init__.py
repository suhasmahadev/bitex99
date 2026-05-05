"""
models/__init__.py — imports ALL models in FK-dependency order.
This is the SINGLE entry point that registers every table with Base.metadata.
Alembic env.py and application startup MUST import this module.

Layer order (must not import a model before its FK dependency):
  Layer 0: no FK deps
  Layer 1: FK → Layer 0 tables
  Layer 2: FK → Layer 0+1 tables
  ... and so on
"""
# ── Layer 0: no FK deps ───────────────────────────────────────────────────────
from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.coupon import Coupon, DiscountType

# ── Layer 1: FK → users / restaurants ────────────────────────────────────────
from app.models.address import Address, AddressLabel
from app.models.menu import MenuCategory, MenuItem

# ── Layer 2: FK → users + restaurants + menu_items ───────────────────────────
from app.models.cart import CartItem

# ── Layer 3: FK → users + restaurants + addresses ────────────────────────────
from app.models.order import (
    Order, OrderItem,
    OrderStatus, PaymentMethod, PaymentStatus,
    VALID_TRANSITIONS, USER_CANCELLABLE_STATUSES,
)

# ── Layer 4: FK → orders + users + restaurants ───────────────────────────────
from app.models.review import Review

# ══════════════════════════════════════════════════════════════════════════════
# SPEC2 — Delivery Partner models (in FK-dependency order)
# ══════════════════════════════════════════════════════════════════════════════

# Layer 5: FK → users only
from app.models.delivery_partner import DeliveryPartner, VehicleType

# Layer 6: FK → delivery_partners
from app.models.kyc_document import KycDocument, DocType, DocStatus, REQUIRED_DOC_TYPES
from app.models.partner_location import PartnerLocation
from app.models.partner_shift import PartnerShift

# Layer 7: FK → orders + delivery_partners
from app.models.delivery_assignment import DeliveryAssignment, AssignmentStatus

# Layer 8: FK → delivery_assignments
from app.models.delivery_otp import DeliveryOtp

# Layer 9: FK → delivery_partners + delivery_assignments + orders
from app.models.partner_earnings import PartnerEarnings

# Layer 10: FK → delivery_partners only (payout must come before partner_incentive)
from app.models.payout import Payout, PayoutStatus

# Layer 11: FK → delivery_partners + orders (no FK to payout in rules table)
from app.models.incentive_rule import IncentiveRule, IncentiveType

# Layer 12: FK → delivery_partners + incentive_rules + payouts
from app.models.partner_incentive import PartnerIncentive

# Layer 13: FK → delivery_partners + delivery_assignments
from app.models.support_ticket import SupportTicket, TicketCategory, TicketStatus

# ══════════════════════════════════════════════════════════════════════════════
# SPEC3 — Restaurant Partner models (in FK-dependency order)
# ══════════════════════════════════════════════════════════════════════════════

from app.models.restaurant_partner import RestaurantPartner, BusinessType
from app.models.restaurant_document import RestaurantDocument, DocType as RestDocType, DocStatus as RestDocStatus
from app.models.restaurant_timing import RestaurantTiming
from app.models.restaurant_payout import RestaurantPayout, PayoutStatus as RestPayoutStatus
from app.models.restaurant_offer import RestaurantOffer, OfferType as RestOfferType
from app.models.order_response import OrderResponse, OrderResponseAction


__all__ = [
    # ── SPEC.md models ────────────────────────────────────────────────────────
    "User",
    "Address",
    "Restaurant",
    "MenuCategory",
    "MenuItem",
    "CartItem",
    "Order",
    "OrderItem",
    "Review",
    "Coupon",
    # Enums (re-exported so services import from one place)
    "AddressLabel",
    "OrderStatus",
    "PaymentMethod",
    "PaymentStatus",
    "DiscountType",
    # Constants
    "VALID_TRANSITIONS",
    "USER_CANCELLABLE_STATUSES",

    # ── SPEC2.md models ───────────────────────────────────────────────────────
    "DeliveryPartner",
    "VehicleType",
    "KycDocument",
    "DocType",
    "DocStatus",
    "REQUIRED_DOC_TYPES",
    "PartnerLocation",
    "PartnerShift",
    "DeliveryAssignment",
    "AssignmentStatus",
    "DeliveryOtp",
    "PartnerEarnings",
    "Payout",
    "PayoutStatus",
    "IncentiveRule",
    "IncentiveType",
    "PartnerIncentive",
    "SupportTicket",
    "TicketCategory",
    "TicketStatus",

    # ── SPEC3.md models ───────────────────────────────────────────────────────
    "RestaurantPartner",
    "BusinessType",
    "RestaurantDocument",
    "RestDocType",
    "RestDocStatus",
    "RestaurantTiming",
    "RestaurantPayout",
    "RestPayoutStatus",
    "RestaurantOffer",
    "RestOfferType",
    "OrderResponse",
    "OrderResponseAction",
]
