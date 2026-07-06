import os
import logging
from kubernetes import client, config

K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", "collab-platform")
WORKSPACE_IMAGE = os.getenv("WORKSPACE_IMAGE", "lashyainternacr.azurecr.io/workspace-base:latest")
STORAGE_CLASS = os.getenv("STORAGE_CLASS", "managed-csi")

logger = logging.getLogger("uvicorn")


def _load_k8s():
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()
    return client.CoreV1Api()


def _labels(workspace_id: int, owner_id: int) -> dict:
    return {
        "app": "workspace",
        "workspace-id": str(workspace_id),
        "user-id": str(owner_id),
    }


def create_workspace_pvc(workspace_id: int, owner_id: int):
    api = _load_k8s()
    body = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": f"workspace-pvc-{workspace_id}",
            "namespace": K8S_NAMESPACE,
            "labels": _labels(workspace_id, owner_id),
        },
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "resources": {
                "requests": {
                    "storage": "1Gi"
                }
            },
            "storageClassName": STORAGE_CLASS,
        }
    }
    return api.create_namespaced_persistent_volume_claim(
        namespace=K8S_NAMESPACE, body=body
    )


def create_workspace_pod(workspace_id: int, owner_id: int):
    api = _load_k8s()
    labels = _labels(workspace_id, owner_id)
    pod_name = f"workspace-{workspace_id}"

    body = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod_name,
            "namespace": K8S_NAMESPACE,
            "labels": labels,
        },
        "spec": {
            "imagePullSecrets": [{"name": "acr-pull-secret"}],
            "volumes": [
                {
                    "name": "workspace-data",
                    "persistentVolumeClaim": {
                        "claimName": f"workspace-pvc-{workspace_id}"
                    }
                }
            ],
            "containers": [
                {
                    "name": "code-server",
                    "image": WORKSPACE_IMAGE,
                    "ports": [{"containerPort": 8080}],
                    "volumeMounts": [
                        {
                            "name": "workspace-data",
                            "mountPath": "/home/coder/project"
                        }
                    ],
                    "env": [
                        {"name": "PASSWORD", "value": "workspace123"}
                    ],
                },
                {
                    "name": "ttyd",
                    "image": "tsl0922/ttyd:latest",
                    "ports": [{"containerPort": 4200}],
                    "command": ["ttyd", "-p", "4200", "sh"],
                    "securityContext": {
                        "allowPrivilegeEscalation": True
                    }
                }
            ],
            "restartPolicy": "Never",
        }
    }
    return api.create_namespaced_pod(namespace=K8S_NAMESPACE, body=body)


def delete_workspace_pod(workspace_id: int):
    api = _load_k8s()
    pod_name = f"workspace-{workspace_id}"
    return api.delete_namespaced_pod(name=pod_name, namespace=K8S_NAMESPACE)


def delete_workspace_pvc(workspace_id: int):
    api = _load_k8s()
    pvc_name = f"workspace-pvc-{workspace_id}"
    return api.delete_namespaced_persistent_volume_claim(
        name=pvc_name, namespace=K8S_NAMESPACE
    )


def get_workspace_pod_status(workspace_id: int) -> str:
    api = _load_k8s()
    pod_name = f"workspace-{workspace_id}"
    try:
        pod = api.read_namespaced_pod(name=pod_name, namespace=K8S_NAMESPACE)
        return pod.status.phase
    except:
        return "NotFound"


def provision_workspace_pod(workspace_id: int, owner_id: int):
    logger.info(f"Creating PVC for workspace {workspace_id}")
    create_workspace_pvc(workspace_id, owner_id)

    logger.info(f"Creating pod for workspace {workspace_id}")
    create_workspace_pod(workspace_id, owner_id)

    logger.info(f"Workspace {workspace_id} pod creation initiated")