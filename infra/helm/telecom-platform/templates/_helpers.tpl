{{- define "telecom.image" -}}
{{- $global := $.Values.global -}}
{{- $local := $.Values -}}
{{- $repo := $local.image.repository -}}
{{- $tag := $local.image.tag | default $global.imageTag -}}
{{ $global.imageRegistry }}/{{ $repo }}:{{ $tag }}
{{- end -}}

{{- define "telecom.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "telecom.serviceName" -}}
{{ .Chart.Name }}-{{ .Values.name | default "svc" }}
{{- end -}}
