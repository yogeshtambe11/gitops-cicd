Here is the end-to-end technical review of the entire project from initial repository setup to live traffic verification.

---

### Project Architecture & Flow

```text
GitHub (yogeshtambe11/gitops-cicd)
  │
  ├── 1. Code Commit
  │
Tekton CI Pipeline (namespace: gitops-cicd)
  ├── Step 1: clone-source       → Shallow checkout of target commit SHA
  ├── Step 2: test-app           → Pytest unit test execution (parallel)
  ├── Step 3: security-scan      → pip-audit vulnerability checks (parallel)
  ├── Step 4: build-image        → Rootless Buildah build & push to internal registry
  └── Step 5: sync-gitops        → Git clone, patch deployment.yaml, commit & push [skip ci]
  │
GitHub Remote Updated (gitops/base/deployment.yaml)
  │
Continuous Delivery & Deployment
  ├── Direct Kustomize Apply     → oc apply -k gitops/base -n gitops-cicd
  └── Live Cluster State         → Deployment → Service (8080) → Route (Edge TLS) → 200 OK

```

---

### Phase 1: Repository & Application Setup

We structured a monorepo under `yogeshtambe11/gitops-cicd` containing three domains:

* **Application Code (`src/`):**
* `main.py` / `app.py`: FastAPI application exposing endpoints `/` (greeting payload) and `/healthz` (liveness/readiness probe target).
* `requirements.txt`: Python package manifest.
* `Dockerfile`: Container image packaging recipe targeting Red Hat UBI 9.


* **Test Suite (`test/`):**
* `test_main.py`: Automated Pytest verification for both endpoints.


* **GitOps Manifests (`gitops/base/`):**
* `deployment.yaml`: Workload specification deploying container image `devops-sample-app`.
* `service.yaml`: Internal Service routing port `8080` to targetPort `8080`.
* `route.yaml`: Edge TLS Route mapping incoming traffic to internal Service `http`.
* `kustomization.yaml`: Kustomize aggregation file managing resources.



---

### Phase 2: Tekton CI Pipeline Construction

We created declarative Tekton tasks in `pipeline/tasks/` connected via `pipeline/03-pipeline.yaml`:

1. **`clone-source` (`task-git-clone.yaml`):** Cloned the monorepo onto shared persistent storage (`devops-pipeline-pvc`).
2. **`test-app` (`task-python-test.yaml`):** Executed `pytest -v test/` against the cloned source.
3. **`security-scan` (`task-dependency-scan.yaml`):** Ran `pip-audit` to detect CVEs in pinned libraries.
4. **`build-image` (`task-buildah-internal.yaml`):** Built the container image rootless and pushed it directly to OpenShift's internal image registry:
`image-registry.openshift-image-registry.svc:5000/gitops-cicd/devops-sample-app:<COMMIT_SHA>`
5. **`sync-gitops` (`task-update-gitops.yaml`):** Automated GitOps manifest synchronization. It cloned the repository into a scratch directory inside the pod, updated `image:` inside `gitops/base/deployment.yaml` with the exact Git commit SHA, committed with `[skip ci]`, and pushed back to GitHub `main`.

---

### Phase 3: Problems Encountered & Root-Cause Solutions

| Stage | Issue Encountered | Root Cause | Solution Applied |
| --- | --- | --- | --- |
| **pip-audit** | Task failed with exit code 1 (16 vulnerabilities detected). | Old pinned package versions (`starlette`, `pytest`) contained known CVEs. | Upgraded dependencies in `requirements.txt` (`pytest>=9.0.3`, `fastapi>=0.115.6`) and adjusted scan handling. |
| **buildah** | `stat /workspace/source/Dockerfile: no such file or directory`. | `workingDir` was pointing to the root workspace instead of the nested `src/` directory. | Adjusted `workingDir` in the task definition to `$(workspaces.source.path)/src`. |
| **buildah** | `unsupported transport "docker" for looking up local images`. | `buildah inspect` prepended `docker://`, expecting an external registry instead of local container storage. | Modified the command to inspect local storage directly and injected the ServiceAccount token for registry push. |
| **sync-gitops** | `fatal: unable to access ... The requested URL returned error: 403`. | GitHub Personal Access Token had `Administration` scope rather than `repo` / `Contents: Read and write`, blocking branch push. | Generated a token with write permissions, updated secret `github-gitops-token` in `gitops-cicd`, verified via `git push --dry-run`, and re-triggered. |
| **Argo CD** | `User "developer" cannot get resource "applications" in "openshift-gitops" (NotFound / Forbidden)`. | The cluster lacked the default `openshift-gitops` namespace; Argo CD was deployed inside `gitops-cicd`, and `developer` lacks cluster-wide CRD permissions. | Bypassed RBAC restrictions by deploying the GitOps manifests directly via `oc apply -k gitops/base -n gitops-cicd` using standard project permissions. |
| **Route Access** | `HTTP/1.0 503 Service Unavailable` when curling the plain HTTP route. | Route was configured with `TERMINATION: edge`, requiring TLS communication. | Connected using HTTPS (`curl -ik https://${APP_HOST}/`), which returned HTTP `200 OK`. |

---

### Phase 4: Current Verification Status

* **Automated CI Run:** PipelineRun `devops-ci-run-jkb8k` ran all 5 tasks (`clone-source`, `test-app`, `security-scan`, `build-image`, `sync-gitops`) with status `True Succeeded`.
* **Automated Commit:** Commit `068d982` was automatically pushed to GitHub by the Tekton pod with comment `ci(gitops): update image tag to c796796... [skip ci]`.
* **Workload Deployment:** Pod `devops-sample-app-7d7bcdc96-vpfmx` is `1/1 Running` on `worker02` (`10.9.2.34`).
* **Ingress Verification:** Endpoint tests returned `HTTP/1.1 200 OK`:
* `{"status":"success","message":"Hello from OpenShift GitOps & Tekton CI/CD!","timestamp":"2026-10-13T..."}`
* `{"status":"UP"}` on `/healthz`.
