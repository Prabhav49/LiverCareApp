pipeline {
    agent any

    environment {
        GIT_CREDENTIALS = 'github-cred'
        DOCKER_IMAGE_FRONTEND = 'prabhav49/frontend-app'
        DOCKER_IMAGE_BACKEND = 'prabhav49/backend-app'
        DOCKER_TAG = "${env.BUILD_NUMBER}"  // Unique tag per build
        KUBECONFIG_FILE = credentials('kube-config')
        KUBECONFIG_PATH = "${WORKSPACE}/.kube/config"
        MINIKUBE_CERTS_DIR = "${WORKSPACE}/.minikube"
    }

    stages {
        stage('Clone Repository') {
            steps {
                git(
                    url: 'https://github.com/Prabhav49/LiverCareApp.git',
                    credentialsId: 'github-cred',
                    poll: true  // Enable SCM polling
                )
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    sh 'python3 -m venv venv-backend'
                    sh '. venv-backend/bin/activate && pip install -r backend/requirements.txt'
                    sh '. venv-backend/bin/activate && pip install pytest'

                    sh 'python3 -m venv venv-frontend'
                    sh '. venv-frontend/bin/activate && pip install -r frontend/requirements.txt'
                    sh '. venv-frontend/bin/activate && pip install pytest'
                }
            }
        }

        stage('Run Tests') {
            steps {
                script {
                    sh '''
                    . venv-backend/bin/activate && 
                    export PYTHONPATH=$PYTHONPATH:$PWD/backend/src && 
                    pytest tests/backend/ --maxfail=1 --disable-warnings -q
                    '''
                    sh '''
                    . venv-frontend/bin/activate && 
                    export PYTHONPATH=$PYTHONPATH:$PWD/frontend && 
                    pytest tests/frontend/ --maxfail=1 --disable-warnings -q
                    '''
                }
            }
        }

        stage('Build Docker Images') {
            steps {
                script {
                    // Force clean builds without cache and use build args
                    sh """
                    docker build \
                        --no-cache \
                        --build-arg BUILD_NUMBER=${env.BUILD_NUMBER} \
                        -t ${DOCKER_IMAGE_FRONTEND}:${DOCKER_TAG} \
                        -t ${DOCKER_IMAGE_FRONTEND}:latest \
                        ./frontend
                    """
                    sh """
                    docker build \
                        --no-cache \
                        --build-arg BUILD_NUMBER=${env.BUILD_NUMBER} \
                        -t ${DOCKER_IMAGE_BACKEND}:${DOCKER_TAG} \
                        -t ${DOCKER_IMAGE_BACKEND}:latest \
                        ./backend
                    """
                }
            }
        }

        stage('Push Docker Images') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'docker-hub-credentials', 
                    usernameVariable: 'DOCKER_USER', 
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    script {
                        sh 'echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin'
                        sh "docker push ${DOCKER_IMAGE_FRONTEND}:${DOCKER_TAG}"
                        sh "docker push ${DOCKER_IMAGE_FRONTEND}:latest"
                        sh "docker push ${DOCKER_IMAGE_BACKEND}:${DOCKER_TAG}"
                        sh "docker push ${DOCKER_IMAGE_BACKEND}:latest"
                    }
                }
            }
        }

        stage('Prepare Deployment') {
            steps {
                script {
                    // Update k8s manifests with new image tags
                    sh """
                    sed -i 's|image: ${DOCKER_IMAGE_FRONTEND}:.*|image: ${DOCKER_IMAGE_FRONTEND}:${DOCKER_TAG}|g' k8s-manifests/frontend-deployment.yaml
                    sed -i 's|image: ${DOCKER_IMAGE_BACKEND}:.*|image: ${DOCKER_IMAGE_BACKEND}:${DOCKER_TAG}|g' k8s-manifests/backend-deployment.yaml
                    """
                    
                    // Prepare kubeconfig
                    sh "mkdir -p ${MINIKUBE_CERTS_DIR}/profiles/minikube"
                    sh "mkdir -p ${WORKSPACE}/.kube"
                    
                    withCredentials([
                        file(credentialsId: 'minikube-client-cert', variable: 'CLIENT_CERT'),
                        file(credentialsId: 'minikube-client-key', variable: 'CLIENT_KEY'),
                        file(credentialsId: 'minikube-ca', variable: 'CA_CRT'),
                        file(credentialsId: 'kube-config', variable: 'KUBECONFIG_FILE')
                    ]) {
                        sh "cp '$CLIENT_CERT' ${MINIKUBE_CERTS_DIR}/profiles/minikube/client.crt"
                        sh "cp '$CLIENT_KEY' ${MINIKUBE_CERTS_DIR}/profiles/minikube/client.key"
                        sh "cp '$CA_CRT' ${MINIKUBE_CERTS_DIR}/ca.crt"
                        sh "cp '$KUBECONFIG_FILE' ${KUBECONFIG_PATH}"
                        
                        sh """
                        sed -i 's|/home/prabhav/.minikube/profiles/minikube/client.crt|${MINIKUBE_CERTS_DIR}/profiles/minikube/client.crt|g' ${KUBECONFIG_PATH}
                        sed -i 's|/home/prabhav/.minikube/profiles/minikube/client.key|${MINIKUBE_CERTS_DIR}/profiles/minikube/client.key|g' ${KUBECONFIG_PATH}
                        sed -i 's|/home/prabhav/.minikube/ca.crt|${MINIKUBE_CERTS_DIR}/ca.crt|g' ${KUBECONFIG_PATH}
                        """
                        
                        sh "chmod 644 ${MINIKUBE_CERTS_DIR}/profiles/minikube/client.crt"
                        sh "chmod 600 ${MINIKUBE_CERTS_DIR}/profiles/minikube/client.key"
                        sh "chmod 644 ${MINIKUBE_CERTS_DIR}/ca.crt"
                        sh "chmod 600 ${KUBECONFIG_PATH}"
                    }
                    
                    sh "KUBECONFIG=${KUBECONFIG_PATH} kubectl cluster-info"
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                script {
                    sh """
                    KUBECONFIG=${KUBECONFIG_PATH} kubectl apply -f k8s-manifests/ -n mlops-project
                    KUBECONFIG=${KUBECONFIG_PATH} kubectl rollout restart deployment/frontend-deployment -n mlops-project
                    KUBECONFIG=${KUBECONFIG_PATH} kubectl rollout restart deployment/backend-deployment -n mlops-project
                    KUBECONFIG=${KUBECONFIG_PATH} kubectl rollout status deployment/frontend-deployment -n mlops-project --timeout=300s
                    KUBECONFIG=${KUBECONFIG_PATH} kubectl rollout status deployment/backend-deployment -n mlops-project --timeout=300s
                    """
                }
            }
        }
    }

    post {
        success {
            script {
                def frontend_url = sh(
                    script: "KUBECONFIG=${KUBECONFIG_PATH} kubectl get svc frontend-service -n mlops-project -o jsonpath='http://{.status.loadBalancer.ingress[0].ip}:{.spec.ports[0].nodePort}'",
                    returnStdout: true
                ).trim()
                
                emailext(
                    to: 'iam49smith@gmail.com',
                    subject: "SUCCESS: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                    body: """<p>The build and deployment were <b>successful!</b></p>
                             <p>Frontend URL: <a href="${frontend_url}">${frontend_url}</a></p>
                             <p>Check the build details: <a href="${env.BUILD_URL}">${env.BUILD_URL}</a></p>"""
                )
            }
        }
        failure {
            emailext(
                to: 'iam49smith@gmail.com',
                subject: "FAILURE: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                body: """<p>The build or deployment <b>failed!</b></p>
                         <p>Check the build details: <a href="${env.BUILD_URL}">${env.BUILD_URL}</a></p>"""
            )
        }
        always {
            sh "docker system prune -f"
            cleanWs()
        }
    }
}