#!/usr/bin/env bash
#
# verify_p0_1.sh — end-to-end proof for the P0-1 "Real authentication" patch.
#
# Every check is OUTBOUND only: we curl the running business-api exactly like a client would.
# No internal DB/container access, no poking at tables. The container already proves those
# facts in the introspected assertions; this script proves the wire behaviour.
#
# Usage:  bash scripts/verify_p0_1.sh
# Exit:   0 = all cases passed; 1 = any case failed (first failure aborts).

set -uo pipefail

# ------------------------------------------------ config -------------------

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

api="${API:-http://localhost:8108}"

getenv() { grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | sed -E 's/[[:space:]]+#.*$//; s/[[:space:]]+$//' ; }

internal_key="$(getenv INTERNAL_API_KEY)"
machine_key="${internal_key}" # the on-call/machine flows authenticate with the shared INSTANCE key
admin_email="$(getenv ADMIN_EMAIL)"
admin_password="$(getenv ADMIN_PASSWORD)"

if [[ -z "$internal_key" || -z "$admin_email" || -z "$admin_password" ]]; then
  echo "FAIL: INTERNAL_API_KEY / ADMIN_EMAIL / ADMIN_PASSWORD must be set in $ENV_FILE" >&2
  exit 1
fi

pass=0; fail=0

report() { # report <name> <expect> <got>
  local name="$1" expect="$2" got="$3"
  if [[ "$got" == "$expect" ]]; then
    echo "  ok    $name (HTTP $got)"
    pass=$((pass + 1))
  else
    echo "  FAIL  $name : expected HTTP $expect, got ${got:-?}" >&2
    fail=$((fail + 1))
  fi
}

code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
body()  { curl -s "$@"; }

echo "== P0-1 real-authentication wire proof (API=$api) =="

# 1. Service is up
c=$(code "$api/health"); report "health responds" 200 "$c"

# 2. Anonymous must not reach customer data
c=$(code "$api/api/v1/customers"); report "no token -> /customers 401" 401 "$c"

# 3. A forged role header must NOT grant access (legacy spoofing is dead)
c=$(code -H "X-Role: administrateur" "$api/api/v1/customers"); report "forged X-Role -> 401" 401 "$c"

# 3b. §19 proof 4: anonymous must not reach the retain/purge job either
c=$(code -X POST "$api/api/v1/jobs/retention"); report "no token -> retention 401" 401 "$c"

# 4. Machine identity (INTERNAL_API_KEY) CAN read conseiller data
c=$(code -H "X-API-Key: $internal_key" "$api/api/v1/advisors/on-call"); report "machine key conseiller 200" 200 "$c"

# 4b. §19 proof 14: the 403 body is byte-identical to pre-P0-1 contract
m403="$(body -H "X-API-Key: $internal_key" "$api/api/v1/tickets")"
if [[ "$m403" == '{"detail":"requires role >= superviseur"}' ]]; then
  echo "  PASS 403 body byte-identical (detail string)"; pass=$((pass + 1))
else
  echo "  FAIL 403 body = '$m403'" >&2; fail=$((fail + 1))
fi

# 5. but must NOT lift a superviseur gate
c=$(code -H "X-API-Key: $internal_key" "$api/api/v1/tickets"); report "machine key tickets 403 (superviseur)" 403 "$c"

# 6. A wrong machine key is rejected
c=$(code -H "X-API-Key: wrong-key-0000000000000000" "$api/api/v1/advisors/on-call"); report "wrong machine key 401" 401 "$c"

# 7. Staff login issues a token
login_body="{\"email\":\"$admin_email\",\"password\":\"$admin_password\"}"
login_json="$(body -s -X POST -H "Content-Type: application/json" -d "$login_body" "$api/api/v1/auth/login")"
tok="$(printf '%s' "$login_json" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p' || true)"
if [[ -z "$tok" ]]; then
  echo "  FAIL 7 login token extraction"; fail=$((fail + 1))
else
  echo "  PASS login issues token (${#tok} chars)"; pass=$((pass + 1))
fi

# 8. The bearer token reaches customer data
c=$(code -H "Authorization: Bearer $tok" "$api/api/v1/customers"); report "token -> /customers 200" 200 "$c"

