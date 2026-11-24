# 文件信息：L1-05 的开发与生产镜像共用入口，固定 CPython 和 uv 制品身份。
# 作用：开发阶段安装测试工具；生产阶段只复制非 editable 安装后的虚拟环境。
# 边界：镜像托管可信宿主，不提供 Blender 或不可信动态代码的执行沙箱。
FROM ghcr.io/astral-sh/uv:0.11.25@sha256:1e3808aa9023d0980e7c15b1fa7c1ac16ff35925780cf5c459858b2d693f01a9 AS uv

FROM python:3.14.6-slim-trixie@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144 AS python-base

FROM python-base AS build-base
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

FROM python-base AS prod
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN groupadd --gid 10001 vet3d \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin vet3d
COPY --from=production-build /opt/venv /opt/venv
WORKDIR /opt/vet3d
USER 10001:10001
CMD ["vet3d-operations-probe", "--config", "/etc/vet3d/config.yaml"]
