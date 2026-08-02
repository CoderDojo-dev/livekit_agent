import { createFileRoute } from "@tanstack/react-router";
import { Plus, Filter } from "lucide-react";
import {
  Avatar,
  Button,
  Checkbox,
  SearchInput,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { HeroStat, StatCard } from "@/components/nexus/blocks";
import { PageSection } from "@/components/nexus/app-topbar";
import { CUSTOMER_STATS, CUSTOMERS } from "@/lib/nexus/data";
import { initials } from "@/lib/nexus/format";

export const Route = createFileRoute("/customers")({
  head: () => ({
    meta: [
      { title: "Users Management — Nexus" },
      {
        name: "description",
        content: "Every account, role, invitation and access level in one monochrome table.",
      },
      { property: "og:title", content: "Users Management — Nexus" },
      { property: "og:description", content: "Manage accounts, roles and access levels." },
    ],
  }),
  component: CustomersPage,
});

function CustomersPage() {
  const { hero, cards } = CUSTOMER_STATS;

  return (
    <>
      <PageSection className="grid gap-sp-6 xl:grid-cols-4">
        <HeroStat label={hero.label} value={hero.value} delta={hero.delta} context={hero.context} />
        {cards.map((c) => (
          <StatCard key={c.label} {...c} />
        ))}
      </PageSection>

      <PageSection>
        <TableShell
          toolbar={
            <>
              <SearchInput placeholder="Search users" className="w-[260px]" />
              <Button icon={Filter} size="sm">
                Filters
              </Button>
              <Button icon={Plus} size="sm" variant="primary" className="ml-auto">
                Invite user
              </Button>
            </>
          }
          head={
            <tr>
              <Th className="w-[44px]">
                <Checkbox label="Select all users" />
              </Th>
              <Th>User</Th>
              <Th>Status</Th>
              <Th>Role</Th>
              <Th align="right">Last active</Th>
            </tr>
          }
          footer={
            <>
              <span className="t-caption text-ink-4">
                Showing {CUSTOMERS.length} of 18,204 users
              </span>
              <div className="flex gap-sp-4">
                <Button size="sm">Previous</Button>
                <Button size="sm">Next</Button>
              </div>
            </>
          }
        >
          {CUSTOMERS.map((c) => (
            <tr key={c.email} className="transition-colors duration-[120ms] hover:bg-surface-3">
              <Td>
                <Checkbox label={`Select ${c.name}`} />
              </Td>
              <Td>
                <span className="flex items-center gap-sp-5">
                  <Avatar initials={initials(c.name)} name={c.name} />
                  <span className="min-w-0">
                    <span className="t-ui block truncate text-ink-1">{c.name}</span>
                    <span className="t-caption block truncate text-ink-4">{c.email}</span>
                  </span>
                </span>
              </Td>
              <Td>
                <StatusChip status={c.status} />
              </Td>
              <Td>
                <Token mono={false}>{c.role}</Token>
              </Td>
              <Td align="right">
                <span className="t-mono text-ink-3">{c.lastActive}</span>
              </Td>
            </tr>
          ))}
        </TableShell>
      </PageSection>
    </>
  );
}