# 8b. §19 proof 6: a wrong password must not grant
bad_code="$(code -X POST -H "Content-Type: application/json" -d "{\"email\":\"$admin_email\",\"password\":\"wrong-password-0000\"}" "$api/api/v1/auth/login")"
report "wrong password -> login 401" 401 "$bad_code"

# 9. The token also survives a role-gated (administrateur) endpoint
c=$(code -H "Authorization: Bearer $tok" "$api/api/v1/jobs/integrity"); report "token -> /jobs/integrity 200" 200 "$c"

# 10. /auth/me reflects the identity derived from the token
me="$(body -H "Authorization: Bearer $tok" "$api/api/v1/auth/me")"
if [[ "$me" == *'"kind":"staff"'* && "$me" == *'"customer_id":null'* ]]; then
  echo "  PASS /auth/me identity payload"; pass=$((pass + 1))
else
  echo "  FAIL /auth/me : got $me" >&2; fail=$((fail + 1))
fi

# 11. Logout revokes the token
c=$(code -X POST -H "Authorization: Bearer $tok" -H "Content-Type: application/json" -d '{}' "$api/api/v1/auth/logout"); report "logout 200" 200 "$c"

# 12. Reusing the token after logout is rejected
c=$(code -H "Authorization: Bearer $tok" "$api/api/v1/customers"); report "revoked token -> 401" 401 "$c"

# 13. CORS: a browser origin may preflight against the backend
c=$(code -X OPTIONS -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: GET" "$api/api/v1/customers"); report "CORS preflight 200" 200 "$c"

# 14. The CORS response echoes the allow-listed origin, not a wildcard
cors_a="$(${curl:-curl} -s -X OPTIONS -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: GET" -D - -o /dev/null "$api/api/v1/customers" | grep -i '^access-control-allow-origin:' | tr -d '\r' | awk '{print $2}')"
if [[ "$cors_a" == "http://localhost:5173" ]]; then
  echo "  PASS CORS allow-origin pinned to origin"; pass=$((pass + 1))
else
  echo "  FAIL CORS allow-origin = '$cors_a'" >&2; fail=$((fail + 1))
fi

# 14b. §19 proof 15: the preflight no longer advertises X-Role among allowed headers
cors_h="$(${curl:-curl} -s -X OPTIONS -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: GET" -D - -o /dev/null "$api/api/v1/customers" | tr -d '\r' | grep -i '^access-control-allow-headers:' | sed -E 's/^[^:]*:[[:space:]]*//I')"
if [[ "$cors_h" == *"X-Role"* ]]; then
  echo "  FAIL CORS allow-headers still lists X-Role: '$cors_h'" >&2; fail=$((fail + 1))
else
  echo "  PASS CORS allow-headers has no X-Role ($cors_h)"; pass=$((pass + 1))
fi

# 15. Final gate: no X-Role read/sent remains in shipped runtime code.
#
# Allow-listed by construction (documented, intentional):
#   * docstrings in principal.py / security.py that STATE the header is dead;
#   * tests that forge an X-Role to prove it no longer grants access;
#   * supervisor-dashboard (out of scope for P0-1, separate static app);
#   * compiled/pycache artifacts of the above.
set +e
grep -rn --include='*.py' --include='*.ts' --include='*.tsx' --include='*.js' \
  --exclude-dir=__pycache__ --exclude-dir=node_modules --exclude-dir=.output \
  --exclude-dir=dist --exclude-dir=.git --exclude-dir=.wrangler \
  "X-Role" \
  "$REPO_ROOT/apps/business-api/src" "$REPO_ROOT/apps/agent-worker/src" \
  "$REPO_ROOT/packages" "$REPO_ROOT/Frontend/admin_dashboard/src" \
  "$REPO_ROOT/Frontend/customer_portal/src" 2>/dev/null \
  > "$REPO_ROOT/scripts/.xrole_leak.tmp"
set -e
leaks=0
while IFS= read -r line; do
  [ -z "$line" ] && continue
  _rest="${line#*:}"
  _text="${_rest#*:}"
  # Docstring/comment lines that only document the dead header are allowed.
  case "$_text" in
    *"NO LONGER READ"*) continue ;;
    *"not read anywhere"*) continue ;;
    *"no longer read"*) continue ;;
    *"not read in this file"*) continue ;;
    *"It is NO LONGER SENT"*) continue ;;
    *"no longer sets"*) continue ;;
    *"before P0-1"*) continue ;;
  esac
  # Tests legitimately send a forged X-Role to prove it grants nothing.
  case "$line" in
    *"/tests/"*) continue ;;
  esac
  echo "  FAIL X-Role in $line" >&2
  leaks=$((leaks + 1))
