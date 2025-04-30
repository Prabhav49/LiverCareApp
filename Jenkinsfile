pipeline {
    agent any

    environment {
        GIT_CREDENTIALS = 'github-cred'
        DOCKER_IMAGE_FRONTEND = 'prabhav49/frontend-app'
        DOCKER_IMAGE_BACKEND = 'prabhav49/backend-app'
        KUBECONFIG_FILE = credentials('kube-config')  // Should be a File credential
        KUBECONFIG_PATH = "${WORKSPACE}/.kube/config" // Workspace subdir (safe for writes)
    }

    stages {
        stage('Clone Repository') {
            steps {
                git(
                    url: 'https://github.com/Prabhav49/LiverCareApp.git',
                    credentialsId: 'github-cred'
                )
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    sh 'python3 -m venv venv-backend'
                    sh '. venv-backend/bin/activate && pip install -r backend/requirements.txt'

                    sh 'python3 -m venv venv-frontend'
                    sh '. venv-frontend/bin/activate && pip install -r frontend/requirements.txt'
                }
            }
        }

        stage('Run Backend Tests') {
            steps {
                script {
                    sh '''
                        export PYTHONPATH=$PYTHONPATH:$PWD/backend/src
                        . venv-backend/bin/activate && pytest tests/backend/ --maxfail=1 --disable-warnings -q
                    '''
                }
            }
        }

        stage('Run Frontend Tests') {
            steps {
                script {
                    sh '''
                        export PYTHONPATH=$PYTHONPATH:$PWD/frontend
                        . venv-frontend/bin/activate && pytest tests/frontend/ --maxfail=1 --disable-warnings -q
                    '''
                }
            }
        }

        stage('Build and Push Docker Images') {
            steps {
                script {
                    sh 'docker build -t $DOCKER_IMAGE_FRONTEND ./frontend'
                    sh 'docker build -t $DOCKER_IMAGE_BACKEND ./backend'
                }

                withCredentials([usernamePassword(credentialsId: 'docker-hub-credentials', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
                    script {
                        sh 'echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin'
                        sh 'docker push $DOCKER_IMAGE_FRONTEND'
                        sh 'docker push $DOCKER_IMAGE_BACKEND'
                    }
                }
            }
        }

        stage('Prepare Kubeconfig') {
            steps {
                script {
                    // Ensure .kube directory exists in workspace
                    sh 'mkdir -p $(dirname "$KUBECONFIG_PATH")'
                    // Copy securely into workspace instead of /tmp
                    sh 'cp "$KUBECONFIG_FILE" "$KUBECONFIG_PATH"'
                }
            }
        }

        stage('Deploy using Ansible') {
            steps {
                script {
                    sh "ansible-playbook -i localhost, ansible/playbook.yml --extra-vars kubeconfig_path=$KUBECONFIG_PATH"
                }
            }
        }
    }

    post {
        success {
            emailext(
                to: 'iam49smith@gmail.com',
                subject: "SUCCESS: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                body: """<p>The build and deployment were <b>successful!</b></p>
                         <p>Check the build details: <a href="${env.BUILD_URL}">${env.BUILD_URL}</a></p>"""
            )
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
            cleanWs()
        }
    }
}
