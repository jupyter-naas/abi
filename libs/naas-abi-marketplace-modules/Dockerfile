# SDK-only image for one application module. No naas-abi-core: the engine is
# reached only through NATS. Build from the repository root:
#   docker build -f libs/naas-abi-marketplace-modules/Dockerfile \
#     --build-arg APP=pennylane -t abi-app-pennylane libs
# or from Compose with named contexts (abi_proto, abi_sdk) and this folder.
FROM python:3.12-slim

ARG APP
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ABI_APP=${APP}

COPY --from=abi_proto . /build/naas-abi-proto
COPY --from=abi_sdk . /build/naas-abi-sdk
COPY pyproject.toml README.md /build/modules/
COPY naas_abi_apps /build/modules/naas_abi_apps
RUN test -n "$APP" \
    && pip install /build/naas-abi-proto "/build/naas-abi-sdk[agent,otel,workflows]" \
       "/build/modules[${APP}]" \
    && rm -rf /build

# The point of the image: fail the build if core sneaks in, or if the module
# cannot import without it.
RUN python -c "import importlib.util, sys; sys.exit([m for m in ('naas_abi_core', 'naas_abi', 'naas_abi_marketplace') if importlib.util.find_spec(m)] or 0)"
RUN python -c "import importlib, os; importlib.import_module('naas_abi_apps.' + os.environ['ABI_APP'] + '.__main__')"

USER nobody
ENTRYPOINT ["sh", "-c", "exec python -m naas_abi_apps.$ABI_APP"]
