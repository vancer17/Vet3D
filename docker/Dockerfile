# 文件信息：L1-05／L2-01 的开发与生产镜像共用入口，固定 CPython、uv 和 Blender 制品身份。
# 作用：在 Linux x86_64 镜像中提供受信 CPU 环境探针；生产阶段安装非 editable 产品包。
# 边界：Blender 安装不等于资源可执行或模型验收；镜像不是不可信动态代码的执行沙箱。
FROM ghcr.io/astral-sh/uv:0.11.25@sha256:1e3808aa9023d0980e7c15b1fa7c1ac16ff35925780cf5c459858b2d693f01a9 AS uv

FROM python:3.14.6-slim-trixie@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144 AS python-base

FROM python-base AS blender-download
RUN test "$(dpkg --print-architecture)" = amd64 \
    && apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl xz-utils \
    && rm -rf /var/lib/apt/lists/*
RUN curl --fail --silent --show-error --location --connect-timeout 15 --max-time 900 --retry 2 --retry-all-errors \
      https://download.blender.org/release/Blender4.5/blender-4.5.16-linux-x64.tar.xz \
      --output /tmp/blender.tar.xz \
    && printf '%s  %s\n' \
      23432b064977908beb1ab4b7f32f024e7331105c875c187dce002aff84b10c11 /tmp/blender.tar.xz \
      | sha256sum --check \
    && mkdir /opt/blender \
    && tar --extract --xz --file /tmp/blender.tar.xz --directory /opt/blender --strip-components=1 \
    && rm /tmp/blender.tar.xz

FROM python-base AS runtime-base
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
      libx11-6 libxfixes3 libxi6 libxrender1 libxxf86vm1 libxkbcommon0 libsm6 libice6 libgl1 libegl1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=blender-download /opt/blender /opt/blender

FROM runtime-base AS build-base
COPY --from=uv /uv /uvx /usr/local/bin/
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock .python-version README.md LICENSE ./
COPY src/vet3d ./src/vet3d

FROM build-base AS dev
RUN uv sync --locked
COPY tests/runtime ./tests/runtime
ENV PATH="/opt/venv/bin:$PATH" \
    UV_CACHE_DIR=/tmp/uv-cache \
    MYPY_CACHE_DIR=/tmp/mypy-cache
USER 1000:1000
CMD ["vet3d-operations-probe", "--config", "/etc/vet3d/config.yaml"]

FROM build-base AS production-build
RUN uv sync --locked --no-dev --no-editable

FROM runtime-base AS prod
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN groupadd --gid 10001 vet3d \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin vet3d
COPY --from=production-build /opt/venv /opt/venv
WORKDIR /opt/vet3d
USER 10001:10001
CMD ["vet3d-operations-probe", "--config", "/etc/vet3d/config.yaml"]
