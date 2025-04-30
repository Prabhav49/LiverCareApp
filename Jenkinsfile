pipeline {
    agent any

    environment {
        DOCKER_IMAGE_FRONTEND = 'prabhav49/frontend-app'
        DOCKER_IMAGE_BACKEND = 'prabhav49/backend-app'
    }

    stages {
        stage('Clone Repository') {
            steps {
                git 'https://github.com/Prabhav49/LiverCareApp.git'
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    // Install dependencies for backend and frontend
                    sh 'pip install -r frontend/requirements.txt'
                    sh 'pip install -r backend/requirements.txt'
                }
            }
        }

        stage('Run Backend Tests') {
            steps {
                script {
                    // Run tests for backend
                    sh 'pytest tests/backend/'
                }
            }
        }

        stage('Run Frontend Tests') {
            steps {
                script {
                    // Run tests for frontend
                    sh 'pytest tests/frontend/'
                }
            }
        }

        stage('Build Docker Images') {
            steps {
                script {
                    // Build the Docker images for frontend and backend
                    sh 'docker build -t $DOCKER_IMAGE_FRONTEND ./frontend'
                    sh 'docker build -t $DOCKER_IMAGE_BACKEND ./backend'
                }
            }
        }

        stage('Push Docker Images') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'docker-hub-credentials', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
                    script {
                        // Login to Docker Hub
                        sh 'echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin'

                        // Push the Docker images to Docker Hub
                        sh 'docker push $DOCKER_IMAGE_FRONTEND'
                        sh 'docker push $DOCKER_IMAGE_BACKEND'
                    }
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
