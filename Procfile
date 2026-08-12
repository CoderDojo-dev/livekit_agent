# honcho/foreman process list (diagnostic #1). `honcho start` runs the whole platform in one terminal.
# Console scripts come from each service's [project.scripts]; run `make install` first.
context:       context-service
knowledge:     knowledge-service
decision:      decision-service
policy:        policy-service
execution:     execution-service
notification:  notification-service
token:         token-service
business:      business-api
knowledge-mcp: ai-knowledge-rag
ticketing-mcp: ticketing-glpi
messaging-mcp: messaging-gateway
worker:        python apps/agent-worker/src/server.py start
widget:        npm --prefix apps/client-widget run dev