// Feature 6 — knowledge base. Pure functions, no JSX, no network.
import type { StatusKey } from "@/lib/nexus/status";
import type { KnowledgeDocumentRow, UploadResult } from "@/lib/api/knowledge.server";

/** F3 — total status map. `ready` (the healthy steady state) maps onto the existing `indexed`
 * key; unknown input defaults to `pending` rather than passing through (StatusChip would silently
 * render nothing). Never inline <StatusChip status={d.status} />. */
const DOCUMENT_STATUS: Record<string, StatusKey> = {
  ready: "indexed",
  pending: "pending",
  processing: "processing",
  failed: "failed",
  archived: "archived",
};

export function documentStatusKey(status: string): StatusKey {
  return DOCUMENT_STATUS[status] ?? "pending";
}

/** F14 — `und` is the server default sentinel for "undetermined"; never print it. */
export function languageLabel(code: string): string {
  if (code === "und" || code === "") return "\u2014";
  if (code === "multilingual") return "Multilingual";
  return code.toUpperCase();
}

/** document_type is a free taxonomy; "" becomes a dash, otherwise title-cased. */
export function documentTypeLabel(type: string): string {
  if (type === "") return "\u2014";
  return type
    .split(/[\s_]+/)
    .map((word) => (word ? word[0]!.toUpperCase() + word.slice(1) : word))
    .join(" ");
}

/** F7 — encode per segment, preserving the slashes the :path converter needs. */
export function encodeSourcePath(source: string): string {
  return source.split("/").map(encodeURIComponent).join("/");
}

export function isArchived(doc: KnowledgeDocumentRow): boolean {
  return doc.status === "archived";
}

/** F4/F13 — hide-archived is a client filter (the endpoint has no parameters). */
export function visibleDocuments(
  docs: KnowledgeDocumentRow[],
  hideArchived: boolean,
): KnowledgeDocumentRow[] {
  return hideArchived ? docs.filter((d) => !isArchived(d)) : docs;
}

export function archivedCount(docs: KnowledgeDocumentRow[]): number {
  return docs.filter(isArchived).length;
}

/** F9 — four upload outcomes, three of which are not "success". `failed` arrives as HTTP 422,
 * not a 200 body, so it never reaches this function. */
export function uploadOutcome(result: UploadResult): {
  tone: "success" | "neutral" | "warning";
  message: string;
} {
  const chunks = result.chunks;
  switch (result.status) {
    case "ingested":
      return { tone: "success", message: `Indexed \u2014 ${chunks} chunks` };
    case "unchanged":
      return { tone: "neutral", message: "Already indexed \u2014 unchanged" };
    case "stored":
      return { tone: "warning", message: "Stored, not yet searchable" };
    default:
      return { tone: "warning", message: "Upload outcome unknown" };
  }
}

/** F11 — readiness excludes ce_gate, which may legitimately read "warming". */
export function healthSummary(health: { status: string; checks: Record<string, string> }): {
  ready: boolean;
  failing: string[];
} {
  const failing = Object.entries(health.checks)
    .filter(([key, value]) => key !== "ce_gate" && value !== "ok")
    .map(([key]) => key);
  return { ready: failing.length === 0 && health.status === "ok", failing };
}

/** F16 — raw score to 3 decimals, no colour-coding (E5 scores cluster ~0.7-1.0). */
export function formatScore(n: number): string {
  return n.toFixed(3);
}
