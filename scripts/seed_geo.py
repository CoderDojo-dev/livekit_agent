"""Charge le referentiel des zones tunisiennes en base (probleme #1).

Idempotent : relancable sans effet de bord. La normalisation est importee depuis
nms_sim.geo_resolver pour garantir que la cle stockee est exactement celle utilisee
a la lecture.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from nms_sim.geo_resolver import normalize
from persistence.engine import session_scope

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_geo")

# (area_code, name_fr, name_ar, name_en, area_type, parent_code, [alias, ...])
GOVERNORATES = [
    ("TN-11", "Tunis", "تونس", "Tunis", "governorate", None,
     ["Tounes", "Tunis Ville", "Grand Tunis"]),
    ("TN-12", "Ariana", "أريانة", "Ariana", "governorate", None,
     ["El Ariana", "Aryanah", "Arianna", "Laryana"]),
    ("TN-13", "Ben Arous", "بن عروس", "Ben Arous", "governorate", None,
     ["Bin Arous", "Ben Aroûs"]),
    ("TN-14", "Manouba", "منوبة", "Manouba", "governorate", None,
     ["La Manouba", "Mannouba"]),
    ("TN-21", "Nabeul", "نابل", "Nabeul", "governorate", None, ["Nabul", "Nabel"]),
    ("TN-22", "Zaghouan", "زغوان", "Zaghouan", "governorate", None, ["Zaghwan"]),
    ("TN-23", "Bizerte", "بنزرت", "Bizerte", "governorate", None,
     ["Banzart", "Bizerta"]),
    ("TN-31", "Beja", "باجة", "Beja", "governorate", None, ["Béja", "Badja"]),
    ("TN-32", "Jendouba", "جندوبة", "Jendouba", "governorate", None, ["Jandouba"]),
    ("TN-33", "Kef", "الكاف", "Kef", "governorate", None, ["Le Kef", "El Kef"]),
    ("TN-34", "Siliana", "سليانة", "Siliana", "governorate", None, ["Silyana"]),
    ("TN-41", "Kairouan", "القيروان", "Kairouan", "governorate", None,
     ["Al Qayrawan", "Kairwan"]),
    ("TN-42", "Kasserine", "القصرين", "Kasserine", "governorate", None,
     ["Al Qasrayn", "Kasrine"]),
    ("TN-43", "Sidi Bouzid", "سيدي بوزيد", "Sidi Bouzid", "governorate", None,
     ["Sidi Bou Zid"]),
    ("TN-51", "Sousse", "سوسة", "Sousse", "governorate", None, ["Susah", "Suse"]),
    ("TN-52", "Monastir", "المنستير", "Monastir", "governorate", None,
     ["Al Munastir"]),
    ("TN-53", "Mahdia", "المهدية", "Mahdia", "governorate", None, ["Al Mahdiyah"]),
    ("TN-61", "Sfax", "صفاقس", "Sfax", "governorate", None, ["Safaqis", "Sfaks"]),
    ("TN-71", "Gafsa", "قفصة", "Gafsa", "governorate", None, ["Qafsah", "Gapsa"]),
    ("TN-72", "Tozeur", "توزر", "Tozeur", "governorate", None, ["Tawzar"]),
    ("TN-73", "Kebili", "قبلي", "Kebili", "governorate", None, ["Qibili", "Kbili"]),
    ("TN-81", "Gabes", "قابس", "Gabes", "governorate", None, ["Gabès", "Qabis"]),
    ("TN-82", "Medenine", "مدنين", "Medenine", "governorate", None, ["Madanin"]),
    ("TN-83", "Tataouine", "تطاوين", "Tataouine", "governorate", None,
     ["Tatawin", "Tatouine"]),
]

# Delegations de base (Ariana et Tunis)
DELEGATIONS = [
    ("TN-12-ARIANA-VILLE", "Ariana Ville", "أريانة المدينة", "Ariana City",
     "delegation", "TN-12", ["Ariana centre", "centre Ariana"]),
    ("TN-12-SOUKRA", "La Soukra", "السوكرة", "La Soukra", "delegation", "TN-12",
     ["Soukra", "Sukra"]),
    ("TN-12-RAOUED", "Raoued", "راود", "Raoued", "delegation", "TN-12", ["Raoueed"]),
    ("TN-11-BARDO", "Bardo", "باردو", "Bardo", "delegation", "TN-11", ["Le Bardo"]),
    ("TN-11-CARTHAGE", "Carthage", "قرطاج", "Carthage", "delegation", "TN-11",
     ["Qartaj"]),
    ("TN-11-MARSA", "La Marsa", "المرسى", "La Marsa", "delegation", "TN-11",
     ["Marsa"]),
]

# Delegations de Gafsa (11)
DELEGATIONS_GAFSA = [
    ("TN-71-GAFSA-NORD", "Gafsa Nord", None, "Gafsa North", "delegation", "TN-71",
     ["Nord Gafsa", "Gafsa Chamalia"]),
    ("TN-71-GAFSA-SUD", "Gafsa Sud", None, "Gafsa South", "delegation", "TN-71",
     ["Sud Gafsa", "Gafsa Janoubia"]),
    ("TN-71-KSAR", "El Ksar", None, "El Ksar", "delegation", "TN-71",
     ["Ksar Gafsa", "Lksar"]),
    ("TN-71-METLAOUI", "Metlaoui", None, "Metlaoui", "delegation", "TN-71",
     ["Metlawi", "Mtlaoui", "Metlaou", "Mitlaoui"]),
    ("TN-71-REDEYEF", "Redeyef", None, "Redeyef", "delegation", "TN-71",
     ["Redayef", "Redeyf", "Redyef"]),
    ("TN-71-MOULARES", "Moulares", None, "Moulares", "delegation", "TN-71",
     ["Mulares", "Moularess"]),
    ("TN-71-OM-LARAYES", "Om Larayes", None, "Om Larayes", "delegation", "TN-71",
     ["Oum Larayes", "Om El Araies", "Omlarayes"]),
    ("TN-71-SIDI-AICH", "Sidi Aich", None, "Sidi Aich", "delegation", "TN-71",
     ["Sidi Ich", "Sidi Ayech"]),
    ("TN-71-GUETTAR", "El Guettar", None, "El Guettar", "delegation", "TN-71",
     ["Guettar", "Gtar"]),
    ("TN-71-SENED", "Sened", None, "Sened", "delegation", "TN-71",
     ["Snad", "Es Sened"]),
    ("TN-71-BELKHIR", "Belkhir", None, "Belkhir", "delegation", "TN-71",
     ["Bel Khir"]),
]

# Delegations de Sousse (16)
DELEGATIONS_SOUSSE = [
    ("TN-51-SOUSSE-MEDINA", "Sousse Medina", None, "Sousse Medina", "delegation",
     "TN-51", ["Sousse Ville", "Medina Sousse", "Sousse centre"]),
    ("TN-51-SOUSSE-RIADH", "Sousse Riadh", None, "Sousse Riadh", "delegation",
     "TN-51", ["Riadh", "Sousse Ryadh", "Riadh Sousse"]),
    ("TN-51-SOUSSE-JAWHARA", "Sousse Jawhara", None, "Sousse Jawhara", "delegation",
     "TN-51", ["Jawhara", "Sousse Jouhara"]),
    ("TN-51-SOUSSE-SIDI-ABDELHAMID", "Sousse Sidi Abdelhamid", None,
     "Sousse Sidi Abdelhamid", "delegation", "TN-51", ["Sidi Abdelhamid"]),
    ("TN-51-HAMMAM-SOUSSE", "Hammam Sousse", None, "Hammam Sousse", "delegation",
     "TN-51", ["Hamam Sousse", "Hammam Susa"]),
    ("TN-51-AKOUDA", "Akouda", None, "Akouda", "delegation", "TN-51",
     ["Akuda", "Akoudah"]),
    ("TN-51-KALAA-KEBIRA", "Kalaa Kebira", None, "Kalaa Kebira", "delegation",
     "TN-51", ["Kalaa Kbira", "Klaa Kebira"]),
    ("TN-51-KALAA-SEGHIRA", "Kalaa Seghira", None, "Kalaa Seghira", "delegation",
     "TN-51", ["Kalaa Sghira", "Klaa Seghira"]),
    ("TN-51-MSAKEN", "Msaken", None, "Msaken", "delegation", "TN-51",
     ["M Saken", "Msakan", "Messaken", "Msakn"]),
    ("TN-51-ENFIDHA", "Enfidha", None, "Enfidha", "delegation", "TN-51",
     ["Enfidhaville", "Nfidha"]),
    ("TN-51-BOUFICHA", "Bouficha", None, "Bouficha", "delegation", "TN-51",
     ["Bou Ficha"]),
    ("TN-51-HERGLA", "Hergla", None, "Hergla", "delegation", "TN-51", ["Hargla"]),
    ("TN-51-SIDI-BOU-ALI", "Sidi Bou Ali", None, "Sidi Bou Ali", "delegation",
     "TN-51", ["Sidi Bouali"]),
    ("TN-51-SIDI-EL-HENI", "Sidi El Heni", None, "Sidi El Heni", "delegation",
     "TN-51", ["Sidi Heni"]),
    ("TN-51-KONDAR", "Kondar", None, "Kondar", "delegation", "TN-51", ["Kandar"]),
    ("TN-51-ZAOUIET-SOUSSE", "Zaouiet Sousse", None, "Zaouiet Sousse", "delegation",
     "TN-51", ["Zaouia Sousse", "Zaouiet"]),
]

# Delegations de Monastir (13)
DELEGATIONS_MONASTIR = [
    ("TN-52-MONASTIR", "Monastir", None, "Monastir", "delegation", "TN-52",
     ["Monastir Ville", "Mnastir", "Monastir centre"]),
    ("TN-52-OUERDANINE", "Ouerdanine", None, "Ouerdanine", "delegation", "TN-52",
     ["Werdanine", "Ouardanine"]),
    ("TN-52-SAHLINE", "Sahline", None, "Sahline", "delegation", "TN-52",
     ["Sahline Moatmar", "Sahlin"]),
    ("TN-52-ZERAMDINE", "Zeramdine", None, "Zeramdine", "delegation", "TN-52",
     ["Zermdine", "Zaramdine"]),
    ("TN-52-BENI-HASSEN", "Beni Hassen", None, "Beni Hassen", "delegation",
     "TN-52", ["Bni Hassen"]),
    ("TN-52-JEMMAL", "Jemmal", None, "Jemmal", "delegation", "TN-52",
     ["Jammal", "Jemal"]),
    ("TN-52-BEMBLA", "Bembla", None, "Bembla", "delegation", "TN-52",
     ["Bembla Mnara", "Benbla"]),
    ("TN-52-MOKNINE", "Moknine", None, "Moknine", "delegation", "TN-52",
     ["Mokneen", "Mouknine"]),
    ("TN-52-BEKALTA", "Bekalta", None, "Bekalta", "delegation", "TN-52",
     ["Beqalta", "Bkalta"]),
    ("TN-52-TEBOULBA", "Teboulba", None, "Teboulba", "delegation", "TN-52",
     ["Tboulba", "Taboulba"]),
    ("TN-52-KSAR-HELLAL", "Ksar Hellal", None, "Ksar Hellal", "delegation",
     "TN-52", ["Ksar Helal", "Ksar Hlal", "Ksarhellal"]),
    ("TN-52-KSIBET", "Ksibet El Mediouni", None, "Ksibet El Mediouni", "delegation",
     "TN-52", ["Ksibet", "Ksibet Mediouni"]),
    ("TN-52-SAYADA", "Sayada Lamta Bou Hajar", None, "Sayada Lamta Bou Hajar",
     "delegation", "TN-52", ["Sayada", "Lamta", "Bou Hajar"]),
]

ZONES = (
    GOVERNORATES
    + DELEGATIONS
    + DELEGATIONS_GAFSA
    + DELEGATIONS_SOUSSE
    + DELEGATIONS_MONASTIR
)

UPSERT_AREA = text("""
    INSERT INTO reference.geo_areas
        (area_code, name_fr, name_ar, name_en, area_type, parent_code)
    VALUES (:code, :fr, :ar, :en, :kind, :parent)
    ON CONFLICT (area_code) DO UPDATE
        SET name_fr = EXCLUDED.name_fr,
            name_ar = EXCLUDED.name_ar,
            name_en = EXCLUDED.name_en,
            area_type = EXCLUDED.area_type,
            parent_code = EXCLUDED.parent_code
""")

UPSERT_ALIAS = text("""
    INSERT INTO reference.geo_aliases (area_code, alias, normalized)
    VALUES (:code, :alias, :normalized)
    ON CONFLICT (normalized) DO NOTHING
""")


def seed() -> None:
    rows = ZONES
    with session_scope() as session:
        # 1. les zones d'abord : les parents avant les enfants (contrainte FK)
        for code, fr, ar, en, kind, parent, _aliases in rows:
            session.execute(UPSERT_AREA, {
                "code": code, "fr": fr, "ar": ar, "en": en,
                "kind": kind, "parent": parent,
            })

        # 2. puis tous les alias : noms officiels FR/AR/EN + variantes et fautes
        alias_count = 0
        for code, fr, ar, en, _kind, _parent, aliases in rows:
            forms = [f for f in (fr, ar, en, *aliases) if f]
            for form in forms:
                key = normalize(form)
                if not key:
                    continue
                session.execute(UPSERT_ALIAS, {
                    "code": code, "alias": form, "normalized": key,
                })
                alias_count += 1

    logger.info("seeded %d zones and %d alias forms", len(rows), alias_count)


if __name__ == "__main__":
    seed()
