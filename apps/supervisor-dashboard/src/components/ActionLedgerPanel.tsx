import { useMemo, useState } from "react";
import {
  Button,
  ContentSwitcher,
  DataTable,
  DataTableSkeleton,
  Pagination,
  Switch,
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
} from "@carbon/react";
import { ArrowRight } from "@carbon/icons-react";
import { api } from "../api";
import { usePoll } from "../refresh";
import { ErrorBanner, PageHeader, StatusTag } from "./shared";
const STATUSES = ["failed", "succeeded", "pending"] as const;
type ActionStatus = (typeof STATUSES)[number];
const HEADERS = [
  { key: "action_type", header: "Action type" },
  { key: "status", header: "Status" },
  { key: "idempotency_key", header: "Idempotency key" },
  { key: "reference", header: "Adapter reference" },
  { key: "inspect", header: "" },
];
export function ActionLedgerPanel({
  onInspectSession,
}: {
  onInspectSession: (id: string) => void;
}) {
  const [status, setStatus] = useState<ActionStatus>("failed");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const { data, error, loading } = usePoll(() => api.actions(status), [status]);
  const allRows = useMemo(
    () =>
      (data?.actions ?? []).map((a) => ({
        id: a.id,
        action_type: a.action_type,
        status: a.status,
        idempotency_key: a.idempotency_key,
        reference: a.reference ?? "—",
        inspect: a.id,
      })),
    [data]
  );
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return allRows;
    return allRows.filter((r) =>
      [r.action_type, r.status, r.idempotency_key, r.reference].some((v) =>
        v.toLowerCase().includes(q)
      )
    );
  }, [allRows, search]);
  const paged = useMemo(
    () => filtered.slice((page - 1) * pageSize, page * pageSize),
    [filtered, page, pageSize]
  );
  const switcher = (
    <ContentSwitcher
      size="sm"
      selectedIndex={STATUSES.indexOf(status)}
      onChange={({ name }) => {
        setStatus(name as ActionStatus);
        setPage(1);
      }}
    >
      <Switch name="failed" text="Failed" />
      <Switch name="succeeded" text="Succeeded" />
      <Switch name="pending" text="Pending" />
    </ContentSwitcher>
  );
  if (error) {
    return (
      <>
        <PageHeader title="Action ledger" actions={switcher} />
        <ErrorBanner title="Failed to query action ledger" error={error} />
      </>
    );
  }
  if (loading && !data) {
    return (
      <>
        <PageHeader
          title="Action ledger"
          subtitle="Idempotent sensitive operations (EXECUTE_PAYMENT, UNBLOCK_SIM, PAYMENT_DEFERRAL) gated by policy-service"
          actions={switcher}
        />
        <DataTableSkeleton columnCount={5} rowCount={6} showHeader={false} showToolbar />
      </>
    );
  }
  return (
    <>
      <PageHeader
        title="Action ledger"
        subtitle="Idempotent sensitive operations (EXECUTE_PAYMENT, UNBLOCK_SIM, PAYMENT_DEFERRAL) gated by policy-service"
        actions={switcher}
      />
      <DataTable rows={paged} headers={HEADERS} isSortable>
        {({ rows, headers, getHeaderProps, getRowProps, getTableProps, getToolbarProps }) => (
          <TableContainer>
            <TableToolbar {...getToolbarProps()}>
              <TableToolbarContent>
                <TableToolbarSearch
                  persistent
                  placeholder="Filter by action type, key, reference…"
                  onChange={(_e, value) => {
                    setSearch(value ?? "");
                    setPage(1);
                  }}
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
                {rows.map((row) => (
                  <TableRow {...getRowProps({ row })} key={row.id}>
                    {row.cells.map((cell) => (
                      <TableCell key={cell.id}>
                        {cell.info.header === "status" ? (
                          <StatusTag status={String(cell.value)} />
                        ) : cell.info.header === "inspect" ? (
                          <Button
                            kind="ghost"
                            size="sm"
                            renderIcon={ArrowRight}
                            onClick={() => onInspectSession(String(cell.value))}
                          >
                            Trace
                          </Button>
                        ) : cell.info.header === "action_type" ? (
                          <strong className="mono">{cell.value}</strong>
                        ) : (
                          <span className="mono">{cell.value}</span>
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
      {filtered.length === 0 ? (
        <div className="table-empty">No {status} actions match the current filter.</div>
      ) : (
        <Pagination
          page={page}
          pageSize={pageSize}
          pageSizes={[10, 25, 50]}
          totalItems={filtered.length}
          onChange={({ page: p, pageSize: ps }) => {
            setPage(p);
            setPageSize(ps);
          }}
        />
      )}
    </>
  );
}
