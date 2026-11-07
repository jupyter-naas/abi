# The built-in identity provider, in its own container. SDK-only: no
# naas-abi-core, the engine is reached only through NATS (ABI_NATS_URL). The
# stack's docker-compose.yml builds it with named contexts, so no project root
# is ever sent:
#   context = .abi/libs/naas-abi-idp, abi_proto / abi_sdk = .abi/libs/naas-abi-{proto,sdk}
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY --from=abi_proto . /build/naas-abi-proto
COPY --from=abi_sdk . /build/naas-abi-sdk
COPY . /build/naas-abi-idp
# naas-abi-sdk and naas-abi-proto are the local copies above, not PyPI's.
RUN pip install /build/naas-abi-proto /build/naas-abi-sdk /build/naas-abi-idp \
    && rm -rf /build

# The point of the image: fail the build if core sneaks in, or if the provider
# cannot import without it.
RUN python -c "import importlib.util, sys; sys.exit('naas_abi_core is installed: the identity provider must not depend on it' if importlib.util.find_spec('naas_abi_core') else 0)"
RUN python -c "import naas_abi_idp.__main__"

USER nobody
ENTRYPOINT ["python", "-m", "naas_abi_idp"]
