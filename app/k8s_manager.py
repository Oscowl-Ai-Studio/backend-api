import logging
import contextlib
from kubernetes import client, config, stream
from kubernetes.client.rest import ApiException

logger = logging.getLogger("uvicorn")

try:
    config.load_kube_config()
except:
    try: 
        config.load_incluster_config()
    except: 
        logger.error("K8s config not found")

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
    except: 
        return False

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

# --- Added for Sprint 3 File Writing & Deletion ---

def write_file_contents(workspace_id: int, path: str, content: str):
    """Writes textual raw payload details safely directly into a specific container path"""
    pod_name = f"workspace-{workspace_id}"
    
    # Ensures parent paths exist before passing inputs directly into file path targets
    exec_command = ['sh', '-c', f'mkdir -p $(dirname "{path}") && cat > "{path}"']
    
    try:
        resp = stream.stream(
            v1.connect_get_namespaced_pod_exec,
            pod_name,
            'default',
            container='ide',
            command=exec_command,
            stderr=True, stdin=True,
            stdout=True, tty=False,
            _preload_content=False
        )
        resp.write_stdin(content)
        resp.close()
        return True
    except Exception as e:
        logger.error(f"K8s File Write Error: {e}")
        raise e

def delete_container_file(workspace_id: int, path: str):
    """Executes a clean removal block for targeted folder structures or explicit items"""
    # Simply reuse the teammate's clean shell invocation runner pattern
    output = execute_command(workspace_id, ['rm', '-rf', path])
    if output is None:
        raise Exception("Failed to execute deletion inside container")
    return True

# --- Added for Sprint 3 Interactive WebSocket Terminal Tunnels ---

@contextlib.asynccontextmanager
async def connect_pod_terminal_stream(workspace_id: int):
    """
    Spawns an interactive bidirectional persistent terminal hook 
    pointing directly into the container subshell process framework.
    """
    pod_name = f"workspace-{workspace_id}"
    exec_command = ['/bin/bash']
    
    try:
        resp = stream.stream(
            v1.connect_get_namespaced_pod_exec,
            pod_name,
            'default',
            container='ide',
            command=exec_command,
            stderr=True, stdin=True,
            stdout=True, tty=True,
            _preload_content=False
        )
        
        class PodStreamWrapper:
            async def read(self):
                # Reads stdout stream output segments returning out of K8s shell runtime context
                if resp.is_open():
                    # Prevents async blocking loops using a shallow timeout check hook
                    out = resp.read_stdout(timeout=1)
                    return out.encode('utf-8') if out else b""
                return b""
                
            async def write(self, data: bytes):
                # Channels frontend browser terminal keyboard events straight into running pod shell
                if resp.is_open():
                    resp.write_stdin(data.decode('utf-8', errors='ignore'))

        yield PodStreamWrapper()
    finally:
        if 'resp' in locals() and resp.is_open():
            resp.close()