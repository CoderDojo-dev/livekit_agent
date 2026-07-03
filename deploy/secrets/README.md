# Secrets Management

## Development
Copy `.env.example` to `.env` and fill in values for local development:

```bash
cp deploy/secrets/.env.example deploy/secrets/.env
```

Docker Compose reads the `.env` file automatically.

## Staging / Production

### Option A: Docker Secrets (Swarm)
Define secrets in `docker-compose.yml` under the `secrets:` top-level key and reference
them in each service. Never embed secrets in environment variables directly.

### Option B: Kubernetes Secrets
The Helm chart (`infra/helm/telecom-platform/templates/secrets.yaml`) creates a
`telecom-platform-secrets` Secret from Helm values. In production, use SealedSecrets
or External Secrets Operator with Vault/AWS Secrets Manager.

### Option C: HashiCorp Vault
Services authenticate via their Kubernetes service account and fetch secrets from
Vault at startup. The agent-worker and services use the Vault agent sidecar.

## Key rotation
- Rotate `INTERNAL_API_KEY` quarterly
- Rotate database passwords on each staging/prod deploy
- LiveKit API key/secret: rotate monthly
