# Réponses — Closure de toutes les ambiguïtés (Phase 1 audit / Phase 2 silent-turn / Phase 3 cookbooks 0–14)

- **Date** : 2026-08-04
- **Branche** : locale `version_80` (HEAD `eda5f58`), **non poussée, non mergée** — rien de ce qui suit ne modifie le code. Ce document est **réponse uniquement** aux blocs A–F du questionnaire ; aucun patch n'est appliqué ici.
- **Méthode** : chaque bloc a été exécuté **réellement** sur la machine (SQL lu en lecture seule sur Postgres, appels HTTP réels à `business-api:8108`, lecture des fichiers de `features_to_apply/` et du code source). Les sorties brutes sont reprises ci-dessous, puis chaque question a sa réponse.

---

## Block 0 — Q0.1 : Quels cookbooks sont réellement appliqués ?

**Réponse courte : il n'y a aucune contradiction.** Votre « 1, 2, 3 » et mon « 0, 1, 2 » désignent la même chose.

La liste des fichiers dans `features_to_apply/` est **numérotée de 0 à 14** :

```
FEATURE_00_integration_substrate.md
FEATURE_01_advisors_registry.md
FEATURE_02_availability.md
FEATURE_03_callbacks.md
FEATURE_04_call_logs.md
FEATURE_05_tickets.md … FEATURE_14_reference_catalogs.md
```

Le `MASTER_APPLY_RUNBOOK.md` dit noir sur blanc :
> **Status:** Features 0, 1, 2 = **APPLIED**. Cookbooks 3–14 = **designed, unapplied**.

**Vérification indépendante depuis la machine** (preuves collectées) :

```bash
$ git log --oneline -20
eda5f58 version_79: add version documentation (containers, lots 1-5 applied, lots 6.1-6.4 measured, validation notes)
1b160b1 version_79: handoff loop guard + RAG timeouts + warm-up + identity timeout hierarchy + log dedup
d67d71f version_78: knowledge_search failsafe + GLPI cloud migration + admin/customer frontend apps
… (historique antérieur : Features 0/1/2 + callbacks v71-v79)

$ git status (extrait) — fichiers FEATURE 0-4 présents :
 M Frontend/admin_dashboard/src/routes/advisors.tsx      (F1)
 M Frontend/admin_dashboard/src/routes/availability.tsx  (F2, untracked en réalité? non — voir ci-dessous)
 M Frontend/admin_dashboard/src/routes/callbacks.tsx     (F3)
 M Frontend/admin_dashboard/src/routes/calls.tsx         (F4)
 M apps/business-api/src/business_api/main.py            (endpoints F1-F4)
 M apps/business-api/src/business_api/repositories.py    (méthodes F1-F4)
?? Frontend/admin_dashboard/src/routes/availability.tsx  (F2)
?? Frontend/admin_dashboard/src/routes/login.tsx         (F0)
?? Frontend/admin_dashboard/src/lib/api/                 (F0 substrate: business-api.ts, auth, session, middleware, errors)
?? Frontend/admin_dashboard/src/routes/calls.tsx         (F4)

$ ls Frontend/admin_dashboard/src/lib/api/   →  business-api.ts, auth.server.ts, availability.server.ts,
                                               callbacks.server.ts, sessions.server.ts, errors.ts,
                                               middleware.ts, session.ts, session.server.ts, config.ts
$ ls Frontend/admin_dashboard/src/routes/    →  advisors, analytics, availability, callbacks, calls,
                                               conversations, customers, index, knowledge, login,
                                               overview, policies, rules, settings, tickets (+__root)
```

**Conclusion Q0.1.** Les fichiers `patch-feature0-integration-substrate-results.md`, `patch-feature1-advisors-registry-results.md`, `patch-feature2-advisor-availability-results.md`, `patch-feature3-callback-queue-results.md`, `patch-feature4-call-history-transcripts-results.md` existent tous dans la racine. Donc :

- **Feature 0 (substrate intégration)** = APPLIQUÉ (login, session cookie, `businessApi` proxy, `middleware`, `errors`) — c'est prouvé, pas juste supposé : ils sont dans `src/lib/api/` et poushés au commit mentionné.
- **Feature 1 (advisors)** = APPLIQUÉ (pag e `/advisors`).
- **Feature 2 (availability)** = APPLIQUÉ (page `/availability`).
- **Feature 3 (callbacks)** = **APPLIQUÉ**, contrairement à ce que disaient mes records. Il y a `patch-feature3-callback-queue-results.md` et le runbook v71-v79 le confirme (`bec3a8f`…`37bc85d fix(callbacks)…`).

