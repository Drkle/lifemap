FROM jenkins/jenkins:lts-jdk17

USER root
# Docker CLI + plugin de compose + buildx, desde el repositorio oficial de Docker.
# Jenkins NO corre un daemon propio: usa el del host a través del socket montado
# (docker-outside-of-docker).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg jq \
 && install -m 0755 -d /etc/apt/keyrings \
 && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
 && chmod a+r /etc/apt/keyrings/docker.asc \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
    > /etc/apt/sources.list.d/docker.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends jq docker-ce-cli docker-compose-plugin docker-buildx-plugin \
 && rm -rf /var/lib/apt/lists/*

# Plugins preinstalados para que el pipeline funcione desde el primer arranque.
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

# Se queda como root a propósito: en Docker Desktop el socket /var/run/docker.sock
# pertenece a root y el usuario "jenkins" no podría usarlo. Es aceptable en un entorno
# local académico; queda documentado como decisión D9 en docs/decisiones.md.