done < "$REPO_ROOT/scripts/.xrole_leak.tmp"
rm -f "$REPO_ROOT/scripts/.xrole_leak.tmp"
if [[ $leaks -eq 0 ]]; then
  echo "  PASS no live X-Role in product code (docstrings/tests only)"
  pass=$((pass + 1))
else
  fail=$((fail + leaks))
fi

# ---------------------------------------------------------------------------
# Case 20 - INTERNAL_API_KEY UNSET must still fail closed (reviewer addition).
#
# P0-1 changed the meaning of X-API-Key: on match it now mints a conseiller
# principal. If an unconfigured deploy left the key unset AND an empty/forged
# header compared empty-to-empty and succeeded, anyone reaching the published
# :8108 port would get conseiller. Prove the unset path returns 401 for both an
# empty and an arbitrary X-API-Key, with a live login as a positive control so a
# dead probe cannot produce a false green. Runs a throwaway copy of the image
# with the key forced empty on a scratch host port, then removes it.
#
# Only runs when docker is reachable (it is for the compose stack this script
# verifies); otherwise reported as SKIP so the gate degrades, never lies.
if command -v docker >/dev/null 2>&1; then
  probe_ctr="verify-p0-1-key-unset"
  probe_port="8199"
  probe_img="docker-compose-business-api:latest"
  probe_net="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' docker-compose-business-api-1 2>/dev/null | tr ' ' '\n' | sed '/^$/d' | head -1)"

  if [[ -z "$probe_net" ]]; then
    echo "  SKIP case 20: compose network not resolvable" >&2
  else
    docker rm -f "$probe_ctr" >/dev/null 2>&1 || true
    cid="$(docker run -d --name "$probe_ctr" --network "$probe_net" \
      -p "$probe_port:8108" \
      --env-file "$ENV_FILE" \
      -e "INTERNAL_API_KEY=" \
      -e "CORS_ORIGINS=http://localhost:5173,http://localhost:5174" \
      -e "DATABASE_URL=postgresql+psycopg://telecom:telecom@postgres:5432/telecom" \
      "$probe_img" 2>/dev/null)"
    if [[ -z "$cid" ]]; then
      echo "  FAIL case 20: probe container could not start" >&2
      fail=$((fail + 1))
    else
      # Wait for the probe to become healthy, then check it directly.
      probe_ready=""
      for _ in $(seq 1 30); do
        sleep 2
        probe_ready="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$probe_port/health" 2>/dev/null)"
        [[ "$probe_ready" == "200" ]] && break
      done
      if [[ "$probe_ready" != "200" ]]; then
        echo "  FAIL case 20: probe never became healthy" >&2
        fail=$((fail + 1))
      else
        e1="$(code -H "X-API-Key: " "http://localhost:$probe_port/api/v1/advisors/on-call")"
        e2="$(code -H "X-API-Key: anything" "http://localhost:$probe_port/api/v1/advisors/on-call")"
        # positive control: a real login must still succeed on the probe
        pc_json="{\"email\":\"$admin_email\",\"password\":\"$admin_password\"}"
        pc="$(code -X POST -H "Content-Type: application/json" -d "$pc_json" "http://localhost:$probe_port/api/v1/auth/login")"
        if [[ "$e1" == "401" && "$e2" == "401" && "$pc" == "200" ]]; then
          echo "  PASS unset key: X-API-Key:'' 401, X-API-Key:anything 401 (login positive control $pc)"
          pass=$((pass + 1))
        else
          echo "  FAIL case 20: unset key -> empty=$e1 anything=$e2 (want 401/401), login control=$pc (want 200)" >&2
          fail=$((fail + 1))
        fi
      fi
      docker rm -f "$probe_ctr" >/dev/null 2>&1 || true
    fi
  fi
else
  echo "  SKIP case 20: docker unavailable" >&2
fi

echo
echo "== result: $pass passed, $fail failed =="
[[ $fail -eq 0 ]]
