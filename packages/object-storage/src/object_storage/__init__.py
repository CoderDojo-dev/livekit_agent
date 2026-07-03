"""Optional object storage (report #8): consent-gated call recordings + retention purge.

Gated + degradation-safe: if `MINIO_ENDPOINT` is unset (or the client can't be built), `get_store`
returns a `NullStore` whose `put` returns None and whose `delete` is a no-op.
"""
from object_storage.store import MinioStore, NullStore, ObjectStore, get_store

__all__ = ["MinioStore", "NullStore", "ObjectStore", "get_store"]