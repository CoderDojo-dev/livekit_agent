#!/usr/bin/env bash
# Enforces the constraints from cookbooks 1-6 that a type checker cannot see.
# Run from Frontend/customer_portal.
set -uo pipefail
fail=0
check() { # name, pattern, path-glob
  if git grep -nE "$2" -- $3 >/dev/null 2>&1; then
    echo "FAIL  $1"; git grep -nE "$2" -- $3 | head -n 10; fail=1
  else
    echo "ok    $1"
  fi
}

check "no fixtures"                 "lib/fixtures"                                   "src"
check "no hardcoded hex colours"    "#[0-9a-fA-F]{3,8}"                              "src/routes src/components/portal src/components/shell"
check "no tailwind font sizes"      "text-(xs|sm|base|lg|xl|[0-9]xl)\b"              "src"
check "no tailwind radii"           "rounded-(sm|md|lg|xl|2xl|3xl)\b"                "src"
check "no arbitrary z-index"        "z-\["                                           "src"
check "no fake randomness"          "Math\.random"                                   "src"
check "no endless scroll"           "loadMore"                                       "src"
check "no raw tool names rendered"  "function_tools_executed|call_id"                "src"
check "no client-side env leak"     "VITE_(BUSINESS_API|TOKEN_SERVICE|PORTAL_SESSION)" "src .env.example"
check "no card/payment UI"          "card_number|cardNumber|cvv|expiry|Visa|Mastercard" "src"
check "no min. 8 characters"        "min\. 8|minLength=\{8\}"                        "src"

# Raw enum values must only appear inside label maps, never in a route file.
check "no raw enums in routes"      "in_progress|network_complaint|scratch_card|pre-connect-buffering" "src/routes"

# 13. Any projection that reports an offset must apply one. A function that
#     resolves _page(limit, offset) and never calls .offset() is the version_94
#     notifications()/callbacks() bug.
if grep -n "_page(limit, offset)" ../../apps/business-api/src/business_api/me_reads.py >/dev/null; then
  missing=$(python3 - <<'PY'
import re, pathlib
src = pathlib.Path("../../apps/business-api/src/business_api/me_reads.py").read_text()
bad = []
for block in re.split(r"\ndef ", src):
    if "_page(limit, offset)" in block and ".offset(start)" not in block:
        bad.append(block.split("(")[0].strip())
print(",".join(bad))
PY
)
  if [ -n "$missing" ]; then
    echo "FAIL 13: these readers resolve a page window but never apply it: $missing"
    exit 1
  fi
fi
echo "PASS 13: every paged reader applies its offset"

# 14 - no residual generic branding. The two exceptions are the migration
#      literals in lib/preferences.ts and lib/api/session.ts
#      ("nexus_portal_preferences" / "nexus_portal_session"): they must survive
#      for existing users' settings and sessions to migrate, and they are data
#      compatibility, not branding.
if grep -rni "nexus" src/ | grep -viq "nexus_portal_"; then
  echo "FAIL 14: Nexus reference remains"; grep -rni "nexus" src/ | grep -vi "nexus_portal_" | head -n 10; exit 1
fi
echo "PASS 14: no residual generic branding"

# 15 - route heads derive from the centralised title helper
if grep -rq "Customer Portal\"" src/routes/_portal/; then
  echo "FAIL 15: hardcoded title"; grep -rn "Customer Portal\"" src/routes/_portal/ | head -n 5; exit 1
fi
echo "PASS 15: route heads derive from pageTitle()"

# 16 - light theme block present
if ! grep -q '\[data-theme="light"\]' src/styles.css; then
  echo "FAIL 16: no light theme"; exit 1
fi
echo "PASS 16: light theme block present"

# 17 - focus ring is tokenised, not a literal grey
if ! grep -q -- "--focus-ring-color" src/styles.css; then
  echo "FAIL 17: focus ring not tokenised"; exit 1
fi
echo "PASS 17: focus ring tokenised"

# 18 - grid background present on body::before
if ! grep -q "body::before" src/styles.css; then
  echo "FAIL 18: no grid background"; exit 1
fi
echo "PASS 18: grid background present"

exit "$fail"