{{- define "dispatch-service.fullname" -}}
{{- printf "%s-dispatch-service" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- define "dispatch-service.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: dispatch-service
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
{{- define "dispatch-service.selectorLabels" -}}
app.kubernetes.io/name: dispatch-service
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
