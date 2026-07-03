# client-widget
Embeddable voice+chat client on the LiveKit client SDK. Connects via the token-service. Built in Phase 10.

## Run from WSL/Linux
```bash
cp .env.example .env
npm ci
npm run dev # http://localhost:5173
```

If Vite/Rollup reports a missing `@rollup/rollup-linux-x64-gnu` package, the dependencies were installed for a different OS. From the repository root, run:
```bash
bash scripts/fix_frontend_deps.sh
```
