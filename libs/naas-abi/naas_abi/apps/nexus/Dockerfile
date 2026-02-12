FROM node:20-alpine

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate
RUN apk add --no-cache inotify-tools

COPY pnpm-lock.yaml pnpm-workspace.yaml package.json turbo.json ./
COPY apps/web ./apps/web

WORKDIR /app/apps/web

RUN pnpm install --frozen-lockfile

ENV NODE_ENV=development
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 3000

CMD ["sh", "-c", "[ -d node_modules ] || pnpm install --frozen-lockfile; pnpm build; pnpm start --hostname 0.0.0.0 --port ${PORT:-3000} & SERVER_PID=$!; trap 'kill $SERVER_PID 2>/dev/null || true' INT TERM EXIT; while inotifywait -r -e modify,create,delete,move --exclude '(^|/)(node_modules|\\.next|\\.git)(/|$)' .; do if pnpm build; then kill $SERVER_PID 2>/dev/null || true; wait $SERVER_PID 2>/dev/null || true; pnpm start --hostname 0.0.0.0 --port ${PORT:-3000} & SERVER_PID=$!; fi; done"]
