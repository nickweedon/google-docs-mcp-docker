"""Tests for Docker port discovery functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from google_docs_mcp.utils.docker import get_container_id, get_published_port, discover_oauth_port


class TestGetContainerId:
    """Test container ID detection from cgroup files."""

    def test_container_id_from_cgroup_v1(self, tmp_path):
        """Test container ID extraction from cgroup v1 format."""
        cgroup_file = tmp_path / "cgroup"
        cgroup_file.write_text(
            "12:memory:/docker/1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef\n"
        )

        with patch("google_docs_mcp.utils.docker.Path") as mock_path:
            mock_cgroup = MagicMock()
            mock_cgroup.exists.return_value = True
            mock_cgroup.read_text.return_value = cgroup_file.read_text()
            mock_path.return_value = mock_cgroup

            container_id = get_container_id()
            assert container_id == "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

    def test_container_id_from_cgroup_with_containers_path(self, tmp_path):
        """Test container ID extraction from cgroup with /containers/ in path."""
        cgroup_file = tmp_path / "cgroup"
        cgroup_file.write_text(
            "1:name=systemd:/docker/containers/abcdef123456abcdef123456abcdef123456abcdef123456abcdef123456abcd\n"
        )

        with patch("google_docs_mcp.utils.docker.Path") as mock_path:
            mock_cgroup = MagicMock()
            mock_cgroup.exists.return_value = True
            mock_cgroup.read_text.return_value = cgroup_file.read_text()
            mock_path.return_value = mock_cgroup

            container_id = get_container_id()
            assert container_id == "abcdef123456abcdef123456abcdef123456abcdef123456abcdef123456abcd"

    def test_no_container_id_when_not_in_docker(self, tmp_path):
        """Test that None is returned when not running in Docker."""
        cgroup_file = tmp_path / "cgroup"
        cgroup_file.write_text("12:memory:/user.slice/user-1000.slice\n")

        with patch("google_docs_mcp.utils.docker.Path") as mock_path:
            mock_cgroup = MagicMock()
            mock_cgroup.exists.return_value = True
            mock_cgroup.read_text.return_value = cgroup_file.read_text()
            mock_path.return_value = mock_cgroup

            container_id = get_container_id()
            assert container_id is None


class TestGetPublishedPort:
    """Test port mapping discovery via Docker API."""

    @patch("google_docs_mcp.utils.docker.get_container_id")
    def test_successful_port_discovery(self, mock_get_id):
        """Test successful port discovery from Docker API."""
        mock_get_id.return_value = "test_container_123"

        mock_container = MagicMock()
        mock_container.attrs = {
            "NetworkSettings": {
                "Ports": {
                    "3000/tcp": [{"HostIp": "0.0.0.0", "HostPort": "32768"}]
                }
            }
        }

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        with patch("docker.from_env", return_value=mock_client):
            port = get_published_port(3000)
            assert port == 32768

    @patch("google_docs_mcp.utils.docker.get_container_id")
    def test_port_not_found(self, mock_get_id):
        """Test when port mapping is not found."""
        mock_get_id.return_value = "test_container_123"

        mock_container = MagicMock()
        mock_container.attrs = {
            "NetworkSettings": {
                "Ports": {}
            }
        }

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        with patch("docker.from_env", return_value=mock_client):
            port = get_published_port(3000)
            assert port is None

    @patch("google_docs_mcp.utils.docker.get_container_id")
    def test_no_container_id(self, mock_get_id):
        """Test when container ID cannot be determined."""
        mock_get_id.return_value = None

        port = get_published_port(3000)
        assert port is None


class TestDiscoverOAuthPort:
    """Test OAuth port discovery with fallback."""

    @patch("google_docs_mcp.utils.docker.get_published_port")
    @patch("google_docs_mcp.utils.docker.get_container_id")
    def test_discover_port_success(self, mock_get_id, mock_get_port):
        """Test successful port discovery."""
        mock_get_id.return_value = "test_container_123"
        mock_get_port.return_value = 32768

        port = discover_oauth_port(3000)
        assert port == 32768

    @patch("google_docs_mcp.utils.docker.get_container_id")
    def test_fallback_to_default_when_not_in_docker(self, mock_get_id):
        """Test fallback to default port when not in Docker."""
        mock_get_id.return_value = None

        port = discover_oauth_port(3000)
        assert port == 3000

    @patch("google_docs_mcp.utils.docker.get_published_port")
    @patch("google_docs_mcp.utils.docker.get_container_id")
    def test_fallback_when_port_not_found(self, mock_get_id, mock_get_port):
        """Test fallback to default when port mapping not found."""
        mock_get_id.return_value = "test_container_123"
        mock_get_port.return_value = None

        port = discover_oauth_port(3000)
        assert port == 3000

    @patch("google_docs_mcp.utils.docker.get_container_id")
    def test_fallback_on_exception(self, mock_get_id):
        """Test fallback to default on any exception."""
        mock_get_id.side_effect = Exception("Docker API error")

        port = discover_oauth_port(3000)
        assert port == 3000
