# Analyse de l'erreur `tts_node called but no TTS node is available`

## Résumé

Pendant la phase de collecte du consentement (`ConsentTask`), le système lève une `RuntimeError: tts_node called but no TTS node is available` à chaque tentative de génération de parole. L'erreur disparaît immédiatement après la fin du `ConsentTask`, lorsque le `TriageAgent` principal reprend la main. Cela prouve que le **TTS est correctement configuré au niveau session** — le problème est spécifique au `ConsentTask`.

---

## Symptômes observés dans les logs

```
12:02:19.225  🎤 Caller: Alors,                       ← STT transcrit l'appelant
12:02:19.890  ERROR RuntimeError: tts_node called but  ← TTS échoue PENDANT le ConsentTask
              no TTS node is available.
12:02:20.059  🤖 Agent: Puis-je avoir une réponse...   ← LLM a répondu, mais sans audio
12:02:35.745  🎤 Caller: Alors,                       ← Tour suivant
12:02:36.500  ERROR RuntimeError: tts_node ...         ← TTS échoue à nouveau
...
12:02:59.292  INFO: caller gave recording consent       ← ConsentTask se termine
12:03:00.414  time_to_first_audio_seconds=2.072         ← TTS fonctionne MAINTENANT !
12:03:01.690  TTS metrics (Cartesia sonic-3)            ← Synthèse vocale réussie
```

L'erreur apparaît **exclusivement** entre 12:02:19 et 12:02:59 — la fenêtre d'exécution du `ConsentTask`. Après, tout fonctionne.

---

## Architecture de la résolution TTS dans LiveKit Agents 1.6.5

LiveKit utilise un mécanisme de résolution hiérarchique pour le TTS dans `AgentActivity` :

```python
# livekit/agents/voice/agent_activity.py, line 4249
@property
def tts(self) -> tts.TTS | None:
    if self._text_only:
        return None
    return self._agent.tts if is_given(self._agent.tts) else self._session.tts
```

- **`is_given(x)`** retourne `True` si `x` n'est PAS un `NotGiven` (classe sentinelle).
  - `is_given(NOT_GIVEN)` → `False` → on utilise `self._session.tts` (le TTS de session)
  - `is_given(None)` → `True` → on utilise `self._agent.tts` (qui vaut `None` → pas de TTS)
  - `is_given(objet_tts)` → `True` → on utilise l'objet TTS de l'agent

**Piège :** `None` est une valeur explicite, pas une absence de valeur. Le passage de `tts=None` est interprété par LiveKit comme « l'agent ne veut PAS de TTS », et non comme « utiliser le TTS par défaut de la session ».

---

## La chaîne causale complète

### Étape 1 : `triage_agent.py:76` — Appel à `active_persona_tts(None)`

```python
# triage_agent.py:72-77
if user_data.recording_consent is None:
    granted = await ConsentTask(
        language=self._language,
        chat_ctx=self.chat_ctx.copy(exclude_instructions=True),
        tts=active_persona_tts(None),    # <-- LE PROBLÈME
    )
```

### Étape 2 : `voice_flow.py:105-113` — `active_persona_tts()` retourne `None`

```python
def active_persona_tts(context: RunContext | None) -> object | None:
    if context is None:
        return None                    # ← TOUJOURS ce chemin, car context=None
    current = getattr(context.session, "current_agent", None)
    tts = getattr(current, "tts", None)
    return persona_tts(tts)
```

Le paramètre `context` reçoit la valeur littérale `None`. La fonction retourne immédiatement `None` sans même essayer de lire le TTS de l'agent courant.

### Étape 3 : `voice_flow.py:98-102` — `persona_tts()` transforme `None` en `None`

```python
def persona_tts(tts: NotGivenOr[object] | None) -> object | None:
    if tts is None or isinstance(tts, NotGivenOr):
        return None                    # ← None → None
    return tts
```

La fonction reçoit `None`, retourne `None`.

### Étape 4 : `consent_task.py:34` — `ConsentTask.__init__` reçoit `tts=None`

```python
class ConsentTask(AgentTask[bool]):
    def __init__(self, language: str = "fr", chat_ctx=None, tts=None) -> None:
        ...
        super().__init__(
            instructions=...,
            chat_ctx=chat_ctx,
            tts=persona_tts(tts),       # ← persona_tts(None) = None
        )
```

### Étape 5 : `Agent.__init__` stocke `self._tts = None`

Dans le constructeur de `Agent` (livekit library) :
```python
self._tts = tts    # None est stocké tel quel
```

### Étape 6 : `AgentActivity.tts` résout `None`

```python
# agent_activity.py:4249
return self._agent.tts if is_given(self._agent.tts) else self._session.tts
#     = None             if is_given(None) → True      else CartesiaFallbackAdapter
#     = None
```

`is_given(None)` retourne `True` car `None` n'est pas une instance de `NotGiven`. L'activité utilise donc `None`, court-circuitant le TTS de session pourtant correctement configuré (`build_tts()` → `FallbackAdapter(Cartesia, ...)`).

### Étape 7 : `_tts_inference_task` échoue sur `activity.tts is None`

```python
# livekit/agents/voice/agent.py, Agent.default.tts_node
@staticmethod
async def tts_node(agent, text, model_settings):
    activity = agent._get_activity_or_raise()
    if activity.tts is None:
        raise RuntimeError(
            "`tts_node` called but no TTS node is available. ..."
        )
```

