# Fuseki for `abi deploy local`: the stain/jena-fuseki image, with its
# Fuseki 5.1.0 replaced by the official Apache Fuseki 5.6.0 distribution.
#
# Why: Fuseki 5.1.0 leaks one TDB2 read lock on every query
# (DatasetGraphTxnCtl.beginMultiMode). A ReentrantReadWriteLock holds at most
# 65535 read locks, so after 65535 requests every query fails with HTTP 500
# "Maximum lock count exceeded" until the JVM restarts. The compose health
# check alone sends one query every 10s, so that is under a week, and the ABI
# API then cannot start because its startup connectivity check gets a 500.
# Upstream: apache/jena#2755, fixed from Jena 5.2.0. stain/jena-fuseki
# publishes nothing newer than 5.1.0.
#
# Why this base rather than another image: keeping stain's entrypoint, user,
# /fuseki data layout and curl (used by the compose health check) means an
# existing fuseki_data volume, ADMIN_PASSWORD handling and the health check
# work unchanged. TDB2's on-disk format is the same across Jena 5.x, so the
# data needs no reload.
# Pinned by digest: the image this template used before (stain/jena-fuseki:latest = 5.1.0).
FROM stain/jena-fuseki:5.1.0@sha256:b1d0c96f19adddef417520184471ac816cf36c6e72936a88ea02b29f4305929a

ARG FUSEKI_VERSION=5.6.0
# From https://archive.apache.org/dist/jena/binaries/apache-jena-fuseki-5.6.0.tar.gz.sha512
ARG FUSEKI_SHA512=53dfe13cdd5f6387a0c62917e275fde2cd2e2f2052bfe7515384934f24915228b8512a2dd2b50b7060cc300c976254349d991fcea239484cae48e0a59d67cd54

USER root
RUN set -eux; \
    cd /tmp; \
    wget -q "https://archive.apache.org/dist/jena/binaries/apache-jena-fuseki-${FUSEKI_VERSION}.tar.gz"; \
    echo "${FUSEKI_SHA512}  apache-jena-fuseki-${FUSEKI_VERSION}.tar.gz" | sha512sum -c -; \
    tar -xzf "apache-jena-fuseki-${FUSEKI_VERSION}.tar.gz"; \
    src="/tmp/apache-jena-fuseki-${FUSEKI_VERSION}"; \
    rm -rf /jena-fuseki/webapp /jena-fuseki/fuseki-server.jar; \
    cp "$src/fuseki-server.jar" "$src/fuseki" "$src/log4j2.properties" /jena-fuseki/; \
    cp "$src/fuseki-server" /jena-fuseki/fuseki-server.dist; \
    chmod 755 /jena-fuseki/fuseki-server.dist /jena-fuseki/fuseki; \
    rm -rf /tmp/apache-jena-fuseki-*

# /jena-fuseki/fuseki-server (what docker-compose runs) adapts a 5.1-era
# shiro.ini, then starts the 5.6 server script. --chmod because `abi deploy
# local` writes template files without their mode.
COPY --chmod=755 fuseki-server-launcher.sh /jena-fuseki/fuseki-server

USER fuseki
