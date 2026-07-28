NL = chr(10)
BAR = "-" * 74

OK = 0
FAIL = 0


def check(label, cond):
    global OK, FAIL
    if cond:
        OK += 1
        print("[OK]   " + label)
    else:
        FAIL += 1
        print("[FAIL] " + label)


def section(title):
    print("")
    print(BAR)
    print(title)
    print(BAR)


# ---------------------------------------------------------------------------
# 1. base_agent.py v61 (SHA 01bd1edc) : le mandat de routage tel qu'il existe
# ---------------------------------------------------------------------------
L_BILLING = ("- If the caller asks about their BALANCE, INVOICE, PAYMENT, or DEFERRAL, "
             "call route_to_billing immediately.")
L_ACCOUNT = ("- If the caller asks about their PLAN, RECHARGE, ROAMING, or PHONE LINE, "
             "call route_to_account_services immediately.")
L_TECH = ("- If the caller has a SIM, NETWORK, or CONNECTIVITY problem, "
          "call route_to_technical immediately.")
L_CLAR = "- If the request is ambiguous, call request_clarification."
L_NEVER = ("- NEVER tell the caller to call a different department or number yourself. "
           "Use the route_* tool. If none of the above fits, call escalate_to_manager.")
L_LAST = ("- The route_* tools transfer the caller to the right specialist; after calling "
          "one you will NOT speak again, so do not also say goodbye yourself.")

HEADER = NL + NL + "Routing mandate (you MUST follow this):" + NL

# Reproduction litterale de la constante actuelle (chaque ligne suivie de NL sauf la derniere)
NO_DEAD_END_MANDATE = HEADER + L_BILLING + NL + L_ACCOUNT + NL + L_TECH + NL + L_CLAR + NL + L_NEVER + NL + L_LAST

CLOSING_PROTOCOL = (
    NL + NL + "Ending the call: when the caller's need is fully handled - information "
    "delivered, a ticket created, an issue escalated, a callback scheduled, or "
    "the caller signals they are finished - first ask, in the caller's language, "
    "whether there is anything else you can help with. If they need more, "
    "continue normally. Only once the caller clearly has nothing else, or clearly "
    "wants to leave or says goodbye, call end_conversation to close the call. "
    "Judge this from the caller's intent, not from a fixed list of keywords. "
    "Never call end_conversation while the caller still needs help, and never end "
    "without first confirming there is nothing else. When you call "
    "end_conversation, do not also speak a goodbye yourself - the tool delivers "
    "the farewell."
)

LANGUAGE_SWITCH_POLICY = (
    NL + NL + "Language: keep speaking your fixed language and never drift on your own. "
    "The only exception overriding any 'never switch language' rule above: if the "
    "caller EXPLICITLY asks to continue in French, Arabic, or English, call "
    "switch_spoken_language with that language code, then continue in it."
)

TTS_REMINDER = NL + NL + "IMPORTANT: You MUST speak ONLY in the language already specified above. Never switch."


def merge_instructions(core, tts_provided=True):
    parts = [core, NO_DEAD_END_MANDATE, CLOSING_PROTOCOL, LANGUAGE_SWITCH_POLICY]
    if tts_provided:
        parts.append(TTS_REMINDER)
    return NL.join(parts)


# ---------------------------------------------------------------------------
# 2. Proposition opus : mandat genere par domaine
# ---------------------------------------------------------------------------
ROUTE_LINES = {
    "billing": L_BILLING[2:],
    "account": L_ACCOUNT[2:],
    "technical": L_TECH[2:],
}


def routing_mandate(own_domain=None):
    lines = ["- " + text for domain, text in ROUTE_LINES.items() if domain != own_domain]
    if own_domain is None:
        lines.append(L_CLAR)
    lines.append(L_NEVER)
    lines.append(L_LAST)
    return NL + NL + "Routing mandate (you MUST follow this):" + NL + NL.join(lines)


section("A. PROPOSITION OPUS : la promesse d'identite octet par octet")
generated = routing_mandate()
check("mandat Triage regenere identique a la constante actuelle", generated == NO_DEAD_END_MANDATE)
check("longueurs identiques (" + str(len(generated)) + " vs " + str(len(NO_DEAD_END_MANDATE)) + ")",
      len(generated) == len(NO_DEAD_END_MANDATE))

