# Diagnostic du problème de ticketing — Cause racine identifiée et confirmée par test

## Résultat des tests

| Test | Résultat |
|------|----------|
| Santé du service ticketing-glpi | ✅ OK — `glpi: configured` |
| GLPI API (initSession) | ✅ OK — `HTTP 200` |
| Création de ticket GLPI | ✅ OK — `HTTP 201 Created` |
| Notification service | ✅ OK — `HTTP 200` |
| Connectivité agent-worker → ticketing-glpi:8202 | ✅ OK |
| MCP call `create_ticket` depuis agent-worker | ✅ **SUCCÈS — Ticket GLPI-18 créé** |
| MCP call `create_ticket` (2e test) | ✅ **SUCCÈS — Ticket GLPI-19 créé** |

## Cause racine : BUG dans `_mcp_call()` dans `ticket_tools.py:38-72`

Le problème a été **confirmé expérimentalement**. Voici la démonstration :

```
=== RESULT OBJECT ===
isError: False
structuredContent: None
content: [TextContent(type='text', text='{
  "ticket_id": "GLPI-19",
  "status": "open",
  ...
}')]

--- Ce que _mcp_call() vérifie ---
structuredContent is None → retourne None
BUG: le contenu est dans result.content (TextContent) mais jamais lu !
```

### Le code buggé (`ticket_tools.py:63-67`)

```python
if result.structuredContent is not None:
    content = result.structuredContent
    return content.get("result", content) if isinstance(content, dict) else content
return None  # ← TOUJOURS ce chemin car structuredContent est None
```

Le code ne lit que `result.structuredContent`. Or **FastMCP ne remplit PAS `structuredContent`** — il met le résultat dans `result.content` sous forme de liste `[TextContent(text='{...}')]`.

### La chaîne d'échec complète

```
Agent appelle create_support_ticket()
       │
       ▼
_mcp_call("create_ticket", {...})
       │
       ├─ streamablehttp_client → ✅ Connexion OK
       ├─ ClientSession.initialize() → ✅ OK
       ├─ session.call_tool("create_ticket") → ✅ SUCCÈS
       │     └─ ticketing-glpi crée le ticket dans GLPI (201 Created)
       │     └─ notification-service envoie la confirmation WhatsApp (200 OK)
       │
       ▼
result.isError = False
result.structuredContent = None   ← FastMCP ne le remplit PAS
result.content = [TextContent(text='{"ticket_id": "GLPI-19", ...}')]  ← Le résultat est ICI
       │
       ▼
_mcp_call() lit structuredContent → None
retourne None
       │
       ▼
create_support_ticket() ligne 129:
  return result or _unavailable()
  → None or _unavailable() → _unavailable()
       │
       ▼
LLM reçoit: {"outcome": "unavailable", "message": "The ticketing system is unavailable..."}
       │
       ▼
Agent dit: "Je ne peux pas créer le ticket pour le moment, car le système de ticketing
           est indisponible."
       │
       ▼
MAIS LE TICKET EXISTE DÉJÀ DANS GLPI ! (GLPI-18, GLPI-19, etc.)
```

### Impact

1. **Tous les appels à `_mcp_call()` échouent** à retourner le résultat, même quand le ticket est créé avec succès
2. **L'agent ment à l'appelant** en disant « système indisponible » alors que le ticket a été créé
3. **Des tickets orphelins** sont créés dans GLPI sans que l'agent puisse communiquer la référence
4. **Les callers sont frustrés** (certains raccrochent immédiatement après avoir entendu « indisponible »)
5. **Le bug affecte TOUS les outils de ticketing** : `create_support_ticket`, `check_customer_tickets`, `get_ticket_state`, `mark_ticket_resolved`, `update_support_ticket`

### Correction

Dans `_mcp_call()` (`ticket_tools.py:63-67`), remplacer :

```python
if result.structuredContent is not None:
    content = result.structuredContent
    return content.get("result", content) if isinstance(content, dict) else content
return None
```

Par :

```python
if result.structuredContent is not None:
    content = result.structuredContent
    return content.get("result", content) if isinstance(content, dict) else content
if result.content:
    import json
    text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
return None
```
