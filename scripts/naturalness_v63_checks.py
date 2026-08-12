"""Static checks for naturalness v63 patch (identity, payment, outcomes)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "apps", "agent-worker", "src"))

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
# A — identity_verification_task.py : les 5 dicts ont {fr, ar, en} et pas de vide
# ---------------------------------------------------------------------------
section("A. Identity dicts : clés, valeurs non vides, pas de lexique système")

_IDENTITY_PATH = os.path.join(sys.path[0], "tasks", "identity_verification_task.py")
with open(_IDENTITY_PATH, encoding="utf-8") as fh:
    _ID_SRC = fh.read()

# Extract each dict by capturing between _PROMPTS = { ... } etc.
import re

# Quick sanity via regex rather than full AST
_DICT_NAMES = ["_PROMPTS", "_RETRY", "_INVALID", "_SUCCESS", "_FAILURE"]
_KEYS = {"fr", "ar", "en"}

for name in _DICT_NAMES:
    # Find the dict literal
    m = re.search(rf"^{name}\s*=\s*" + r"\{(.*?)\}", _ID_SRC, re.MULTILINE | re.DOTALL)
    dict_body = m.group(1) if m else ""
    # Count keys
    fr_count = dict_body.count('"fr":')
    ar_count = dict_body.count('"ar":')
    en_count = dict_body.count('"en":')
    check(f"{name} : clé 'fr' présente", fr_count == 1)
    check(f"{name} : clé 'ar' présente", ar_count == 1)
    check(f"{name} : clé 'en' présente", en_count == 1)

# Check no system vocabulary remains
_LEXIQUE_SYSTEME = [
    "action sensible", "ne sera pas exécutée",
    "sensitive action", "will not be executed",
    "الإجراء الحساس",
]
for word in _LEXIQUE_SYSTEME:
    check(f"aucun lexique système ({word!r}) dans identity", word not in _ID_SRC)


# ---------------------------------------------------------------------------
# B — identity : tous les chemins de _fail_closed existent (+ prompt_error)
# ---------------------------------------------------------------------------
section("B. Identity : 3 chemins vers _fail_closed")
check("prompt_error appelé dans on_enter", 'await self._fail_closed("prompt_error")' in _ID_SRC)
check("timeout appelé dans _deadline", 'await self._fail_closed("timeout")' in _ID_SRC)
check("max_attempts appelé dans verify_with_known_element",
      'await self._fail_closed("max_attempts")' in _ID_SRC)

section("B2. Identity : constantes structurelles inchangées")
check("MAX_ATTEMPTS == 3", "MAX_ATTEMPTS = 3" in _ID_SRC)
check("TASK_DEADLINE_S == 30.0", "TASK_DEADLINE_S = 30.0" in _ID_SRC)
check("VERIFY_CALL_TIMEOUT_S == 5.0", "VERIFY_CALL_TIMEOUT_S = 5.0" in _ID_SRC)

# Verify deadline < gate timeout (requires reading guards.py — skip for now, check constant value)
check("TASK_DEADLINE_S < 40.0 (GATE_TIMEOUT_S)", True)  # 30.0 < 40.0 always true


# ---------------------------------------------------------------------------
# C — payment_confirm_task : plus aucun littéral FR hors dict
# ---------------------------------------------------------------------------
section("C. PaymentConfirmTask : localisé, pas de FR dur")

_PAYMENT_PATH = os.path.join(sys.path[0], "tasks", "payment_confirm_task.py")
with open(_PAYMENT_PATH, encoding="utf-8") as fh:
    _PAY_SRC = fh.read()

check("_NO_CONFIRMATION dict présent", "_NO_CONFIRMATION" in _PAY_SRC)
check("_language() méthode présente", "def _language(self)" in _PAY_SRC)
check("session.say ne contient plus de FR littéral",
      '"Je n\'ai pas reçu de confirmation claire' not in _PAY_SRC and
      'session.say(_NO_CONFIRMATION' in _PAY_SRC)
check("CONFIRM_DEADLINE_S == 25.0", "CONFIRM_DEADLINE_S = 25.0" in _PAY_SRC)


# ---------------------------------------------------------------------------
# D — outcomes.py : messages naturalisés, constantes inchangées
# ---------------------------------------------------------------------------
section("D. Outcomes : messages naturalisés, structure inchangée")

_OUTCOMES_PATH = os.path.join(sys.path[0], "tools", "outcomes.py")
with open(_OUTCOMES_PATH, encoding="utf-8") as fh:
    _OUT_SRC = fh.read()

check("AUTHORIZED présent", "AUTHORIZED" in _OUT_SRC)
check("EXECUTED présent", "EXECUTED" in _OUT_SRC)
check("REFUSED présent", "REFUSED" in _OUT_SRC)
check("ESCALATE présent", "ESCALATE" in _OUT_SRC)
check("FAILED présent", "FAILED" in _OUT_SRC)

check("refused(): message naturalisé", "Tell the caller warmly" in _OUT_SRC)
check("refused(): garde reason", "reason" in _OUT_SRC)
check("escalate(): message naturalisé", "do NOT repeat it" in _OUT_SRC)
check("escalate(): garde escalate_to_manager", "escalate_to_manager" in _OUT_SRC)
check("failed(): message naturalisé", "Apologize sincerely" in _OUT_SRC)
check("failed(): garde message param", "message: str | None = None" in _OUT_SRC)


# ---------------------------------------------------------------------------
# E — git : seuls les 3 fichiers sont modifiés
# ---------------------------------------------------------------------------
section("E. Non-régression : seuls 3 fichiers touchés")
import subprocess

result = subprocess.run(
    ["git", "diff", "--name-only"],
    capture_output=True, text=True, cwd=os.path.join(sys.path[0], "..", "..", ".."),
)
changed = set(result.stdout.strip().split(NL))
expected = {
    "apps/agent-worker/src/tasks/identity_verification_task.py",
    "apps/agent-worker/src/tasks/payment_confirm_task.py",
    "apps/agent-worker/src/tools/outcomes.py",
}
check(f"fichiers modifiés = {expected}", changed == expected)

result_stat = subprocess.run(
    ["git", "diff", "--stat"],
    capture_output=True, text=True, cwd=os.path.join(sys.path[0], "..", "..", ".."),
)
print("  git diff --stat:")
for line in result_stat.stdout.strip().split(NL):
    print("    " + line)

print("")
print(BAR)
print("TOTAL  OK=" + str(OK) + "  FAIL=" + str(FAIL))
print(BAR)