billing_mandate = routing_mandate("billing")
check("mandat Billing : ne cite plus route_to_billing", "route_to_billing" not in billing_mandate)
check("mandat Billing : ne cite plus request_clarification", "request_clarification" not in billing_mandate)
check("mandat Billing : cite encore route_to_technical", "route_to_technical" in billing_mandate)
check("mandat Billing : cite encore route_to_account_services", "route_to_account_services" in billing_mandate)
check("mandat Billing : cite encore escalate_to_manager", "escalate_to_manager" in billing_mandate)


# ---------------------------------------------------------------------------
# 3. Outils REELLEMENT possedes par chaque persona sur version_61
#    (releves dans les listes tools=[...] des 5 fichiers d'agents)
# ---------------------------------------------------------------------------
AUTO = ["end_conversation", "switch_spoken_language"]

TOOLS = {
    "triage": ["request_clarification", "check_customer_tickets", "get_ticket_state",
               "route_to_account_services", "route_to_billing", "route_to_technical",
               "escalate_to_manager", "knowledge_search"] + AUTO,
    "billing": ["get_invoice_summary", "get_balance_summary", "make_payment",
                "request_payment_deferral", "route_to_account_services", "route_to_technical",
                "escalate_to_manager", "knowledge_search"] + AUTO,
    "account": ["get_plan_details", "change_plan", "top_up", "toggle_roaming",
                "route_to_billing", "route_to_technical", "escalate_to_manager"] + AUTO,
    "technical": ["unblock_sim", "replace_sim", "diagnose_data_issue", "check_network_status",
                  "route_to_account_services", "route_to_billing", "escalate_to_manager",
                  "create_support_ticket", "check_customer_tickets", "get_ticket_state",
                  "mark_ticket_resolved", "update_support_ticket", "delete_support_ticket",
                  "knowledge_search"] + AUTO,
    "manager": ["transfer_to_human", "create_support_ticket", "check_customer_tickets",
                "get_ticket_state"] + AUTO,
}

ALL_NAMES = sorted({n for names in TOOLS.values() for n in names})


def named_tools(text):
    return sorted({n for n in ALL_NAMES if n in text})


section("B. ETAT ACTUEL version_61 : outils cites mais NON possedes")

# Les 4 personas qui passent par merge_instructions recoivent le mandat complet.
for persona in ["triage", "billing", "account", "technical"]:
    cited = named_tools(NO_DEAD_END_MANDATE)
    missing = [n for n in cited if n not in TOOLS[persona]]
    print("  " + persona.ljust(10) + " mandat cite " + str(cited))
    print("             manquants -> " + str(missing))
    if persona == "triage":
        check("triage : aucun outil cite qu'il ne possede pas", missing == [])
    else:
        check(persona + " : defaut confirme (" + str(len(missing)) + " outil(s) cite(s) sans etre possede(s))",
              len(missing) > 0)

section("C. ETAT ACTUEL version_61 : le cas ManagerAgent")

MANAGER_CORE = (
    "You are a senior support manager handling an escalated call. You MUST speak ONLY in French. Never switch language." + NL +
    "Call transfer_to_human immediately and do not speak before calling it. "
    "The transfer tool owns the single transition announcement and will schedule a callback "
    "if none is free). Ticketing is optional and only when it helps: if the caller "
    "asks about a ticket, or the issue needs tracking, you MAY call "
    "check_customer_tickets to see existing ones, and create_support_ticket only "
    "if none covers the issue - then give them the reference. Never invent a "
    "ticket or status, and if a ticket tool returns 'unavailable', say honestly "
    "you cannot reach the ticketing system right now. "
    "Keep replies short and calm; always reply in French."
)

# Sur version_61 le Manager passe cette chaine BRUTE a super().__init__ : pas de merge_instructions.
manager_now = MANAGER_CORE

check("Manager possede end_conversation (injecte par BaseTelecomAgent)",
      "end_conversation" in TOOLS["manager"])
check("DEFAUT : end_conversation n'est explique nulle part dans ses instructions",
      "end_conversation" not in manager_now)
check("Manager possede switch_spoken_language (injecte par BaseTelecomAgent)",
      "switch_spoken_language" in TOOLS["manager"])