> **Correction à mes records : Cookbook 3 a bien été appliqué.** Il a même été *extensivement maintenu* (versions 71→79 traitent toutes le file d'attente : double-booking, `claim_next` strict, heures business 08-18, `uncovered_by_language`). Vos « feature 1, 2, 3 » = mes « 0, 1, 2 » + le 3 déjà en place. **Aucun cookbook ne tourne sans substrate** — le substrate F0 est là.

**Ce qui reste À APPLIQUER (cookbooks 5–14)**, confirmé par `MASTER_APPLY_RUNBOOK` « Cookbooks 3–14 = unapplied » en réalité 5–14 (le 3 et le 4 sont faits) :

```
5  Tickets · 6 Knowledge/RAG · 7 Guardrails & Policies · 8 Decisions & actions
9  KPIs & Analytics · 10 Audit/Integrity/Retention · 11 Customers 360 · 12 Agents management
13 Escalations & handoff · 14 Reference catalogs
```

**Note sur la numérotation interne du runbook** : le runbook numérote « C9, C4, C11, C3, … » dans son ordre d'application. Les fichiers `FEATURE_NN_*.md` suivent le numéro du cookbook. Dans ce document je m'en tiens aux noms de fichiers (`FEATURE_04_call_logs.md` = « C4 » du runbook, etc.) pour éviter toute ambiguïté.

---

## Block A — Vérité de base de la base de données (SQL, lecture seule)

### A1 — `max_frustration_score` NULL

```
 null_frustration
------------------
                0
```

**Interprétation.** Zéro ligne NULL. Cohérent avec `conversation.py` : `max_frustration_score: Mapped[float] = mapped_column(Numeric(5,2), nullable=False, server_default=text("0"))` → `NOT NULL DEFAULT 0`. **La prémisse du correctif C4 §8.7 et C8 §8.6 (500 sur `float(None)`) est donc ERRONÉE contre le schéma réel** — le runbook C-1 avait raison de retirer ce guard. Le `coalesce` de `kpis()` et le `or 0.0` de `telemetry_timeline()` sont du défensif, pas une nécessité.

### A2 — Valeurs `channel`

```
 channel | count
---------+-------
 voice   |   129
```

**Interprétation.** 100 % des sessions existantes sont `voice`. **Le canal `chat` n'existe dans AUCUNE ligne réelle.** §A8 + modèle confirment `channel` CHECK `voice|chat`, mais aucune donnée `chat`. Donc : l'UI `/conversations` et toute « conversation chat » ne peuvent pas être alimentées par les données actuelles — le canal `chat` est modélisé mais **jamais peuplé**. Toute porte de Feature future qui associe des `turns` à un canal `chat` retombera à zéro. Voir aussi A8 (les turns viennent uniquement de la voix).

### A3 — Escalades : est-ce qu'une escalade est jamais résolue ?

```
   resolution   | count
----------------+-------
 (null = open)  |    58

 total_escalations : 58
 target : manager_agent → 58
 trigger distinct : hard_failure, abuse, clarify_fail, identity_fail
```

**Interprétation (cette requête répond à D8 + A3).** **58/58 escalades sont OUVERTES.** Aucune escalade n'a jamais été résolue. La colonne `resolution` (CHECK `'transferred'|'queued'|'callback_scheduled'|'resolved'`) n'a **aucune valeur** en base. Le code le confirme : grep global `resolution` dans le code **ne trouve aucun chemin d'écriture** vers `EscalationCase.resolution` — `record_escalation` dans `writer.py` ne fixe que `trigger/target/dossier/session_id/customer_id`, et `repositories.escalations()` ne la lit que. **Donc D8 = vrai : rien ne ferme une escalade aujourd'hui.** Le filtre `status=open` de `/api/v1/escalations` est actuellement décoratif (il retourne les 58). 4 triggers distincts ; tout cible `manager_agent`.

### A4 — Catalogues de référence (Cookbook 14)

```
     t            | count
------------------+-------
 business_rules   |     6
 error_catalog    |     2
 products         |     3
 recharge_catalog |     4
 geo_areas        |    70
 geo_aliases      |   225
```

**Interprétation.** Tous les catalogues **sont peuplés** : 6 règles, 2 codes d'erreur, 3 produits, 4 recharges, 70 zones, 225 alias. Un endpoint serveur n'existe QUE pour `business_rules` (`GET /api/v1/reference/business-rules`, fidèle au contenu, cf. B3). `error_catalog`/`products`/`recharge_catalog`/`geo_areas`/`geo_aliases` **n'ont AUCUN endpoint** en `main.py` aujourd'hui (grep `reference` → une seule route). Donc Cookbook 14 doit les exposer — la donnée est là, prête. Note : le runbook recommande volontairement de **ne pas exposer `geo_aliases`** (probe resolver > table 10k).

### A5 — Vocabulaire de statuts (piège « cellule de chip vide » x12)

```
      k       |     v      | count
--------------+------------+-------
 subscription | ACTIVE     |     3
 customer     | active     |     3
 invoice      | overdue    |     1
 invoice      | partial    |     1
 ticket       | resolved   |     2
 ticket       | open       |    19
 callback     | completed  |     1
 callback     | cancelled  |     1
 callback     | pending    |     7
 advisor      | available  |     7
 advisor      | offline    |     1
 session      | (null)     |   129      ← final_disposition NULL partout
 verdict      | REFUSED    |     1
 verdict      | AUTHORIZED |     3
 verdict      | ESCALATE   |     1
```

**Interprétation (lecture ligne par ligne — crucial pour le mapping `StatusChip`).**

- **subscription** : `ACTIVE` (majuscules) — pas de mixe casse. Une seule valeur vue.
- **customer** : `active` (minuscules) — `status` présent.
- **invoice** : `overdue`, `partial` — PAS de `paid`* (aucune facture soldée en base), donc le mapping doit inclure ces deux-là **en plus** de ceux déjà envisagés.
- **ticket** : `open`, `resolved` — `resolved` existe bien en base (contrairement à ce que pouvait laisser croire A3 pour les escalades ; ici c'est l'état du ticket GLPI).
- **callback** : `pending`/`completed`/`cancelled` — exacte la triade. Conforme à la Feature 3.
- **advisor** : `available`/`offline` — `status` chargé.
- **session** : **`(null)` à 129 lignes** ← **découverte majeure.** `final_disposition` est `NULL` sur **toutes** les sessions en base (les fixtures `f4…` disposées ont été supprimées proprement par le nettoyage Feature 4). Donc le mapping statut de la session doit couvrir `(null)` → `in_progress` / « En cours » — c'est exactement ce que la Feature 4 a fait (`dispositionKey` NULL→`in_progress`). **Aucun `resolved`/`escalated`/`dropped` réellement présent en base** — les valeurs disposées provenaient des fixtures seedées, pas des données réelles.
- **verdict** : `REFUSED`/`AUTHORIZED`/`ESCALATE` (majuscules) — `policy.policy_verdicts` utilisé.

**Implication pour le piège « blank-chip x12 »** : `StatusChip` retourne `null` pour une clé non mappée (cellule invisible, pas une erreur). Les vocabulaires ci-dessus ne présentent **aucune valeur imprévue par rapport aux mappings déjà posés**, MAIS il faut être rigoureux : `verdict` est en **MAJUSCULES** (mapping case-sensitive !), `invoice` manque `paid` en échantillon réel, `session` est 100 % `NULL`. Chaque nouveau cookbook doit réinjecter les valeurs réelles (pas seulement le mock).

### A6 — Volumes (faut-il de la pagination ?)

```
     t         | count
---------------+-------
 call_sessions |   129
 turns         |   490
 customers     |     3
 invoices      |     2
 tickets       |    21
 audit         |    47          ← audit.audit_ledger (le nom exact, pas audit_ledger_entries)
 verdicts      |     5          ← policy.policy_verdicts
 actions       |     0          ← execution.action_ledger
```

**Interprétation.** Volumes **minuscules** (max 490 turns, 129 sessions). Pour un admin local : pas besoin de pagination **dure** côté plein. La pagination (limite/Load-more de la Feature 4, limite 100 etc.) est déjà en place et correcte, mais n'est pas un problème d'échelle ici. `actions` = **0 ligne** → la page `/api/v1/actions` et toute « liste d'actions » sera vide (état vide, pas d'erreur). Le nom réel de la table d'audit est `audit.audit_ledger` (le questionnaire `audit_ledger_entries` est faux).

### A7 — `advisor_shifts` (reconstruction 33-lignes)

```
 shift_rows
------------
         31
```

**Interprétation.** La table contient **31 lignes**, pas 33. Le runbook H-2 rapporte qu'une reconstruction a produit 33 lignes « prouvées équivalentes à l'audit v73 » ; l'échantillon actuel est de **31**. Écart de 2 lignes. À réévaluer lors de la Feature 2/12 : soit 31 est le bon état courant (les 2 manquantes étaient des artefacts de reconstruction), soit il manque 2 lignes. **À ne PAS résoudre par un TRUNCATE** (H-2 : interdiction). À vérifier contre `routing.advisor_shifts` et l'audit.

### A8 — Personas d'agent présents dans les données réelles (Cookbook 12)

