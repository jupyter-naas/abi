# SDK-only image for the {{module_name}} module. No naas-abi-core: the engine is
# reached only through NATS (ABI_NATS_URL). Build from this folder:
#   docker build -t {{module_name}} .
FROM python:3.12-slim AS build

# git fetches naas-abi-proto and naas-abi-sdk (see pyproject.toml).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local

# The point of the image: fail the build if core sneaks in, or if the module
# cannot import without it.
RUN python -c "import importlib.util, sys; sys.exit('naas_abi_core is installed: a remote module must not depend on it' if importlib.util.find_spec('naas_abi_core') else 0)"
RUN python -c "import {{module_name_snake}}.__main__"

USER nobody
ENTRYPOINT ["python", "-m", "{{module_name_snake}}"]
