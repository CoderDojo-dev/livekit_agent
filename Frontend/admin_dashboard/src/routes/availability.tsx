import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { CalendarClock } from "lucide-react";
import { PageSection } from "@/components/nexus/app-topbar";
import { Card, CardHeader, EmptyState, Segmented, Token } from "@/components/nexus/primitives";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { getCoverage } from "@/lib/api/availability.server";
import type { CoverageReport } from "@/lib/api/availability.server";
import { availabilityKeys } from "@/lib/nexus/query-keys";
import { coverageMatrix, coverageTone } from "@/lib/nexus/availability-view";
import { pageTitle } from "@/lib/nexus/brand";

export const Route = createFileRoute("/availability")({
  head: () => ({
    meta: [
      { title: pageTitle("Availability") },
      {
        name: "description",
        content: "Hour-by-hour advisor coverage, gaps and language gaps.",
      },
      { property: "og:title", content: pageTitle("Availability") },
      { property: "og:description", content: "Where the rota is thin." },
    ],
  }),
  component: AvailabilityPage,
});

const RANGES = [
  { id: "7", label: "7 days" },
  { id: "14", label: "14 days" },
  { id: "30", label: "30 days" },
];

function AvailabilityPage() {
  const [range, setRange] = useState("7");
  const days = Number(range);

  const query = useQuery({
    queryKey: availabilityKeys.coverage(days),
    queryFn: () => getCoverage({ data: { days } }),
  });

  return (
    <PageSection index={0}>
      <Card>
        <CardHeader
          title="Coverage"
          subtitle={
            query.data
              ? `${query.data.advisors_total} advisors in the escalation rota · times in ${query.data.timezone}`
              : "Hour-by-hour staffing across the booking horizon."
          }
          action={
            <Segmented
              groupId="availability-range"
              items={RANGES.map((r) => r.label)}
              active={RANGES.find((r) => r.id === range)!.label}
              onSelect={(label) => setRange(RANGES.find((r) => r.label === label)!.id)}
            />
          }
        />

        <div className="mt-sp-7">
          {query.isPending ? <CardSkeleton /> : null}

          {query.isError ? (
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          ) : null}

          {query.data && query.data.advisors_total === 0 ? (
            <EmptyState
              icon={CalendarClock}
              title="No advisors in the rota"
              description="Coverage counts only advisors with Rota enabled. Turn Rota on for at least one active advisor in the Advisors page, then give them a weekly schedule."
            />
          ) : null}

          {query.data && query.data.advisors_total > 0 ? (
            <CoverageGrid report={query.data} />
          ) : null}
        </div>
      </Card>
    </PageSection>
  );
}