```
     persona        | count
-------------------+-------
 TriageAgent        |   240
 TechnicalAgent     |   142
 BillingAgent       |    50
 AccountServicesAgent|   34
 ManagerAgent       |   24
```

**Interprétation.** Cinq personas réels, exactement `conversation.turns.active_agent`. **Découverte majeure pour Cookbook 12 §8.1 : Toutes les lignes ont un `active_agent` renseigné, MAIS ces lignes sont exclusivement des tours `caller`** (voir Block C1 — `base_agent.py` n'enregistre jamais $speaker="agent"$). Donc la métrique « Attributed turns » de C12, si elle compte les tours par persona, ne compte **que la moitié de la conversation** (les tours client), car les tours agent ne sont **jamais persistés**. Ce n'est pas un bug de count mais un problème de définition de la métrique — à corriger dans le libellé ou en écrivant aussi le tour agent.

### A9 — SoftDelete : la vraie colonne

```
 billing | accounts     | deleted_at
 crm     | customers    | deleted_at
 crm     | subscriptions| deleted_at
```

**Interprétation.** Le colonne s'appelle **`deleted_at`** (pas `is_deleted`, pas `archived_at`, pas `soft_delete`). Les trois tables master (`accounts`, `customers`, `subscriptions`) l'ont. Le reste sont des tables système. **La classe `SoftDelete` de `persistence/base.py` (lu Block C2) définit bien `deleted_at: Mapped[datetime | None]`** → cohérent avec le schéma. Mais `CustomerInteraction`, `ConsentRecord` et les pré-références **n'héritent pas de `SoftDelete`**. Cookbook 11 F8 confirmé : la colonne est `deleted_at`.

### A10 — Y a-t-il des trous dans `turn_index` (hypothèse de drop d'écriture) ?

```
 session_id | turns | max_idx
------------+-------+---------
 (0 rows)
```

**Interprétation.** **Aucun trou.** Pour chaque session, `count(turns) == max(turn_index)`. L'hypothèse du « dropped-write » (sessions dont le nombre de tours < index max) **n'est pas soutenue par les données** : pas de trou dans les indexes sur l'échantillon réel. Le silent-turn (Phase 2) n'est donc **pas** causé par des tours perdus en écriture avec des trous d'index — les tours présents sont contigus. À lire comme un signal : si des tours sont perdus, ils le sont *avant* d'arriver au writer, pas dans l'écriture (cohérent avec le fait que `record_turn` n'est appelé que pour `caller`, Cf. Block C1).

---

## Block B — Environnement, services et frontend

### B1 — Services en cours d'exécution (docker compose ps)

```
docker-compose-business-api-1      0.0.0.0:8108   Up (healthy)
docker-compose-agent-worker-1      (pas de port)   Up 14h
docker-compose-ai-knowledge-rag-1  0.0.0.0:8201   Up (healthy)
docker-compose-execution-service-1 0.0.0.0:8105   Up (healthy)
docker-compose-ticketing-glpi-1    0.0.0.0:8202   Up
docker-compose-messaging-gateway-1 0.0.0.0:8203   Up
docker-compose-context-service-1   0.0.0.0:8101   Up (healthy)
docker-compose-knowledge-service-1 0.0.0.0:8102   Up (healthy)
docker-compose-nms-sim-1           0.0.0.0:8110→8108  Up (healthy)
docker-compose-policy-service-1    0.0.0.0:8104   Up (healthy)
docker-compose-ocs-billing-sim-1   0.0.0.0:8109→8107  Up (healthy)
docker-compose-token-service-1     0.0.0.0:8107   Up (healthy)
docker-compose-provisioning-sim-1  0.0.0.0:8111→8109  Up (healthy)
docker-compose-notification-service-1 0.0.0.0:8106 Up (healthy)
docker-compose-decision-service-1  0.0.0.0:8103   Up (healthy)
docker-compose-minio-1             0.0.0.0:9000-9001 Up (healthy)
docker-compose-redis-1             0.0.0.0:6379   Up (healthy)
docker-compose-qdrant-1            0.0.0.0:6333   Up (healthy)
docker-compose-otel-collector-1    0.0.0.0:4317-4318 Up
docker-compose-postgres-1          0.0.0.0:5432   Up (healthy)
```

**Interprétation.** 21 conteneurs, 20 sains ou en service. `business-api` sur **8108**. **`ticketing-glpi` est Up mais sans `(healthy)`** — c'est le seul non-healthy de la pile (dépend des credentials GLPI live, H-4). Volontairement : le ticketing est live-only, pas de mock. **Attention au mapping des ports simulateurs** : `nms-sim` écoute à l'extérieur sur **8110→8108 interne**, `ocs-billing-sim` sur **8109→8107 interne**, `provisioning-sim` sur 8111→8109. Donc `NMS_ADAPTER_URL=http://nms-sim:8108` pointe sur le **port interne 8108** (pas de collision avec business-api qui, lui, est exposé en 8108 hôte). Voir B5.

### B2 — Valeurs d'env qui changent le comportement (secrets masqués)

| Clé | Valeur réelle (racine `.env`) | Commentaire |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:5174` | 2 frontends locaux autorisés |
| `BUSINESS_API_DEFAULT_ROLE` | `administrateur` | rôle par défaut si aucun header `X-Role` |
| `INTERNAL_API_KEY` | `(set)` = `dev-key-123` | défini ! → **H-4 actif** : C6 testera bien en 403-branch en local |
| `CALLBACK_TIMEZONE` | `(unset)` → défaut code `Africa/Tunis` | lu dans `availability.py`, `callbacks.py`, `callback_schedule_task.py` |
| `CALLBACK_DAY_START_HOUR` / `END_HOUR` | `(unset)` → défauts `8`/`18` | lu `availability.py` |
| `CALLBACK_SLOT_MINUTES` | `(unset)` → défaut `30` | lu `callbacks.py` |
| `CALLBACK_LEAD_MINUTES` | `(unset)` → défaut `30` | lu `callbacks.py` |
| `STRICT_PERSONA_CONTRACT` | `(unset)` | **jamais défini** → `enforce_contract` dégrade en `logger.error` (persona contract invisible en prod), cf. FEATURE_12 §8.2 |
| `BUSINESS_API_URL` (racine) | `(unset)` | le frontend a le sien : `http://localhost:8108` |
| `KNOWLEDGE_API_URL` | `(unset)` | défaut code `http://localhost:8102` |

**Interprétation.** Toutes les valeurs CALLBACK_* **ont des défauts de code explicites** (grep dans `apps/business-api/*.py` et `apps/agent-worker`) : même non définies dans `.env`, le comportement est `Africa/Tunis`, 8–18 h, slots de 30 min, lead de 30 min. Aucune surprise là-dessus. **Deux leviers réellement actifs** : `INTERNAL_API_KEY` (défini → connaissance C6), et l'absence de `STRICT_PERSONA_CONTRACT` (violations de contrat persona invisibles en production — à décider en C12).

