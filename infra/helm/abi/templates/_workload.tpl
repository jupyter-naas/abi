{{/*
abi.workload — renders a ServiceAccount + Deployment + Service for a single
workload block defined at .Values.<svc>. Takes a dict:
  { "ctx": $, "name": "abi-api", "svcKey": "abiApi", "containerArgs": [...] }
*/}}
{{- define "abi.workload" -}}
{{- $ctx := .ctx -}}
{{- $name := .name -}}
{{- $svcKey := .svcKey -}}
{{- $svc := index $ctx.Values $svcKey -}}
{{- if $svc.enabled -}}
{{- if $svc.serviceAccount -}}
{{- if $svc.serviceAccount.create }}
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ $svc.serviceAccount.name }}
  namespace: {{ include "abi.namespace" $ctx }}
  {{- if $svc.serviceAccount.roleArn }}
  annotations:
    eks.amazonaws.com/role-arn: {{ $svc.serviceAccount.roleArn | quote }}
  {{- end }}
  labels:
    app.kubernetes.io/name: {{ $name }}
    {{- include "abi.commonLabels" $ctx | nindent 4 }}
{{- end -}}
{{- end }}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $name }}
  namespace: {{ include "abi.namespace" $ctx }}
  labels:
    app.kubernetes.io/name: {{ $name }}
    {{- include "abi.commonLabels" $ctx | nindent 4 }}
spec:
  replicas: {{ $svc.replicaCount | default 1 }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ $name }}
      app.kubernetes.io/instance: {{ $ctx.Release.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ $name }}
        {{- include "abi.commonLabels" $ctx | nindent 8 }}
    spec:
      {{- if and $svc.serviceAccount $svc.serviceAccount.create }}
      serviceAccountName: {{ $svc.serviceAccount.name }}
      {{- end }}
      containers:
        - name: {{ $name }}
          image: {{ include "abi.image" (dict "Values" $ctx.Values "svc" $svcKey) }}
          imagePullPolicy: {{ $svc.image.pullPolicy | default "IfNotPresent" }}
          ports:
            - name: http
              containerPort: {{ $svc.service.port }}
              protocol: TCP
            {{- if $svc.service.streamlitPort }}
            - name: streamlit
              containerPort: {{ $svc.service.streamlitPort }}
              protocol: TCP
            {{- end }}
          {{- with $svc.env }}
          env:
            {{- range $k, $v := . }}
            - name: {{ $k }}
              value: {{ $v | quote }}
            {{- end }}
          {{- end }}
          {{- with $svc.extraEnvFrom }}
          envFrom:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          {{- with $svc.resources }}
          resources:
            {{- toYaml . | nindent 12 }}
          {{- end }}
---
apiVersion: v1
kind: Service
metadata:
  name: {{ $name }}
  namespace: {{ include "abi.namespace" $ctx }}
  labels:
    app.kubernetes.io/name: {{ $name }}
    {{- include "abi.commonLabels" $ctx | nindent 4 }}
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: {{ $name }}
    app.kubernetes.io/instance: {{ $ctx.Release.Name }}
  ports:
    - name: http
      port: {{ $svc.service.port }}
      targetPort: http
      protocol: TCP
    {{- if $svc.service.streamlitPort }}
    - name: streamlit
      port: {{ $svc.service.streamlitPort }}
      targetPort: streamlit
      protocol: TCP
    {{- end }}
{{- end -}}
{{- end -}}
