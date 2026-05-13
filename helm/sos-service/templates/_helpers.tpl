{{- define "sos-service.fullname" -}}
{{- printf "%s-sos-service" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- define "sos-service.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: sos-service
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
{{- define "sos-service.selectorLabels" -}}
app.kubernetes.io/name: sos-service
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
