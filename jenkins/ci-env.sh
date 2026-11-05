#!/usr/bin/env bash
# Traduce las credenciales de Jenkins a las variables que espera docker-compose.yml.
# Jenkins expone la credencial "mongo-root" como MONGO_CRED_USR / MONGO_CRED_PSW.
# Se usa con:  . jenkins/ci-env.sh   (así los secretos nunca aparecen en el Jenkinsfile)
export MONGO_ROOT_USER="${MONGO_CRED_USR:?Falta la credencial mongo-root en Jenkins}"
export MONGO_ROOT_PASSWORD="${MONGO_CRED_PSW:?Falta la credencial mongo-root en Jenkins}"
