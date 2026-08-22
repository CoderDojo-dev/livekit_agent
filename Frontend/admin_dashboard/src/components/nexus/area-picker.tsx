import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MapPin, X } from "lucide-react";
import { Token } from "@/components/nexus/primitives";
import { getReferenceCatalog, type AreaEntry } from "@/lib/api/reference.server";
import { referenceKeys } from "@/lib/nexus/query-keys";
import { useDebounced } from "@/hooks/use-debounced";
import { cn } from "@/lib/utils";

/**
 * Pick a geo area BY NAME.
 *
 * An area code ("TN-12") is an identifier, not a fact anybody holds in their head — an operator
 * declaring an incident knows they mean Ariana, not that Ariana is the twelfth governorate. So
 * this searches on the name and keeps the code as the value it submits.
 *
 * The search runs against the existing catalog endpoint, which already matches French name,
 * Arabic name and code, so typing "Ariana", "أريانة" or "TN-12" all find the same row.
 *
 * The code is still SHOWN beside each result and on the selected chip: the operator picks by
 * name, but the thing that gets written is visible, so an ambiguous choice between two
 * similarly-named localities is resolvable rather than a guess.
 */

const AREA_TYPE_LABEL: Record<string, string> = {
  governorate: "Governorate",
  delegation: "Delegation",
  locality: "Locality",
};

export function AreaPicker({
  value,
  onChange,
  label = "Area",
}: {
  /** The selected area_code, or "" when nothing is chosen. */
  value: string;
  onChange: (areaCode: string, area: AreaEntry | null) => void;
  label?: string;
}) {
  const inputId = useId();
  const listId = `${inputId}-list`;

  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [selected, setSelected] = useState<AreaEntry | null>(null);

  const wrapperRef = useRef<HTMLDivElement>(null);
  const debounced = useDebounced(query, 200);

  /* The catalog endpoint caps at 200 rows; a 2-character floor keeps the first keystroke from
   * pulling the whole referential back and makes the list meaningful rather than alphabetical. */
  const results = useQuery({
    queryKey: referenceKeys.catalog("areas", debounced),
    queryFn: () => getReferenceCatalog({ data: { catalog: "areas", search: debounced } }),
    enabled: open && debounced.trim().length >= 2,
    staleTime: 30_000,
  });

  const matches = useMemo(() => {
    const rows = (results.data ?? []) as AreaEntry[];
    // Active areas only: an area that has been deactivated no longer matches a caller's spoken
    // place, so declaring an incident on it would be invisible to the agent.
    return rows.filter((row) => row.active).slice(0, 8);
  }, [results.data]);

  useEffect(() => setHighlight(0), [debounced]);

  /* Dismiss on outside click — Escape is handled on the input so it does not fight the modal. */
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  function choose(area: AreaEntry) {
    setSelected(area);
    onChange(area.area_code, area);
    setQuery("");
    setOpen(false);
  }

  function clear() {
    setSelected(null);
    onChange("", null);
    setQuery("");
  }

  /* ---- Chosen state: a chip, not an input. The decision is made; show it and offer undo. ---- */
  if (selected && value) {
    return (
      <div>
        <p className="t-micro mb-sp-3 text-ink-5">{label}</p>
        <div className="flex items-center gap-sp-4 rounded-r-3 border border-stroke-strong bg-surface-3 px-sp-5 py-sp-4">
          <MapPin size={14} strokeWidth={1.5} aria-hidden="true" className="shrink-0 text-ink-3" />
          <span className="min-w-0 flex-1">
            <span className="t-body-strong block truncate text-ink-1">{selected.name_fr}</span>
            <span className="t-caption block truncate text-ink-4">
              {AREA_TYPE_LABEL[selected.area_type] ?? selected.area_type}
            </span>
          </span>
          <Token className="shrink-0">{selected.area_code}</Token>
          <button
            type="button"
            onClick={clear}
            aria-label="Choose a different area"
            className="inline-flex size-[24px] shrink-0 items-center justify-center rounded-r-2 text-ink-4 transition-colors duration-[120ms] hover:bg-surface-4 hover:text-ink-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X size={13} strokeWidth={1.5} aria-hidden="true" />
          </button>
        </div>
      </div>
    );
  }

  /* ---- Search state ---- */
  return (
    <div ref={wrapperRef} className="relative">
      <label htmlFor={inputId} className="t-micro mb-sp-3 block text-ink-5">
        {label}
      </label>

      <input
        id={inputId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        value={query}
        placeholder="Start typing a place name — Ariana, Sfax…"
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setOpen(true);
            setHighlight((index) => Math.min(index + 1, Math.max(0, matches.length - 1)));
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setHighlight((index) => Math.max(index - 1, 0));
          } else if (event.key === "Enter") {
            const pick = matches[highlight];
            if (pick) {
              // Only swallow Enter when there is something to choose, so an empty field still
              // submits the surrounding form normally.
              event.preventDefault();
              choose(pick);
            }
          } else if (event.key === "Escape" && open) {
            // Stop the modal closing behind the list.
            event.stopPropagation();
            setOpen(false);
          }
        }}
        className="w-full rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 py-sp-4 t-body text-ink-1 placeholder:text-ink-5 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink focus:outline-none"
      />

      {open && debounced.trim().length >= 2 ? (
        <ul
          id={listId}
          role="listbox"
          aria-label={label}
          className="absolute inset-x-0 top-[calc(100%+4px)] z-50 max-h-[240px] overflow-y-auto overscroll-contain rounded-r-3 border border-stroke-default bg-surface-4 py-sp-2 shadow-elev-3"
        >
          {results.isPending ? (
            <li className="px-sp-5 py-sp-4 t-caption text-ink-4">Searching…</li>
          ) : matches.length === 0 ? (
            <li className="px-sp-5 py-sp-4 t-caption text-ink-4">
              No area matches “{debounced}”. Add it in the Geo areas catalog first.
            </li>
          ) : (
            matches.map((area, index) => (
              <li key={area.area_code}>
                <button
                  type="button"
                  role="option"
                  aria-selected={index === highlight}
                  onMouseEnter={() => setHighlight(index)}
                  onClick={() => choose(area)}
                  className={cn(
                    "flex w-full items-center gap-sp-4 px-sp-5 py-sp-3 text-start transition-colors duration-[120ms]",
                    index === highlight ? "bg-surface-5 text-ink-1" : "text-ink-2",
                  )}
                >
                  <span className="min-w-0 flex-1">
                    <span className="t-ui block truncate">{area.name_fr}</span>
                    <span className="t-caption block truncate text-ink-4">
                      {AREA_TYPE_LABEL[area.area_type] ?? area.area_type}
                      {area.parent_code ? ` · under ${area.parent_code}` : ""}
                    </span>
                  </span>
                  {/* The code stays visible: two localities can share a name, and the code is
                   * what actually gets written. */}
                  <Token className="shrink-0">{area.area_code}</Token>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}

      {query.trim().length > 0 && query.trim().length < 2 ? (
        <p className="t-caption mt-sp-2 text-ink-5">Keep typing — at least two characters.</p>
      ) : null}
    </div>
  );
}
