#!/usr/bin/env bash
# El tar via stdin evita bind mounts del workspace en Docker-outside-of-Docker.
set -euo pipefail
: "${API_TAG:?Falta API_TAG}"
tar -cf - scripts/deploy_api.sh scripts/tests/test_deploy.py scripts/tests/test_modo_jenkins.py jenkins/ci-env.sh Jenkinsfile \
    | docker run --rm -i --entrypoint sh "lifemap-api-test:${API_TAG}" \
        -c 'mkdir -p /tmp/prueba-deploy; cd /tmp/prueba-deploy; tar -xf -; python -m pytest -q scripts/tests'
