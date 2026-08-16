import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { requireRole } from "@/lib/api/middleware";
import { ApiError } from "@/lib/api/errors";

/* ---------- knowledge-service configuration ----------
 * Kept here, not in config.ts, because this cookbook modifies no file under src/lib/api/
 * other than this one (F18-adjacent lock). The URL and timeout are read from env at call time.
 */
const DEFAULT_KNOWLEDGE_URL = "http://localhost:8102";
const DEFAULT_KNOWLEDGE_TIMEOUT_MS = 60000;

function knowledgeUrl(): string {
  return (process.env["KNOWLEDGE_API_URL"] || DEFAULT_KNOWLEDGE_URL).replace(/\/$/, "");
}

function knowledgeTimeoutMs(): number {
  return Number(process.env["KNOWLEDGE_API_TIMEOUT_MS"] || DEFAULT_KNOWLEDGE_TIMEOUT_MS);
}

/* ---------- wire types: exactly what knowledge-service :8102 serialises ---------- */

export type KnowledgeDocumentRow = {
  document_id: string;
  source: string;
  title: string;
  language: string;
  document_type: string;
  version: number;
  status: string;
  chunks: number;
  checksum: string;
};

export type KnowledgeDocumentList = {
  documents: KnowledgeDocumentRow[];
  total_documents: number;
  total_chunks: number;
};

export type KnowledgeHealth = {
  status: "ok" | "degraded";
  model: string | null;
  dimensions: number | null;
  collection: string | null;
  points: number | null;
  checks: Record<string, string>;
};

export type UploadResult = {
  source: string;
  status: "ingested" | "unchanged" | "stored" | "failed";
  document_id: string | null;
  version: number;
  chunks: number;
  indexed: number;
  message: string;
};

export type PurgeResult = {
  source: string;
  documents_archived: number;
  chunks_deactivated: number;
  points_removed: number;
  object_removed: boolean;
};

export type Passage = {
  text: string;
  source: string;
  score: number;
  title: string;
  language: string;
  document_type: string;
  version: number;
  metadata: Record<string, string | number | boolean | null> | null;
};

export type ProbeResult = {
  passages: Passage[];
};

/* ---------- internal transport ---------- */

function buildUrl(
  path: string,
  query?: Record<string, string | number | boolean | undefined | null>,
): string {
  const url = new URL(`${knowledgeUrl()}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/**
 * Server-only HTTP client for knowledge-service. The browser never contacts :8102 (F18 guard,
 * F21). Follows businessApi()'s shape and reuses its error taxonomy so the page shares the same
 * state components.
 *
 * F2: X-API-Key is sent iff INTERNAL_API_KEY is present in the dashboard's server env — mirroring
 * internal_headers() exactly, never conditionally on NODE_ENV. A 403 mentions the internal key by
 * name so an operator hunts config, not a networking problem.
 */
async function knowledgeApi<T>(
  path: string,
  options: {
    method?: "GET" | "POST" | "DELETE";
    query?: Record<string, string | number | boolean | undefined | null>;
    body?: unknown;
    formData?: FormData;
  },
): Promise<T> {
  const { method = "GET", query, body, formData } = options;

  if (body !== undefined && formData !== undefined) {
    throw new ApiError(500, "knowledgeApi received both body and formData", path);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), knowledgeTimeoutMs());

  const headers: Record<string, string> = {
    Accept: "application/json",
  };

  const internalKey = process.env["INTERNAL_API_KEY"];

  if (internalKey) {
    headers["X-API-Key"] = internalKey;
  }

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const requestBody =
    formData !== undefined ? formData : body !== undefined ? JSON.stringify(body) : undefined;

  let response: Response;

  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      signal: controller.signal,
      ...(requestBody === undefined ? {} : { body: requestBody }),
    });
  } catch (cause) {
    const offline = (cause as Error)?.name === "AbortError";
    throw new ApiError(
      offline ? 504 : 503,
      offline ? "knowledge-service did not respond in time" : "knowledge-service is unreachable",
      path,
    );
  } finally {
    clearTimeout(timeout);
  }

  if (response.status === 204) return undefined as T;

  const raw = await response.text();

  if (!response.ok) {
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
      else if (parsed.detail !== undefined) detail = JSON.stringify(parsed.detail);
    } catch {
      /* non-JSON error body — keep the raw text */
    }
    if (response.status === 403) {
      throw new ApiError(403, "knowledge-service rejected the internal key", path);
    }
    throw new ApiError(response.status, detail, path);
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new ApiError(502, "knowledge-service returned a malformed JSON body", path);
  }
}

/* ---------- schemas ---------- */

const SearchInputSchema = z.object({
  query: z.string().min(1),
});

const PurgeInput = z.object({
  source: z.string().min(1),
});

const UploadInput = z.object({
  documentType: z.string().min(1),
  fileName: z.string().min(1),
  fileType: z.string().optional(),
  /** file content as base64 — a live File/Blob cannot cross the RPC boundary */
  fileBase64: z.string().min(1),
});

/* ---------- server functions ---------- */

/** Corpus inventory. F10 — 503 surfaces as an error state, never an empty table. */
export const listDocuments = createServerFn({ method: "GET" })
  .middleware([requireRole("superviseur")])
  .handler(async () => {
    return knowledgeApi<KnowledgeDocumentList>("/knowledge/documents", { method: "GET" });
  });

/** Readiness probe. F11 — the only place that answers "is the corpus searchable right now". */
export const knowledgeHealth = createServerFn({ method: "GET" })
  .middleware([requireRole("superviseur")])
  .handler(async () => {
    return knowledgeApi<KnowledgeHealth>("/health", { method: "GET" });
  });

/** Upload a source document and index it. administrateur — it changes what the agent tells customers. */
export const uploadDocument = createServerFn({ method: "POST" })
  .middleware([requireRole("administrateur")])
  .inputValidator((data: unknown) => UploadInput.parse(data))
  .handler(async ({ data }) => {
    const bytes = base64ToBytes(data.fileBase64);
    const file = new File([toBlobPart(bytes)], data.fileName, {
      type: data.fileType ?? "application/octet-stream",
    });
    const formData = new FormData();
    formData.append("file", file, data.fileName);
    formData.append("document_type", data.documentType);
    formData.append("auto_ingest", "true");
    return knowledgeApi<UploadResult>("/knowledge/upload", { method: "POST", formData });
  });

function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function toBlobPart(bytes: Uint8Array): BlobPart {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

/** Purge a source from records, index, and storage bucket. POST at the CSRF layer (F20). */
export const purgeDocument = createServerFn({ method: "POST" })
  .middleware([requireRole("administrateur")])
  .inputValidator((data: unknown) => PurgeInput.parse(data))
  .handler(async ({ data }) => {
    // F7 — encode per segment, preserving the slashes the :path converter needs.
    const sourcePath = data.source.split("/").map(encodeURIComponent).join("/");
    return knowledgeApi<PurgeResult>(`/knowledge/documents/${sourcePath}`, {
      method: "DELETE",
      query: { remove_object: true },
    });
  });

/** Retrieval probe (F16). POST but non-mutating — a strict query, never cached. */
export const probeSearch = createServerFn({ method: "POST" })
  .middleware([requireRole("superviseur")])
  .inputValidator((data: unknown) => SearchInputSchema.parse(data))
  .handler(async ({ data }) => {
    return knowledgeApi<ProbeResult>("/search", {
      method: "POST",
      body: { query: data.query, top_k: 4 },
    });
  });
