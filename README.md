# tyk-sre-assignment

This repository contains the boilerplate projects for the SRE role interview assignments. There are two projects: one for Go and one for Python respectively.

### Go Project

Location: https://github.com/TykTechnologies/tyk-sre-assignment/tree/main/golang

In order to build the project run:
```
go mod tidy & go build
```

To run it against a real Kubernetes API server:
```
./tyk-sre-assignment --kubeconfig '/path/to/your/kube/conf' --address ":8080"
```

To execute unit tests:
```
go test -v
```

### Python Project

Location: https://github.com/TykTechnologies/tyk-sre-assignment/tree/main/python

We suggest using a Python virtual env, e.g.:
```
python3 -m venv .venv
source .venv/bin/activate
```

Make sure to install the dependencies using `pip`:
```
pip3 install -r requirements.txt
```

To run it against a real Kubernetes API server:
```
python3 main.py --kubeconfig '/path/to/your/kube/conf' --address ":8080"
```

To execute unit tests:
```
python3 tests.py -v
```

### Code Implemented in Python
The solution includes:

- SRE-focused health endpoints
- Kubernetes API integration
- Deployment health evaluation
- Unit tests
- Container image build 
- Helm chart for Kubernetes deployment
- CI workflow to build, deploy, and validate the application in a Kind cluster

### Requirements & Completed Tasks
- **As an SRE, I want to always know whether this tool can successfully communicate with the configured Kubernetes API server**
- **As an SRE, I want to know whether all the deployments in the Kubernetes cluster have as many healthy pods as requested by their respective Deployment spec.**
- **As an application developer, I want to build this application into a container image when I push a commit to the main branch of its repository.**
- **As an application developer, I want to be able to deploy this application into a Kubernetes cluster using Helm.**
#### 1. API Server Connectivity Check

##### User Story:

As an SRE, I want to always know whether this tool can successfully communicate with the configured Kubernetes API server.

##### Implementation:
Added a new endpoint /health/apiserver which:

- Creates a Kubernetes API client using:
    - load_kube_config when running locally (Local mode: --kubeconfig /path/to/kubeconfig)
    - load_incluster_config when running inside Kubernetes (config.load_incluster_config() when running inside Kubernetes)
- Calls the API server’s /version endpoint
- On success returns HTTP 200 with:
```
{ "status": "ok", "version": "v1.x.y" }
```
- On failure returns HTTP 500 with the underlying error
- This gives SREs quick visibility into API server connectivity and authentication health.

#### 2. Cluster Deployment Health Evaluation

##### User Story
As an SRE, I want to verify that every Deployment in the Kubernetes cluster is running the expected number of healthy pods as defined in its Deployment specification.

##### Implementation
A new endpoint **`/health/deployments`** was added. This endpoint:

- Retrieves all Deployments across all namespaces.
- Compares:
  - **spec.replicas** (desired pod count)
  - **status.ready_replicas** (healthy pod count)
- Determines whether each Deployment is healthy based on this comparison.
- Produces an overall cluster status:
  - **ok** – all deployments are healthy
  - **degraded** – at least one deployment is not healthy
- Returns a detailed JSON report to help with debugging and visibility.

This endpoint offers a single place to check the overall health of deployed workloads in the cluster.

#### 3. Containerization

##### User Story
As an application developer, I want this application to be built into a container image whenever a commit is pushed to the `main` branch of the repository.

##### Implementation
A `Dockerfile` is included in the `python/` directory. It:

- Uses an official Python base image
- Installs all dependencies from `requirements.txt`
- Copies the application source code
- Exposes port **8080**
- Runs `main.py` as the entrypoint, supporting both kubeconfig and in-cluster authentication

###### Local Image Build
```bash
cd python
docker build -t tyk-sre-assignment:latest .
```
###### Local Run Example (using local kubeconfig)
```
docker run -p 8080:8080 \
  -v ~/.kube/config:/root/.kube/config \
  tyk-sre-assignment:latest \
  --kubeconfig /root/.kube/config --address ":8080"
```
###### CI Build (GitHub Actions)
The container image is also built inside the GitHub Actions workflow build-image.yml

#### 4. Helm Chart Deployment

##### User Story
As an application developer, I want to deploy this application into a Kubernetes cluster using Helm.
##### Chart Location
`helm/tyk-sre-assignment/`
##### Chart Contents
- **Chart.yaml** – chart metadata  
- **values.yaml** – configurable settings (image, tag, resources, service type, etc.)  
- **templates/deployment.yaml** – Deployment including:
  - Container running on port **8080**
  - Liveness and readiness probes pointing to `/healthz`
- **templates/service.yaml** – ClusterIP Service exposing the application  
- **templates/serviceaccount.yaml** – ServiceAccount for in-cluster execution  
- **templates/clusterrole.yaml** – ClusterRole allowing `deployments.apps` list permissions  
- **templates/clusterrolebinding.yaml** – Binds the ServiceAccount to the ClusterRole  
- **templates/NOTES.txt** – helper commands for debugging and checking endpoints  
##### Why RBAC Is Required
The `/health/deployments` endpoint lists deployments across **all namespaces**, which requires permission to read `deployments.apps`.  
The Helm chart provides the required RBAC resources (ServiceAccount, ClusterRole, ClusterRoleBinding) so the pod can perform this action when running inside Kubernetes.
##### Installation Example
```bash
helm install tyk-sre ./helm/tyk-sre-assignment -n sre-tools --create-namespace
```
##### Check Pods:
```bash
kubectl get pods -n sre-tools
```
##### Port-Forward and Test Endpoints
```bash
kubectl port-forward svc/tyk-sre-service 8080:8080 -n sre-tools

curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/health/apiserver
curl http://127.0.0.1:8080/health/deployments
```
##### GitHub Actions CI: Build, Deploy, and Validate

A GitHub Actions workflow is included to validate the full stack by deploying the application into a temporary Kubernetes cluster created with **Kind**.

###### Workflow Location
`.github/workflows/helm-deploy-test.yaml`

###### What the Workflow Does
- Checks out the repository  
- Sets up Python and executes the unit tests  
- Creates a Kind cluster inside the GitHub Actions runner  
- Builds the Docker image (`tyk-sre-assignment:latest`)  
- Loads the image into the Kind cluster  
- Installs the Helm chart into a namespace (for example, `ci`)  
- Waits for the Deployment to become ready  
- Starts a temporary curl pod inside the cluster to test the application via:

  - `http://tyk-sre-service:8080/healthz`  
  - `http://tyk-sre-service:8080/health/apiserver`  
  - `http://tyk-sre-service:8080/health/deployments`

###### What This Validates
- The Docker image is built successfully  
- The Helm chart deploys without errors  
- The application can interact with the Kubernetes API  
- All SRE health endpoints respond correctly inside a real Kubernetes environment  

**This workflow provides full end-to-end validation of the application, chart, and cluster readiness**
