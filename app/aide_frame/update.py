"""
Remote update manager for applications.

Provides GitHub-based updates with:
- Version checking against GitHub repository
- Manual download and staging
- Automatic rollback on failure (max 2 attempts)
- Detection when local version is ahead of remote

Update flow:
1. CHECK: Compare local VERSION with GitHub
2. DOWNLOAD: Download files to .update/staging/, verify checksums
3. APPLY: Backup current files, copy staging to app/, restart service
4. VERIFY: After 60s stable, confirm update; on failure, rollback

Usage:
    from aide_frame.update import UpdateManager, get_local_version

    # Configure for your application
    update_config = {
        "enabled": True,
        "source": {
            "repo": "username/repo-name",
            "branch": "main"
        },
        "service_name": "myapp",  # For systemctl restart
        "updateable_dirs": ["src", "static", "templates"],
        "required_files": ["main.py", "VERSION"]
    }

    manager = UpdateManager(update_config)
    status = manager.get_status()
"""

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request

from . import paths


def get_local_version():
    """Read the local version from VERSION file."""
    paths.ensure_initialized()
    if paths.VERSION_FILE is None:
        return "0.0.0"
    try:
        with open(paths.VERSION_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"


def compare_versions(local, remote):
    """
    Compare two version strings.

    Returns:
        1 if remote > local (update available)
        0 if remote == local (up to date)
        -1 if remote < local (local is ahead, development mode)
    """
    def parse_version(v):
        # Handle versions like "1.2.3" or "1.2.3-dev"
        base = v.split('-')[0]
        parts = base.split('.')
        return tuple(int(p) for p in parts if p.isdigit())

    try:
        local_parts = parse_version(local)
        remote_parts = parse_version(remote)

        if remote_parts > local_parts:
            return 1
        elif remote_parts < local_parts:
            return -1
        else:
            return 0
    except (ValueError, AttributeError):
        return 0  # Can't compare, assume equal


class UpdateManager:
    """
    Manages remote updates from GitHub.

    Configuration options:
        enabled: bool - Enable/disable updates
        source.repo: str - GitHub repo (e.g., "username/repo")
        source.branch: str - Branch to update from
        service_name: str - Systemd service name for restart
        updateable_dirs: list - Directories that can have files deleted
        required_files: list - Files that must be downloaded successfully
        file_extensions: list - File extensions to include in updates
        auto_check: bool - Periodically check for updates
        auto_check_hours: int - Hours between auto-checks
        auto_download: bool - Automatically download updates
        auto_apply: bool - Automatically apply updates
    """

    DEFAULT_CONFIG = {
        "enabled": True,
        "source": {
            "repo": None,  # Must be set by application
            "branch": "main"
        },
        "service_name": None,  # For systemctl restart
        "updateable_dirs": [],  # Directories where files can be deleted
        "required_files": ["VERSION"],  # Files that must be downloaded
        "file_extensions": [
            '.py', '.md', '.html', '.css', '.js', '.json', '.txt',
            '.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp', '.svg'
        ],
        "auto_check_hours": 24,
        "auto_check": True,
        "auto_download": False,
        "auto_apply": False
    }

    def __init__(self, config=None):
        paths.ensure_initialized()
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.state_dir = paths.UPDATE_STATE_DIR
        self.state_file = os.path.join(self.state_dir, "state.json") if self.state_dir else None
        self._ensure_state_dir()
        self._state = self._load_state()

    def _ensure_state_dir(self):
        """Create state directory if it doesn't exist."""
        if not self.state_dir:
            return
        if not os.path.exists(self.state_dir):
            try:
                os.makedirs(self.state_dir, exist_ok=True)
            except OSError:
                pass  # May fail on read-only filesystem, that's ok

    def _load_state(self):
        """Load update state from file."""
        default_state = {
            "current_version": get_local_version(),
            "available_version": None,
            "update_state": "idle",  # idle, checking, downloading, staged, verifying
            "pending_verification": False,
            "consecutive_failures": 0,
            "updates_disabled": False,
            "backup_version": None,
            "last_check": None,
            "last_update": None
        }

        if not self.state_file:
            return default_state

        try:
            with open(self.state_file, 'r') as f:
                saved_state = json.load(f)
                # Merge with defaults to handle new fields
                return {**default_state, **saved_state}
        except (FileNotFoundError, json.JSONDecodeError):
            return default_state

    def _save_state(self):
        """Save update state to file."""
        if not self.state_file:
            return
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self._state, f, indent=2)
        except OSError:
            pass  # May fail on read-only filesystem

    def get_status(self):
        """Get current update status for API response."""
        local_version = get_local_version()
        available = self._state.get("available_version")

        # Determine update availability
        update_available = False
        version_comparison = "unknown"
        if available:
            cmp = compare_versions(local_version, available)
            if cmp == 1:
                update_available = True
                version_comparison = "update_available"
            elif cmp == -1:
                version_comparison = "local_ahead"
            else:
                version_comparison = "up_to_date"

        return {
            "current_version": local_version,
            "available_version": available,
            "update_available": update_available,
            "version_comparison": version_comparison,
            "update_state": self._state.get("update_state", "idle"),
            "pending_verification": self._state.get("pending_verification", False),
            "consecutive_failures": self._state.get("consecutive_failures", 0),
            "updates_disabled": self._state.get("updates_disabled", False),
            "updates_enabled": self.config.get("enabled", True),
            "backup_version": self._state.get("backup_version"),
            "can_rollback": self._state.get("backup_version") is not None,
            "last_check": self._state.get("last_check"),
            "last_update": self._state.get("last_update"),
            "source": self.config.get("source", {})
        }

    def check_for_updates(self):
        """
        Check GitHub for a newer version.

        Returns:
            dict with check results including available_version and comparison
        """
        if not self.config.get("enabled", True):
            return {"success": False, "error": "Updates are disabled in config"}

        if self._state.get("updates_disabled", False):
            return {"success": False, "error": "Updates disabled due to repeated failures"}

        source = self.config.get("source", {})
        repo = source.get("repo")
        if not repo:
            return {"success": False, "error": "No repository configured"}

        branch = source.get("branch", "main")

        # Build URL for raw VERSION file
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/app/VERSION"

        self._state["update_state"] = "checking"
        self._save_state()

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AIDE-Frame-Updater"})
            with urllib.request.urlopen(req, timeout=10) as response:
                remote_version = response.read().decode('utf-8').strip()

            local_version = get_local_version()
            cmp = compare_versions(local_version, remote_version)

            # Update state
            self._state["available_version"] = remote_version
            self._state["last_check"] = datetime.datetime.now().isoformat()
            self._state["update_state"] = "idle"
            self._save_state()

            # Determine result
            if cmp == 1:
                return {
                    "success": True,
                    "update_available": True,
                    "current_version": local_version,
                    "available_version": remote_version,
                    "message": f"Update available: {local_version} → {remote_version}"
                }
            elif cmp == -1:
                return {
                    "success": True,
                    "update_available": False,
                    "current_version": local_version,
                    "available_version": remote_version,
                    "message": f"Local version ({local_version}) is ahead of remote ({remote_version})"
                }
            else:
                return {
                    "success": True,
                    "update_available": False,
                    "current_version": local_version,
                    "available_version": remote_version,
                    "message": f"Already up to date ({local_version})"
                }

        except urllib.error.URLError as e:
            self._state["update_state"] = "idle"
            self._save_state()
            return {"success": False, "error": f"Network error: {e.reason}"}
        except Exception as e:
            self._state["update_state"] = "idle"
            self._save_state()
            return {"success": False, "error": str(e)}

    def _get_remote_file_list(self, repo, branch):
        """
        Get list of all files in the remote app/ directory using GitHub API.

        Returns list of relative file paths (e.g., ['main.py', 'utils/__init__.py'])
        """
        api_url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
        file_extensions = tuple(self.config.get("file_extensions", self.DEFAULT_CONFIG["file_extensions"]))

        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "AIDE-Frame-Updater",
                "Accept": "application/vnd.github.v3+json"
            })
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

            files = []
            for item in data.get("tree", []):
                path = item.get("path", "")
                item_type = item.get("type", "")

                # Only include files (not directories) under app/
                if item_type == "blob" and path.startswith("app/"):
                    # Remove 'app/' prefix
                    rel_path = path[4:]

                    # Skip certain files/directories
                    if rel_path.startswith(('.', 'sample_images/', '__pycache__')):
                        continue
                    if rel_path.endswith('.pyc'):
                        continue

                    # Include updateable files
                    if rel_path.endswith(file_extensions) or rel_path == 'VERSION':
                        files.append(rel_path)

            return files

        except Exception as e:
            # Log error but don't crash
            return None

    def download_update(self):
        """
        Download update files from GitHub and stage them.

        Downloads all updateable files to .update/staging/ directory
        and verifies checksums if available.

        Returns:
            dict with download results
        """
        if not self.config.get("enabled", True):
            return {"success": False, "error": "Updates are disabled in config"}

        if self._state.get("updates_disabled", False):
            return {"success": False, "error": "Updates disabled due to repeated failures"}

        # Check if update is available
        available = self._state.get("available_version")
        local = get_local_version()
        if not available or compare_versions(local, available) != 1:
            return {"success": False, "error": "No update available to download"}

        source = self.config.get("source", {})
        repo = source.get("repo")
        if not repo:
            return {"success": False, "error": "No repository configured"}

        branch = source.get("branch", "main")
        base_url = f"https://raw.githubusercontent.com/{repo}/{branch}/app"

        # Get file list from GitHub API
        files_to_update = self._get_remote_file_list(repo, branch)
        if not files_to_update:
            self._state["update_state"] = "idle"
            self._save_state()
            return {"success": False, "error": "Could not retrieve file list from GitHub"}

        # Prepare staging directory
        staging_dir = os.path.join(self.state_dir, "staging")
        try:
            if os.path.exists(staging_dir):
                shutil.rmtree(staging_dir)
            os.makedirs(staging_dir, exist_ok=True)
            # Create subdirectories as needed
            subdirs = set(os.path.dirname(f) for f in files_to_update if '/' in f)
            for subdir in subdirs:
                os.makedirs(os.path.join(staging_dir, subdir), exist_ok=True)
        except OSError as e:
            return {"success": False, "error": f"Cannot create staging directory: {e}"}

        self._state["update_state"] = "downloading"
        self._save_state()

        downloaded = []
        errors = []
        checksums = {}

        # First, try to download CHECKSUMS.sha256 if it exists
        checksums_url = f"{base_url}/CHECKSUMS.sha256"
        try:
            req = urllib.request.Request(checksums_url, headers={"User-Agent": "AIDE-Frame-Updater"})
            with urllib.request.urlopen(req, timeout=10) as response:
                checksums_content = response.read().decode('utf-8')
                for line in checksums_content.strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            checksums[parts[1]] = parts[0]
        except urllib.error.HTTPError:
            pass  # Checksums file is optional
        except Exception:
            pass

        # Download each file
        for filepath in files_to_update:
            url = f"{base_url}/{filepath}"
            staging_path = os.path.join(staging_dir, filepath)

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AIDE-Frame-Updater"})
                with urllib.request.urlopen(req, timeout=30) as response:
                    content = response.read()

                # Verify checksum if available
                if filepath in checksums:
                    actual_hash = hashlib.sha256(content).hexdigest()
                    if actual_hash != checksums[filepath]:
                        errors.append(f"{filepath}: checksum mismatch")
                        continue

                # Write to staging
                with open(staging_path, 'wb') as f:
                    f.write(content)
                downloaded.append(filepath)

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    pass  # File doesn't exist in remote, skip
                else:
                    errors.append(f"{filepath}: HTTP {e.code}")
            except Exception as e:
                errors.append(f"{filepath}: {str(e)}")

        # Check if we got the required files
        required_files = self.config.get("required_files", ["VERSION"])
        missing_required = [f for f in required_files if f not in downloaded]
        if missing_required:
            self._state["update_state"] = "idle"
            self._save_state()
            return {
                "success": False,
                "error": f"Failed to download required files: {missing_required}",
                "downloaded": downloaded,
                "errors": errors
            }

        # Update state
        self._state["update_state"] = "staged"
        self._state["staged_version"] = available
        self._save_state()

        return {
            "success": True,
            "message": f"Update {available} staged successfully",
            "staged_version": available,
            "downloaded": downloaded,
            "errors": errors if errors else None
        }

    def _collect_files_recursive(self, directory):
        """Collect all files recursively from a directory."""
        files = []
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, directory)
                files.append(rel_path)
        return files

    def apply_update(self):
        """
        Apply a staged update.

        1. Backs up current app/ files to .update/backup/
        2. Removes files that don't exist in staging (in updateable_dirs)
        3. Copies staged files to app/
        4. Sets pending_verification flag
        5. Triggers service restart

        Returns:
            dict with apply results
        """
        if self._state.get("update_state") != "staged":
            return {"success": False, "error": "No staged update to apply"}

        staged_version = self._state.get("staged_version")
        if not staged_version:
            return {"success": False, "error": "Staged version unknown"}

        staging_dir = os.path.join(self.state_dir, "staging")
        backup_dir = os.path.join(self.state_dir, "backup")

        if not os.path.exists(staging_dir):
            return {"success": False, "error": "Staging directory not found"}

        # Get list of staged files (the new state)
        staged_files = set(self._collect_files_recursive(staging_dir))

        # Create backup of current updateable files
        try:
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            os.makedirs(backup_dir, exist_ok=True)

            current_version = get_local_version()

            # Backup all files that are either in staging or currently exist
            for rel_path in staged_files:
                src = os.path.join(paths.APP_DIR, rel_path)
                dst = os.path.join(backup_dir, rel_path)
                if os.path.exists(src):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)

            # Also backup files that will be deleted (exist locally but not in staging)
            updateable_dirs = self.config.get("updateable_dirs", [])
            for upd_dir in updateable_dirs:
                dir_path = os.path.join(paths.APP_DIR, upd_dir)
                if os.path.isdir(dir_path):
                    for root, _, files in os.walk(dir_path):
                        for f in files:
                            full_path = os.path.join(root, f)
                            rel_path = os.path.relpath(full_path, paths.APP_DIR)
                            if rel_path not in staged_files:
                                dst = os.path.join(backup_dir, rel_path)
                                os.makedirs(os.path.dirname(dst), exist_ok=True)
                                shutil.copy2(full_path, dst)

            self._state["backup_version"] = current_version

        except OSError as e:
            return {"success": False, "error": f"Backup failed: {e}"}

        # Apply staged files
        self._state["update_state"] = "applying"
        self._save_state()

        try:
            # First, remove files that were deleted in the update
            for upd_dir in updateable_dirs:
                dir_path = os.path.join(paths.APP_DIR, upd_dir)
                if os.path.isdir(dir_path):
                    for root, _, files in os.walk(dir_path, topdown=False):
                        for f in files:
                            full_path = os.path.join(root, f)
                            rel_path = os.path.relpath(full_path, paths.APP_DIR)
                            if rel_path not in staged_files:
                                os.remove(full_path)
                        # Remove empty directories
                        if root != dir_path and not os.listdir(root):
                            os.rmdir(root)

            # Copy all staged files to app/
            for rel_path in staged_files:
                src = os.path.join(staging_dir, rel_path)
                dst = os.path.join(paths.APP_DIR, rel_path)

                # Create parent directories if needed
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)

        except OSError as e:
            self._state["update_state"] = "idle"
            self._save_state()
            return {"success": False, "error": f"Apply failed: {e}"}

        # Update state for verification
        self._state["update_state"] = "verifying"
        self._state["pending_verification"] = True
        self._state["current_version"] = staged_version
        self._save_state()

        # Trigger restart (non-blocking)
        restart_result = self._trigger_restart()

        return {
            "success": True,
            "message": f"Update {staged_version} applied, restarting service",
            "applied_version": staged_version,
            "backup_version": self._state.get("backup_version"),
            "restart": restart_result
        }

    def _trigger_restart(self):
        """Trigger service restart via systemctl."""
        service_name = self.config.get("service_name")
        if not service_name:
            return {"triggered": False, "error": "No service name configured"}

        try:
            subprocess.Popen(
                ["sudo", "systemctl", "restart", service_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return {"triggered": True}
        except Exception as e:
            return {"triggered": False, "error": str(e)}

    def rollback(self):
        """
        Rollback to the backup version.

        Returns:
            dict with rollback results
        """
        backup_dir = os.path.join(self.state_dir, "backup")
        backup_version = self._state.get("backup_version")

        if not backup_version:
            return {"success": False, "error": "No backup version available"}

        if not os.path.exists(backup_dir):
            return {"success": False, "error": "Backup directory not found"}

        # Restore backup files recursively
        try:
            backup_files = set(self._collect_files_recursive(backup_dir))

            for rel_path in backup_files:
                src = os.path.join(backup_dir, rel_path)
                dst = os.path.join(paths.APP_DIR, rel_path)

                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)

        except OSError as e:
            return {"success": False, "error": f"Rollback failed: {e}"}

        # Update state
        self._state["current_version"] = backup_version
        self._state["update_state"] = "idle"
        self._state["pending_verification"] = False
        self._state["consecutive_failures"] = self._state.get("consecutive_failures", 0) + 1

        # Disable updates after too many failures
        if self._state["consecutive_failures"] >= 2:
            self._state["updates_disabled"] = True

        self._save_state()

        # Trigger restart
        restart_result = self._trigger_restart()

        return {
            "success": True,
            "message": f"Rolled back to version {backup_version}",
            "restored_version": backup_version,
            "consecutive_failures": self._state["consecutive_failures"],
            "updates_disabled": self._state.get("updates_disabled", False),
            "restart": restart_result
        }

    def confirm_update(self):
        """
        Confirm that the update is working (called after successful startup).

        Clears the pending_verification flag and resets failure counter.
        """
        if not self._state.get("pending_verification"):
            return {"success": False, "error": "No pending verification"}

        self._state["pending_verification"] = False
        self._state["consecutive_failures"] = 0
        self._state["update_state"] = "idle"
        self._state["last_update"] = datetime.datetime.now().isoformat()
        self._save_state()

        # Clean up staging directory
        staging_dir = os.path.join(self.state_dir, "staging")
        if os.path.exists(staging_dir):
            try:
                shutil.rmtree(staging_dir)
            except OSError:
                pass

        return {
            "success": True,
            "message": "Update verified and confirmed",
            "version": self._state.get("current_version")
        }

    def enable_updates(self):
        """Re-enable updates after they were disabled due to failures."""
        self._state["updates_disabled"] = False
        self._state["consecutive_failures"] = 0
        self._save_state()

        return {
            "success": True,
            "message": "Updates re-enabled"
        }


__all__ = [
    'get_local_version',
    'compare_versions',
    'UpdateManager',
]
