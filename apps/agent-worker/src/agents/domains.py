"""Single source of truth for the specialist domains of the persona graph.

A domain is declared ONCE here: the topics that belong to it, the tool that hands
a caller over to it, and the deterministic spoken transition line. Both the
routing mandate (agents.instruction_kit) and the handoff tools
(tools.routing_tools) read from this table, so a domain can never again be
half-wired -- named in a prompt but missing from a tool set, or vice versa.

This module intentionally imports nothing from the project: it must stay free of
import cycles so that both agents.* and tools.* can depend on it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class Domain:
    """One specialist domain of the persona graph."""

    #: Stable internal key. Also the key used by build_persona_tts.
    key: str
    #: LLM-facing condition clause used when the persona MAY route this
    #: domain away. Carries its own subject and verb so that the generated
    #: line is byte-identical to the v63 hand-written mandate.
    route_condition: str
    #: LLM-facing wording used when the persona OWNS this domain.
    own_topics: str
    #: Name of the @function_tool that performs the handoff to this domain.
    route_tool: str
    #: Deterministic spoken transition line, per language code.
    lines: Mapping[str, str]


DOMAINS: tuple[Domain, ...] = (
    Domain(
        key="billing",
        route_condition="the caller asks about their BALANCE, INVOICE, PAYMENT, or DEFERRAL",
        own_topics="Balance, invoice, payment and deferral requests",
        route_tool="route_to_billing",
        lines=MappingProxyType(
            {
                "fr": "Très bien, je vous mets en relation avec notre service de facturation.",
                "ar": "حسنًا، سأحوّلك إلى قسم الفوترة لدينا.",
                "en": "Sure, I'm connecting you with our billing department.",
            }
        ),
    ),
    Domain(
        key="account",
        route_condition="the caller asks about their PLAN, RECHARGE, ROAMING, or PHONE LINE",
        own_topics="Plan, recharge, roaming and phone-line requests",
        route_tool="route_to_account_services",
        lines=MappingProxyType(
            {
                "fr": "Très bien, je vous mets en relation avec notre service de gestion de compte.",
                "ar": "حسنًا، سأحوّلك إلى قسم إدارة الحساب لدينا.",
                "en": "Sure, I'm connecting you with our account services team.",
            }
        ),
    ),
    Domain(
        key="technical",
        route_condition="the caller has a SIM, NETWORK, or CONNECTIVITY problem",
        own_topics="SIM, network and connectivity problems",
        route_tool="route_to_technical",
        lines=MappingProxyType(
            {
                "fr": "Très bien, je vous mets en relation avec notre service technique.",
                "ar": "حسنًا، سأحوّلك إلى الدعم الفني لدينا.",
                "en": "Sure, I'm connecting you with our technical support.",
            }
        ),
    ),
)

DOMAIN_BY_KEY: Mapping[str, Domain] = MappingProxyType(
    {domain.key: domain for domain in DOMAINS}
)
DOMAIN_BY_ROUTE_TOOL: Mapping[str, Domain] = MappingProxyType(
    {domain.route_tool: domain for domain in DOMAINS}
)
ROUTE_TOOL_NAMES: frozenset[str] = frozenset(domain.route_tool for domain in DOMAINS)
SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"fr", "ar", "en"})
