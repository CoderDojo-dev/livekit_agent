# Secrets management (report #23)

`.env` is for local dev only (git-ignored). Nothing secret is baked into an image or committed.

## Staging / prod
- **Kubernetes**: create the `telecom-secrets` Secret the Helm chart references:
  ```bash
  kubectl create secret generic telecom-secrets \
    --from-literal=DATABASE_URL=postgresql+psycopg://... \
    --from-literal=INTERNAL_API_KEY=... \
    --from-literal=LIVEKIT_API_SECRET=... \
    --from-literal=DEEPGRAM_API_KEY=... --from-literal=ELEVEN_API_KEY=... \
    --from-literal=OPENAI_API_KEY=... --from-literal=GOOGLE_API_KEY=... \
    --from-literal=GLPI_APP_TOKEN=... --from-literal=GLPI_USER_TOKEN=... \
    --from-literal=TWILIO_AUTH_TOKEN=...
  ```
  For GitOps, encrypt with **SOPS** (age/KMS) or use the **External Secrets Operator** backed by Vault.
- **Docker Compose**: use `docker secret` (swarm) or an `env_file:` that is provisioned out-of-band and
  never committed. `infra/docker-compose/docker-compose.yml` already reads `${...}` for every credential.

## Rotation
Rotate `INTERNAL_API_KEY` and all provider keys on a schedule; the services read them from the
environment at boot, so rotation is a rolling restart. Never log secret values (the PII masker + the
audit ledger both avoid persisting them).