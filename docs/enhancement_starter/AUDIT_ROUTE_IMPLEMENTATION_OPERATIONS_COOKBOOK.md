# Audit Route Implementation and Operations Cookbook

## Decision

Audit is a dedicated administrator-only /audit destination. The append-only cursor-paginated ledger, integrity checks, and retention jobs are operational controls rather than personal settings. Existing backend contracts, administrator RBAC, and an audit-specific query namespace support this split.

## Information architecture

- /settings contains password change and sign-out-all-sessions for every authenticated user.
- /audit contains chain verification, referential integrity, retention preview and purge, and ledger browsing for administrators.
- Audit appears once under Insights. Audit panels were removed from Settings, preventing duplicated or dead UI.
- Existing /settings deep links remain valid for account security; /audit is the canonical audit deep link.

## Migration and component reuse

The existing audit panels moved to src/routes/audit.tsx. RetentionPanel remains reused rather than copied. Server adapters, wire types, view helpers, and auditKeys.entries(eventType) are unchanged. Generated route-tree files are not edited manually; the supported Vite and TanStack build discovers the route file.

## Route and RBAC

Protection has three layers: navigation metadata requires administrateur; route beforeLoad redirects lower roles to Settings; and the real security boundary remains server-side. Every audit server function uses authedMiddleware plus requireRole(administrateur), while business-api independently requires AdministrateurRole. Unauthenticated users are redirected to Login by the root route. Navigation hiding and redirects are UX gates, not authorization substitutes.

## APIs and backend contracts

- GET /api/v1/audit/entries returns newest-first entries with limit 50, optional before_seq and exact event_type, plus has_more and next_before_seq.
- GET /api/v1/audit/verify recomputes the full chain and returns intact and entries. It runs only on user request.
- GET /api/v1/jobs/integrity returns orphan counts and audit-chain state.
- POST /api/v1/jobs/retention accepts retention_days and dry_run query parameters. The UI requires a current preview before purge.
No backend behavior or contract changed.

## Pagination and cache behavior

Ledger paging uses decreasing sequence cursors instead of offsets. next_before_seq becomes the next before_seq, avoiding drift as rows are appended. The exact event filter is part of auditKeys.entries(eventType), so each filter has an isolated cache and page chain. Verification, integrity, and retention remain uncached mutations. The table distinguishes loading, initial error, empty, and loaded states; supports retry; reports loaded rows; disables Load older without a cursor; and reports link mismatch only when the adjacent older row is loaded.

## Accessibility and truthful states

The semantic primary navigation exposes aria-current. Pending actions have disabled controls and progress labels. Not-run, success, broken-chain, empty, and error states remain distinct. Retention requires a same-window preview and typed session-count confirmation; changing days invalidates the preview. Settings now truthfully presents only account security.

## Testing and acceptance

Automated tests assert a single Audit destination and visibility for administrator versus supervisor and anonymous sessions. Backend tests were not required because backend behavior did not change and existing authorization tests cover forbidden lower roles.

Run from Frontend/admin_dashboard:

1. npm run typecheck
2. npm test
3. npm run lint
4. npm run build

Manual acceptance: administrator sees one Audit link and all operational panels; ledger filtering and cursor paging work; integrity states remain truthful; changing retention days relocks purge; lower roles do not see Audit and a direct deep link returns to Settings; Settings still changes passwords and revokes sessions.

## Deployment

Deploy the frontend normally. No schema, environment, or backend migration is required. The production build performs supported route generation. Smoke-test Settings, administrator Audit, and a lower-role Audit deep link. Monitor frontend errors and business-api 401, 403, and 5xx rates for audit endpoints.

## Rollback

Revert the Audit route, navigation metadata and test, and restore the panels to Settings. Keep adapters and contracts unchanged. Rebuild to regenerate routing. Rollback is frontend-only. If Audit bookmarks must survive rollback, add an application redirect rather than editing generated route files.

## Troubleshooting

- Audit missing: verify the signed session role is administrateur and refresh the session.
- Unexpected redirect: inspect session expiry and role; the gate fails closed.
- 403: verify frontend and backend bearer sessions; client role headers are not trusted.
- Repeated or skipped pages: verify decreasing next_before_seq and outgoing before_seq.
- Empty filter: backend event_type matching is exact.
- Slow checks: verify and integrity can scan the complete chain and run only on demand.
- Purge disabled: obtain a successful preview for the unchanged day value; zero matches cannot purge.
- Missing route type: run npm run build and never edit routeTree.gen.ts.

## Changed files

- Frontend/admin_dashboard/src/routes/audit.tsx
- Frontend/admin_dashboard/src/routes/settings.tsx
- Frontend/admin_dashboard/src/lib/nexus/nav.ts
- Frontend/admin_dashboard/src/components/nexus/app-sidebar.tsx
- Frontend/admin_dashboard/src/lib/nexus/nav.test.ts
- docs/AUDIT_ROUTE_IMPLEMENTATION_OPERATIONS_COOKBOOK.md
