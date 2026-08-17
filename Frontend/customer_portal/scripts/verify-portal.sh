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

exit "$fail"