import { useMemo, useState } from "react";
import {
  DataTable,
  DataTableSkeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TableToolbar,
  TableToolbarContent,
  TableToolbarSearch,
  Tag,
} from "@carbon/react";
import { api } from "../api";
import { usePoll } from "../refresh";
import { ErrorBanner, PageHeader, StatusTag } from "./shared";
const HEADERS = [
  { key: "rule_id", header: "Rule ID" },
  { key: "domain", header: "Domain" },
  { key: "version", header: "Version" },
  { key: "active", header: "Status" },
  { key: "thresholds", header: "Thresholds (enforced)" },
  { key: "description", header: "Description" },
];

function formatThresholds(rule: { definition?: Record<string, unknown>; enforced?: boolean }): string {
  const def = rule.definition;
  if (rule.enforced && def) {
    const pairs = Object.entries(def).map(([k, v]) => `${k}: ${v}`);
    return pairs.length ? pairs.join(" · ") : "—";
  }
  return "—";
}
export function BusinessRuleRegistry() {
  const [search, setSearch] = useState("");
  const { data, error, loading } = usePoll(api.businessRules);
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (data?.rules ?? [])
      .filter(
        (r) =>
          !q ||
          r.rule_id.toLowerCase().includes(q) ||
          r.domain.toLowerCase().includes(q) ||
          r.description.toLowerCase().includes(q)
      )
      .map((r) => ({
        id: `${r.domain}-${r.rule_id}`,
        rule_id: r.rule_id,
        domain: r.domain,
        version: `v${r.version}`,
        active: r.active ? "active" : "inactive",
        thresholds: formatThresholds(r),
        description: r.description,
      }));
  }, [data, search]);
  if (error) {
    return (
      <>
        <PageHeader title="Policy rules" />
        <ErrorBanner title="Failed to query the business rule registry" error={error} />
      </>
    );
  }
  if (loading && !data) {
    return (
      <>
        <PageHeader
          title="Policy rules"
          subtitle="Versioned deterministic rules (SENSITIVE_ACTIONS, MANDATORY_ESCALATION, OUTBOUND_GUARDRAILS) evaluated before every action"
        />
        <DataTableSkeleton columnCount={6} rowCount={8} showHeader={false} showToolbar />
      </>
    );
  }
  return (
    <>
      <PageHeader
        title="Policy rules"
        subtitle="Versioned deterministic rules (SENSITIVE_ACTIONS, MANDATORY_ESCALATION, OUTBOUND_GUARDRAILS) evaluated before every action"
      />
      <DataTable rows={rows} headers={HEADERS} isSortable>
        {({ rows: tableRows, headers, getHeaderProps, getRowProps, getTableProps, getToolbarProps }) => (
          <TableContainer>
            <TableToolbar {...getToolbarProps()}>
              <TableToolbarContent>
                <TableToolbarSearch
                  persistent
                  placeholder="Filter by rule ID, domain or description…"
                  onChange={(_e, value) => setSearch(value ?? "")}
                />
              </TableToolbarContent>
            </TableToolbar>
            <Table {...getTableProps()} size="lg">
              <TableHead>
                <TableRow>
                  {headers.map((header) => (
                    <TableHeader {...getHeaderProps({ header })} key={header.key}>
                      {header.header}
                    </TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {tableRows.map((row) => (
                  <TableRow {...getRowProps({ row })} key={row.id}>
                    {row.cells.map((cell) => (
                      <TableCell key={cell.id}>
                        {cell.info.header === "rule_id" ? (
                          <strong className="mono">{cell.value}</strong>
                        ) : cell.info.header === "domain" ? (
                          <Tag size="sm" type="blue">
                            {cell.value}
                          </Tag>
                        ) : cell.info.header === "active" ? (
                          <StatusTag status={String(cell.value)} />
                        ) : cell.info.header === "version" ? (
                          <span className="mono">{cell.value}</span>
                        ) : cell.info.header === "thresholds" ? (
                          <span className="mono" title="Live values read from the policy engine (POLICY_* env)">
                            {cell.value}
                          </span>
                        ) : (
                          cell.value
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DataTable>
      {rows.length === 0 && (
        <div className="table-empty">No rules match the current filter.</div>
      )}
    </>
  );
}
