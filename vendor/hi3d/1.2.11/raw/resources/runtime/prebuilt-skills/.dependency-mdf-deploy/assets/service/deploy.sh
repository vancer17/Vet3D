#!/usr/bin/env bash
# Explicit local target only. Never removes/replaces an existing container.
set -euo pipefail
: "${IMAGE_NAME:?Set the built business image}"
: "${CONTAINER_NAME:?Set a new local container name}"
: "${SERVICE_NAME:?Set an authorized non-conflicting test service name}"
: "${TCP_PORT:?Set an unused TCP port}"
: "${MDF3_CONFIG:?Set the absolute dedicated config file path}"
: "${MDF3_ENV:?Set the corresponding environment}"
: "${MDF3_GROUP:?Set the corresponding Nacos group}"
: "${MODEL_DIR:?Set the absolute model directory (empty directory for text demo)}"
[[ "$MDF3_CONFIG" == /* && -f "$MDF3_CONFIG" && "$MODEL_DIR" == /* && -d "$MODEL_DIR" ]]
docker info >/dev/null
docker image inspect "$IMAGE_NAME" >/dev/null
if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    echo 'Container already exists; inspect ownership and stop/replace only with the appropriate scope.' >&2
    exit 2
fi
# Probe in the same network namespace; this neither reads the config nor reserves the port.
docker run --rm --network host --entrypoint python "$IMAGE_NAME" -c \
    'import socket,sys; p=int(sys.argv[1]); assert 1 <= p <= 65535; s=socket.socket(); s.bind(("0.0.0.0",p)); s.close()' "$TCP_PORT"
gpu_args=()
if [[ -n "${GPUS:-}" ]]; then gpu_args=(--gpus "$GPUS"); fi
if [[ "${DEVICE:-cpu}" == cuda* && ${#gpu_args[@]} == 0 ]]; then
    echo 'CUDA requires an explicit GPUS selection' >&2
    exit 2
fi
docker run -d --init --name "$CONTAINER_NAME" --network host \
    --restart unless-stopped --stop-timeout 120 --label local.deployer=mdf-deploy \
    --label "local.service=$SERVICE_NAME" --shm-size "${SHM_SIZE:-8g}" \
    --log-opt max-size=20m --log-opt max-file=3 --tmpfs /tmp:rw,mode=1777 \
    --user "$(id -u):$(id -g)" "${gpu_args[@]}" \
    -e DEVICE="${DEVICE:-cpu}" -e ALLOW_CPU_DEMO="${ALLOW_CPU_DEMO:-0}" \
    --mount "type=bind,src=$MDF3_CONFIG,dst=/config/mdf.yaml,readonly" \
    --mount "type=bind,src=$MODEL_DIR,dst=/models,readonly" "$IMAGE_NAME" \
    --service-name "$SERVICE_NAME" --config /config/mdf.yaml \
    --env "$MDF3_ENV" --group "$MDF3_GROUP" --tcp-port "$TCP_PORT" \
    --task-timeout "${TASK_TIMEOUT:-1800}"
