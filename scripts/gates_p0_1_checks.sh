#!/usr/bin/env bash
# Gate checks 4, 5, 8, 9, 13 from §14.3. Run from repo root: bash scripts/gate_p0_1_checks.sh
set -u
echo "=== G4: src/lib/nexus/status.ts diff ==="
git diff -- Frontend/admin_dashboard/src/lib/nexus/status.ts 2>/dev/null
echo "(empty = clean)"
echo
echo "=== G5: no new npm dependency (package.json diffs) ==="
git diff HEAD --stat -- Frontend/admin_dashboard/package.json Frontend/customer_portal/package.json 2>/dev/null
echo "(empty = clean)"
echo
echo "=== G8: no rgb()/#hex in new UI files ==="
grep -rnE "rgb\(|#[0-9a-fA-F]{6}" \
  Frontend/customer_portal/src/lib/api \
  Frontend/customer_portal/src/routes/login.tsx \
  Frontend/customer_portal/src/routes/signup.tsx \
  Frontend/customer_portal/src/routes/_portal.tsx \
  Frontend/admin_dashboard/src/lib/api 2>/dev/null
echo "(empty = clean)"
echo
echo "=== G9: no date-math in new UI/route files ==="
grep -rnE "getDay\(|getHours\(|new Date\(|toLocaleString\(" \
  Frontend/customer_portal/src/routes/login.tsx \
  Frontend/customer_portal/src/routes/signup.tsx 2>/dev/null
echo "(empty = clean)"
echo
echo "=== G13: git grep X-Role (outside .env.example/docs/tests) ==="
git grep -n "X-Role" 2>/dev/null | grep -vE "\.env\.example|CHANGELOG|docs|/tests/|supervisor-dashboard" | grep -vE "NO LONGER READ|not read anywhere|no longer read|It is NO LONGER SENT|no longer sets|before P0-1"
echo "(empty = zero live hits)"
echo "DONE"