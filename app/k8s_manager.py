import logging
from kubernetes import client, config, stream
from kubernetes.client.rest import ApiException

logger = logging.getLogger("uvicorn")

try:
    config.load_kube_config()
except:
    try: config.load_incluster_config()
    except: logger.error("K8s config not found")

v1 = client.CoreV1Api()

def create_workspace_pod(workspace_id: int, username: str):
    pod_name = f"workspace-{workspace_id}"
    namespace = "default"
    
    manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": pod_name, "labels": {"workspace_id": str(workspace_id), "owner": username}},
        "spec": {
            "containers": [{
                "name": "ide",
                "image": "codercom/code-server:latest", # Standard code-server
                "ports": [{"containerPort": 8080}],
                "env": [{"name": "AUTH", "value": "none"}]
            }],
            "restartPolicy": "Never"
        }
    }
    try:
        v1.create_namespaced_pod(namespace=namespace, body=manifest)
        return True
    except ApiException as e:
        logger.error(f"K8s Create Error: {e}")
        return False

def get_pod_status(workspace_id: int):
    try:
        pod = v1.read_namespaced_pod_status(name=f"workspace-{workspace_id}", namespace="default")
        return pod.status.phase # Returns "Running", "Pending", etc.
    except:
        return "NotFound"

def delete_workspace_pod(workspace_id: int):
    try:
        v1.delete_namespaced_pod(name=f"workspace-{workspace_id}", namespace="default")
        return True
    except: return False

# --- File API Logic ---

def execute_command(workspace_id: int, command: list):
    """Executes a shell command inside the workspace container"""
    try:
        resp = stream.stream(v1.connect_get_namespaced_pod_exec,
                             f"workspace-{workspace_id}", 'default',
                             container='ide', command=command,
                             stderr=True, stdin=False, stdout=True, tty=False)
        return resp
    except Exception as e:
        logger.error(f"K8s Exec Error: {e}")
        return None

def list_files(workspace_id: int, path: str = "/home/coder"):
    # Simple 'ls' command
    output = execute_command(workspace_id, ['ls', '-p', path])
    if output is None: return []
    return output.split()