# Development image (`pnpm dev`): never a deployment's. Node 24 LTS, pinned by
# digest, and the pnpm version package.json names.
FROM node:24.22.3-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@8.15.0 --activate
RUN apk add --no-cache inotify-tools

COPY pnpm-lock.yaml pnpm-workspace.yaml package.json turbo.json ./
COPY apps/web ./apps/web

WORKDIR /app/apps/web

RUN pnpm install --frozen-lockfile

ENV NODE_ENV=development
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 3000

CMD ["sh", "-ec", "pnpm dev"]

#CMD ["sh", "-ec", "if [ ! -f node_modules/.modules.yaml ]; then pnpm install --frozen-lockfile; fi; pnpm build; pnpm start --hostname 0.0.0.0 --port ${PORT:-3000} & SERVER_PID=$!; trap 'kill $SERVER_PID 2>/dev/null || true' INT TERM EXIT; while inotifywait -r -e modify,create,delete,move --exclude '(^|/)(node_modules|\\.next|\\.git)(/|$)' .; do if pnpm build; then kill $SERVER_PID 2>/dev/null || true; wait $SERVER_PID 2>/dev/null || true; pnpm start --hostname 0.0.0.0 --port ${PORT:-3000} & SERVER_PID=$!; fi; done"]