check("DEFAUT : switch_spoken_language n'est explique nulle part dans ses instructions",
      "switch_spoken_language" not in manager_now)
check("DEFAUT : aucune regle de cloture (CLOSING_PROTOCOL absent)",
      "Ending the call" not in manager_now)
check("DEFAUT : aucune politique de langue partagee (LANGUAGE_SWITCH_POLICY absent)",
      "Language: keep speaking your fixed language" not in manager_now)

lock_now = manager_now.count("MUST speak ONLY") + manager_now.count("Never switch") + manager_now.count("always reply in")
print("  ancrages de langue dans le Manager : " + str(lock_now))
for persona in ["triage", "billing", "account", "technical"]:
    sample = merge_instructions("You MUST speak ONLY in French. Never switch to another language.")
    lock_other = sample.count("MUST speak ONLY") + sample.count("Never switch") + sample.count("never drift on your own")
print("  ancrages de langue chez un specialiste : " + str(lock_other))
check("DEFAUT : le Manager est le persona le MOINS ancre en langue", lock_now < lock_other)


# ---------------------------------------------------------------------------
# 4. Correctif local propose : 1 seul fichier, manager_agent.py
# ---------------------------------------------------------------------------
section("D. CORRECTIF LOCAL (manager_agent.py seul, base_agent.py INTOUCHE)")

NO_REDIRECT = (
    " Never tell the caller to call another department or another number yourself: "
    "you are the final escalation point, so either transfer_to_human, arrange the "
    "callback the tool schedules, or track the issue with a ticket."
)

manager_fixed = NL.join([
    MANAGER_CORE + NO_REDIRECT,
    CLOSING_PROTOCOL,
    LANGUAGE_SWITCH_POLICY,
    TTS_REMINDER,
])

cited = named_tools(manager_fixed)
print("  outils cites : " + str(cited))
missing = [n for n in cited if n not in TOOLS["manager"]]
print("  cites sans etre possedes : " + str(missing))

check("correctif : aucun outil cite que le Manager ne possede pas", missing == [])
check("correctif : end_conversation explique", "end_conversation" in manager_fixed)
check("correctif : switch_spoken_language explique", "switch_spoken_language" in manager_fixed)
check("correctif : regle de cloture presente", "Ending the call" in manager_fixed)
check("correctif : politique de langue presente", "Language: keep speaking" in manager_fixed)
check("correctif : rappel TTS present", "IMPORTANT: You MUST speak ONLY" in manager_fixed)
check("correctif : aucun route_to_* (le Manager n'en a aucun)", "route_to_" not in manager_fixed)
check("correctif : aucun request_clarification", "request_clarification" not in manager_fixed)
check("correctif : aucun auto-renvoi escalate_to_manager", "escalate_to_manager" not in manager_fixed)
check("correctif : la garde anti-cul-de-sac est conservee", "another number" in manager_fixed)

lock_fixed = (manager_fixed.count("MUST speak ONLY") + manager_fixed.count("Never switch")
              + manager_fixed.count("never drift on your own"))
print("  ancrages de langue apres correctif : " + str(lock_fixed))
check("correctif : ancrage de langue au niveau des specialistes", lock_fixed >= lock_other)
check("correctif : le coeur metier du Manager est inchange (transfer_to_human en premier)",
      manager_fixed.startswith(MANAGER_CORE))

section("E. NON-REGRESSION DES 4 AUTRES PERSONAS")
check("base_agent.py non modifie -> NO_DEAD_END_MANDATE inchange",
      NO_DEAD_END_MANDATE == HEADER + L_BILLING + NL + L_ACCOUNT + NL + L_TECH + NL + L_CLAR + NL + L_NEVER + NL + L_LAST)
check("merge_instructions garde exactement 2 parametres (aucune API nouvelle)",
      merge_instructions.__code__.co_argcount == 2)
for persona in ["triage", "billing", "account", "technical"]:
    before = merge_instructions("CORE " + persona)
    after = merge_instructions("CORE " + persona)
    check(persona + " : instructions identiques avant/apres le correctif", before == after)

print("")
print(BAR)
print("TOTAL  OK=" + str(OK) + "  FAIL=" + str(FAIL))
print(BAR)
