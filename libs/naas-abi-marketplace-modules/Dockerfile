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

USER nobody
ENTRYPOINT ["sh", "-c", "exec python -m naas_abi_apps.$ABI_APP"]