C'est cette exception qui remonte dans les logs sous `Error in _tts_inference_task`.

---

## Preuve que le TTS session est fonctionnel

Dans `session_factory.py:34` :
```python
return AgentSession(
    ...
    tts=build_tts(preset, settings.tts_model, settings.eleven_voice_id, settings.chaos_break_tts),
    ...
)
```

`build_tts()` retourne un `tts_module.FallbackAdapter([cartesia.TTS(...)])` — un objet TTS valide qui fonctionne. La preuve : dès que le `ConsentTask` se termine, les appels suivants à `session.generate_reply()` (depuis `TriageAgent.on_enter()`) produisent correctement de l'audio (logs `TTS metrics` à 12:03:01).

---

## Schéma récapitulatif

```
triage_agent.py:76
  tts=active_persona_tts(None)
       │
       ▼
voice_flow.py:105-113  (active_persona_tts)
  context is None → return None
       │
       ▼
voice_flow.py:98-102  (persona_tts)
  None → return None
       │
       ▼
consent_task.py:34
  tts=persona_tts(tts) → tts=None
       │
       ▼
Agent.__init__ (livekit)
  self._tts = None
       │
       ▼
AgentActivity.tts (agent_activity.py:4249)
  is_given(None) → True → utilise self._agent.tts = None
  (au lieu du session.tts = FallbackAdapter Cartesia)
       │
       ▼
Agent.default.tts_node (agent.py)
  activity.tts is None → raise RuntimeError("tts_node called but no TTS node is available")
```

---

## Impact

1. **Silence pendant le consentement** : L'agent demande le consentement, mais sa voix n'est pas audible. L'appelant n'entend que « Alors, », « Oui, », « Bonjour. » — des bribes transcrites par STT qui ne correspondent pas à ce que l'agent a réellement dit.

2. **Boucle de clarification infinie** : Comme l'appelant n'entend pas la question de consentement, il ne répond pas clairement. L'agent répète sa question (via LLM uniquement, sans audio), ce qui génère des tours STT vides ou partiels, faisant grimper le compteur de tentatives.

3. **Consentement obtenu par hasard** : Dans le log, l'appelant finit par dire « Oui » (à 12:02:58), probablement après plusieurs tentatives frustrées. Le `record_consent` est appelé et le `ConsentTask` se termine, débloquant le TTS pour la suite.

---

## Causes racines (3 bugs concourants)

### Bug primaire — `triage_agent.py:76`
`active_persona_tts(None)` reçoit `None` comme argument. La fonction retourne immédiatement `None`. L'intention était probablement de ne **pas** passer de TTS (pour hériter de la session), mais la valeur `None` explicitement passée est interprétée par LiveKit comme « désactiver le TTS ».

### Bug secondaire — `voice_flow.py:98-102` (`persona_tts`)
La fonction transforme `None` en `None`. Elle devrait retourner `NOT_GIVEN` (le sentinelle de LiveKit) pour préserver la sémantique « non spécifié, utiliser la valeur par défaut ». Avec `NOT_GIVEN`, `is_given(NOT_GIVEN)` → `False`, et le TTS de session serait utilisé.

### Bug tertiaire — `consent_task.py:34`
Le `ConsentTask` passe `tts=persona_tts(tts)` au constructeur parent. Si le but du paramètre `tts` du `ConsentTask` est d'être optionnel, la valeur par défaut dans `__init__` (`tts=None`) entre en conflit avec la sémantique de LiveKit où `None` = « pas de TTS ». La valeur par défaut devrait être omise ou explicitée comme `NOT_GIVEN`.

---

## Correction possible

### Option A — Ne pas passer `tts` du tout (recommandée)
```python
# triage_agent.py:73-77
granted = await ConsentTask(
    language=self._language,
    chat_ctx=self.chat_ctx.copy(exclude_instructions=True),
    # tts non passé → Agent hérite de session.tts
)
```
Le `ConsentTask` utilise alors le TTS de session, qui est correctement configuré.

### Option B — Passer explicitement le TTS de l'agent courant
```python
# triage_agent.py:73-77
granted = await ConsentTask(
    language=self._language,
    chat_ctx=self.chat_ctx.copy(exclude_instructions=True),
    tts=self._tts,  # TTS du TriageAgent
)
```

### Option C — Changer `persona_tts` pour retourner `NOT_GIVEN`
```python
from livekit.agents.types import NOT_GIVEN

def persona_tts(tts):
    if isinstance(tts, NotGivenOr):
        return NOT_GIVEN  # préserve la sémantique "non spécifié"
    return tts
```
Combiner avec l'utilisation de `NOT_GIVEN` comme valeur par défaut dans `ConsentTask`.

---

## Conclusion

L'erreur est causée par l'appel `active_persona_tts(None)` dans `triage_agent.py:76` qui neutralise le TTS du `ConsentTask` en passant `None` explicitement. LiveKit interprète `None` comme « pas de TTS pour cet agent », court-circuitant le TTS de session. La correction la plus simple est de ne pas passer de `tts` au `ConsentTask`, lui permettant d'hériter du TTS de session qui est déjà correctement configuré avec Cartesia `sonic-3`.
