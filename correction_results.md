# Correction Results — Runbook v2 appliqué (2026-08-04)

Applicable corrections appliquées et vérifiées contre le système réel (21 conteneurs up).
Ce document répond aux deux questions ouvertes du Runbook v2 (§7) et enregistre les résultats
des vérifications (G2/G3, ordre des routes, gate de lint, clamp D1).

---

## 1. Corrections applicables — résultats

### 1.1 D1 — Clamp retention appliqué (route-level 422)

Modification : `apps/business-api/src/business_api/main.py:157`

```python
if retention_days < 30:
    raise HTTPException(status_code=422, detail="retention_days must be >= 30")
```

Vérification live (business-api rebuildé via `docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml up -d --build business-api`):

| Cas | Méthode | URL | Statut réel | Attendu | Verdict |
|---|---|---|---|---|---|
| Négatif | POST | `/api/v1/jobs/retention?retention_days=-5&dry_run=true` | **422** | 422 | OK |
| Valide | POST | `/api/v1/jobs/retention?retention_days=31&dry_run=true` | **200** | 200 | OK |

Réponse 200 (dry_run, aucune suppression) : `{"cutoff":"2026-07-04T07:16:26.182824+00:00","sessions_matched":0,"turns_anonymized":0,"dry_run":true}`

Le clamp vit au niveau de la **route** (comme décidé D1), pas dans le job. Le job lui-même (`jobs/retention.py`) reste non modifié → aucun changement du comportement de purge interne.

### 1.2 G3 — TableErrorRow (states.tsx)

Vérifié : `Frontend/admin_dashboard/src/components/nexus/states.tsx:114-130`
`TableErrorRow` rend un **`<td colSpan={columns}>` brut** (pas un `<Td colSpan>`) → l'attribut est bien transmis au DOM. **Aucune correction nécessaire.**

### 1.3 G2 — Vérification sur C3 déjà appliqué (callbacks.tsx)

`Frontend/admin_dashboard/src/routes/callbacks.tsx:102-118` utilise déjà la vraie signature :
`items={labels}`, `active={label}`, `onSelect={(label) => setScope(id)}` — shape `items:string[] + active:string + onSelect` label-keyed. **Aucune correction nécessaire.**

### 1.4 Ordre des routes `/sessions` (main.py)

Vérifié : `main.py:56` `GET /api/v1/sessions` précède `main.py:71` `GET /api/v1/sessions/{session_id}` → **ordre correct**, pas de capture accidentelle.

**Écart live relevé (à entériner, pas corrigé silencieusement)** : `GET /api/v1/sessions` avec `X-Role: conseiller` renvoie **403**, pas 200. Le routeur est gated `SuperviseurRole` (décision volontaire du Feature 4 : liste superviseur, détail conseiller). Le Runbook v2 §3 attendait conseiller→200 ; la décision Feature 4 (déjà appliquée et documentée) prime. **Action proposée : conserver le gate superviseur**, ou basculer la liste en conseiller si le runbook doit prévaloir — décision à confirmer.

### 1.5 Vérification `max_frustration` (repositories.py)

`repositories.py:141-142` garde `float(r.max_frustration_score) if r.max_frustration_score is not None else None` — le garde-fou NULL est bien présent (masque les NULL comme prévu par A1 : 0 NULL en base, donc le garde est défensif et ne change aucun affichage actuel).

### 1.6 Gate de lint (Runbook v2 §2)

| Contrôle | Commande | Résultat réel |
|---|---|---|
| TypeScript | `tsc --noEmit` (admin_dashboard) | **CLEAN** |
| ESLint non-prettier | `eslint src --format json` (filtre prettier) | **9 warnings pré-existants** (react-refresh/only-export-components ×7, react-hooks/exhaustive-deps ×2), tous dans des fichiers Feature 0-4, **aucun** introduit par cette session |
| Python (main.py) | — (pas de linter Python configuré dans la gate) | modification de 1 ligne, isolée |

→ Gate respectée : zéro nouveau non-prettier, tsc clean, aucune modification de fichiers déjà-formatés en dehors de `main.py`.

---

## 2. Réponse Q1 — « Où est-ce qu'une escalade se ferme ? »

**Réponse : nulle part. Aucun chemin de fermeture n'existe dans le système actuel.**

Preuve (Block A3, données réelles) : les 58/58 escalades sont `open`, aucune `resolution` n'a jamais été posée,
le trigger est toujours `hard_failure|abuse|clarify_fail|identity_fail` et la cible toujours `manager_agent`.
Aucun tool/route/worker ne référence la fermeture d'escalade (D8).

**Décision appliquée — Option (a) : C13 reste en lecture seule.** La fermeture des escalades est
**hors scope** du cookbook C13 ; elle fera l'objet d'un cookbook dédié (écriture + nouvelle business
rule), conformément à la Contrainte 3 (ne jamais inventer de logique métier non approuvée).
La colonne `resolution` (4 valeurs) est déjà exposée par `/api/v1/escalations` → elle « s'allumera »
dès qu'un chemin de fermeture existera, sans nécessiter de changement du cookbook C13.

---

## 3. Réponse Q2 — « Quel outil était en vol quand l'agent est resté muet ? »

**Réponse : non déterminé par reproduction — décision reportée, phase 2 non étendue.**

Contexte (Block C3) : `ticket_tools._mcp_call()` est le seul appel MCP asynchrone sans `foreground()`
(avec `guards.ensure_identity_verified` comme précédent d'exception de workflow). Mais les journaux
agent-worker ne contiennent aucune trace exploitable (E3, grep vide), et la reproduction nécessite
l'outil réellement en vol au moment du silence — information qui ne peut pas être déduite du code seul.

**Décision appliquée :** conformément à l'engagement du Runbook v2 §9, **aucun patch n'est étendu aux
six tools de ticket sur inférence**. La phase 2 reste scopée à `guards.ensure_identity_verified`.
Dès que la reproduction est fournie (l'outil en vol au moment du silence), on décidera
d'étendre ou non.

---

## 4. Enregistrement des décisions D3 / D12 / H

- **D3 (C14) — Option (a) retenue : deux routes déclaratives.** `/reference/catalogs/{catalog}`
  (superviseur) et `/reference/geo-areas` (administrateur). Pas de switch de rôle runtime.
- **D12** : `updated_at` = migration délibérée (4 modèles sans `Timestamps`) — rien à corriger.
- **H-registre** : H-1 **clamp expédié** (ce doc, §1.1) ; H-4 **actif** (`INTERNAL_API_KEY=dev-key-123`
  déjà posé) ; H-5 **retiré** (guard 404 existant) ; H-2 **31 lignes** advisor_shifts — ne pas
  tronquer/reconstruire.

---

## 5. Gate globale à la sortie de cette session

- `git diff --stat` : 1 fichier modifié côté applicatif (`apps/business-api/src/business_api/main.py`).
- tsc clean, zero nouveau non-prettier, build à vérifier au batch 1.
- DB intacte : 129 sessions, aucune purge (dry_run seulement), actions/audit non touchés.
