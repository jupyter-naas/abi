# SDK-only image for one application module. No naas-abi-core: the engine is
# reached only through NATS. Build from the repository root:
#   docker build -f libs/naas-abi-marketplace-modules/Dockerfile \
#     --build-arg APP=pennylane -t abi-app-pennylane libs
# or from Compose with named contexts (abi_proto, abi_sdk) and this folder.

# The X module's Recent Tweets app is a Next.js static export the module
# publishes (build_app job) from /opt/x-app-web/out. Built for APP=x only; an
# empty folder for every other application. src/lib/appConfig.generated.ts is
# committed, so `next build` runs without the Python prebuild.
FROM node:22-slim AS x_web
ARG APP
ENV NEXT_TELEMETRY_DISABLED=1
COPY naas_abi_apps/x/x_proxy/web /web
RUN mkdir -p /out \
    && if [ "$APP" = "x" ]; then \
        cd /web \
        && corepack enable \
        && corepack prepare pnpm@8.15.9 --activate \
        && pnpm install --frozen-lockfile \
        && pnpm exec next build \
        && cp -r out/. /out/; \
    fi

FROM python:3.12-slim

ARG APP
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ABI_APP=${APP}

COPY --from=abi_proto . /build/naas-abi-proto
COPY --from=abi_sdk . /build/naas-abi-sdk
COPY pyproject.toml README.md build-requirements.txt /build/modules/
COPY requirements /build/modules/requirements
COPY naas_abi_apps /build/modules/naas_abi_apps
# Every third-party package comes from this package's uv.lock, with its hashes
# (requirements/<app>.txt, `uv export` of the app's extra), and the build
# backend from build-requirements.txt. naas-abi-sdk and naas-abi-proto are the
# local copies above, installed without dependencies or a build environment of
# their own, so nothing is resolved at build time.
RUN test -n "$APP" && test -f "/build/modules/requirements/${APP}.txt" \
    && pip install --require-hashes --no-deps \
        -r "/build/modules/requirements/${APP}.txt" \
        -r /build/modules/build-requirements.txt \
    && pip install --no-deps --no-build-isolation \
        /build/naas-abi-proto /build/naas-abi-sdk /build/modules \
    && pip check \
    && rm -rf /build

# The point of the image: fail the build if core sneaks in, or if the module
# cannot import without it.
RUN python -c "import importlib.util, sys; sys.exit([m for m in ('naas_abi_core', 'naas_abi', 'naas_abi_marketplace') if importlib.util.find_spec(m)] or 0)"
RUN python -c "import importlib, os; importlib.import_module('naas_abi_apps.' + os.environ['ABI_APP'] + '.__main__')"

COPY --from=x_web /out /opt/x-app-web/out

USER nobody
ENTRYPOINT ["sh", "-c", "exec python -m naas_abi_apps.$ABI_APP"]
