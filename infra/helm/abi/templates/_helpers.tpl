{{/*
Shared helpers.
*/}}

{{- define "abi.namespace" -}}
{{- .Values.namespace.name | default .Release.Namespace -}}
{{- end -}}

{{- define "abi.commonLabels" -}}
app.kubernetes.io/part-of: abi
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
abi/env: {{ .Values.global.env | quote }}
{{- end -}}

{{/*
abi.image "svc" — resolves repository[:tag] from a service block.
*/}}
{{- define "abi.image" -}}
{{- $svc := index .Values .svc -}}
{{- $tag := $svc.image.tag | default .Values.global.imageTag -}}
{{- printf "%s:%s" $svc.image.repository $tag -}}
{{- end -}}