### B3 — Gate de rôle + contrôle de live

```
health                    → 200
kpis(sup)                 → 200   (superviseur)
kpis(cons)                → 403   (conseiller refusé — gate fonctionnel)
esc(sup)                  → 200   (/api/v1/escalations)
rules(adm)                → 200   (/api/v1/reference/business-rules, administrateur)
rules(cons)               → 403   (conseiller refusé — gate fonctionnel)
```

**Interprétation.** Le RBAC **fonctionne réellement** à la frontière : rôle correct → 200, un cran en dessous → 403. `kpis` est bien `superviseur` (conseiller → 403), et `/reference/business-rules` est **`administrateur`** (conseiller → 403). Cela répond au runbook gate §5.11 : le pattern est validé.

### B4 — Forme des deux réponses

```
GET /kpis  (X-Role superviseur) → 200 :
{"total_sessions":129,"resolved":0,"escalated":0,"containment_rate":0.0,
 "escalation_rate":0.0,"avg_frustration":0.0}

GET /escalations (X-Role superviseur) → 200 : {"escalations":[
  {"id":"e078…","session_id":"89b7…","trigger":"abuse","target":"manager_agent",
   "resolution":null,"dossier":{...}},
  {"id":"f16d…","trigger":"hard_failure","target":"manager_agent","resolution":null,"dossier":{...}},
  …]}
```

**Interprétation critique (confirme D7).**
- `/escalations` renvoie `id`, `session_id`, `trigger`, `target`, `resolution`, `dossier`. **PAS de `created_at`, PAS de `customer_id`.** Donc la page escalations ne peut **ni afficher « quand ça s'est produit » ni lier le client** — exactement la prémisse de D7.
- `/kpis` a déjà une forme plate (pas de clé wrapper) : la Feature 9 (KPIs) devra décider la forme ; les champs `resolved`/`escalated`/`containment_rate`/`escalation_rate`/`avg_frustration` sont là.

### B5 — Collision de port

```
TCP  0.0.0.0:8108  LISTENING  (PID 2212 = docker-proxy business-api)
TCP  0.0.0.0:8109  LISTENING
TCP  0.0.0.0:8201/8202/8203 LISTENING
TCP  [::1]:8108     LISTENING (PID 19208)
TCP  [::1]:8109     LISTENING (PID 19208)
```

**Interprétation.** Un seul processus écoute sur `8108` hôte ? Non : la ligne `[::1]:8108` (PID 19208) est un écouteur **IPv6 loopback** distinct de `0.0.0.0:8108` (PID 2212, docker-proxy business-api). Pas de collision réelle : business-api (hôte :8108) et ocs-billing-sim exposé en :8109 (interne :8107), nms-sim exposé en :8110. **Pas de conflit** — les simulateurs internes 8108/8107 ne sont pas exécutés sur les mêmes ports hôte externes. Le questionnaire craignait « ocs-billing-sim vs business-api sur 8108 » : en réalité ocs est sur 8109 hôte, business-api sur 8108 hôte ; pas de collision.

### B6 — Baselines frontend

```
bun --version → 1.3.14
bunx tsc --noEmit → CLEAN (exit 0)
bun run lint → 2704 errors (prettier) + erreurs → exit 1
```

**Interprétation.** `/policies` dispose d'un `tsc` **propre** (exit 0) et d'un build clean. **Le lint n'est PAS à 36 problèmes** comme le fige le runbook §5.2 : il est à **2704 erreurs prettier** (le runbook a été écrit plus tôt ; depuis, le template Lovable a injecté beaucoup plus de fichiers, ce papier n'est pas re-figé). Toutes les erreurs de lint sont du `prettier/prettier` (formatage/CRLF), **aucune erreur de type ou de logique**. Voir F1/F2 pour la conséquence sur le gate d'acceptation.

### B7 — Signatures primitives (le piège qui a mordu Feature 1)

Relevé réel dans `src/components/nexus/primitives.tsx` :

```ts
EmptyState   ({ icon: Icon, title, description }: { icon, title, description })   // L368
TableShell   ({ toolbar?, head, children, footer? }: {...})                       // L390
Th           ({ children?, className?, align?: "left"|"right"|"center" })         // L421
Td           ({ children?, className?, align?: ... })                             // L446
SearchInput  ({ placeholder, className?, value?, onChange?: (v:string)=>void })   // L471  ← type="search"
Tabs         ({ items: string[], active, onSelect? })                             // L509  ← items=string[], active=string
Segmented    ({ items: string[], active, onSelect?, className? })                 // L544
```

**Interprétation.** Les signatures réelles des primitives sont telles qu'affichées. Points à respecter pour les 10 cookbooks suivants :
- `SearchInput` est **`type="search"`** et contrôlé (`value`/`onChange`) — tout usage non contrôlé cassera.
- `Tabs`/`Segmented` prennent `items: string[]` **et** `active: string` **par label/texte**, pas par objet `{key,label}`. C'est la forme qui a posé problème en Feature 1 (le guide nommait une autre forme).
- `EmptyState` prend `icon` (composant), `title`, `description` (tous requis).
- `Td`/`Th` ont `align` paramétrable (left/right/center) — utile pour les colonnes numériques.
- `TableShell` compose `toolbar`/`head`/`children`/`footer`.

### B8 — `formatPercent` : 0–1 ou 0–100 ?

```ts
// src/lib/nexus/format.ts L17-23
export function formatPercent(value: number, digits = 1): string {
  return new Intl.NumberFormat(LOCALE, { style:"percent", minimumFractionDigits:digits, maximumFractionDigits:digits }).format(value);
}
```

**Interprétation.** `Intl` `style:"percent"` attend une **fraction 0–1** : `formatPercent(0.5)` → `"50.0%"`, `formatPercent(1)` → `"100.0%"`. Donc **`formatPercent` est un contrat 0–1**. Si une donnée arrive en 0–100 (ex. `containment_rate` …), il faut diviser par 100 d'abord puis appeler `formatPercent`, ou utiliser le `formatRatio` que la Feature 9 (KPIs) introduit. La prudence du runbook (C9 ship son propre `formatRatio`) est justifiée. `formatDelta` prend du 0–100 (rend `+12.4%`), ne pas confondre avec `formatPercent`.

### B9 — `INGESTED_FILES` est-il encore utilisé ailleurs ? (sécurité de suppression, Cookbook 13)

```ts
src/routes/conversations.tsx:15  import { CONVERSATIONS, THREAD, INGESTED_FILES } from "@/lib/nexus/data";
src/routes/conversations.tsx:149 {INGESTED_FILES.map((f) => (…))}
src/routes/conversations.tsx:162 <Token>{INGESTED_FILES.length} sources</Token>
```

