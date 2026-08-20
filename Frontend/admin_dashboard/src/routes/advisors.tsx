import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Pencil, Plus, Power, Trash2, Users } from "lucide-react";
import {
  Avatar,
  Button,
  EmptyState,
  IconButton,
  SearchInput,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { Pager } from "@/components/nexus/pager";
import { TableBodySwap } from "@/components/nexus/motion";
import { clampPage, slicePage } from "@/lib/nexus/paginate";
import { useAdaptivePageSize, ROW_HEIGHT } from "@/hooks/use-adaptive-page-size";
import {
  AdvisorFormModal,
  DeleteAdvisorModal,
  type AdvisorFormValues,
} from "@/components/nexus/advisor-form";
import { ScheduleEditor } from "@/components/nexus/schedule-editor";
import {
  advisorContact,
  advisorLoad,
  advisorMatches,
  advisorStatusKey,
} from "@/lib/nexus/advisor-view";
import { initials } from "@/lib/nexus/format";
import {
  createAdvisor,
  deleteAdvisor,
  listAdvisors,
  updateAdvisor,
  type Advisor,
} from "@/lib/api/advisors.server";
import { queryKeys } from "@/lib/nexus/query-keys";
import { pageTitle } from "@/lib/nexus/brand";

const COLUMN_COUNT = 8;

export const Route = createFileRoute("/advisors")({
  head: () => ({
    meta: [
      { title: pageTitle("Advisors") },
      {
        name: "description",
        content: "Advisor registry: presence, skills, capacity and reachability.",
      },
      { property: "og:title", content: pageTitle("Advisors") },
      { property: "og:description", content: "Who is online, on call and away." },
    ],
  }),
  component: AdvisorsPage,
});

function AdvisorsPage() {
  const queryClient = useQueryClient();

  const [scope, setScope] = useState<"Active" | "All">("Active");
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Advisor | null>(null);
  const [deleting, setDeleting] = useState<Advisor | null>(null);
  const [scheduleFor, setScheduleFor] = useState<Advisor | null>(null);

  const includeInactive = scope === "All";

  const advisorsQuery = useQuery({
    queryKey: queryKeys.advisors.list(includeInactive),
    queryFn: () => listAdvisors({ data: { includeInactive } }),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: queryKeys.advisors.all,
    });

  const createMutation = useMutation({
    mutationFn: (values: AdvisorFormValues) => createAdvisor({ data: values }),
    onSuccess: async () => {
      await invalidate();
      setFormOpen(false);
      setEditing(null);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (input: { id: string } & Partial<AdvisorFormValues>) =>
      updateAdvisor({ data: input }),
    onSuccess: async () => {
      await invalidate();
      setFormOpen(false);
      setEditing(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAdvisor({ data: { id } }),
    onSuccess: async () => {
      await invalidate();
      setDeleting(null);
    },
  });

  const advisors = advisorsQuery.data ?? [];
  const [page, setPage] = useState(0);

  /* Advisor rows are single-line, so the registry fits more of them than a stacked table. */
  const pageSize = useAdaptivePageSize({
    rowHeight: ROW_HEIGHT.table,
    chrome: 400,
    min: 6,
    max: 16,
    fallback: 10,
  });

  const visible = useMemo(
    () => advisors.filter((advisor) => advisorMatches(advisor, search)),
    [advisors, search],
  );

  useEffect(() => setPage(0), [search, scope, pageSize]);
  const safePage = clampPage(page, visible.length, pageSize);
  const pageRows = slicePage(visible, safePage, pageSize);

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(advisor: Advisor) {
    setEditing(advisor);
    setFormOpen(true);
  }

  function submitForm(values: AdvisorFormValues) {
    if (editing) {
      updateMutation.mutate({ id: editing.id, ...values });
    } else {
      createMutation.mutate(values);
    }
  }

  function toggleActive(advisor: Advisor) {
    updateMutation.mutate({ id: advisor.id, is_active: !advisor.is_active });
  }

  const formError =
    (editing ? updateMutation.error : createMutation.error) instanceof Error
      ? ((editing ? updateMutation.error : createMutation.error) as Error).message
      : null;

  const deleteError = deleteMutation.error instanceof Error ? deleteMutation.error.message : null;

  return (
    <PageSection index={0}>
      <TableShell
        minWidth={1080}
        bodyAsChild
        busy={advisorsQuery.isFetching && !advisorsQuery.isPending}
        toolbar={
          <>
            <SearchInput
              placeholder="Search advisors"
              className="w-[260px]"
              value={search}
              onChange={setSearch}
            />
            <Segmented
              groupId="advisor-scope"
              items={["Active", "All"]}
              active={scope}
              onSelect={(value) => setScope(value as "Active" | "All")}
            />
            <span className="ml-auto">
              <Button variant="primary" icon={Plus} onClick={openCreate}>
                New advisor
              </Button>
            </span>
          </>
        }
        head={
          <tr>
            <Th>Advisor</Th>
            <Th>Skills</Th>
            <Th>Contact</Th>
            <Th>Lang</Th>
            <Th align="right">Load</Th>
            <Th>Rota</Th>
            <Th>Status</Th>
            <Th />
          </tr>
        }
        footer={
          <Pager
            page={safePage}
            pageSize={pageSize}
            total={visible.length}
            onPageChange={setPage}
            noun="advisors"
            busy={advisorsQuery.isFetching && !advisorsQuery.isPending}
            className="w-full"
          />
        }
      >
        <TableBodySwap pageKey={`${safePage}-${scope}`}>
          {advisorsQuery.isPending ? (
            <TableSkeleton columns={COLUMN_COUNT} rows={pageSize} />
          ) : advisorsQuery.isError ? (
            <TableErrorRow
              columns={COLUMN_COUNT}
              error={
                advisorsQuery.error instanceof Error
                  ? advisorsQuery.error.message
                  : "Could not load advisors."
              }
              onRetry={() => advisorsQuery.refetch()}
            />
          ) : visible.length === 0 ? (
            <tr>
              <td colSpan={COLUMN_COUNT}>
                <EmptyState
                  icon={Users}
                  title={search.trim() ? "No matching advisors" : "No advisors yet"}
                  description={
                    search.trim()
                      ? "No advisor matches this search. Clear it to see the full registry."
                      : "Register an advisor so escalated calls have somewhere to go."
                  }
                />
              </td>
            </tr>
          ) : (
            pageRows.map((advisor) => {
              const contact = advisorContact(advisor);
              return (
                <tr
                  key={advisor.id}
                  className="group transition-colors duration-[120ms] hover:bg-surface-3"
                >
                  <Td>
                    <span className="flex items-center gap-sp-5">
                      <Avatar initials={initials(advisor.full_name)} name={advisor.full_name} />
                      <span className="flex flex-col">
                        <span className="t-ui text-ink-1">{advisor.full_name}</span>
                        {advisor.email ? (
                          <span className="t-caption text-ink-4">{advisor.email}</span>
                        ) : null}
                      </span>
                    </span>
                  </Td>
                  <Td>
                    <span className="flex flex-wrap items-center gap-sp-2">
                      {advisor.skills.map((skill) => (
                        <Token key={skill} mono={false}>
                          {skill}
                        </Token>
                      ))}
                    </span>
                  </Td>
                  <Td>
                    {contact ? (
                      <span className="t-mono-s text-ink-3">{contact}</span>
                    ) : (
                      <span className="t-caption text-ink-5">—</span>
                    )}
                  </Td>
                  <Td>
                    <Token>{advisor.language}</Token>
                  </Td>
                  <Td align="right">
                    <span className="t-mono text-ink-3">{advisorLoad(advisor)}</span>
                  </Td>
                  <Td>
                    {advisor.is_on_call ? (
                      <Token mono={false}>Rota</Token>
                    ) : (
                      <span className="t-caption text-ink-5">—</span>
                    )}
                  </Td>
                  <Td>
                    <StatusChip status={advisorStatusKey(advisor)} />
                  </Td>
                  <Td align="right">
                    <span className="inline-flex items-center gap-sp-1 opacity-0 transition-opacity duration-[120ms] group-hover:opacity-100 focus-within:opacity-100">
                      <IconButton
                        label={`Schedule ${advisor.full_name}`}
                        icon={CalendarClock}
                        size="sm"
                        onClick={() => setScheduleFor(advisor)}
                      />
                      <IconButton
                        label={`Edit ${advisor.full_name}`}
                        icon={Pencil}
                        size="sm"
                        onClick={() => openEdit(advisor)}
                      />
                      <IconButton
                        label={
                          advisor.is_active
                            ? `Deactivate ${advisor.full_name}`
                            : `Activate ${advisor.full_name}`
                        }
                        icon={Power}
                        size="sm"
                        onClick={() => toggleActive(advisor)}
                      />
                      <IconButton
                        label={`Delete ${advisor.full_name}`}
                        icon={Trash2}
                        size="sm"
                        onClick={() => setDeleting(advisor)}
                      />
                    </span>
                  </Td>
                </tr>
              );
            })
          )}
        </TableBodySwap>
      </TableShell>

      <AdvisorFormModal
        open={formOpen}
        advisor={editing}
        pending={createMutation.isPending || updateMutation.isPending}
        serverError={formError}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
          createMutation.reset();
          updateMutation.reset();
        }}
        onSubmit={submitForm}
      />

      <DeleteAdvisorModal
        advisor={deleting}
        pending={deleteMutation.isPending}
        serverError={deleteError}
        onClose={() => {
          setDeleting(null);
          deleteMutation.reset();
        }}
        onConfirm={() => {
          if (deleting) deleteMutation.mutate(deleting.id);
        }}
      />

      {scheduleFor ? (
        <ScheduleEditor advisor={scheduleFor} onClose={() => setScheduleFor(null)} />
      ) : null}
    </PageSection>
  );
}
