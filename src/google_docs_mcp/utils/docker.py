"""
Docker API utilities for container introspection and port discovery.

Enables automatic discovery of Docker port mappings for OAuth loopback flows
when running in containers with ephemeral port bindings.
"""

import re
from pathlib import Path
from typing import Optional

from google_docs_mcp.utils import log


def get_container_id() -> Optional[str]:
    """
    Get the current container ID if running in a Docker container.

    Supports both cgroup v1 and v2:
    - cgroup v1: Reads from /proc/self/cgroup
    - cgroup v2: Reads from /proc/self/mountinfo

    Returns:
        Container ID (64-char hex string) or None if not in container
    """
    # Try cgroup v1 format first
    cgroup_path = Path("/proc/self/cgroup")
    if cgroup_path.exists():
        try:
            content = cgroup_path.read_text()
            # Look for patterns like: 12:name=systemd:/docker/CONTAINER_ID
            # or: 1:name=systemd:/docker/containers/CONTAINER_ID
            match = re.search(r"/docker(?:/containers)?/([0-9a-f]{64})", content)
            if match:
                return match.group(1)

            # Also check for shorter container IDs (12 chars)
            match = re.search(r"/docker(?:/containers)?/([0-9a-f]{12,})", content)
            if match:
                return match.group(1)
        except Exception as e:
            log(f"[Port Discovery] Error reading cgroup: {e}")

    # Try cgroup v2 / mountinfo format
    mountinfo_path = Path("/proc/self/mountinfo")
    if mountinfo_path.exists():
        try:
            content = mountinfo_path.read_text()
            # Look for patterns in mountinfo
            match = re.search(r"/docker/containers/([0-9a-f]{64})", content)
            if match:
                return match.group(1)

            match = re.search(r"/docker/containers/([0-9a-f]{12,})", content)
            if match:
                return match.group(1)
        except Exception as e:
            log(f"[Port Discovery] Error reading mountinfo: {e}")

    return None


def get_published_port(container_port: int) -> Optional[int]:
    """
    Get the host port mapped to a container port via Docker API.

    Requires Docker socket to be mounted at /var/run/docker.sock

    Args:
        container_port: The port number inside the container

    Returns:
        Host port number or None if not found or Docker unavailable
    """
    try:
        import docker
    except ImportError:
        log("[Port Discovery] Docker SDK not installed")
        return None

    try:
        # Connect to Docker socket
        client = docker.from_env()

        # Get current container ID
        container_id = get_container_id()
        if not container_id:
            log("[Port Discovery] Not running in Docker container")
            return None

        # Get container object
        container = client.containers.get(container_id)

        # Get port bindings
        # Format: {'3000/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32768'}]}
        port_bindings = container.attrs.get("NetworkSettings", {}).get("Ports", {})

        # Look for our container port
        port_key = f"{container_port}/tcp"
        if port_key in port_bindings:
            bindings = port_bindings[port_key]
            if bindings and len(bindings) > 0:
                # Use first binding
                host_port = bindings[0].get("HostPort")
                if host_port:
                    return int(host_port)

        log(f"[Port Discovery] No port mapping found for container port {container_port}")
        return None

    except docker.errors.DockerException as e:
        log(f"[Port Discovery] Docker API error: {e}")
        return None
    except Exception as e:
        log(f"[Port Discovery] Unexpected error during port discovery: {e}")
        return None


def discover_oauth_port(default_port: int = 3000) -> int:
    """
    Discover the host port mapped to the container's OAuth port.

    Uses Docker API to query port mappings when running in a container
    with Docker socket mounted. Falls back to default port if:
    - Not running in Docker
    - Docker socket not available
    - No port mapping found
    - Any errors occur

    Args:
        default_port: Port to use if discovery fails (default: 3000)

    Returns:
        Discovered host port or default_port
    """
    try:
        container_id = get_container_id()
        if not container_id:
            log(f"[Port Discovery] Not running in Docker container, using default port {default_port}")
            return default_port

        log(f"[Port Discovery] Detected container ID: {container_id[:12]}...")

        host_port = get_published_port(default_port)
        if host_port:
            log(f"[Port Discovery] Discovered OAuth host port via Docker API: {host_port}")
            return host_port
        else:
            log(f"[Port Discovery] No port mapping found, using default port {default_port}")
            return default_port

    except Exception as e:
        log(f"[Port Discovery] Error during discovery: {e}, using default port {default_port}")
        return default_port
