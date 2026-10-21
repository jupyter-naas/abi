# SDK-only image for the {{module_name}} module. No naas-abi-core: the engine is
# reached only through NATS. docker-compose.override.yml builds it with named
# contexts, so the project root is never sent:
#   context = src/{{module_name_snake}}, abi_proto / abi_sdk = .abi/libs/naas-abi-{proto,sdk}
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

COPY --from=abi_proto . /build/naas-abi-proto
COPY --from=abi_sdk . /build/naas-abi-sdk
RUN pip install /build/naas-abi-proto "/build/naas-abi-sdk[agent,otel]" \
    && rm -rf /build

COPY . /app/{{module_name_snake}}

# The point of the image: fail the build if core sneaks in, or if the module
# cannot import without it.
RUN python -c "import importlib.util, sys; sys.exit('naas_abi_core is installed: a remote module must not depend on it' if importlib.util.find_spec('naas_abi_core') else 0)"
RUN python -c "import {{module_name_snake}}.__main__"

USER nobody
ENTRYPOINT ["python", "-m", "{{module_name_snake}}"]
