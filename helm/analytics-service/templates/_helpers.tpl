{{- define "analytics-service.fullname" -}}
{{- printf "%s-analytics-service" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- define "analytics-service.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: analytics-service
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
{{- define "analytics-service.selectorLabels" -}}
app.kubernetes.io/name: analytics-service
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
