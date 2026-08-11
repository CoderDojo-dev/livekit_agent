#!/usr/bin/env bash
# P0-2 — fail-closed default role. Static sweep + live re-proof.
# Usage: bash scripts/verify_p0_2.sh
set -uo pipefail

API="${BUSINESS_API_HOST:-http://localhost:8108}"
pass=0; fail=0

ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=$((fail+1)); }

# Adapted from cookbook §9.1 (decision logged in the P0-2 results file): the §4.3 prohibition
# blocks and the §6.2 config.ts comment quote the removed symbols in documentation prose, so a
# bare grep would flag intentional lesson text. Every static check below therefore filters out
# comment lines (content whose first non-blank char is '#' or '*'); an actual reintroduction is a
# definition/forward/accessor, which never begins with a comment marker and is still caught.
# P0-3 follow-up (decision logged in the P0-3 results file): docs/versions/version_84.md is a
# handoff changelog that quotes the removed variable in prose - same class as ':!features_to_apply',
# so it is excluded too.
no_comments() { grep -vE '^[^:]+:[0-9]+:[[:space:]]*[#*]'; }

# --- static: nothing may reference an environment-sourced role default -------
echo "static sweep"

if git grep -n "BUSINESS_API_DEFAULT_ROLE" -- . ':!features_to_apply' ':!scripts/verify_p0_2.sh' ':!apps/business-api/tests/test_no_default_role.py' ':!docs/versions/version_84.md' | no_comments; then
  bad "1  BUSINESS_API_DEFAULT_ROLE still present:"
  git grep -n "BUSINESS_API_DEFAULT_ROLE" -- . ':!features_to_apply' ':!scripts/verify_p0_2.sh' ':!apps/business-api/tests/test_no_default_role.py' ':!docs/versions/version_84.md' | no_comments | sed 's/^/        /'
else
  ok  "1  BUSINESS_API_DEFAULT_ROLE absent from the repo"
fi

if git grep -n "X-Role\|x_role" -- deploy/ infra/ .github/ | no_comments; then
  bad "2  a role header is still set in deploy/infra/CI:"
  git grep -n "X-Role\|x_role" -- deploy/ infra/ .github/ | no_comments | sed 's/^/        /'
else
  ok  "2  no role header set anywhere in deploy/, infra/ or .github/"
fi

if git grep -n "adminEmail\|adminPassword\|adminRole" -- Frontend/ | no_comments; then
  bad "3  dead admin credential/role config still present:"
  git grep -n "adminEmail\|adminPassword\|adminRole" -- Frontend/ | no_comments | sed 's/^/        /'
else
  ok  "3  admin frontend holds no credential or role config"
fi

if [ -f Frontend/customer_portal/.env.example ]; then
  ok  "4  Frontend/customer_portal/.env.example exists"
else
  bad "4  Frontend/customer_portal/.env.example is missing"
fi

if grep -q "PORTAL_SESSION_SECRET" Frontend/customer_portal/.env.example 2>/dev/null; then
  ok  "5  the portal template documents PORTAL_SESSION_SECRET"
else
  bad "5  the portal template does not mention PORTAL_SESSION_SECRET"
fi

# --- live: fail-closed is still fail-closed ---------------------------------
echo "live re-proof against ${API}"

code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

c=$(code "${API}/health")
[ "$c" = "200" ] && ok "6  /health 200 (the API is actually up)" \
                 || bad "6  /health returned ${c} — the API is down; later cases are meaningless"

c=$(code "${API}/api/v1/customers")
[ "$c" = "401" ] && ok "7  anonymous /customers 401" || bad "7  anonymous /customers returned ${c}, expected 401"

c=$(code -H 'X-Role: administrateur' "${API}/api/v1/customers")
[ "$c" = "401" ] && ok "8  forged X-Role: administrateur 401" || bad "8  forged X-Role returned ${c}, expected 401"

c=$(code -X POST -H 'X-Role: administrateur' "${API}/api/v1/jobs/retention")
[ "$c" = "401" ] && ok "9  forged X-Role on an admin-gated route 401" || bad "9  returned ${c}, expected 401"

printf '\n  %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]