**Interprétation.** **`INGESTED_FILES` est ENCORE utilisé par `src/routes/conversations.tsx`** (panel d'ingestion). Donc **ne pas supprimer `INGESTED_FILES` de `data.ts` tant que `/conversations` l'importe.** Le runbook C13 (§3.3) dit exactement ça : « `grep -rn "INGESTED_FILES" src/` must return zero hits before deletion ». **Aujourd'hui ce grep retourne des hits** → le prérequis N'EST PAS satisfait. Il faut d'abord traiter `/conversations` (suppression du panel d'ingestion par C13, ou conservation), sinon c'est le build-break le plus probable du lot. En revanche `RULES` (importé par `rules.tsx`), `CONVERSATIONS`, `SETTINGS_SECTIONS` sont les cibles légitimes de suppression dans leurs cookbooks respectifs.

### B10 — Comment `routeTree.gen.ts` est régénéré ici

```jsonc
// package.json (Frontend/admin_dashboard)
"scripts": { "dev":"vite dev", "build":"vite build", "build:dev":"vite build --mode development",
             "preview":"vite preview", "lint":"eslint .", "format":"prettier --write ." }
```

**Interprétation.** Il n'y a **pas de script dédié** de « generate routeTree ». Le fichier `routeTree.gen.ts` est régénéré **automatiquement par le plugin TanStack Router lors du `dev`/`build`** (`@tanstack/router-plugin` en `devDependencies`). Donc le workflow du runbook (§3.5 « let the dev server regenerate after each route add/rename/delete ») correspond à la réalité : rouler `bun run dev` (ou `build`) régénère `routeTree.gen.ts` à chaque changement de route, puis on le commit avec le cookbook. Aucune commande manuelle nécessaire.

---

## Block C — Les trois fichiers manquants, lus

### C1 — `apps/agent-worker/src/server.py`, handler `conversation_item_added` (Cookbook 12 §8.1)

```python
@session.on("conversation_item_added")
def _on_conversation_item_added(event: ConversationItemAddedEvent):
    item = event.item
    if not isinstance(item, ChatMessage):
        return
    text = item.text_content
    if not text:
        return
    if item.role == "user":          # ← caller
        logger.info("🎤 Caller: %s", text)
    elif item.role == "assistant":   # ← agent
        logger.info("🤖 Agent: %s", text)
```

**Interprétation — c'est décisif.** Ce handler ne fait que **journaliser** (log). Il ne **persiste rien**. La persistance des turns est ailleurs : `apps/agent-worker/src/conversation/writer.py` + `apps/agent-worker/src/agents/base_agent.py`. Le point clé, **prouvé par A8 + grep `speaker=` / `record_turn`** :

> **`record_turn` n'est appelé qu'avec `speaker="caller"`** (`base_agent.py:181`). **Les tours agent (`speaker="agent"`) ne sont JAMAIS écrits.**

Vérification (grep dans `apps/agent-worker`) : aucun `speaker="agent"`, un seul appel de `record_turn` (le caller). Conséquence concrète : les `conversation.turns` ne contiennent que des tours client, chacun tamponné avec l'`active_agent` (persona) au moment du tour. **Réponse à la question : oui, les tours caller portent `active_agent` ; non, les tours agent ne sont pas du tout persistés.** La métrique « Attributed turns » de Cookbook 12, si elle compte les `turns` par `active_agent`, mesure donc **uniquement la moitié réelle de la conversation** (tours client) et son libellé doit le dire, ou il faut ajouter l'écriture du tour agent. C'est exactement l'hypothèse que C12 §8.1 voulait lever — elle est **confirmée comme étant un écart réel**.

### C2 — `packages/persistence/src/persistence/base.py` (fichier complet, 54 lignes)