function CoverageGrid({ report }: { report: CoverageReport }) {
  const { hourLabels, days, peak } = coverageMatrix(report.hours);

  if (days.length === 0) {
    return (
      <EmptyState
        icon={CalendarClock}
        title="Nothing to show for this window"
        description="The coverage report only reports hours inside the configured business day."
      />
    );
  }

  return (
    <div>
      {/*
       * Two axes, two containments.
       *
       * Horizontal: the hour columns have always scrolled. Vertical is new — at 14 or 30 days the
       * grid grew a row per day and pushed the legend, the uncovered-hours list and the language
       * gaps off the bottom of the page, so choosing a longer window made the summary you were
       * reaching for HARDER to see. Seven rows stay visible whatever the range; the rest scroll
       * within the grid, and everything below it stays put.
       *
       * The header row is sticky so the hour labels remain readable while scrolling days.
       */}
      <div className="max-h-[336px] overflow-auto overscroll-contain rounded-r-2 border border-stroke-subtle">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 z-10 bg-surface-2">
            <tr>
              <th className="sticky left-0 z-20 h-[38px] border-b border-stroke-subtle bg-surface-2 px-sp-5 text-left t-micro font-medium text-ink-5">
                Day
              </th>
              {hourLabels.map((hh) => (
                <th
                  key={hh}
                  className="h-[38px] border-b border-stroke-subtle px-sp-2 t-micro font-medium text-ink-5"
                >
                  {hh.slice(0, 2)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {days.map((day) => (
              <tr key={day.date}>
                <td className="sticky left-0 z-10 h-[40px] whitespace-nowrap border-b border-stroke-subtle bg-surface-2 px-sp-5 t-ui text-ink-2">
                  {day.label}
                </td>
                {day.cells.map((cell, index) => (
                  <td
                    key={`${day.date}-${hourLabels[index]}`}
                    className="h-[40px] border-b border-stroke-subtle px-sp-2"
                  >
                    {cell ? (
                      <span
                        title={`${cell.local} · ${cell.advisors} advisor${cell.advisors === 1 ? "" : "s"}${
                          cell.languages.length ? ` · ${cell.languages.join(", ")}` : ""
                        }`}
                        className={`block h-[22px] w-full rounded-r-1 transition-[transform,opacity] duration-[120ms] hover:scale-y-110 hover:opacity-80 ${coverageTone(cell.advisors, peak)}`}
                        aria-label={`${cell.local}: ${cell.advisors} advisors`}
                      />
                    ) : (
                      <span className="block h-[22px] w-full" aria-hidden="true" />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-sp-6 flex flex-wrap items-center gap-sp-6 border-t border-stroke-subtle pt-sp-5">
        <span className="inline-flex items-center gap-sp-3">
          <span className="block h-[10px] w-[16px] rounded-r-1 border border-dashed border-stroke-strong" />
          <span className="t-caption text-ink-4">No cover</span>
        </span>
        <span className="inline-flex items-center gap-sp-3">
          <span className="block h-[10px] w-[16px] rounded-r-1 border border-n-8 bg-n-8/15" />
          <span className="t-caption text-ink-4">Thin</span>
        </span>
        <span className="inline-flex items-center gap-sp-3">
          <span className="block h-[10px] w-[16px] rounded-r-1 border border-n-9 bg-n-9/45" />
          <span className="t-caption text-ink-4">Steady</span>
        </span>
        <span className="inline-flex items-center gap-sp-3">
          <span className="block h-[10px] w-[16px] rounded-r-1 border border-n-11 bg-n-11/85" />
          <span className="t-caption text-ink-4">Peak ({peak})</span>
        </span>
      </div>

      <div className="mt-sp-7 grid gap-sp-6 md:grid-cols-2">
        <div>
          <p className="t-micro mb-sp-4 text-ink-5">Uncovered hours</p>
          {report.uncovered_hours.length === 0 ? (
            <p className="t-caption text-ink-4">Every business hour has at least one advisor.</p>
          ) : (
            <div className="flex flex-wrap gap-sp-3">
              {report.uncovered_hours.slice(0, 40).map((hour) => (
                <Token key={hour}>{hour}</Token>
              ))}
              {report.uncovered_hours.length > 40 ? (
                <span className="t-caption text-ink-4">
                  +{report.uncovered_hours.length - 40} more
                </span>
              ) : null}
            </div>
          )}
        </div>

        <div>
          <p className="t-micro mb-sp-4 text-ink-5">Gaps by language</p>
          {report.languages.length === 0 ? (
            <p className="t-caption text-ink-4">No languages declared on rota advisors.</p>
          ) : (
            <div className="flex flex-col gap-sp-3">
              {report.languages.map((language) => {
                const gaps = report.uncovered_by_language[language] ?? [];
                return (
                  <span key={language} className="flex items-center justify-between gap-sp-5">
                    <Token strong>{language}</Token>
                    <span className="t-caption text-ink-4">
                      {gaps.length === 0
                        ? "fully covered"
                        : `${gaps.length} uncovered hour${gaps.length === 1 ? "" : "s"}`}
                    </span>
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
