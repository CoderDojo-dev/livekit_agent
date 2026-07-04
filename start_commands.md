# Startup Guides & Commands

This guide describes how to run and monitor the Telecom AI Voice Agent Platform.

---

## Option 1: Full Local Development (Recommandée)
In this mode, all infrastructure containers (PostgreSQL, Redis, Qdrant, MinIO) are started in Docker, but all microservices, MCP servers, and frontends are run locally as host processes under a single terminal monitor (`honcho`).

### 1. Install frontend dependencies (Only once)
```bash
make frontends
```

### 2. Startup the entire stack
Run the unified dev command:
```bash
make dev
```
*This command executes sequentially: `install` dependencies, starts `infra` containers, applies database `migrate` scripts, `seed`s test data, and runs `honcho start` to boot all processes.*

---

## Option 2: Hybrid Mode (Backend in Docker + Frontend Local)
In this mode, all backend microservices, MCP servers, and agent workers are run inside Docker containers, while the frontends are executed locally using Node/Vite.

### 1. Build and start all backend services
```bash
make up
```

### 2. Verify all services are healthy
```bash
make health
```

### 3. Start the Voice Client Widget frontend
In a new terminal window:
```bash
npm --prefix apps/client-widget run dev
```

### 4. Start the Supervisor Dashboard frontend
In a new terminal window:
```bash
npm --prefix apps/supervisor-dashboard run dev
```

---

## Useful Commands & Monitoring

### Live Debugging / Worker Logs
Follow agent transcripts, client actions, and tool calls in real-time:
```bash
make live-logs
```

### Stopping the Stack
* **For Option 1:** Press `Ctrl + C` in the terminal running `honcho`.
* **For Option 2 (Docker services):**
  ```bash
  make down
  ```

### Clean frontends dependencies reinstall
If package locks or Vite/Rollup compilation fails due to OS mismatch:
```bash
make frontends-clean
```
