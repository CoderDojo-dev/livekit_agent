"""Résolution d'une zone parlée vers une zone canonique.

Deux étages, tous deux exécutés par Postgres :
  1. égalité exacte sur reference.geo_aliases.normalized (clé stockée + indexée) ;
  2. repli pg_trgm par similarité au-dessus de GEO_MATCH_THRESHOLD, pour les fautes
     d'orthographe et les variantes non encore déclarées comme alias.

Retourne None quand rien ne franchit le seuil. L'appelant DOIT traiter ce None comme
« je n'ai pas pu vérifier », jamais comme « pas de panne » (problème #4).
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

_ARTICLES = ("el ", "al ", "le ", "la ", "les ", "l ")
_THRESHOLD = float(os.getenv("GEO_MATCH_THRESHOLD", "0.45"))
_SUGGESTION_LIMIT = int(os.getenv("GEO_SUGGESTION_LIMIT", "3"))

# Tatweel + harakat arabes : ils n'ont aucune valeur discriminante à l'écrit.
_ARABIC_MARKS = re.compile("[\u0640\u064b-\u0652]")
_NON_WORD = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class ResolvedArea:
    area_code: str
    name_fr: str
    area_type: str
    score: float
    exact: bool


def normalize(raw: str) -> str:
    """Clé de recherche déterministe.

    DOIT rester strictement identique à la normalisation utilisée par le seeder : c'est
    le contrat qui rend l'égalité indexée valable. Toute évolution ici impose un re-seed
    complet de reference.geo_aliases.
    """
    value = unicodedata.normalize("NFKD", (raw or "").strip().lower())
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = _ARABIC_MARKS.sub("", value)
    value = _NON_WORD.sub(" ", value)
    value = _SPACES.sub(" ", value).strip()
    for article in _ARTICLES:
        if value.startswith(article):
            return value[len(article):].strip()
    return value


_EXACT_SQL = text("""
    SELECT a.area_code, g.name_fr, g.area_type
    FROM reference.geo_aliases a
    JOIN reference.geo_areas g ON g.area_code = a.area_code
    WHERE a.normalized = :needle AND g.active IS TRUE
    LIMIT 1
""")

_COMPACT_SQL = text("""
    SELECT a.area_code, g.name_fr, g.area_type
    FROM reference.geo_aliases a
    JOIN reference.geo_areas g ON g.area_code = a.area_code
    WHERE replace(a.normalized, ' ', '') = :compact AND g.active IS TRUE
    LIMIT 1
""")

_FUZZY_SQL = text("""
    SELECT a.area_code, g.name_fr, g.area_type,
           GREATEST(similarity(a.normalized, :needle),
                    similarity(replace(a.normalized, ' ', ''), :compact)) AS score
    FROM reference.geo_aliases a
    JOIN reference.geo_areas g ON g.area_code = a.area_code
    WHERE g.active IS TRUE
      AND GREATEST(similarity(a.normalized, :needle),
                   similarity(replace(a.normalized, ' ', ''), :compact)) >= :threshold
    ORDER BY score DESC
    LIMIT 1
""")

_SUGGEST_SQL = text("""
    SELECT g.name_fr, MAX(similarity(a.normalized, :needle)) AS score
    FROM reference.geo_aliases a
    JOIN reference.geo_areas g ON g.area_code = a.area_code
    WHERE g.active IS TRUE
    GROUP BY g.name_fr
    HAVING MAX(similarity(a.normalized, :needle)) > 0.2
    ORDER BY score DESC
    LIMIT :limit
""")


def resolve(session: Session, spoken: str) -> ResolvedArea | None:
    """Zone canonique correspondant à ``spoken``, ou None si rien de sûr."""
    needle = normalize(spoken)
    if not needle:
        return None

    compact = needle.replace(" ", "")

    row = session.execute(_EXACT_SQL, {"needle": needle}).first()
    if row is not None:
        return ResolvedArea(row.area_code, row.name_fr, row.area_type, 1.0, True)

    row = session.execute(_COMPACT_SQL, {"compact": compact}).first()
    if row is not None:
        return ResolvedArea(row.area_code, row.name_fr, row.area_type, 1.0, True)

    row = session.execute(
        _FUZZY_SQL, {"needle": needle, "compact": compact, "threshold": _THRESHOLD}
    ).first()
    if row is not None:
        return ResolvedArea(
            row.area_code, row.name_fr, row.area_type, float(row.score), False
        )
    return None


def suggest(session: Session, spoken: str) -> list[str]:
    """Zones les plus proches, pour que l'agent pose une question précise au lieu de deviner."""
    needle = normalize(spoken)
    if not needle:
        return []
    rows = session.execute(
        _SUGGEST_SQL, {"needle": needle, "limit": _SUGGESTION_LIMIT}
    ).all()
    return [r.name_fr for r in rows]


_NAME_COLUMNS = {"fr": "name_fr", "ar": "name_ar", "en": "name_en"}


def keyterms(session: Session, language: str = "fr", limit: int = 100,
             scope: list[str] | None = None) -> list[str]:
    """Noms de lieux a annoncer au moteur de transcription, gouvernorats d'abord.

    ``scope`` restreint au perimetre pilote (codes de gouvernorats) : utile tant que
    le referentiel depasse la limite de mots-cles acceptee par le fournisseur.
    """
    column = _NAME_COLUMNS.get(language, "name_fr")  # liste blanche, pas d'injection
    clause = ""
    params: dict = {"limit": limit}
    if scope:
        clause = " AND (g.area_code = ANY(:scope) OR g.parent_code = ANY(:scope))"
        params["scope"] = list(scope)
    sql = text(
        "SELECT DISTINCT coalesce(g." + column + ", g.name_fr) AS term,"
        " CASE g.area_type WHEN 'governorate' THEN 0"
        " WHEN 'delegation' THEN 1 ELSE 2 END AS rank"
        " FROM reference.geo_areas g WHERE g.active IS TRUE" + clause +
        " ORDER BY rank, term LIMIT :limit"
    )
    return [row.term for row in session.execute(sql, params) if row.term]
