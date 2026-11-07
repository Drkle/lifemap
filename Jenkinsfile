// Pipeline CI/CD — LifeMap (Entrega 1)
//
// Flujo: checkout -> build -> pytest -> Kaggle -> levantar servicios -> ingesta (main)
//        -> integración -> Spark sobre la semilla (verificado) -> Spark real (main)
//        -> API candidata en staging + smoke -> DESPLIEGUE -> verificación de /health y commit.
// Si cualquier etapa falla, las siguientes no se ejecutan: un fallo NUNCA llega a producción.
//
// Credenciales requeridas en Jenkins:
//   mongo-root          (Username with password)  usuario/contraseña root de MongoDB
//   kaggle-api-token    (Secret text)             token de la API de Kaggle
// Job de producción: "lifemap-main" (rama */main). Cualquier otro job es de validación.

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()        // dos builds a la vez pelearían por los mismos contenedores
        timeout(time: 180, unit: 'MINUTES')  // la primera ingesta y el primer entrenamiento son largos
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }

    triggers {
        githubPush()                     // webhook de GitHub (vía smee)
        pollSCM('H/2 * * * *')           // respaldo documentado si no llega el webhook
    }

    parameters {
        string(name: 'FECHA_CORTE', defaultValue: '2019-01-01', description: 'Corte UTC para reservar reseñas de streaming')
        string(name: 'CORTE_ENTRENAMIENTO', defaultValue: '2018-01-01', description: 'Corte anterior para entrenar riesgo sin fuga temporal')
        booleanParam(name: 'ENTREGA2', defaultValue: false,
            description: 'Entrena con corte temporal y valida Kafka/streaming antes de desplegar')
        booleanParam(name: 'ENTRENAR_RIESGO', defaultValue: false,
            description: 'Reentrena riesgo; una nueva versión requiere revisión de checkpoint')
        booleanParam(name: 'FORZAR_FALLO', defaultValue: false,
            description: 'Activa un test que falla a propósito para demostrar que NO se despliega')
        booleanParam(name: 'VERIFICAR_KAGGLE', defaultValue: true,
            description: 'Comprueba que la credencial de Kaggle funciona y el dataset es accesible')
        booleanParam(name: 'FORCE_RELOAD', defaultValue: false,
            description: 'Fuerza la recarga completa aunque ya exista una ingesta válida')
        booleanParam(name: 'RECALCULAR_TASAS', defaultValue: false,
            description: 'Recalcula las tasas de cierre (MapReduce) sobre los datos reales')
        booleanParam(name: 'ENTRENAR_MODELO', defaultValue: false,
            description: 'Reentrena el modelo de sentimiento sobre los datos reales')
        booleanParam(name: 'EJECUTAR_BALANCEO', defaultValue: false,
            description: 'Repite el experimento de balanceo (2, 8, 32 y 200 particiones)')
    }

    environment {
        PRODUCCION     = "${env.JOB_NAME == 'lifemap-main' ? 'true' : 'false'}"
        API_TAG        = "${env.JOB_NAME == 'lifemap-main' ? env.BUILD_NUMBER : 'validation-' + env.BUILD_NUMBER}"
        STAGING        = "lifemap-api-staging-${env.JOB_BASE_NAME}-${env.BUILD_NUMBER}"
        // Las ramas procesan solo 2 particiones de review.json y nunca escriben en producción.
        INGEST_MAX_PARTICIONES = "${env.JOB_NAME == 'lifemap-main' ? '0' : '2'}"
        MONGO_CRED     = credentials('mongo-root')   // MONGO_CRED_USR / MONGO_CRED_PSW (enmascarados)
        KAGGLE_DATASET = 'yelp-dataset/yelp-dataset'
        INFRA          = 'mongodb spark-master spark-worker dask-scheduler dask-worker-1 dask-worker-2'
        DOCKER_BUILDKIT = '1'
        DASK_WORKER_THREADS = '1'
        REVIEW_BLOCKSIZE = '16MB'
        INGEST_MAX_EN_VUELO = '2'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                script {
                    // Hash que se graba en la imagen de la API y que /health debe informar.
                    env.GIT_COMMIT = sh(returnStdout: true, script: 'git rev-parse HEAD').trim()
                }
                sh 'git log -1 --pretty="Commit %H de %an: %s"'
            }
        }

        stage('Construir imágenes') {
            steps {
                sh '''
                    . jenkins/ci-env.sh
                    reintentar() {
                        intento=1
                        until "$@"; do
                            [ "$intento" -ge 3 ] && { echo "Falló después de 3 intentos."; return 1; }
                            echo "Fallo transitorio; reintento en $((intento * 10)) s..."
                            sleep $((intento * 10)); intento=$((intento + 1))
                        done
                    }
                    echo "Commit a construir: ${GIT_COMMIT}"
                    reintentar docker compose build
                    reintentar docker build --target test -t lifemap-api-test:${API_TAG} api
                    reintentar docker build --target test -t lifemap-ingest-test:${API_TAG} ingest
                '''
            }
        }

        stage('Pruebas unitarias (pytest)') {
            steps {
                sh 'docker run --rm -e FORZAR_FALLO=${FORZAR_FALLO} lifemap-api-test:${API_TAG}'
                sh 'docker run --rm lifemap-ingest-test:${API_TAG}'
                sh 'docker run --rm -e SPARK_LOCAL_IP=127.0.0.1 --entrypoint /opt/spark/bin/spark-submit lifemap-spark:latest --master local[2] /opt/tests/test_spark.py'
            }
        }

        stage('Verificar acceso a Kaggle') {
            when { expression { params.VERIFICAR_KAGGLE } }
            steps {
                withCredentials([string(credentialsId: 'kaggle-api-token', variable: 'KAGGLE_API_TOKEN')]) {
                    // -e VAR sin valor: Docker toma el valor del entorno sin mostrarlo en el log
                    sh 'docker run --rm -e KAGGLE_API_TOKEN lifemap-dask:latest kaggle datasets files "${KAGGLE_DATASET}"'
                }
            }
        }

        stage('Levantar servicios') {
            steps {
                sh '''
                    . jenkins/ci-env.sh
                    docker compose up -d --wait --wait-timeout 300 ${INFRA}
                    docker compose ps
                '''
            }
        }

        stage('Ingesta Dask (idempotente)') {
            when { expression { env.PRODUCCION == 'true' } }
            steps {
                withCredentials([string(credentialsId: 'kaggle-api-token', variable: 'KAGGLE_API_TOKEN')]) {
                    sh '''
                        . jenkins/ci-env.sh
                        docker compose run --rm dask-job python prueba_reintentos.py
                        FORCE_RELOAD=${FORCE_RELOAD} docker compose run --rm \
                            -e KAGGLE_API_TOKEN dask-job python pipeline_ingesta.py
                    '''
                }
            }
        }

        stage('Pruebas de integración') {
            steps {
                sh '''
                    . jenkins/ci-env.sh
                    echo "== Dask: 2 workers + MongoDB =="
                    docker compose run --rm dask-job python check_cluster.py
                    echo "== Spark: MongoDB Spark Connector =="
                    docker compose exec -T spark-master spark-submit /opt/jobs/check_conexion.py
                '''
            }
        }

        stage('Spark sobre la semilla') {
            // En TODOS los builds: MapReduce + verificación contra valores conocidos y un
            // entrenamiento rápido del pipeline de sentimiento. Escribe solo semilla_*.
            steps {
                sh '''
                    . jenkins/ci-env.sh
                    SUBMIT="docker compose exec -T spark-master spark-submit"
                    $SUBMIT /opt/jobs/tasas_mapreduce.py --negocios negocios_semilla --min-dias 0
                    $SUBMIT /opt/jobs/verificar_semilla.py
                    $SUBMIT /opt/jobs/sentimiento.py --coleccion resenas_semilla --muestra 0 --num-features 1024
                '''
            }
        }

        stage('Spark sobre los datos reales') {
            when { expression { env.PRODUCCION == 'true' } }
            steps {
                sh '''
                    . jenkins/ci-env.sh
                    SUBMIT="docker compose exec -T spark-master spark-submit"
                    contar() {
                        docker compose exec -T -e COLECCION="$1" mongodb sh -c 'mongosh --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin "$MONGO_DB" --eval "db.getCollection(process.env.COLECCION).countDocuments({})"' | tr -d '[:space:]'
                    }

                    if [ "${RECALCULAR_TASAS}" = "true" ] || [ "$(contar tasas_categoria)" = "0" ]; then
                        echo "== MapReduce de tasas de cierre =="
                        $SUBMIT /opt/jobs/tasas_mapreduce.py --negocios negocios
                    else
                        echo "Tasas ya calculadas (RECALCULAR_TASAS para repetir)."
                    fi

                    requiere_modelo=false
                    if [ "${ENTREGA2}" = "true" ]; then
                        docker compose exec -T -e FECHA_CORTE="${FECHA_CORTE:-2019-01-01}" spark-master python3 -c 'import json,os; from datetime import datetime; from pathlib import Path; p=Path("/models/sentimiento_v1/lifemap_metadata.json"); assert p.exists() and json.loads(p.read_text()).get("fecha_corte")==datetime.fromisoformat(os.environ["FECHA_CORTE"]).isoformat()' || requiere_modelo=true
                    fi
                    if [ "${ENTRENAR_MODELO}" = "true" ] || [ "$requiere_modelo" = "true" ] || ! docker compose exec -T spark-master test -f /models/sentimiento_v1/lifemap_metadata.json; then
                        echo "== Entrenamiento del modelo de sentimiento =="
                        if [ "${ENTREGA2}" = "true" ]; then
                            $SUBMIT /opt/jobs/sentimiento.py --coleccion resenas --fecha-corte "${FECHA_CORTE:-2019-01-01}"
                        else
                            $SUBMIT /opt/jobs/sentimiento.py --coleccion resenas
                        fi
                    else
                        echo "Modelo ya entrenado (ENTRENAR_MODELO para repetir)."
                    fi

                    if [ "${EJECUTAR_BALANCEO}" = "true" ] || [ "$(contar balanceo_resumen)" = "0" ]; then
                        echo "== Balanceo de carga =="
                        $SUBMIT /opt/jobs/balanceo.py --resenas resenas
                    else
                        echo "Balanceo ya medido (EJECUTAR_BALANCEO para repetir)."
                    fi
                '''
            }
        }

        stage('Entrega 2: riesgo y streaming aislado') {
            when { expression { env.PRODUCCION == 'true' && params.ENTREGA2 } }
            steps {
                sh '''
                    . jenkins/ci-env.sh
                    docker compose build streaming-job
                    docker compose run --rm --no-deps streaming-job python -m pytest -q tests/test_riesgo.py
                    if [ "${ENTRENAR_RIESGO}" = "true" ] || ! docker compose run --rm --no-deps streaming-job python -c 'import json,os; from datetime import datetime; from pathlib import Path; p=Path("/models/riesgo_v1.json"); assert p.exists() and json.loads(p.read_text()).get("corte_evaluacion")==datetime.fromisoformat(os.getenv("FECHA_CORTE", "2019-01-01")).isoformat()'; then
                        docker compose run --rm streaming-job python entrenar_riesgo.py
                    fi
                    docker compose --profile streaming up -d --wait kafka
                    docker compose --profile streaming run --rm kafka-init
                    bash scripts/smoke_streaming.sh
                '''
            }
        }

        stage('Pruebas contra la API (staging)') {
            // La imagen candidata se prueba contra la semilla: valida sin tocar producción.
            steps {
                sh '''
                    . jenkins/ci-env.sh
                    docker run -d --name ${STAGING} --network lifemap-net \
                        -e MONGO_ROOT_USER -e MONGO_ROOT_PASSWORD \
                        -e MONGO_HOST=mongodb -e MONGO_DB=lifemap \
                        -e NEGOCIOS_COLLECTION=negocios_semilla -e TASAS_PREFIX=semilla_ \
                        -e MODELO_PATH=/models/semilla_sentimiento_v1 \
                        -e SPARK_UI_URL=http://spark-master:8080 \
                        -e DASK_DASHBOARD_URL=http://dask-scheduler:8787 \
                        -e APP_VERSION=${API_TAG}-staging \
                        -v lifemap_modelos:/models:ro \
                        lifemap-api:${API_TAG}
                    SMOKE_SEMILLA=true SMOKE_COMMIT=${GIT_COMMIT} SMOKE_PREDICT_REQUERIDO=true \
                        bash scripts/smoke_api.sh http://${STAGING}:5000
                '''
            }
        }

        stage('Despliegue') {
            when { expression { env.PRODUCCION == 'true' } }
            steps {
                sh '''
                    . jenkins/ci-env.sh
                    if [ "${ENTREGA2}" = "true" ]; then
                        docker compose --profile streaming up -d --no-build streaming
                        export STREAMING_ENABLED=true
                    fi
                    bash scripts/deploy_api.sh
                '''
            }
        }
    }

    post {
        always {
            sh '''
                docker rm -f ${STAGING} >/dev/null 2>&1 || true
                docker image rm lifemap-api-test:${API_TAG} lifemap-ingest-test:${API_TAG} >/dev/null 2>&1 || true
            '''
        }
        success {
            sh '''
                docker images lifemap-api --format '{{.Tag}}' | grep -E '^[0-9]+$' | sort -n | head -n -5 \
                  | xargs -r -I{} docker image rm lifemap-api:{} >/dev/null 2>&1 || true
            '''
            echo "OK: build ${env.BUILD_NUMBER} (${env.PRODUCCION == 'true' ? 'desplegado' : 'validado sin tocar producción'})."
        }
        failure {
            sh '''
                # Solo metadatos de estado y logs: nunca imprimir .env ni docker inspect completo.
                . jenkins/ci-env.sh
                docker compose ps || true
                for servicio in dask-scheduler dask-worker-1 dask-worker-2; do
                    cid=$(docker compose ps -aq "$servicio")
                    if [ -n "$cid" ]; then
                        docker inspect --format '{{.Name}} estado={{.State.Status}} oom={{.State.OOMKilled}} reinicios={{.RestartCount}} salida={{.State.ExitCode}}' "$cid" || true
                    fi
                done
                docker compose logs --no-color --tail=100 dask-scheduler dask-worker-1 dask-worker-2 || true
            '''
            echo "FALLO: el pipeline se detuvo y NO se desplegó la versión ${env.BUILD_NUMBER}. Revisar logs: no se completó el despliegue; deploy_api restaura la imagen previa si falla su smoke."
        }
    }
}