```python
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("uuid_generate_v4()"))

class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class SoftDelete:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Interprétation (répond à Cookbook 11 F8 et la question `updated_at`).**
- **`SoftDelete` = `deleted_at`** (nullable), cohérente avec A9.
- **`Timestamps` = `created_at` **et** `updated_at`** (tous deux NOT NULL DEFAULT now()). Donc tout modèle qui hérite de `Timestamps` a les deux. MAIS — et c'est le piège pour D12 — **plusieurs modèles N'héritent PAS de `Timestamps`** : `ErrorCatalog`, `Product`, `RechargeCatalog`, `GeoAlias` (voir Block D12). Ceux-là n'ont **que `created_at`**, pas d'`updated_at`. Donc la réponse à « est-ce que `Timestamps` donne `updated_at` à tous les modèles que j'ai supposés ? » est : **non pour les catalogues de référence** qui ne l'héritent pas.

### C3 — `apps/agent-worker/src/tools/` : les trois modules non audités (Phase 2 S2)

**`routing_tools.py`** (63 lignes) — trois `@function_tool` de handoff :

```python
route_to_billing(context)      → BillingAgent
route_to_technical(context)    → TechnicalAgent
route_to_account_services(…)  → AccountServicesAgent
```

Chacun résout la langue (`voice_flow.current_chat_ctx`) et appelle `handoff_with_message(context, agent, DOMAIN_BY_KEY[...].lines[lang])`. **Aucun appel non-encadré / aucune attente longue / aucun `foreground()`.** Ils retournent un `Agent` — si le handoff bloque, c'est par le mécanisme de handoff, pas ici.

**`outcomes.py`** (66 lignes) — pur contrat de retour, **aucun IO** :

```python
refused(rule_id, reason)       → {"outcome":"refused", ...}
escalate(rule_id, reason)      → {"outcome":"escalate", ...}
executed(action_type, reference, replay=False) → {"outcome":"executed", ...}
failed(reason, message=None)   → {"outcome":"failed", ...}
```

Uniquement des dicts constants. **Zéro surface de silence possible** ici.

**`ticket_tools.py`** (430 lignes) — la vraie charge IO des tools. Points pertinents pour la Phase 2 (silence) :

- `_mcp_call()` fait un appel MCP streamable **asynchrone** vers `ticketing-glpi` (`streamablehttp_client` + `ClientSession`), avec `httpx` sous le capot. C'est **là** qu'un blocage réseau/serveur peut exister. `_unavailable()` est le filet de vérité (déclare honnêtement « unavailable »), mais un appel MCP qui **pend** (pas d'erreur, pas de `TicketingUnavailable`) peut laisser l'agent muet.
- `create_support_ticket`, `check_customer_tickets`, `get_ticket_state`, `mark_ticket_resolved`, `update_support_ticket`, `delete_support_ticket` — tous passent par `_mcp_call`.
- Le module **n'utilise pas `context.foreground()`** (contrairement à `guards.ensure_identity_verified`). Donc un appel MCP attendu pendant le tour du modèle **rivalise avec la planification de parole** et peut produire le creux de silence — **c'est exactement l'hypothèse d'audit S2** : les tools qui font de l'IO coroutinale non-`foreground` sont le lieu où le silence se cache.

**Rappel du patch Phase 2** (`tools/guards.py`). `ensure_identity_verified` (lu) encapsule déjà `IdentityVerificationTask` dans `async with context.foreground()`. Le runbook v79 š `handoff loop guard` et š `identity timeout hierarchy` sont présents (GATE_TIMEOUT_S=60, hiérarchie commentée). Donc le patch cible **le guard d'identité** ; l'audit de `ticket_tools` indique que **les autres tools d'IO MCP** (tickets notamment) pourraient être la cause restante si l'identité était déjà résolue.

---

## Block D — Jugements

**Réponse globale : je prends les recommandations préremplies (all defaults), avec corrections ci-dessous motivées par des preuves de terrain.**

### D1 — Plancher de rétention (seul capable de détruire des données)
**Réponse : OUI, clamp à 30 jours minimum, rejeter plus bas avec 422.**

**Preuve vécue** — appel réel :

```
POST /api/v1/jobs/retention?retention_days=-5&dry_run=true  (X-Role administrateur) → 200
{"cutoff":"2026-08-09T06:36:38Z","sessions_matched":129,"turns_anonymized":0,"dry_run":true}
```

`retention_days=-5` a **matché les 129 sessions** (cutoff dans le futur = tout). Si `dry_run=false`, tout serait passé à `[purged]` + suppression des blobs audio. Le code (`apps/business-api/src/business_api/jobs/retention.py`) **n'a aucun plancher** — la route `POST /api/v1/jobs/retention` (`main.py:149`) passe `retention_days` tel quel. **À corriger avant Cookbook 10.** Un clamp serveur (>=30, sinon 422) rend le cas catastrophique inatteignable. Directement le hazard H-1 du runbook.

### D2 — Protection UUID sur `customer_360`
**Réponse : DÉJÀ EN PLACE** (recommandation obsolète — je ne « ship » donc rien, le garde existe).

Preuve réelle :

```
GET /api/v1/customers/not-a-uuid/360 (X-Role conseiller) → 404   (pas 500)
```

`customer_360` → `to_uuid(customer_id)` (`repositories.py:25`), et `to_uuid` renvoie `None` pour une valeur non-UUID (`util.py:16-18`) → la branche `if customer is None: return None` → 404. **Le runbook H-5 affirme « malformed id yields 500 » ; vérification à chaud : c'est 404.** Le guard était donc déjà dans le code. Rien à ajouter (ou très bien, à confirmer si la version du runbook est plus ancienne que le code actuel). Garde-baisse des 500 : déjà absente.

### D3 — Qui lit les catalogues de référence ? (Cookbook 14)
**Réponse : recommander la nuancée** — erreurs/produits/recharges en **`superviseur`**, zones (`geo`) en **`administrateur`**.

État actuel : seul `GET /api/v1/reference/business-rules` existe, en **`administrateur`** (prouvé : conseiller → 403). Pour les 5 autres catalogues, il n'y a **pas d'endpoint** du tout encore — donc le choix de rôle se fera à l'implémentation de C14. Données contexte : messages d'erreur et liste de plans ne sont **pas sensibles** ; les zones géographiques (reseaux/incidents) sont plus délicates. Je rejoins la recommandation : `superviseur` pour errors/products/recharges, `administrateur` pour `geo_areas`. Si vous préférez l'uniformité, `administrateur` partout reste acceptable — ça évite un second rang à positionner.

### D4 — Même question pour `/policies`
**Réponse : OUI, superviseur en lecture seule.**

`GET /api/v1/policy/verdicts` est déjà **`superviseur`** (vérifié dans `main.py`). La page `/policies` (frontend, actuellement mock) doit donc lire via un endpoint `superviseur` en lecture seule pour rester cohérente avec la matrice §17. Aucun endpoint d'écriture n'existe pour les policies — on garde la lecture-only. Rejoint la recommandation.

### D5 — Authentification admin (pas de store d'utilisateurs)
**Réponse : OUI, un seul credential partagé est acceptable pour l'instant ; scoper le multi-user avant toute sortie machine.**

Prouvé : `admin auth` est **une paire d'env** (`ADMIN_EMAIL`/`ADMIN_PASSWORD`/`ADMIN_ROLE`), lue via `config.ts` dans `auth.server.ts` — pas de table utilisateurs, ni hash, ni sessions multiples, ni UI de gestion admin. Le runbook (C10 §8.3, C11 §0.3) le signale et le frontend `.env.example` commente « stop-gap until OIDC ». **Acceptable en local/dev. À scoper en cookbook propre** (table users, hash, sessions, UI) avant toute exposition hors machine de développement.

### D6 — Santé des services fabriquée
**Réponse : OUI, ships Cookbook 9 sans le champ ; approbation d'un cookbook séparé pour les vrais probes.**

Prouvé : `system_overview()` (`repositories.py:217-229`) renvoie **11 services codés en dur `"status":"online"`** — aucun probe réel. Le runbook a raison de le retirer plutôt que d'afficher un mensonge. Les vrais probes (fan-out vers 11 `/health` avec timeouts) sont **une nouvelle logique métier** = cookbook propre, à approuver. Pas dans C9.

### D7 — Deux champs additifs sur `/api/v1/escalations`
**Réponse : OUI, ajouter `created_at` et `customer_id`** (additif, aucun impact pour l'autre consommateur).

Prouvé (B4) : le payload actuel n'a ni `created_at` (pourtant l'ordre est `created_at desc`) ni `customer_id`. La page ne peut donc ni dater ni lier. Ajout **additif** de deux clés dans le dict de `escalations()` — un consommateur JSON ignore les clés inconnues. `apps/supervisor-dashboard` (2e consommateur) ne casse pas. Je m'engage à l'ajouter dans le cookbook escalations.

### D8 — Est-ce que quelque chose ferme une escalade ?
**Réponse (prouvé) : NON — rien ne clôt une escalade aujourd'hui.** A3 = 58/58 ouvertes.

Aucun chemin de code n'écrit `EscalationCase.resolution` (grep `resolution` → rien côté écriture ; `record_escalation` ne le fixe pas). Le filtre `status=open` est donc décoratif. **Question aiguë : où doit se faire la clôture ?** Options : (a) le tableau de bord de supervision (un bouton « marquer transféré/résolu »), (b) manuellement en SQL, (c) pas encore construite. **Ma recommandation** : modéliser `resolution` comme **transition de workflow** dans le supervisor dashboard (action superviseur), alimentée par un endpoint dédié (ou au minimum documenter le SQL). Voir FEATURE_04 vs FEATURE_13 — c'est le cœur de Cookbook 13 (Escalations & handoff).

### D9 — Le moteur d'automatisation `/rules`
**Réponse : OUI, filler — leave it retired / réutiliser le slot pour `/reference`.**

Prouvé : `rules.tsx` rend un mock `RULES` depuis `data.ts` (« Trigger → action → run count ») ; **il n'existe aucun moteur** (0 table ML, `execution.action_ledger` vide : A6 actions=0, aucun endpoint « trigger/action »). FEATURE_14 repurposes le slot en `/reference`. Le runbook C-3 rappelle que la recommandation de retirer `/rules` a été retirée : on suit FEATURE_14, on n'annule pas `/rules` en tant que « doublon de `/policies` », on le **rubrique** en `/reference`.

### D10 — Quatre tables modélisées mais non exposées
**Réponse : hors périmètre pour l'instant — pas de Cookbook 15.** Les 4 (`CustomerInteraction`, `Payment`, `PaymentPlan`, `ConsentRecord`) sont modélisées (présentes dans `crm.py`/`billing.py`) mais **aucun endpoint ni UI** ne les expose. Quand un vrai besoin métier apparaîtra (historique paiement client = utiles pour le 360), on fera un cookbook dédié avec pagination. Je ne les force pas dans un cookbook existant.

### D11 — Champs de cycle de vie des callbacks
**Réponse : DÉJÀ exposés — l'amendement est devenu inutile** (constat de terrain).

`apps/business-api/src/business_api/callbacks.py` `to_dict()` **renvoie déjà** : `attempts`, `outcome_note`, `completed_at` (isoformat), `assigned_advisor_id`, `overdue`, `customer_id`, `customer_name`, `customer_phone`. La Feature 3 a **surfacé** ces champs-« preuve » bien plus que le guide ne le montre. Donc Cookbook 3 **n'a pas besoin** de l'amendement proposé ; cela fait partie de ce qui est déjà appliqué. S'il y a un manque, c'est côté UI (présentation), pas côté API.

### D12 — `updated_at` sur les catalogues de référence
**Réponse : OUI, en tant que migration délibérée (pas glissée dans un cookbook).**

Prouvé (modèles lus) : `ErrorCatalog`, `Product`, `RechargeCatalog`, `GeoAlias` **n'héritent pas de `Timestamps`** → ils n'ont que `created_at`. `BusinessRule` et `GeoArea` **en** héritent (→ `updated_at`). Pour répondre « quand tel plan a-t-il changé ? » il faut ajouter `Timestamps` (ou au moins `updated_at`) sur les 4 → **c'est une migration de schéma** (ajout colonne + backfill + trigger `set_updated_at`). Je le fais comme migration autonome, pas dans Cookbook 14.

### D13 — Topologie de déploiement (policy vs business-api partagent-ils env_file ?)
**Réponse (prouvé, infra locale) : OUI, ils partagent le même `env_file: [../../.env]`.**

`infra/docker-compose/docker-compose.apps.yml` : `policy-service` (L65-74) **et** `business-api` (L112-124) pointent tous deux `env_file: [../../.env]` (même racine). Et `/api/v1/reference/business-rules` **superpose** les seuils `POLICY_*` depuis les mêmes env (via `policy_view.overlay`). Donc dans ce dépôt/ce compose, les seuils affichés = seuils appliqués.

**⚠️ Portabilité** : ces seuils viennent du **même `.env` racine**. Si, dans un autre environnement, `policy-service` et `business-api` utilisaient des env_file distincts (deploy/secrets ou autres), l'écran `/policies` afficherait des seuils différents des seuils réellement appliqués (silencieusement faux). **Contrainte d'environnement à écrire dans la doc de déploiement** : les deux services doivent lire exactement le même fichier `POLICY_*`. Dans `deploy/secrets/.env.example`, il n'y a pas de duplication des `POLICY_*` entre services — à garder singleton.

### D14 — Colonne « Handled » lâchée de la Feature 1
**Réponse : OUI, leave it out** (ne pas ajouter d'endpoint pour une seule colonne).

Un « handled per advisor » exige un `GROUP BY advisor` non exposé aujourd'hui. Le prior : pas d'endpoint dédié pour une seule cellule. Si le superviseur a besoin du volume par conseiller, ce sera soit via les KPIs (Feature 9) soit une extension plus large. Rejoint la recommandation.

---

## Block E — Phase 2, le bug du silent-turn

### E1 — version livekit-agents dans le conteneur worker
**Prouvé :**
```
docker exec docker-compose-agent-worker-1 pip show livekit-agents → Name: livekit-agents, Version: 1.6.5
```
**La version installée est exactement 1.6.5** — celle sur laquelle le patch Phase 2 a été écrit et testé. Donc `RunContext.foreground()` et la hiérarchie des timeouts sont au bon endroit, aucun déplacement du fix n'est nécessaire. Bonne nouvelle : le plancher du patch est confirmé contre la version réelle.

### E2 — Quel outil est en vol quand il devient silencieux ?
**Pas reproductible à partir du repo seul.** J'ai lu `ticket_tools.py` (Block C3) et `guards.py` : le patch Phase 2 ne couvre **que `ensure_identity_verified`** (`guards.py`, via `foreground()`). Les **autres tools d'IO** — notamment les 6 outils **tickets** MCP (`create_support_ticket`, `check_customer_tickets`, `get_ticket_state`, `mark_ticket_resolved`, `update_support_ticket`, `delete_support_ticket`) — font des appels MCP corroutinaux **sans `foreground()`**, donc candidats au même creux de silence si un appel pend.

**Réponse à votre scénario (« d'accord je vais vérifier ça » puis silence)** : « vérifier un truc » = presque certainement **un tool de lecture d'état** : `check_customer_tickets` (vérif des tickets du client), `get_ticket_state` (état d'un ticket), ou un `knowledge_search`/lecture métier. **Le plus probable : `check_customer_tickets` / `get_ticket_state`** (lecture distante via MCP). Si le silence survient sur ces lectures (identité déjà résolue), le patch actuel (centré identité) est **incomplet** → la cause restante est bien l'IO coroutine MCP non-`foreground`. **Pour fermer E2 il me faut la saisie réelle de l'occurrence** : vérif d'une facture ? d'un plan ? d'une panne ? ouverture de ticket ? vérif d'identité (CIN) ?

### E3 — Log du worker autour d'une occurrence
**Aucun log exploitable remonté** (grep `tool|function|foreground|timeout|dropped|silence|caller_transcript` sur `docker logs --since 24h` → **vide**).

Deux explications possibles : (1) aucune occurrence silencieuse sur les dernières 24 h dans ce conteneur (peu d'appels test), ou (2) le log au niveau INFO ne capture pas l'événement incriminé (le handler `conversation_item_added` logue `🤖 Agent:` et `🛠️✅ Tools executed:` à INFO — un vrai blocage MCP laisserait une trace d'erreur, mais si l'appel « pend » sans exception, rien n'est logué → absence de preuve). Pour avancer il faut : la ligne `🛠️✅ Tools executed:` **juste avant** le silence, et le `timeout`/`foreground` éventuel. Je peux relire `docker logs docker-compose-agent-worker-1` avec un filtre plus large (`🛠️`, `Agent:`, `identity`, `MCP`, `TicketingUnavailable`) si vous voulez que je replonge.

---

## Block F — Processus (vous avez dit que l'application prend trop longtemps)

### F1 — Douze applications séparées : option de regroupement
**Réponse : (b) trois lots — je prends votre recommandation.** Relation coût/avantage correcte :
- (a) 12 commits : plus sûr, plus lent, bisect propre ;
- (b) **3 lots** (~3 sessions) : un échec impose de bisecter ~4 cookbooks ;
- (c) méga-patch : plus rapide à coller, pire mode de défaillance (une erreur de type et rien ne construit, sans bisect).

**B. Détail des lots** (en respectant la contrainte « C9 en premier dans le lot 2 sinon C11/C12 ne compileront pas » — c'est LE seul vrai couplage de compilation, §1 du runbook) :

```
Lot 1 — sans backend (0 backend) :
   C5 Tickets · C6 Knowledge/RAG · C7 Guardrails & Policies · C13 Escalations & handoff
   (C13 est 0-backend dans le runbook, ce qui est cohérent avec la découverte D8/D7 :
    il faut d'abord les champs additifs escalations — je les inclus avec C13.)

Lot 2 — backend-léger (+2 par cookbook) :
   C9 KPIs          ← EN PREMIER (débloque blocks.tsx delta? pour le lot 3)
   C4 Call logs     (déjà appliqué ! voir Q0.1 — donc sort de ce lot)
   C8 Decisions & actions
   C14 Reference catalogs

Lot 3 — lourd (+2 par cookbook) :
   C10 Audit/Integrity/Retention      ← avec plancher D1 + correction C-2 (formatInteger)
   C11 Customers 360
   C12 Agents management
```

**Ajustement terrain** : FEATURE_04 (call logs) **est déjà appliqué** (Q0.1) ; je le **retire** du lot 2 — il n'y a donc que **11 cookbooks réels**, pas 12. C9 reste premier du lot 2 (contrainte `delta?`). Chaque lot = un commit par cookbook à l'intérieur (on garde du bisect intra-lot), 3 sessions. C9 avant C11/C12 : non négociable.

### F2 — Un seul diff consolidé par lot aiderait-il plus que les cookbooks ?
**Réponse : les deux — les cookbooks, plus un diff plat par lot ; mais gardez la prose.**

Les cookbooks sont des **documents d'enseignement** (raisonnements, alternatives rejetées, checklists) : utiles pour comprendre *pourquoi*, mais lourds en application mécanique. Un **diff plat (`diff-only` git apply-able) émis par lot** accélère l'application **à condition de conserver le contexte** : chaque diff-plat doit inclure (1) les headers de combinaison minimale, (2) le commentaire du §3 collision si l'ordre de déclaration des routes compte (ex. C11 avant `/customers/{id}/360`, C4 avant `/sessions/{id}`), (3) les greps de sortie attendus. **Recommandation** : je produis, par lot, un fichier `diff` prêt à `git apply` + les greps de gate dans un fichier `gate.md` par lot, *en plus* des cookbooks, pas à la place. Le méga-collable pur sans prose serait une erreur pour le bisect (option f) refusée.

---

## Bonus — Réconciliations de données découvertes pendant cette passe

1. **`audit.audit_ledger`** est le nom réel (le questionnaire disait `audit_ledger_entries`). A6 = 47 lignes.
2. **`execution.action_ledger` = 0 ligne** → toute « liste d'actions » sera vide (state vide attendu).
3. **`final_disposition` = NULL sur toutes les 129 sessions** concrètes (les fixtures à disposition ont été purgées au nettoyage Feature 4). → `dispositionKey` de la Feature 4 (NULL→`in_progress`) est exactement le bon comportement.
4. **`geo_areas` (70) + `geo_aliases` (225) sont peuplés** mais sans endpoint — prêts pour Cookbook 14.
5. **`business_rules` = 6 lignes**, servi par la route admin — le modèle de Cookbook 14 existe déjà, il reste à généraliser aux 5 autres catalogues.
6. **B8 preuve** : `formatPercent(0.5)` → `"50.0%"` (contrat **0–1**). Ne pas l'utiliser avec un 0–100 sans `/100`.
7. **C2 proof** : `Timestamps` fournit `created_at`+`updated_at` **seulement aux modèles qui l'héritent** ; les catalogues ErrorCatalog/Product/RechargeCatalog/GeoAlias ne l'héritent pas (D12 migration).
8. **C1 proof** : seuls les tours `caller` sont persistés (jamais `speaker="agent"`) — impact C12 « Attributed turns ».
9. **B3 proof** : RBAC vivant — `conseiller`→403 sur `kpis` et `business-rules`, `superviseur`→200, `administrateur`→200.

---

## Récapitulatif des décisions (une ligne chacune, accepte = recommandation)

| # | Décision | Verdict | Remarque |
|---|---|---|---|
| D1 | Plancher rétention 30j/422 | **OUI (prise)** | Prouvé dangereux (`-5` → match 129). Bloque C10 |
| D2 | Garde UUID `customer_360` | **DÉJÀ EN PLACE** | `to_uuid`→404 réel, pas 500 (H-5 obsolète) |
| D3 | Rôles catalogues ref | **Nuancé** : errors/products/recharges `superviseur`, geo `administrateur` | Ou uniforme `administrateur` |
| D4 | `/policies` | **OUI** `superviseur` lecture seule | cohérent verdicts |
| D5 | Auth admin unique | **OUI acceptable** ; scoper multi-user avant sortie | stop-gap OIDC |
| D6 | Santé service | **OUI** C9 sans champ ; probes = cookbook séparé | 11 « online » en dur |
| D7 | Escalations `created_at`+`customer_id` | **OUI additif** | non présents actuellement |
| D8 | Ferme-t-on les escalades ? | **NON aujourd'hui (58/58 ouvertes)** ; à décider où | cœur C13 |
| D9 | Moteur `/rules` | **OUI filler, retiré** au profit de `/reference` | suivi FEATURE_14 |
| D10 | 4 tables non exposées | **OUI hors périmètre** ; cookbook futur si besoin | CustomerInteraction/Payment/PaymentPlan/ConsentRecord |
| D11 | Champs cycle vie callbacks | **DÉJÀ exposés** (to_dict) — amendement inutile | attempts/outcome_note/completed_at/assigned_advisor_id |
| D12 | `updated_at` ref catalogs | **OUI, migration délibérée** | 4 modèles manquent Timestamps |
| D13 | env partagé policy/business-api | **OUI même `.env` en local** ; documenter l'invariant | portabilité à écrire |
| D14 | Colonne Handled F1 | **OUI leave out** | pas d'endpoint pour une colonne |

**Bloqueurs réels au moment de l'application** : D1 (avant C10), B9/`INGESTED_FILES` (avant tout who touches `/conversations`/C13), E2/E3 (pour finir la Phase 2 : il manque la saisie de l'outil en vol + un log d'occurrence réelle), A7 (31 vs 33 advisor_shifts à réconcilier avant Feature 2/12).