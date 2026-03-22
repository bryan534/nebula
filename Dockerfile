FROM ghcr.io/astral-sh/uv:python3.13-alpine
LABEL name="Nebula" \
      description="Stremio's fastest torrent/debrid search add-on." \
      url="https://github.com/g0ldyy/nebula"

RUN apk add --no-cache gcc python3-dev musl-dev linux-headers git make tzdata mimalloc2

WORKDIR /app

COPY pyproject.toml uv.lock ./

ENV TZ=UTC \
    UV_HTTP_TIMEOUT=300 \
    PYTHONMALLOC=malloc \
    LD_PRELOAD=/usr/lib/libmimalloc.so.2
ARG TARGETPLATFORM
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-${TARGETPLATFORM},sharing=locked uv sync --frozen

COPY . .

ARG DATABASE_PATH
ARG NEBULA_COMMIT_HASH
ARG NEBULA_BUILD_DATE
ARG NEBULA_BRANCH

ENV NEBULA_COMMIT_HASH=${NEBULA_COMMIT_HASH} \
    NEBULA_BUILD_DATE=${NEBULA_BUILD_DATE} \
    NEBULA_BRANCH=${NEBULA_BRANCH}

ENTRYPOINT ["uv", "run", "python", "-m", "nebula.main"]
