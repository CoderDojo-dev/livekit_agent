import { ChevronLeft, ChevronRight } from "lucide-react";
import { pageCount, pageTokens, rangeFor } from "@/lib/nexus/paginate";
import { formatInteger } from "@/lib/nexus/format";
import { cn } from "@/lib/utils";

/**
 * The one pagination control in the product.
 *
 * Replaces three different affordances that used to coexist: "Load more" (tickets, notifications,
 * calls), "Load older" (audit), and a bare Previous/Next pair (customers). Those all shared a
 * defect — the page grew without bound and scroll position stopped meaning anything.
 *
 * Built entirely from existing tokens: the button metrics are `Segmented`'s (h-[22px]/h-[28px],
 * rounded-r-1/r-2, t-label), the active fill is the inverted chip used by `Token strong` and
 * `Button variant="primary"`, and the bar itself is `TableShell`'s h-[52px] footer.
 *
 * Presentation only: it owns no data. The caller keeps the page index in local state and decides
 * whether that index slices an in-memory array or feeds an `offset` to a server call.
 */

function PageButton({
  children,
  active,
  disabled,
  label,
  onClick,
}: {
  children: React.ReactNode;
  active?: boolean | undefined;
  disabled?: boolean | undefined;
  label: string;
  onClick?: (() => void) | undefined;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-current={active ? "page" : undefined}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex h-[28px] min-w-[28px] items-center justify-center rounded-r-2 px-sp-3 t-label",
        "transition-[background-color,color,transform] duration-[120ms]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface-2",
        active
          ? "bg-n-12 text-n-0"
          : "text-ink-4 hover:bg-surface-4 hover:text-ink-1 active:translate-y-px",
        disabled && "pointer-events-none opacity-35",
      )}
    >
      {children}
    </button>
  );
}

export function Pager({
  page,
  pageSize,
  total,
  onPageChange,
  /** Plural noun for the readout, e.g. "tickets". Singular is derived by trimming a trailing "s". */
  noun = "rows",
  busy = false,
  className,
}: {
  /** Zero-based. */
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  noun?: string | undefined;
  /** Dims the control while a page is in flight, without collapsing its width. */
  busy?: boolean | undefined;
  className?: string | undefined;
}) {
  const pages = pageCount(total, pageSize);
  const range = rangeFor(page, pageSize, total);
  const tokens = pageTokens(page, pages);

  const readout =
    total === 0
      ? `No ${noun}`
      : `Showing ${formatInteger(range.from)}–${formatInteger(range.to)} of ${formatInteger(total)} ${total === 1 ? noun.replace(/s$/, "") : noun}`;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-sp-4",
        busy && "opacity-60",
        className,
      )}
    >
      <span className="t-caption text-ink-4" aria-live="polite">
        {readout}
      </span>

      {/* A single page needs no navigation, but the readout above still earns its place. */}
      {pages > 1 ? (
        <nav aria-label="Pagination" className="flex items-center gap-sp-2">
          <PageButton
            label="Previous page"
            disabled={page <= 0}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft size={14} strokeWidth={1.5} aria-hidden="true" />
          </PageButton>

          {tokens.map((token) =>
            token.kind === "gap" ? (
              <span
                key={token.key}
                aria-hidden="true"
                className="t-label inline-flex h-[28px] w-[18px] items-center justify-center text-ink-5"
              >
                {"…"}
              </span>
            ) : (
              <PageButton
                key={token.page}
                label={`Page ${token.page + 1}`}
                active={token.page === page}
                onClick={() => onPageChange(token.page)}
              >
                {token.page + 1}
              </PageButton>
            ),
          )}

          <PageButton
            label="Next page"
            disabled={page >= pages - 1}
            onClick={() => onPageChange(page + 1)}
          >
            <ChevronRight size={14} strokeWidth={1.5} aria-hidden="true" />
          </PageButton>
        </nav>
      ) : null}
    </div>
  );
}

/**
 * Pager for CURSOR-paginated sources, where the total is unknowable.
 *
 * The audit ledger walks backwards by `beforeSeq`; there is no count of remaining entries, so
 * `Pager`'s "Showing 13–18 of 1,284" readout cannot be honest here. This variant numbers only the
 * pages already fetched and lets Next reach one page further, fetching on demand.
 *
 * That distinction matters: the previous "Load older" button appended each page to a single
 * growing table, so the ledger became unbounded in height. Here the fetched pages accumulate in
 * the cache — which is what makes stepping back instant — while exactly one page is ever rendered.
 */
export function CursorPager({
  page,
  loadedPages,
  hasMore,
  onPageChange,
  onLoadMore,
  loading = false,
  rowsOnPage,
  noun = "entries",
}: {
  page: number;
  loadedPages: number;
  hasMore: boolean;
  onPageChange: (page: number) => void;
  onLoadMore: () => void;
  loading?: boolean | undefined;
  rowsOnPage: number;
  noun?: string | undefined;
}) {
  const atLastLoaded = page >= loadedPages - 1;
  const canGoForward = !atLastLoaded || hasMore;

  return (
    <div className="flex w-full flex-wrap items-center justify-between gap-sp-4">
      <span className="t-caption text-ink-4" aria-live="polite">
        {rowsOnPage === 0
          ? `No ${noun}`
          : `Page ${page + 1} · ${formatInteger(rowsOnPage)} ${noun}`}
        {hasMore ? "" : " · end of ledger"}
      </span>

      <nav aria-label="Pagination" className="flex items-center gap-sp-2">
        <PageButton
          label="Previous page"
          disabled={page <= 0}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft size={14} strokeWidth={1.5} aria-hidden="true" />
        </PageButton>

        {Array.from({ length: loadedPages }, (_, index) => (
          <PageButton
            key={index}
            label={`Page ${index + 1}`}
            active={index === page}
            onClick={() => onPageChange(index)}
          >
            {index + 1}
          </PageButton>
        ))}

        {/* A trailing ellipsis stands in for "there is more, we have not counted it". */}
        {hasMore ? (
          <span
            aria-hidden="true"
            className="t-label inline-flex h-[28px] w-[18px] items-center justify-center text-ink-5"
          >
            {"…"}
          </span>
        ) : null}

        <PageButton
          label="Next page"
          disabled={!canGoForward || loading}
          onClick={() => {
            if (atLastLoaded) onLoadMore();
            else onPageChange(page + 1);
          }}
        >
          <ChevronRight size={14} strokeWidth={1.5} aria-hidden="true" />
        </PageButton>
      </nav>
    </div>
  );
}
