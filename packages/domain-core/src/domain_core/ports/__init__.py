"""Ports: narrow interfaces the domain depends on; adapters implement them (DIP)."""
from domain_core.ports.audit import AuditPort
from domain_core.ports.balance import BalancePort
from domain_core.ports.billing import BillingPort
from domain_core.ports.crm import ContactInfo, Customer360, CrmPort, CrmUnavailable, SubscriptionLine
from domain_core.ports.decision import DecisionPort
from domain_core.ports.execution import ExecutionPort
from domain_core.ports.knowledge import KnowledgePort
from domain_core.ports.nms import NmsPort
from domain_core.ports.notification import NotificationPort
from domain_core.ports.payment import PaymentPort
from domain_core.ports.policy import PolicyPort
from domain_core.ports.ticketing import TicketingPort

__all__ = [
    "AuditPort",
    "BalancePort",
    "BillingPort",
    "ContactInfo",
    "Customer360",
    "CrmPort",
    "CrmUnavailable",
    "SubscriptionLine",
    "DecisionPort",
    "ExecutionPort",
    "KnowledgePort",
    "NmsPort",
    "NotificationPort",
    "PaymentPort",
    "PolicyPort",
    "TicketingPort",
]