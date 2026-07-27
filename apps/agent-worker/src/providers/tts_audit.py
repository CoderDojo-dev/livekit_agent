"""Audit TTS en direct : journalise CHAQUE synthese demandee a un provider.

Emplacement cible : apps/agent-worker/src/providers/tts_audit.py

Non invasif. Aucune logique metier touchee. Inactif par defaut : ne fait quoi
que ce soit que si TTS_AUDIT=1. Sortie JSONL, une ligne par evenement, videe a
chaque ecriture -> lisible en direct avec tail -f.

Evenements emis
  audit_installed   instrumentation demarree
  adapter_created   une chaine TTS (FallbackAdapter) a ete construite
  adapter_closed    une chaine TTS a ete fermee
  pool_prewarm_impl une connexion provider a ete PRECHAUFFEE
  pool_connect      une connexion provider a ete ouverte
  stream_opened     un flux de synthese streaming a ete ouvert
  stream_segment    du texte a ete ENVOYE au provider (donc facture)
  stream_closed     fin du flux
  chunked_synth     synthese non streaming, texte complet

Ce que l'on cherche a prouver
  - combien de chaines TTS existent par appel (attendu : 1, observe : 1 + N)
  - combien sont fermees (si created > closed : fuite)
  - combien de caracteres sont ENVOYES vs combien sont JOUES
  - combien de fois le MEME texte est synthetise (signature de la generation
    preemptive jetee et des reprises)
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import threading
import time
import traceback

_LOG_PATH = os.getenv("TTS_AUDIT_LOG", "/tmp/tts_audit.jsonl")
_LOCK = threading.Lock()
_IDS = itertools.count(1)
_NEWLINE = chr(10)
_installed = False

_KNOWN = ("cartesia", "elevenlabs", "inworld", "smallestai", "azure", "deepgram", "openai")


def _emit(event: str, **fields) -> None:
    """Ecrit une ligne JSON et vide immediatement le tampon (lecture live)."""
    record = {
        "ts": round(time.time(), 3),
        "iso": time.strftime("%H:%M:%S", time.localtime()),
        "pid": os.getpid(),
        "event": event,
    }
    record.update(fields)
    try:
        line = json.dumps(record, ensure_ascii=False)
    except Exception:
        line = json.dumps({"event": event, "error": "unserialisable"})
    with _LOCK:
        try:
            with open(_LOG_PATH, "a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write(_NEWLINE)
                handle.flush()
        except Exception:
            pass


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _provider_name(obj) -> str:
    """Nom du provider reel, en depliant les wrappers du FallbackAdapter."""
    inner = getattr(obj, "tts", None)
    if inner is not None and inner is not obj:
        obj = inner
    module = type(obj).__module__ or ""
    for known in _KNOWN:
        if known in module:
            return known
    return type(obj).__name__


def _caller() -> list[str]:
    """Cinq dernieres frames utiles : dit QUI a construit l'objet."""
    out = []
    try:
        frames = traceback.extract_stack(limit=14)[:-2]
    except Exception:
        return out
    for frame in frames[-5:]:
        base = os.path.basename(frame.filename)
        out.append(base + ":" + str(frame.lineno) + ":" + str(frame.name))
    return out


def _flush_segment(stream, event: str) -> None:
    parts = getattr(stream, "_audit_parts", None) or []
    text = "".join(parts)
    stream._audit_parts = []
    if not text.strip():
        return
    _emit(
        event,
        stream_id=getattr(stream, "_audit_id", None),
        chars=len(text),
        digest=_digest(text),
        text=text[:200],
    )


def _patch_adapter(tts_module) -> None:
    target = getattr(tts_module, "FallbackAdapter", None)
    if target is None:
        _emit("patch_skipped", what="FallbackAdapter")
        return
    original_init = target.__init__

    def audited_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._audit_id = next(_IDS)
        providers = []
        for attr in ("_tts_instances", "_tts", "_instances", "_providers"):
            value = getattr(self, attr, None)
            if isinstance(value, (list, tuple)) and value:
                providers = [_provider_name(item) for item in value]
                break
        _emit(
            "adapter_created",
            adapter_id=self._audit_id,
            providers=providers,
            provider_count=len(providers),
            built_by=_caller(),
        )

    target.__init__ = audited_init


