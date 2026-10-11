from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import PurePosixPath
from typing import Any

try:
    import docker
    from docker.errors import APIError, DockerException, ImageNotFound, NotFound
except ImportError:  # Keep offline dashboard/docs usable before optional runtime dependencies are installed.
    docker = None  # type: ignore[assignment]

    class DockerException(RuntimeError):
        pass

    class APIError(DockerException):
        pass

    class ImageNotFound(DockerException):
        pass

    class NotFound(DockerException):
        pass
from sqlalchemy.orm import Session

from app.config import LAB_IMAGE
from app.models import WorkspaceRecord
from app.services.challenges import safe_relative_path


class LabUnavailable(RuntimeError):
    pass


class ResourceOwnershipError(RuntimeError):
    pass


class LabManager:
    """Manages only labelled RedPanda resources. User shell text never becomes a host command."""

    LABEL_MANAGED = "com.redpanda-labs.managed"
    LABEL_CHALLENGE = "com.redpanda-labs.challenge-id"

    def __init__(self) -> None:
        self._client = None

    def client(self):
        if self._client is None:
            if docker is None:
                raise LabUnavailable("The Docker Python SDK is not installed. Run `bash scripts/setup.sh` to install project dependencies.")
            try:
                self._client = docker.from_env(timeout=5)
                self._client.ping()
            except (DockerException, OSError) as exc:
                self._client = None
                raise LabUnavailable("Docker is not reachable. Start or configure Docker, then run diagnostics.") from exc
        return self._client

    def diagnostics(self) -> dict[str, Any]:
        try:
            client = self.client()
            info = client.info()
            image_ready = any(image.tags and LAB_IMAGE in image.tags for image in client.images.list())
            security_options = info.get("SecurityOptions", [])
            rootless = any("rootless" in str(option).lower() for option in security_options)
            return {
                "available": True,
                "docker_version": client.version().get("Version", "unknown"),
                "daemon": "reachable",
                "rootless": rootless,
                "lab_image": LAB_IMAGE,
                "image_ready": image_ready,
                "warning": None if rootless else "Docker appears to use a rootful daemon. Only run trusted local lab software; rootless Docker is preferred where practical.",
            }
        except LabUnavailable as exc:
            return {"available": False, "docker_version": None, "daemon": "unavailable", "rootless": None, "lab_image": LAB_IMAGE, "image_ready": False, "warning": str(exc)}
        except (DockerException, APIError) as exc:
            return {"available": False, "docker_version": None, "daemon": "error", "rootless": None, "lab_image": LAB_IMAGE, "image_ready": False, "warning": f"Docker diagnostics failed: {type(exc).__name__}"}

    @staticmethod
    def _resource_names(challenge_id: str) -> tuple[str, str, str]:
        slug = re.sub(r"[^a-z0-9-]", "-", challenge_id.lower())
        return f"redpanda-labs-{slug}", f"redpanda-labs-workspace-{slug}", f"redpanda-labs-net-{slug}"

    def _check_image(self) -> None:
        client = self.client()
        try:
            client.images.get(LAB_IMAGE)
        except ImageNotFound as exc:
            raise LabUnavailable(f"Required lab image {LAB_IMAGE!r} is missing. Run `bash scripts/setup.sh` to build it.") from exc

    def ensure_workspace(self, challenge: dict[str, Any], db: Session) -> dict[str, Any]:
        client = self.client()
        self._check_image()
        challenge_id = challenge["id"]
        container_name, volume_name, network_name = self._resource_names(challenge_id)
        labels = {self.LABEL_MANAGED: "true", self.LABEL_CHALLENGE: challenge_id}
        network_mode = challenge.get("network_requirements", {}).get("mode", "none")
        needs_internal_network = network_mode == "internal"
        network = None
        record = db.get(WorkspaceRecord, challenge_id)
        try:
            container = client.containers.get(container_name)
            self._assert_container_owned(container, challenge_id)
            container.reload()
            if container.status != "running":
                container.start()
                self._run_trusted_startup(container, challenge)
            if record is None:
                volume = self._get_owned_volume(client, volume_name, challenge_id, create=False)
                if volume is None:
                    raise ResourceOwnershipError("The container exists but its managed workspace volume is missing.")
                record = WorkspaceRecord(challenge_id=challenge_id, container_name=container_name, volume_name=volume_name,
                                         network_name=network_name if needs_internal_network else None, state="ready")
                db.add(record)
                db.commit()
            return self._workspace_info(container, challenge_id, volume_name, network_name if needs_internal_network else None)
        except NotFound:
            pass

        if needs_internal_network:
            try:
                network = client.networks.get(network_name)
                if network.attrs.get("Labels", {}).get(self.LABEL_MANAGED) != "true" or network.attrs.get("Labels", {}).get(self.LABEL_CHALLENGE) != challenge_id:
                    raise ResourceOwnershipError("A same-named network is not labelled as owned by RedPanda Labs; refusing to use it.")
            except NotFound:
                network = client.networks.create(network_name, driver="bridge", internal=True, labels=labels, check_duplicate=True)
        volume = self._get_owned_volume(client, volume_name, challenge_id, create=True)
        assert volume is not None
        try:
            container = client.containers.create(
                image=LAB_IMAGE,
                command=["sleep", "infinity"],
                name=container_name,
                user="redpanda",
                working_dir="/workspace",
                volumes={volume.name: {"bind": "/workspace", "mode": "rw"}},
                detach=True,
                tty=False,
                stdin_open=False,
                read_only=True,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                mem_limit="256m",
                nano_cpus=500_000_000,
                pids_limit=128,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
                network_mode=network.name if network is not None else "none",
                labels=labels,
                init=True,
            )
            container.start()
            if self._workspace_is_empty(container):
                self._seed_workspace(container, challenge)
            self._run_trusted_startup(container, challenge)
            if record is None:
                record = WorkspaceRecord(challenge_id=challenge_id, container_name=container_name, volume_name=volume_name,
                                         network_name=network_name if needs_internal_network else None, state="ready")
                db.add(record)
            else:
                record.container_name = container_name
                record.volume_name = volume_name
                record.network_name = network_name if needs_internal_network else None
                record.state = "ready"
            db.commit()
            return self._workspace_info(container, challenge_id, volume_name, network_name if needs_internal_network else None)
        except Exception:
            # Never remove a volume on a setup failure: it may contain previously saved work.
            try:
                container = client.containers.get(container_name)
                self._assert_container_owned(container, challenge_id)
                container.stop(timeout=2)
                container.remove(v=False)
            except Exception:
                pass
            raise

    def _get_owned_volume(self, client, name: str, challenge_id: str, *, create: bool):
        labels = {self.LABEL_MANAGED: "true", self.LABEL_CHALLENGE: challenge_id}
        try:
            volume = client.volumes.get(name)
            actual = volume.attrs.get("Labels") or {}
            if actual.get(self.LABEL_MANAGED) != "true" or actual.get(self.LABEL_CHALLENGE) != challenge_id:
                raise ResourceOwnershipError("A same-named volume is not labelled as owned by RedPanda Labs; refusing to use it.")
            return volume
        except NotFound:
            if not create:
                return None
            return client.volumes.create(name=name, labels=labels)

    def _assert_container_owned(self, container, challenge_id: str) -> None:
        container.reload()
        labels = container.attrs.get("Config", {}).get("Labels") or {}
        if labels.get(self.LABEL_MANAGED) != "true" or labels.get(self.LABEL_CHALLENGE) != challenge_id:
            raise ResourceOwnershipError("A same-named container is not labelled as owned by RedPanda Labs; refusing to modify it.")

    def _workspace_is_empty(self, container) -> bool:
        result = container.exec_run(["/bin/sh", "-lc", "find /workspace -mindepth 1 -maxdepth 1 -print -quit"], user="redpanda", demux=True)
        return result.exit_code == 0 and not (result.output[0] or b"").strip()

    def _seed_workspace(self, container, challenge: dict[str, Any]) -> None:
        files = challenge.get("workspace_seed", {})
        archive = io.BytesIO()
        uid, gid = os.getuid(), os.getgid()
        with tarfile.open(fileobj=archive, mode="w") as tar:
            directories: set[str] = set()
            for name in files:
                safe = safe_relative_path(name)
                parts = PurePosixPath(safe).parts[:-1]
                for i in range(1, len(parts) + 1):
                    directories.add("/".join(parts[:i]))
            for directory in sorted(directories, key=lambda item: (item.count("/"), item)):
                info = tarfile.TarInfo(directory)
                info.type = tarfile.DIRTYPE; info.mode = 0o755; info.uid = uid; info.gid = gid
                tar.addfile(info)
            modes = challenge.get("workspace_modes", {})
            for name, content in files.items():
                safe = safe_relative_path(name)
                if len(content.encode("utf-8")) > 1024 * 1024:
                    raise ValueError(f"Seed file {safe} exceeds 1 MiB")
                data = content.encode("utf-8")
                info = tarfile.TarInfo(safe)
                info.size = len(data); info.mode = int(modes.get(safe, "644"), 8) if isinstance(modes.get(safe, "644"), str) else int(modes.get(safe, 0o644))
                info.uid = uid; info.gid = gid
                tar.addfile(info, io.BytesIO(data))
        archive.seek(0)
        ok = container.put_archive("/workspace", archive.read())
        if not ok:
            raise RuntimeError("Docker refused to seed the challenge workspace")

    def _run_trusted_startup(self, container, challenge: dict[str, Any]) -> None:
        for argv in challenge.get("trusted_startup", []):
            # Only bundled, version-controlled manifests can use this field. Custom manifests strip it.
            if not isinstance(argv, list) or not argv or any(not isinstance(part, str) for part in argv):
                raise ValueError("Invalid trusted startup operation")
            result = container.exec_run(argv, user="redpanda", workdir="/workspace", demux=True)
            if result.exit_code not in (0, None):
                # Some service-start commands return after backgrounding, so exit 0 is expected.
                output = ((result.output[0] or b"") + (result.output[1] or b"")).decode("utf-8", "replace")[-600:]
                raise RuntimeError(f"A bundled lab service failed to start: {output}")

    @staticmethod
    def _workspace_info(container, challenge_id: str, volume_name: str, network_name: str | None) -> dict[str, Any]:
        container.reload()
        return {"challenge_id": challenge_id, "container_name": container.name, "volume_name": volume_name,
                "network_name": network_name, "state": container.status, "shell_ready": container.status == "running"}

    def container_for(self, challenge_id: str):
        client = self.client()
        name, volume_name, _ = self._resource_names(challenge_id)
        container = client.containers.get(name)
        self._assert_container_owned(container, challenge_id)
        return container

    def validate(self, challenge: dict[str, Any], db: Session) -> tuple[bool, list[str], dict[str, Any]]:
        challenge_id = challenge["id"]
        try:
            container = self.container_for(challenge_id)
        except (LabUnavailable, NotFound, ResourceOwnershipError) as exc:
            raise LabUnavailable(f"Start this challenge's lab before checking its objective. {exc}") from exc
        rule = challenge["validation"]
        kind = rule.get("type")
        try:
            path = safe_relative_path(rule.get("path") or rule.get("pid_file", ""))
        except ValueError as exc:
            raise ValueError("The challenge validator contains an invalid path") from exc
        if kind == "text_lines":
            content = self._read_text(container, path)
            present = set((content or "").splitlines())
            missing = [line for line in rule.get("required_lines", []) if line not in present]
            return not missing, (["The evidence file is complete."] if not missing else [f"Evidence is missing {len(missing)} required line(s). Inspect your report and compare it with the mission objective."]), {"file_exists": content is not None, "required_lines_present": len(rule.get("required_lines", [])) - len(missing)}
        if kind == "exact_file":
            content = self._read_text(container, path)
            good = content == rule.get("content")
            return good, (["The output matches the expected normalized content."] if good else ["The output file is missing or does not match the expected content. Check spelling, ordering, and duplicate lines."]), {"file_exists": content is not None, "exact_match": good}
        if kind == "json_subset":
            content = self._read_text(container, path)
            try:
                actual = json.loads(content) if content is not None else None
            except json.JSONDecodeError:
                actual = None
            expected = rule.get("expected", {})
            missing = [key for key, val in expected.items() if not isinstance(actual, dict) or actual.get(key) != val]
            good = not missing
            return good, (["The JSON report contains the verified values."] if good else ["The JSON report is missing or has one or more incorrect fields. Check the JSON syntax, field names, and value types."]), {"file_exists": content is not None, "valid_json": isinstance(actual, dict), "verified_fields": len(expected) - len(missing)}
        if kind == "file_mode":
            mode = self._exec_text(container, ["stat", "-c", "%a", "--", f"/workspace/{path}"])
            owner = self._exec_text(container, ["stat", "-c", "%U", "--", f"/workspace/{path}"])
            good = mode.strip() == str(rule["mode"]) and (owner.strip() == rule.get("owner", "redpanda"))
            return good, (["The file mode and owner are correct."] if good else ["The file exists, but its mode or owner does not match the objective. Use `stat` to inspect it."]), {"mode_matches": mode.strip() == str(rule["mode"]), "owner_matches": owner.strip() == rule.get("owner", "redpanda")}
        if kind == "process_stopped":
            pid_text = self._read_text(container, path)
            pid_text = (pid_text or "").strip()
            if not re.fullmatch(r"[0-9]{1,10}", pid_text):
                return False, ["The expected process ID file is missing or invalid."], {"pid_file_valid": False}
            result = container.exec_run(["/bin/sh", "-c", "test -d /proc/\"$1\"", "validator", pid_text], user="redpanda")
            stopped = result.exit_code != 0
            return stopped, (["The lab process is no longer running."] if stopped else ["The identified lab process is still running. Verify its PID, terminate it, and check again."]), {"process_stopped": stopped}
        raise ValueError(f"Unsupported validator type: {kind}")

    @staticmethod
    def _read_text(container, path: str) -> str | None:
        result = container.exec_run(["cat", "--", f"/workspace/{path}"], user="redpanda", demux=True)
        if result.exit_code != 0:
            return None
        stdout = result.output[0] or b""
        if len(stdout) > 1024 * 1024:
            return None
        return stdout.decode("utf-8", "replace")

    @staticmethod
    def _exec_text(container, argv: list[str]) -> str:
        result = container.exec_run(argv, user="redpanda", demux=True)
        if result.exit_code != 0:
            return ""
        return (result.output[0] or b"").decode("utf-8", "replace")

    def reset_workspace(self, challenge_id: str, challenge: dict[str, Any], db: Session) -> dict[str, Any]:
        client = self.client()
        container_name, volume_name, network_name = self._resource_names(challenge_id)
        try:
            container = client.containers.get(container_name)
            self._assert_container_owned(container, challenge_id)
            container.stop(timeout=3)
            container.remove(v=False)
        except NotFound:
            pass
        except APIError as exc:
            raise RuntimeError("Could not stop the challenge container safely") from exc
        # Verify ownership before removing this workspace volume. Unrelated resources are untouched.
        volume = self._get_owned_volume(client, volume_name, challenge_id, create=False)
        if volume is not None:
            volume.remove(force=False)
        record = db.get(WorkspaceRecord, challenge_id)
        if record:
            db.delete(record)
            db.commit()
        info = self.ensure_workspace(challenge, db)
        return {"reset": True, "workspace": info, "preserved": ["notes", "completion history", "achievements", "other challenge workspaces"]}

    def cleanup_registered_workspace(self, challenge_id: str, db: Session) -> None:
        client = self.client()
        container_name, volume_name, network_name = self._resource_names(challenge_id)
        try:
            container = client.containers.get(container_name)
            self._assert_container_owned(container, challenge_id)
            container.remove(force=True, v=False)
        except NotFound:
            pass
        volume = self._get_owned_volume(client, volume_name, challenge_id, create=False)
        if volume is not None:
            volume.remove(force=True)
        try:
            network = client.networks.get(network_name)
            labels = network.attrs.get("Labels") or {}
            if labels.get(self.LABEL_MANAGED) == "true" and labels.get(self.LABEL_CHALLENGE) == challenge_id:
                network.remove()
        except NotFound:
            pass
        db_record = db.get(WorkspaceRecord, challenge_id)
        if db_record:
            db.delete(db_record)
            db.commit()

    def diagnostics_for_registered(self, db: Session) -> list[dict[str, Any]]:
        result = []
        for row in db.query(WorkspaceRecord).all():
            try:
                c = self.container_for(row.challenge_id); c.reload(); state = c.status
            except Exception:
                state = "missing"
            result.append({"challenge_id": row.challenge_id, "container_name": row.container_name, "state": state})
        return result

    def export_workspace(self, challenge_id: str) -> bytes:
        container = self.container_for(challenge_id)
        stream, _stat = container.get_archive("/workspace")
        archive = io.BytesIO()
        for chunk in stream:
            archive.write(chunk)
        archive.seek(0)
        return archive.getvalue()

    def restore_workspace(self, challenge_id: str, archive_bytes: bytes) -> None:
        if len(archive_bytes) > 10 * 1024 * 1024:
            raise ValueError("Workspace archive exceeds the 10 MiB limit")
        container = self.container_for(challenge_id)
        source = io.BytesIO(archive_bytes)
        validated = io.BytesIO()
        count = 0
        total = 0
        with tarfile.open(fileobj=source, mode="r:*") as tar, tarfile.open(fileobj=validated, mode="w") as output:
            for member in tar.getmembers():
                count += 1
                if count > 250:
                    raise ValueError("Workspace archive contains too many entries")
                name = member.name.removeprefix("workspace/").rstrip("/")
                if not name:
                    continue
                safe = safe_relative_path(name)
                if member.issym() or member.islnk() or member.isdev() or not (member.isfile() or member.isdir()):
                    raise ValueError("Workspace archives may contain only regular files and directories")
                if member.size > 1024 * 1024:
                    raise ValueError("A workspace archive file is larger than 1 MiB")
                total += member.size
                if total > 8 * 1024 * 1024:
                    raise ValueError("Total extracted workspace content exceeds 8 MiB")
                member.name = safe
                member.uid = os.getuid(); member.gid = os.getgid(); member.uname = "redpanda"; member.gname = "redpanda"
                # Re-read the original by its original archive path, then write only validated paths.
                if member.isfile():
                    original = next(m for m in tar.getmembers() if m.name.rstrip("/") in (name, f"workspace/{name}"))
                    fileobj = tar.extractfile(original)
                    if fileobj is None:
                        raise ValueError("Malformed archive entry")
                    payload = fileobj.read(1024 * 1024 + 1)
                    if len(payload) != member.size:
                        raise ValueError("Malformed archive file size")
                    output.addfile(member, io.BytesIO(payload))
                else:
                    output.addfile(member)
        validated.seek(0)
        if not container.put_archive("/workspace", validated.read()):
            raise RuntimeError("Docker did not accept the validated workspace archive")
