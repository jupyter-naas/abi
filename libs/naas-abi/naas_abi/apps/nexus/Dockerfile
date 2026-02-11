FROM node:20-alpine

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate

COPY pnpm-lock.yaml pnpm-workspace.yaml package.json turbo.json ./
COPY apps/web ./apps/web

WORKDIR /app/apps/web

RUN pnpm install --frozen-lockfile

ENV NODE_ENV=development
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1
ENV CHOKIDAR_USEPOLLING=1
ENV WATCHPACK_POLLING=true

EXPOSE 3000

WORKDIR /app/apps/web

RUN pnpm install

CMD ["sh", "-c", "[ -d node_modules ] || pnpm install; CHOKIDAR_USEPOLLING=1 WATCHPACK_POLLING=true WATCHPACK_POLLING_INTERVAL=1000 pnpm dev --hostname 0.0.0.0 --port 3000"]