def _patch_close(tts_module) -> None:
    base = getattr(tts_module, "TTS", None)
    original = getattr(base, "aclose", None) if base is not None else None
    if original is None:
        _emit("patch_skipped", what="TTS.aclose")
        return

    async def audited_aclose(self, *args, **kwargs):
        _emit(
            "adapter_closed",
            adapter_id=getattr(self, "_audit_id", None),
            provider=_provider_name(self),
        )
        return await original(self, *args, **kwargs)

    base.aclose = audited_aclose


def _patch_stream(tts_module) -> None:
    cls = getattr(tts_module, "SynthesizeStream", None)
    if cls is None:
        _emit("patch_skipped", what="SynthesizeStream")
        return

    original_init = cls.__init__

    def audited_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._audit_id = next(_IDS)
        self._audit_parts = []
        self._audit_total = 0
        owner = kwargs.get("tts", None)
        _emit(
            "stream_opened",
            stream_id=self._audit_id,
            provider=_provider_name(owner if owner is not None else self),
            opened_by=_caller(),
        )

    cls.__init__ = audited_init

    original_push = getattr(cls, "push_text", None)
    if original_push is not None:

        def audited_push(self, token):
            text = token or ""
            parts = getattr(self, "_audit_parts", None)
            if parts is None:
                parts = []
                self._audit_parts = parts
            parts.append(text)
            self._audit_total = getattr(self, "_audit_total", 0) + len(text)
            return original_push(self, token)

        cls.push_text = audited_push

    original_flush = getattr(cls, "flush", None)
    if original_flush is not None:

        def audited_flush(self, *args, **kwargs):
            _flush_segment(self, "stream_segment")
            return original_flush(self, *args, **kwargs)

        cls.flush = audited_flush

    original_end = getattr(cls, "end_input", None)
    if original_end is not None:

        def audited_end(self, *args, **kwargs):
            _flush_segment(self, "stream_segment")
            return original_end(self, *args, **kwargs)

        cls.end_input = audited_end

    original_close = getattr(cls, "aclose", None)
    if original_close is not None:

        async def audited_close(self, *args, **kwargs):
            _flush_segment(self, "stream_segment")
            _emit(
                "stream_closed",
                stream_id=getattr(self, "_audit_id", None),
                total_chars=getattr(self, "_audit_total", 0),
            )
            return await original_close(self, *args, **kwargs)

        cls.aclose = audited_close


def _patch_chunked(tts_module) -> None:
    cls = getattr(tts_module, "ChunkedStream", None)
    if cls is None:
        _emit("patch_skipped", what="ChunkedStream")
        return
    original_init = cls.__init__

    def audited_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        text = kwargs.get("input_text", None)
        if text is None:
            text = getattr(self, "_input_text", "") or ""
        text = str(text)
        _emit(
            "chunked_synth",
            chars=len(text),
            digest=_digest(text),
            text=text[:200],
            provider=_provider_name(kwargs.get("tts", self)),
            opened_by=_caller(),
        )

    cls.__init__ = audited_init


def _patch_pool() -> None:
    try:
        from livekit.agents.utils import connection_pool as pool_module
    except Exception as exc:
        _emit("patch_skipped", what="ConnectionPool", reason=str(exc))
        return
    cls = getattr(pool_module, "ConnectionPool", None)
    if cls is None:
        _emit("patch_skipped", what="ConnectionPool")
        return

    def make(fn, label):
        async def audited(self, *args, **kwargs):
            _emit("pool_" + label, pool=id(self))
            return await fn(self, *args, **kwargs)

        return audited

    for name in ("_prewarm_impl", "_connect"):
        original = getattr(cls, name, None)
        if original is None:
            continue
        setattr(cls, name, make(original, name.strip("_")))


def install_tts_audit() -> bool:
    """Installe l'audit si TTS_AUDIT=1. Retourne True si actif."""
    global _installed
    if _installed:
        return True
    if os.getenv("TTS_AUDIT", "") != "1":
        return False
    _installed = True
    try:
        from livekit.agents import tts as tts_module
    except Exception as exc:
        _emit("audit_failed", reason=str(exc))
        return False
    _patch_adapter(tts_module)
    _patch_close(tts_module)
    _patch_stream(tts_module)
    _patch_chunked(tts_module)
    _patch_pool()
    _emit(
        "audit_installed",
        log_path=_LOG_PATH,
        cartesia_model_env=os.getenv("CARTESIA_TTS_MODEL", "(absent -> defaut code)"),
        tts_primary_env=os.getenv("TTS_PRIMARY", "(absent -> cartesia)"),
        preemptive_env=os.getenv("PREEMPTIVE_GENERATION", "(absent -> True)"),
    )
    return True
