#!/usr/bin/env python3
"""
GUI Manager for Gitea: select a folder (or pass one as argv),
enter Gitea URL + username + token/password, create remote repo via API,
then push without persisting credentials. Works with folders or .zip files.

Deps: requests  (installed by wrappers)
"""

import os
import sys
import subprocess
import tempfile
import shutil
import zipfile
import threading
import json
import time
import logging
import base64
import configparser
import datetime
from pathlib import Path
from urllib.parse import quote
from typing import Optional, Tuple, Dict, List, Any, Callable
from dataclasses import dataclass

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font

try:
    import requests
    from requests.auth import HTTPBasicAuth
except Exception as e:
    raise SystemExit("Missing 'requests'. Run via the provided .bat/.sh so it installs automatically.")

# Constants
APP_TITLE = "Gitea Repo Uploader"
VERSION = "1.3.4"
DEFAULT_GITEA_URL = "[ENTER GITEA URL]"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

# Enhanced theme colors with modern aesthetics
THEME_COLORS = {
    "bg": "#1e1e1e",  # Darker background
    "fg": "#e8e8e8",  # Brighter text
    "entry_bg": "#404040",  # Light grey entry background
    "entry_fg": "#ffffff",  # White text in entries
    "button_bg": "#0078d4",  # Modern blue buttons
    "button_fg": "#ffffff",  # White button text
    "button_hover": "#106ebe",  # Darker blue on hover
    "highlight_bg": "#404040",  # Highlighted elements
    "highlight_fg": "#ffffff",  # White highlight text
    "accent": "#00bcf2",  # Bright accent color
    "log_bg": "#0d1117",  # Dark log background
    "log_fg": "#c9d1d9",  # Light gray log text
    "progress_bg": "#21262d",  # Progress bar background
    "progress_fg": "#00bcf2",  # Progress bar fill
    "success": "#28a745",  # Green for success
    "error": "#dc3545",  # Red for errors
    "warning": "#ffc107",  # Yellow for warnings
    "border": "#30363d",  # Border color
    "section_bg": "#161b22",  # Section backgrounds
    "labelframe_bg": "#505050",  # Light grey for section frames
}

# Data structures for Management functionality
@dataclass
class Repo:
    owner: str
    name: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"

@dataclass
class Branch:
    name: str

# Set up logging
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Use a single log file for all sessions
log_file = os.path.join(LOG_DIR, "gitea_uploader.log")

# Check if log file is too large (>10MB) and rotate it
if os.path.exists(log_file) and os.path.getsize(log_file) > 10 * 1024 * 1024:
    backup_file = os.path.join(LOG_DIR, f"gitea_uploader_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    shutil.move(log_file, backup_file)

# Set up logging to file only (headless mode)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='a'),  # Append mode
    ]
)
logger = logging.getLogger(APP_TITLE)

def normalize_api_path(path: str) -> str:
    """Normalize a repository file path for Gitea API usage.

    - Convert OS-specific separators to forward slashes
    - Remove leading './' and leading '/'
    - URL-encode path segments but keep '/' intact
    """
    try:
        posix_path = Path(path).as_posix()
    except Exception:
        posix_path = str(path).replace("\\", "/")
    if posix_path.startswith("./"):
        posix_path = posix_path[2:]
    posix_path = posix_path.lstrip("/")
    return quote(posix_path, safe="/")

def run(cmd, cwd=None):
    """Run a command and return returncode and output"""
    logger.info(f"Running command: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out, _ = proc.communicate()
    logger.info(f"Command output: {out}")
    return proc.returncode, out

def git_exists():
    """Check if git is installed and available on PATH"""
    try:
        code, _ = run(["git", "--version"])
        return code == 0
    except Exception as e:
        logger.error(f"Error checking git: {e}")
        return False

def ensure_local_repo(path, branch, log_callback, username=None, email=None):
    """Initialize a git repo if needed and ensure a branch exists"""
    logger.info(f"Ensuring local repo in {path} with branch {branch}")
    
    # Init if needed
    if not os.path.isdir(os.path.join(path, ".git")):
        log_callback(f"Initializing git repository in {path}...")
        code, out = run(["git", "init"], cwd=path)
        log_callback(out)
        if code != 0:
            error_msg = "git init failed"
            log_callback(f"ERROR: {error_msg}")
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    # Set up local git config to avoid identity issues
    git_user = username or "GiteaPush User"
    git_email = email or f"{git_user.lower().replace(' ', '.')}@localhost"
    
    log_callback("Setting up git identity for this repository...")
    run(["git", "config", "user.name", git_user], cwd=path)
    run(["git", "config", "user.email", git_email], cwd=path)
    logger.info(f"Set git identity: {git_user} <{git_email}>")
    log_callback(f"Git identity set: {git_user} <{git_email}>")

    # Make sure a branch exists and there is at least one commit
    code, out = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    current_branch = out.strip() if code == 0 else None
    log_callback(f"Current branch: {current_branch or 'None'}")

    # If HEAD or detached or empty, create branch
    if not current_branch or current_branch in ("HEAD", "head"):
        # Try to create the desired branch
        log_callback(f"Creating/switching to branch '{branch}'...")
        code, out = run(["git", "checkout", "-B", branch], cwd=path)
        log_callback(out)
        if code != 0:
            error_msg = "Failed to create/check out branch"
            log_callback(f"ERROR: {error_msg}")
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    # Stage & commit if nothing committed yet
    code, out = run(["git", "rev-parse", "HEAD"], cwd=path)
    if code != 0:  # no commits
        log_callback("No commits found. Creating initial commit...")
        run(["git", "add", "."], cwd=path)
        code, out = run(["git", "commit", "-m", "Initial commit"], cwd=path)
        log_callback(out)
        if code != 0:
            error_msg = "git commit failed"
            log_callback(f"ERROR: {error_msg}")
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    # Determine final branch name
    code, out = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    final_branch = out.strip() if code == 0 else branch
    log_callback(f"Using branch: {final_branch}")
    return final_branch

def create_remote_repo(base_url, owner_or_org, repo_name, private, default_branch,
                      username, token, password, verify_tls, log_callback):
    """
    Creates a repo via Gitea API. Uses token if provided, otherwise Basic auth with password.
    If owner_or_org differs from username, uses /orgs/{org}/repos. Otherwise /user/repos.
    Returns the canonical "owner/name" actually created.
    """
    logger.info(f"Creating remote repo: {repo_name} for owner/org: {owner_or_org or username}")
    base = base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    auth = None

    if token:
        headers["Authorization"] = f"token {token}"
        logger.info("Using token authentication")
    else:
        auth = HTTPBasicAuth(username, password)
        logger.info("Using basic authentication with username/password")

    payload = {
        "name": repo_name,
        "private": bool(private),
        "auto_init": False,
        "default_branch": default_branch,
    }

    # Choose endpoint
    if owner_or_org and owner_or_org != username:
        endpoint = f"{base}/api/v1/orgs/{owner_or_org}/repos"
    else:
        endpoint = f"{base}/api/v1/user/repos"

    log_callback(f"Creating remote repo via {endpoint} ...")
    
    try:
        resp = requests.post(endpoint, headers=headers, auth=auth, json=payload, verify=verify_tls)
        
        # If already exists, continue; else require OK
        if resp.status_code in (201, 200):
            data = resp.json()
            full_name = data.get("full_name")  # "owner/name"
            log_callback(f"Remote created: {full_name}")
            return full_name
        elif resp.status_code in (409, 422):  # probably exists / name taken
            log_callback("Remote may already exist; continuing.")
            # Construct assumed owner/name
            assumed_owner = owner_or_org or username
            return f"{assumed_owner}/{repo_name}"
        else:
            try:
                msg = resp.json()
            except Exception:
                msg = resp.text
            error_msg = f"Failed to create remote ({resp.status_code}): {msg}"
            log_callback(f"ERROR: {error_msg}")
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error creating repository: {str(e)}"
        log_callback(f"ERROR: {error_msg}")
        logger.error(error_msg)
        raise RuntimeError(error_msg)

def one_shot_push(local_path, full_name, branch, base_url, username, secret, log_callback):
    """
    Push without saving credentials: use `git push <url> HEAD:branch`.
    secret = token (recommended) OR password. URL-encode both user and secret.
    """
    logger.info(f"Performing one-shot push to {full_name} on branch {branch}")
    base = base_url.rstrip("/")
    owner, name = full_name.split("/", 1)
    # URL-encode creds to tolerate special chars
    u = quote(username, safe="")
    s = quote(secret, safe="")
    push_url = f"{base.replace('://', f'://{u}:{s}@')}/{owner}/{name}.git"

    log_callback(f"Pushing to {owner}/{name} on branch '{branch}' ...")
    
    # Configure git for better network handling
    run(["git", "config", "http.postBuffer", "524288000"], cwd=local_path)  # 500MB buffer
    run(["git", "config", "http.lowSpeedLimit", "1000"], cwd=local_path)   # 1KB/s minimum
    run(["git", "config", "http.lowSpeedTime", "300"], cwd=local_path)      # 5 minute timeout
    
    try:
        log_callback("Attempting git push with enhanced network settings...")
        
        # First try: standard push
        code, out = run(["git", "push", "--set-upstream", push_url, f"HEAD:{branch}"], cwd=local_path)
        log_callback(out)
        
        # Retry with smaller chunks if network hiccup detected
        if code != 0 and "unexpected disconnect" in out.lower():
            log_callback("Network disconnect detected, retrying with smaller chunks...")
            run(["git", "config", "pack.windowMemory", "10m"], cwd=local_path)
            run(["git", "config", "pack.packSizeLimit", "20m"], cwd=local_path)
            code, out = run(["git", "push", "--set-upstream", push_url, f"HEAD:{branch}"], cwd=local_path)
            log_callback(out)

        # If rejected because remote has history, merge and try again
        out_lower = (out or "").lower()
        if code != 0 and ("fetch first" in out_lower or "non-fast-forward" in out_lower or "rejected" in out_lower):
            log_callback("Remote has existing commits; attempting automatic merge with remote history...")
            temp_remote = "temp-origin"
            # Ensure branch is checked out
            run(["git", "checkout", "-B", branch], cwd=local_path)
            # Reset any existing remote of the same name
            run(["git", "remote", "remove", temp_remote], cwd=local_path)
            add_code, add_out = run(["git", "remote", "add", temp_remote, push_url], cwd=local_path)
            if add_code != 0:
                log_callback(f"Failed to add temporary remote: {add_out}")
                raise RuntimeError(f"Failed to add temporary remote: {add_out}")
            # Fetch the remote branch
            fetch_code, fetch_out = run(["git", "fetch", temp_remote, branch], cwd=local_path)
            log_callback(fetch_out)
            if fetch_code != 0:
                # Clean up remote and fail
                run(["git", "remote", "remove", temp_remote], cwd=local_path)
                raise RuntimeError(f"Failed to fetch remote branch: {fetch_out}")
            # Merge histories, preferring local changes on conflicts
            merge_code, merge_out = run(["git", "merge", "--no-edit", "--allow-unrelated-histories", "-X", "ours", f"{temp_remote}/{branch}"], cwd=local_path)
            log_callback(merge_out)
            if merge_code != 0:
                run(["git", "remote", "remove", temp_remote], cwd=local_path)
                raise RuntimeError(f"Failed to merge remote history: {merge_out}")
            # Push again after merge
            code, out = run(["git", "push", "--set-upstream", push_url, f"HEAD:{branch}"], cwd=local_path)
            log_callback(out)
            # Remove temporary remote
            run(["git", "remote", "remove", temp_remote], cwd=local_path)

        if code != 0:
            error_msg = f"git push failed. Exit code: {code}. Output: {out}"
            log_callback(f"ERROR: {error_msg}")
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
    except Exception as e:
        error_msg = f"Error during git push: {str(e)}"
        log_callback(f"ERROR: {error_msg}")
        logger.error(error_msg)
        raise RuntimeError(error_msg)

def extract_zip_to_temp(zip_path, log_callback, progress_callback=None):
    """Extract a ZIP file to a temporary directory with progress updates"""
    logger.info(f"Extracting ZIP: {zip_path}")
    if not zipfile.is_zipfile(zip_path):
        error_msg = "Selected .zip is invalid or corrupted."
        log_callback(f"ERROR: {error_msg}")
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    tmpdir = tempfile.mkdtemp(prefix="gitea_zip_")
    log_callback(f"Extracting {zip_path} -> {tmpdir}")
    
    try:
        with zipfile.ZipFile(zip_path) as zf:
            # Get total file count for progress
            total_files = len(zf.infolist())
            
            # Extract with progress updates
            for i, file_info in enumerate(zf.infolist(), 1):
                if progress_callback:
                    progress_callback(i / total_files * 100, f"Extracting {file_info.filename}")
                zf.extract(file_info, tmpdir)
        
        # If the zip contains a single top-level folder, prefer that as the working dir
        entries = [e for e in os.listdir(tmpdir) if not e.startswith("__MACOSX")]
        if len(entries) == 1 and os.path.isdir(os.path.join(tmpdir, entries[0])):
            return os.path.join(tmpdir, entries[0]), tmpdir
        return tmpdir, tmpdir  # workdir, cleanup_root
    except Exception as e:
        error_msg = f"Error extracting ZIP: {str(e)}"
        log_callback(f"ERROR: {error_msg}")
        logger.error(error_msg)
        raise RuntimeError(error_msg)

def create_branch(repo_path, current_branch, new_branch, log_callback):
    """Create a new branch from the current branch"""
    logger.info(f"Creating branch {new_branch} from {current_branch}")
    
    # Check if branch already exists
    code, out = run(["git", "show-ref", "--verify", f"refs/heads/{new_branch}"], cwd=repo_path)
    if code == 0:
        error_msg = f"Branch '{new_branch}' already exists."
        log_callback(f"ERROR: {error_msg}")
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    # Create and checkout the new branch
    log_callback(f"Creating branch '{new_branch}' from '{current_branch}'...")
    code, out = run(["git", "checkout", "-b", new_branch], cwd=repo_path)
    log_callback(out)
    if code != 0:
        error_msg = f"Failed to create branch '{new_branch}'."
        log_callback(f"ERROR: {error_msg}")
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    return new_branch

def list_repo_files(base_url, owner, repo_name, path, branch, username, token, password, verify_tls):
    """List files in a repository via Gitea API"""
    logger.info(f"Listing repo files: {owner}/{repo_name} path={path} branch={branch}")
    base = base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    auth = None

    if token:
        headers["Authorization"] = f"token {token}"
    else:
        auth = HTTPBasicAuth(username, password)
    
    api_path = normalize_api_path(path)
    endpoint = f"{base}/api/v1/repos/{owner}/{repo_name}/contents/{api_path}?ref={quote(branch, safe='')}"
    
    try:
        resp = requests.get(endpoint, headers=headers, auth=auth, verify=verify_tls)
        
        if resp.status_code == 200:
            return resp.json()
        else:
            try:
                msg = resp.json()
            except Exception:
                msg = resp.text
            error_msg = f"Failed to list repo files ({resp.status_code}): {msg}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error listing repository files: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

def upload_files(base_url, owner, repo_name, branch, file_path, local_path, username, token, 
                password, verify_tls, log_callback, progress_callback=None, force_overwrite=False):
    """Upload a file to a repository via Gitea API with progress updates"""
    logger.info(f"Uploading file: {file_path} to {owner}/{repo_name}")
    base = base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    auth = None

    if token:
        headers["Authorization"] = f"token {token}"
    else:
        auth = HTTPBasicAuth(username, password)
    
    # Update progress if callback provided
    if progress_callback:
        progress_callback(0, f"Checking if {file_path} exists...")
    
    # Always check if file exists to get correct SHA - this is required by Gitea API
    try:
        existing = list_repo_files(base_url, owner, repo_name, file_path, branch, username, token, password, verify_tls)
        if isinstance(existing, dict) and 'sha' in existing:
            update = True
            sha = existing['sha']
            if force_overwrite:
                logger.info(f"Force overwrite mode: {file_path} exists, will update with current SHA: {sha[:8]}...")
                log_callback(f"Force overwrite: {file_path} (updating with current SHA)")
            else:
                logger.info(f"File {file_path} exists, will update with SHA: {sha[:8]}...")
        elif isinstance(existing, list):
            update = False  # It's a directory listing, not a file
            sha = None
            logger.info(f"Path {file_path} is a directory, will create new file")
            if force_overwrite:
                log_callback(f"Force overwrite: {file_path} (creating new - no existing file)")
        else:
            update = False
            sha = None
            logger.info(f"File {file_path} doesn't exist, will create new")
            if force_overwrite:
                log_callback(f"Force overwrite: {file_path} (creating new - no existing file)")
    except Exception as e:
        # If we can't determine if the file exists, assume it's new but log the error
        logger.warning(f"Could not check if file {file_path} exists: {e}")
        if force_overwrite:
            log_callback(f"Force overwrite: {file_path} (could not check existence, assuming new)")
        else:
            log_callback(f"Could not check if {file_path} exists, assuming new file")
        update = False
        sha = None
    
    # Update progress
    if progress_callback:
        progress_callback(20, f"Reading {file_path}...")
    
    try:
        # Use OS-native path for local filesystem access
        local_fs_path = os.path.join(local_path, file_path)
        with open(local_fs_path, 'rb') as f:
            content = f.read()
        
        # Update progress
        if progress_callback:
            progress_callback(40, f"Encoding {file_path}...")
        
        encoded_content = base64.b64encode(content).decode('utf-8')
        
        payload = {
            "content": encoded_content,
            "branch": branch,
            "message": f"{'Update' if update else 'Add'} {file_path}"
        }
        
        if update and sha:
            payload["sha"] = sha
        
        # Update progress
        if progress_callback:
            progress_callback(60, f"Uploading {file_path}...")
        
        remote_path = normalize_api_path(file_path)
        endpoint = f"{base}/api/v1/repos/{owner}/{repo_name}/contents/{remote_path}"
        resp = requests.put(endpoint, headers=headers, auth=auth, json=payload, verify=verify_tls)
        
        # If SHA error, try to refresh SHA and retry, then delete+create if needed
        if not resp.ok:  # Any non-success status code
            try:
                error_detail = resp.json()
                error_str = str(error_detail).lower()
                
                # Log the exact error for debugging
                log_callback(f"Upload failed for {file_path}: {error_detail}")
                logger.error(f"Upload error for {file_path}: {error_detail}")
                
                # Check if it's a SHA-related error (be more specific)
                if (('sha' in error_str and 'required' in error_str) or 
                    '[sha]' in error_str or 
                    'sha mismatch' in error_str or
                    'object does not exist' in error_str):
                    log_callback(f"SHA error for {file_path} (status {resp.status_code}), refreshing SHA and retrying...")
                    logger.warning(f"SHA error for {file_path}: {error_detail}")
                    
                    # Try to get fresh SHA and retry with correct SHA
                    try:
                        fresh_file = list_repo_files(base_url, owner, repo_name, file_path, branch, username, token, password, verify_tls)
                        if isinstance(fresh_file, dict) and 'sha' in fresh_file:
                            fresh_sha = fresh_file['sha']
                            log_callback(f"Got fresh SHA for {file_path}: {fresh_sha[:8]}..., retrying upload...")
                            
                            # Retry with fresh SHA
                            payload_fresh = {
                                "content": encoded_content,
                                "branch": branch,
                                "message": f"Update {file_path}",
                                "sha": fresh_sha
                            }
                            resp = requests.put(endpoint, headers=headers, auth=auth, json=payload_fresh, verify=verify_tls)
                            
                            # If still failing with fresh SHA, try delete+create
                            if not resp.ok:
                                log_callback(f"Fresh SHA retry failed for {file_path}, trying delete+create...")
                                
                                # Delete with fresh SHA, then create new
                                delete_payload = {
                                    "message": f"Remove {file_path} for overwrite",
                                    "sha": fresh_sha,
                                    "branch": branch
                                }
                                delete_resp = requests.delete(endpoint, headers=headers, auth=auth, 
                                                            json=delete_payload, verify=verify_tls)
                                
                                if delete_resp.ok:
                                    log_callback(f"Successfully deleted {file_path}, creating new version...")
                                    # File deleted, now create new (without SHA)
                                    payload_new = {
                                        "content": encoded_content,
                                        "branch": branch,
                                        "message": f"Add {file_path} (recreated)"
                                    }
                                    resp = requests.put(endpoint, headers=headers, auth=auth, json=payload_new, verify=verify_tls)
                                else:
                                    log_callback(f"Delete also failed for {file_path} (status {delete_resp.status_code})")
                                    try:
                                        delete_error = delete_resp.json()
                                        log_callback(f"Delete error details: {delete_error}")
                                    except:
                                        log_callback(f"Delete error: {delete_resp.text}")
                            else:
                                log_callback(f"Fresh SHA retry succeeded for {file_path}")
                        else:
                            log_callback(f"Could not get fresh SHA for {file_path}, trying create as new file...")
                            # Try as completely new file
                            payload_new = {
                                "content": encoded_content,
                                "branch": branch,
                                "message": f"Add {file_path}"
                            }
                            resp = requests.put(endpoint, headers=headers, auth=auth, json=payload_new, verify=verify_tls)
                            
                    except Exception as refresh_error:
                        log_callback(f"Could not refresh SHA for {file_path}: {refresh_error}")
                        logger.warning(f"SHA refresh failed for {file_path}: {refresh_error}")
                else:
                    # Not a SHA error, log the specific error for debugging
                    log_callback(f"Non-SHA error for {file_path} (status {resp.status_code}): {error_detail}")
                        
            except Exception as e:
                logger.warning(f"Could not parse error response for {file_path}: {e}")
                # Continue with original response
        
        # Final progress update
        if progress_callback:
            progress_callback(100, f"Completed {file_path}")
        
        if resp.status_code in (200, 201):
            log_callback(f"✓ {'Updated' if update else 'Added'} {file_path} successfully")
            logger.info(f"Successfully uploaded {file_path} with status {resp.status_code}")
            return True
        else:
            try:
                msg = resp.json()
            except Exception:
                msg = resp.text
            
            # Provide specific error messages for common issues
            if resp.status_code == 422:
                if 'sha' in str(msg).lower():
                    log_callback(f"Failed to upload {file_path}: SHA mismatch error (this should have been handled automatically)")
                else:
                    log_callback(f"Failed to upload {file_path}: Validation error - {msg}")
            elif resp.status_code == 404:
                log_callback(f"Failed to upload {file_path}: Repository or branch not found - {msg}")
            elif resp.status_code == 401:
                log_callback(f"Failed to upload {file_path}: Authentication failed - check credentials")
            elif resp.status_code == 403:
                log_callback(f"Failed to upload {file_path}: Permission denied - check token permissions")
            else:
                log_callback(f"Failed to upload {file_path} (status {resp.status_code}): {msg}")
            
            return False
    except Exception as e:
        error_msg = f"Error uploading {file_path}: {str(e)}"
        log_callback(f"ERROR: {error_msg}")
        logger.error(error_msg)
        return False

def upload_directory(base_url, owner, repo_name, branch, directory, username, token, password, 
                    verify_tls, log_callback, progress_callback=None, force_overwrite=False):
    """Upload all files in a directory to a repository with progress updates"""
    logger.info(f"Uploading directory: {directory} to {owner}/{repo_name}")
    success_count = 0
    error_count = 0
    
    # Get list of all files for progress calculation
    all_files = []
    for root, dirs, files in os.walk(directory):
        # Skip .git directories entirely
        dirs[:] = [d for d in dirs if not d.startswith('.git')]
        
        for file in files:
            # Skip hidden files and git-related files
            if file.startswith('.git') or file.startswith('.'):
                continue
            
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, directory)
            
            # Skip files in .git directories (extra safety)
            if '.git' + os.sep in relative_path or relative_path.startswith('.git'):
                continue
                
            all_files.append(relative_path)
    
    total_files = len(all_files)
    log_callback(f"Found {total_files} files to upload")
    
    # Process each file
    for i, relative_path in enumerate(all_files, 1):
        # Update overall progress
        if progress_callback:
            overall_progress = (i - 1) / total_files * 100
            progress_callback(overall_progress, f"Processing {i}/{total_files}: {relative_path}")
        
        # Create a progress callback for this specific file
        def file_progress(percent, message):
            if progress_callback:
                # Scale the file progress to just a small part of the overall progress
                file_portion = 1 / total_files * 100
                current_base = (i - 1) / total_files * 100
                overall_percent = current_base + (percent / 100 * file_portion)
                progress_callback(overall_percent, message)
        
        try:
            if upload_files(base_url, owner, repo_name, branch, relative_path, directory, 
                          username, token, password, verify_tls, log_callback, file_progress, force_overwrite):
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            error_msg = f"Error uploading {relative_path}: {str(e)}"
            log_callback(f"ERROR: {error_msg}")
            logger.error(error_msg)
            error_count += 1
    
    # Final progress update
    if progress_callback:
        progress_callback(100, f"Upload complete: {success_count} succeeded, {error_count} failed")
    
    return success_count, error_count

def save_preferences(config_data):
    """Save user preferences to config file"""
    logger.info("Saving preferences")
    config = configparser.ConfigParser()
    config['Preferences'] = config_data
    
    try:
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        return True
    except Exception as e:
        logger.error(f"Error saving preferences: {e}")
        return False

def load_preferences():
    """Load user preferences from config file"""
    logger.info("Loading preferences")
    if not os.path.exists(CONFIG_FILE):
        logger.info("Config file does not exist, using defaults")
        return {
            'gitea_url': DEFAULT_GITEA_URL,
            'username': '',
            'last_directory': '',
        }
    
    config = configparser.ConfigParser()
    try:
        config.read(CONFIG_FILE)
        if 'Preferences' in config:
            prefs = dict(config['Preferences'])
            logger.info(f"Loaded preferences: {prefs}")
            return prefs
        else:
            logger.info("No Preferences section in config, using defaults")
            return {
                'gitea_url': DEFAULT_GITEA_URL,
                'username': '',
                'last_directory': '',
            }
    except Exception as e:
        logger.error(f"Error loading preferences: {e}")
        return {
            'gitea_url': DEFAULT_GITEA_URL,
            'username': '',
            'last_directory': '',
        }

# Management functionality - API helpers
def search_repos(base_url, username, password, q, verify_tls=True):
    """Search repositories using Gitea API with proper authentication"""
    logger.info(f"Searching repos for owner={username}, query='{q}'")
    repos = []
    
    # Try token authentication first
    session_token = requests.Session()
    session_token.headers.update({"Authorization": f"token {password}"})
    session_token.verify = verify_tls
    
    try:
        # Try search API first with token auth
        params = {"owner": username, "q": q, "limit": 100, "exclusive": "true"}
        url = f"{base_url.rstrip('/')}/api/v1/repos/search"
        
        resp = session_token.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        for item in data.get("data", []):
            full = item.get("full_name", "")
            if "/" in full:
                o, n = full.split("/", 1)
                repos.append(Repo(owner=o, name=n))
                
        logger.info(f"Token authentication successful, found {len(repos)} repos via search API")
        
    except Exception as e:
        logger.warning(f"Search API with token failed: {e}")
        
        # Try user repos endpoint with token auth
        try:
            url = f"{base_url.rstrip('/')}/api/v1/users/{username}/repos"
            params = {"limit": 200}
            
            resp = session_token.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            qlow = q.lower() if q else ""
            for item in data:
                n = item.get("name", "")
                if not q or qlow in n.lower():
                    repos.append(Repo(owner=username, name=n))
                    
            logger.info(f"Token authentication successful, found {len(repos)} repos via user API")
            
        except Exception as e2:
            logger.warning(f"User repos API with token failed: {e2}")
            
            # Try basic authentication as fallback
            try:
                session_basic = requests.Session()
                session_basic.auth = (username, password)
                session_basic.verify = verify_tls
                
                url = f"{base_url.rstrip('/')}/api/v1/users/{username}/repos"
                params = {"limit": 200}
                
                resp = session_basic.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                qlow = q.lower() if q else ""
                for item in data:
                    n = item.get("name", "")
                    if not q or qlow in n.lower():
                        repos.append(Repo(owner=username, name=n))
                        
                logger.info(f"Basic authentication successful, found {len(repos)} repos")
                
            except Exception as e3:
                logger.error(f"All authentication methods failed: {e3}")
                if "401" in str(e3) or "Unauthorized" in str(e3):
                    raise RuntimeError(f"Authentication failed. Please check your username and password/token.\n\n" +
                                     "If using a password, try creating a Personal Access Token instead:\n" +
                                     "Go to Gitea → Settings → Applications → Generate New Token\n" +
                                     "Required permissions: read:repository, write:repository")
                elif "403" in str(e3) or "Forbidden" in str(e3):
                    raise RuntimeError(f"Access denied. Your account may not have permission to access repositories.\n" +
                                     "Contact your Gitea administrator if this persists.")
                elif "404" in str(e3) or "Not Found" in str(e3):
                    raise RuntimeError(f"Gitea server or API endpoint not found. Please check your Gitea URL.\n" +
                                     "Make sure the URL is correct and the server is accessible.")
                else:
                    raise RuntimeError(f"Failed to connect to Gitea server. Error: {e3}")
    
    # Remove duplicates and sort
    seen = set()
    unique_repos = []
    for r in repos:
        if r.slug not in seen:
            seen.add(r.slug)
            unique_repos.append(r)
    
    unique_repos.sort(key=lambda r: r.name.lower())
    return unique_repos

def list_branches(base_url, username, password, repo, verify_tls=True):
    """List branches for a repository with proper authentication"""
    logger.info(f"Listing branches for {repo.slug}")
    
    # Try token authentication first
    session_token = requests.Session()
    session_token.headers.update({"Authorization": f"token {password}"})
    session_token.verify = verify_tls
    
    try:
        url = f"{base_url.rstrip('/')}/api/v1/repos/{repo.owner}/{repo.name}/branches"
        params = {"limit": 200}
        
        resp = session_token.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        branches = [Branch(name=b["name"]) for b in data]
        branches.sort(key=lambda b: b.name.lower())
        logger.info(f"Token authentication successful, found {len(branches)} branches")
        return branches
        
    except Exception as e:
        logger.warning(f"Token authentication failed for branches: {e}")
        
        # Try basic authentication as fallback
        try:
            session_basic = requests.Session()
            session_basic.auth = (username, password)
            session_basic.verify = verify_tls
            
            url = f"{base_url.rstrip('/')}/api/v1/repos/{repo.owner}/{repo.name}/branches"
            params = {"limit": 200}
            
            resp = session_basic.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            branches = [Branch(name=b["name"]) for b in data]
            branches.sort(key=lambda b: b.name.lower())
            logger.info(f"Basic authentication successful, found {len(branches)} branches")
            return branches
            
        except Exception as e2:
            logger.error(f"All authentication methods failed for branches: {e2}")
            if "401" in str(e2) or "Unauthorized" in str(e2):
                raise RuntimeError(f"Authentication failed while fetching branches.\n\n" +
                                 "Please check your username and password/token.\n" +
                                 "Your token needs 'read:repository' permission.")
            elif "403" in str(e2) or "Forbidden" in str(e2):
                raise RuntimeError(f"Access denied to repository {repo.slug}.\n" +
                                 "You may not have permission to access this repository.")
            elif "404" in str(e2) or "Not Found" in str(e2):
                raise RuntimeError(f"Repository {repo.slug} not found or may be private.\n" +
                                 "Check if the repository exists and you have access.")
            else:
                raise RuntimeError(f"Failed to fetch branches for {repo.slug}. Error: {e2}")

def wipe_branch_via_git(base_url, username, token, repo, branch, log_callback, progress_callback=None):
    """
    Clone the selected repo/branch to a temp dir, delete all tracked files,
    commit, and push to the same branch.
    """
    logger.info(f"Starting branch wipe: {repo.slug}@{branch}")
    
    # Build HTTPS remote URL with credentials
    remote_url = f"{base_url.rstrip('/')}/{repo.owner}/{repo.name}.git"
    auth_remote_url = remote_url.replace("://", f"://{quote(username)}:{quote(token)}@")
    
    with tempfile.TemporaryDirectory(prefix="gitea-wipe-") as tmp:
        tmp_path = Path(tmp)
        log_callback(f"Working in temporary directory: {tmp_path}")
        
        if progress_callback:
            progress_callback(10, "Cloning repository...")
        
        # Clone single branch at shallow depth
        log_callback(f"Cloning {repo.slug} branch '{branch}'...")
        code, out = run(["git", "clone", "--single-branch", "--branch", branch, "--depth", "1", remote_url, "."], cwd=tmp_path)
        if code != 0:
            error_msg = f"Failed to clone repository: {out}"
            log_callback(f"ERROR: {error_msg}")
            raise RuntimeError(error_msg)
        
        if progress_callback:
            progress_callback(30, "Configuring git identity...")
        
        # Configure author (local repo only)
        run(["git", "config", "--local", "user.name", username], cwd=tmp_path)
        run(["git", "config", "--local", "user.email", f"{username}@localhost"], cwd=tmp_path)
        
        if progress_callback:
            progress_callback(50, "Removing all files...")
        
        # Delete all tracked files
        log_callback("Removing all tracked files from branch...")
        code, out = run(["git", "rm", "-r", "-f", "."], cwd=tmp_path)
        # Note: git rm might fail if there are no files, which is okay
        
        if progress_callback:
            progress_callback(70, "Checking for changes...")
        
        # Check if there are changes to commit
        code, status = run(["git", "status", "--porcelain"], cwd=tmp_path)
        if not status.strip():
            log_callback("Branch is already empty - no changes to commit")
            if progress_callback:
                progress_callback(100, "Branch was already empty")
            return
        
        if progress_callback:
            progress_callback(80, "Committing changes...")
        
        # Commit the deletions
        log_callback("Committing file deletions...")
        code, out = run(["git", "commit", "-m", f"chore: empty branch {branch}"], cwd=tmp_path)
        if code != 0:
            error_msg = f"Failed to commit changes: {out}"
            log_callback(f"ERROR: {error_msg}")
            raise RuntimeError(error_msg)
        
        if progress_callback:
            progress_callback(90, "Pushing changes...")
        
        # Push to the branch
        log_callback("Pushing changes to remote...")
        proc = subprocess.Popen(
            ["git", "push", auth_remote_url, f"HEAD:{branch}"],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        out, _ = proc.communicate()
        
        if proc.returncode != 0:
            error_msg = f"Push failed: {out}"
            log_callback(f"ERROR: {error_msg}")
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        if progress_callback:
            progress_callback(100, "Branch emptied successfully")
        
        log_callback("Branch emptied successfully!")
        logger.info(f"Successfully wiped branch: {repo.slug}@{branch}")

class DragDropListbox(tk.Listbox):
    """A Listbox with drag-and-drop reordering"""
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.bind('<Button-1>', self._select)
        self.bind('<B1-Motion>', self._on_motion)
        self.bind('<ButtonRelease-1>', self._on_release)
        self._drag_start_index = None

    def _select(self, event):
        self._drag_start_index = self.nearest(event.y)
        return 'break'

    def _on_motion(self, event):
        if self._drag_start_index is not None:
            current_index = self.nearest(event.y)
            if current_index != self._drag_start_index:
                item = self.get(self._drag_start_index)
                self.delete(self._drag_start_index)
                self.insert(current_index, item)
                self._drag_start_index = current_index
        return 'break'

    def _on_release(self, event):
        self._drag_start_index = None
        return 'break'

class ToolTip:
    """Create a tooltip for a given widget"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)

    def on_enter(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip, text=self.text, bg="#ffffe0", relief="solid", borderwidth=1)
        label.pack()

    def on_leave(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class App(tk.Tk):
    """Main application window"""
    def __init__(self, initial_path=None):
        super().__init__()
        self.title(f"{APP_TITLE} v{VERSION}")
        # Center window on screen
        window_width = 800
        window_height = 750
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)
        self.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        self.minsize(780, 700)
        self.resizable(True, True)
        
        # Set window icon (if available)
        try:
            # Try to set a modern window icon from images directory
            icon_path = os.path.join(os.path.dirname(__file__), "images", "gitea.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(default=icon_path)
            else:
                # Fallback to local directory
                if os.path.exists("images/gitea.ico"):
                    self.iconbitmap(default="images/gitea.ico")
        except Exception:
            pass  # Icon file not found, continue without it
        
        # Load preferences
        self.preferences = load_preferences()
        
        # Initialize variables
        self.var_path = tk.StringVar(value=initial_path or self.preferences.get('last_directory', ''))
        self.var_gitea = tk.StringVar(value=self.preferences.get('gitea_url', DEFAULT_GITEA_URL))
        self.var_username = tk.StringVar(value=self.preferences.get('username', ''))
        self.var_password = tk.StringVar(value="")
        self.var_repo = tk.StringVar(value="")
        self.var_private = tk.BooleanVar(value=True)
        self.var_branch = tk.StringVar(value="main")
        self.var_extract_zip = tk.BooleanVar(value=True)
        self.var_tls_verify = tk.BooleanVar(value=True)
        self.var_show_secrets = tk.BooleanVar(value=False)
        self.var_mode = tk.StringVar(value="git_push")
        self.var_new_branch = tk.StringVar(value="")
        
        # Management tab variables
        self.var_mgmt_gitea = tk.StringVar(value=self.preferences.get('gitea_url', DEFAULT_GITEA_URL))
        self.var_mgmt_username = tk.StringVar(value=self.preferences.get('username', ''))
        self.var_mgmt_password = tk.StringVar(value="")
        self.var_mgmt_tls_verify = tk.BooleanVar(value=True)
        self.var_mgmt_show_secrets = tk.BooleanVar(value=False)
        self.var_search_query = tk.StringVar(value="")
        self.var_selected_repo = tk.StringVar(value="")
        self.var_selected_branch = tk.StringVar(value="")
        self.selected_repos = []
        self.selected_branches = []
        self.selected_repo = None
        self.selected_branch = None
        
        # Set up the UI
        self._apply_theme()
        self._build_ui()
        self._setup_drag_drop()
        
        # Initialize progress tracking
        self.progress_value = 0
        self.progress_text = "Ready"
        
        # Log app start with session marker
        session_start = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info("=" * 60)
        logger.info(f"NEW SESSION STARTED: {session_start}")
        logger.info(f"Application: {APP_TITLE} v{VERSION}")
        logger.info(f"Python: {sys.version}")
        logger.info(f"Platform: {os.name}")
        logger.info("=" * 60)
        self.log(f"Welcome to {APP_TITLE} v{VERSION}")
        self.log(f"Session started: {session_start}")

    def _apply_theme(self):
        """Apply the modern dark theme to the UI"""
        # Configure ttk styles with enhanced modern theme
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        
        # Configure general styles
        self.style.configure("TLabel", 
                           background=THEME_COLORS["bg"], 
                           foreground=THEME_COLORS["fg"],
                           font=("Segoe UI", 9))
        
        self.style.configure("TCheckbutton", 
                           background=THEME_COLORS["bg"], 
                           foreground=THEME_COLORS["fg"],
                           focuscolor="none",
                           font=("Segoe UI", 9))
        
        self.style.configure("TRadiobutton", 
                           background=THEME_COLORS["bg"], 
                           foreground=THEME_COLORS["fg"],
                           focuscolor="none",
                           font=("Segoe UI", 9))
        
        self.style.configure("TEntry", 
                           fieldbackground=THEME_COLORS["entry_bg"], 
                           foreground=THEME_COLORS["entry_fg"],
                           bordercolor=THEME_COLORS["border"],
                           lightcolor=THEME_COLORS["border"],
                           darkcolor=THEME_COLORS["border"],
                           insertcolor=THEME_COLORS["accent"],
                           font=("Consolas", 9))
        
        self.style.configure("TButton", 
                           background=THEME_COLORS["button_bg"], 
                           foreground=THEME_COLORS["button_fg"],
                           bordercolor=THEME_COLORS["button_bg"],
                           lightcolor=THEME_COLORS["button_bg"],
                           darkcolor=THEME_COLORS["button_bg"],
                           focuscolor="none",
                           font=("Segoe UI", 9, "bold"))
        
        # Button hover effect
        self.style.map("TButton",
                      background=[("active", THEME_COLORS["button_hover"]),
                                ("pressed", THEME_COLORS["button_hover"])])
        
        self.style.configure("TFrame", 
                           background=THEME_COLORS["bg"],
                           bordercolor=THEME_COLORS["border"])
        
        self.style.configure("TLabelFrame", 
                           background=THEME_COLORS["labelframe_bg"],
                           foreground=THEME_COLORS["fg"],
                           bordercolor=THEME_COLORS["border"],
                           font=("Segoe UI", 9, "bold"))
        
        self.style.configure("TNotebook", 
                           background=THEME_COLORS["bg"],
                           bordercolor=THEME_COLORS["border"])
        
        self.style.configure("TNotebook.Tab", 
                           background=THEME_COLORS["section_bg"],
                           foreground=THEME_COLORS["fg"],
                           padding=[20, 8],
                           font=("Segoe UI", 9))
        
        self.style.map("TNotebook.Tab",
                      background=[("selected", THEME_COLORS["bg"]),
                                ("active", THEME_COLORS["highlight_bg"])])
        
        self.style.configure("Horizontal.TProgressbar", 
                           background=THEME_COLORS["progress_fg"], 
                           troughcolor=THEME_COLORS["progress_bg"],
                           bordercolor=THEME_COLORS["border"],
                           lightcolor=THEME_COLORS["progress_fg"],
                           darkcolor=THEME_COLORS["progress_fg"])
        
        # Configure root window
        self.configure(bg=THEME_COLORS["bg"])

    def _build_ui(self):
        """Build the main UI elements"""
        pad = {"padx": 8, "pady": 5}
        
        # Create a main frame with padding
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Top bar with version
        top_bar = ttk.Frame(main_frame)
        top_bar.pack(fill="x", **pad)
        
        # Version label
        version_label = ttk.Label(top_bar, text=f"v{VERSION}")
        version_label.pack(side="left")
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True, **pad)
        
        # Main tab
        main_tab = ttk.Frame(self.notebook)
        self.notebook.add(main_tab, text="Upload")
        
        # Path section
        path_frame = ttk.LabelFrame(main_tab, text="Project Source")
        path_frame.pack(fill="x", **pad)
        
        # Path row
        row = ttk.Frame(path_frame)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Project Folder or .zip:").pack(side="left")
        self.path_entry = ttk.Entry(row, textvariable=self.var_path, width=60)
        self.path_entry.pack(side="left", padx=8, fill="x", expand=True)
        ttk.Button(row, text="Browse...", command=self.pick_path).pack(side="left")
        
        # Drag-drop hint
        hint_row = ttk.Frame(path_frame)
        hint_row.pack(fill="x")
        ttk.Label(hint_row, text="💡 Drag & drop a folder or zip file onto this window", 
                 font=("", 9, "italic")).pack(side="left", padx=20)
        
        # Zip handling
        zip_row = ttk.Frame(path_frame)
        zip_row.pack(fill="x", **pad)
        ttk.Checkbutton(zip_row, text="If a .zip is selected, extract before pushing", 
                       variable=self.var_extract_zip).pack(side="left")
        
        # Gitea connection section
        conn_frame = ttk.LabelFrame(main_tab, text="Gitea Connection")
        conn_frame.pack(fill="x", **pad)
        
        # Server 
        row = ttk.Frame(conn_frame)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Gitea URL:").pack(side="left")
        ttk.Entry(row, textvariable=self.var_gitea, width=50).pack(side="left", padx=8, fill="x", expand=True)
        
        # Auth
        row = ttk.Frame(conn_frame)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Username:").pack(side="left")
        ttk.Entry(row, textvariable=self.var_username, width=25).pack(side="left", padx=8)
        ttk.Label(row, text="Password/Token:").pack(side="left", padx=(15, 0))
        self.ent_password = ttk.Entry(row, textvariable=self.var_password, width=25, show="•")
        self.ent_password.pack(side="left", padx=8)
        ttk.Checkbutton(row, text="Show", variable=self.var_show_secrets, 
                       command=self.toggle_secret_visibility).pack(side="left", padx=8)
        
        # TLS verification
        tls_row = ttk.Frame(conn_frame)
        tls_row.pack(fill="x", **pad)
        ttk.Checkbutton(tls_row, text="Verify TLS certificates (recommended)", 
                       variable=self.var_tls_verify).pack(side="left")
        

        # Repository details section
        repo_frame = ttk.LabelFrame(main_tab, text="Repository Details")
        repo_frame.pack(fill="x", **pad)
        
        # Repo name and privacy
        row = ttk.Frame(repo_frame)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Repo Name (blank = folder name):").pack(side="left")
        ttk.Entry(row, textvariable=self.var_repo, width=28).pack(side="left", padx=8)
        ttk.Checkbutton(row, text="Private repo", variable=self.var_private).pack(side="left", padx=8)
        
        # Branch and operation mode
        row = ttk.Frame(repo_frame)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Default Branch:").pack(side="left")
        ttk.Combobox(row, textvariable=self.var_branch, values=["main", "master"], 
                    width=9, state="readonly").pack(side="left", padx=8)
        
        # Mode selection (Push with Git or Upload Files)
        ttk.Label(row, text="Operation Mode:").pack(side="left", padx=(15, 0))
        ttk.Radiobutton(row, text="Git Push", variable=self.var_mode, 
                       value="git_push").pack(side="left", padx=5)
        ttk.Radiobutton(row, text="API Upload", variable=self.var_mode, 
                       value="api_upload").pack(side="left", padx=5)
        
        # Branch options
        row = ttk.Frame(repo_frame)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Create New Branch (optional):").pack(side="left")
        ttk.Entry(row, textvariable=self.var_new_branch, width=20).pack(side="left", padx=8)
        ttk.Label(row, text="(Leave empty to use default branch)").pack(side="left")
        
        # Progress section - compact layout
        progress_frame = ttk.LabelFrame(main_tab, text="Progress")
        progress_frame.pack(fill="x", **pad)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=100, mode="determinate")
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        
        # Progress text
        self.progress_label = ttk.Label(progress_frame, text="Ready", font=("", 8))
        self.progress_label.pack(fill="x", padx=10, pady=2)
        
        # Action buttons
        btn_frame = ttk.Frame(main_tab)
        btn_frame.pack(fill="x", **pad)
        
        self.btn_go = ttk.Button(btn_frame, text="Create & Push", command=self.go_clicked)
        self.btn_go.pack(side="left", padx=5)
        
        self.btn_save_prefs = ttk.Button(btn_frame, text="Save Preferences", command=self.save_current_preferences)
        self.btn_save_prefs.pack(side="left", padx=5)
        
        self.btn_clear = ttk.Button(btn_frame, text="Clear Log", command=self.clear_log)
        self.btn_clear.pack(side="left", padx=5)
        
        # Log box with scrollbar - compact
        log_frame = ttk.LabelFrame(main_tab, text="Operation Log")
        log_frame.pack(fill="both", expand=True, **pad)
        
        self.txt = tk.Text(log_frame, height=8, bg=THEME_COLORS["log_bg"], fg=THEME_COLORS["log_fg"], wrap="word", font=("Consolas", 8))
        self.txt.pack(fill="both", expand=True, side="left")
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.txt.yview)
        scrollbar.pack(fill="y", side="right")
        self.txt.configure(yscrollcommand=scrollbar.set)
        
        # Management tab
        management_tab = ttk.Frame(self.notebook)
        self.notebook.add(management_tab, text="Management")
        self._build_management_ui(management_tab)
        
        # Help tab
        help_tab = ttk.Frame(self.notebook)
        self.notebook.add(help_tab, text="Help")
        
        # Help content
        help_frame = ttk.Frame(help_tab)
        help_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(help_frame, text="Quick Help Guide", 
                 font=("", 14, "bold")).pack(anchor="w", pady=10)
        
        help_text = """
        How to use this tool:
        
        UPLOAD TAB:
        1. Select a project folder or ZIP file using the Browse button or drag-and-drop
        2. Enter your Gitea server URL, username, and password/token
        3. Choose a repository name (or leave blank to use folder name)
        4. Select upload method:
           - Git Push: Uses git commands (requires Git installation)
           - API Upload: Uploads files directly via the API (no Git required)
        5. Optionally create a new branch by entering a name
        6. Click "Create & Push" to start the upload process
        
        MANAGEMENT TAB (NEW!):
        1. Enter Gitea credentials or copy from Upload tab
        2. Search repositories (leave empty to list all)
        3. Select a repository from the dropdown
        4. Select a branch from the dropdown
        5. Click "Empty Selected Branch" to delete all files (preserves git history)
        
        Tips:
        
        • Personal Access Tokens are more secure than passwords
        • Create tokens in your Gitea instance under Settings → Applications
        • The Password/Token field accepts either your password or a token
        • The log areas show detailed progress information
        • Drag and drop works for both folders and ZIP files
        • Save your preferences to remember Gitea URL and username
        • Progress bars show real-time status of operations
        • Management operations are DESTRUCTIVE - use with caution!
        """
        
        help_label = ttk.Label(help_frame, text=help_text, justify="left")
        help_label.pack(padx=10, pady=10, fill="x")
        
        # About section
        # Removed empty About section (no content to display)
        
        # Add some tooltips
        ToolTip(self.btn_save_prefs, "Save Gitea URL and username for future use")
        ToolTip(self.btn_go, "Create repository (if needed) and upload files")
        ToolTip(self.btn_clear, "Clear the log display")

    def _build_management_ui(self, parent):
        """Build the Management tab UI - compact layout"""
        pad = {"padx": 8, "pady": 3}
        
        # Main frame with padding
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Connection section
        conn_frame = ttk.LabelFrame(main_frame, text="Gitea Connection")
        conn_frame.pack(fill="x", **pad)
        
        # Server row
        server_row = ttk.Frame(conn_frame)
        server_row.pack(fill="x", **pad)
        ttk.Label(server_row, text="Gitea URL:", width=12).pack(side="left")
        ttk.Entry(server_row, textvariable=self.var_mgmt_gitea, width=40).pack(side="left", padx=5, fill="x", expand=True)
        
        # Auth row
        auth_row = ttk.Frame(conn_frame)
        auth_row.pack(fill="x", **pad)
        ttk.Label(auth_row, text="Username:", width=12).pack(side="left")
        ttk.Entry(auth_row, textvariable=self.var_mgmt_username, width=20).pack(side="left", padx=5)
        ttk.Label(auth_row, text="Password/Token:").pack(side="left", padx=(10, 5))
        self.mgmt_password_entry = ttk.Entry(auth_row, textvariable=self.var_mgmt_password, width=20, show="•")
        self.mgmt_password_entry.pack(side="left", padx=5)
        ttk.Checkbutton(auth_row, text="Show", variable=self.var_mgmt_show_secrets, 
                       command=self.toggle_mgmt_secret_visibility).pack(side="left", padx=5)
        
        # Help text row
        help_row = ttk.Frame(conn_frame)
        help_row.pack(fill="x", **pad)
        ttk.Label(help_row, text="💡 Use Personal Access Token (recommended) or password. Create tokens: Settings → Applications", 
                 font=("", 8, "italic"), foreground=THEME_COLORS["accent"]).pack(side="left")
        
        # TLS verification and copy button row
        options_row = ttk.Frame(conn_frame)
        options_row.pack(fill="x", **pad)
        ttk.Checkbutton(options_row, text="Verify TLS certificates", 
                       variable=self.var_mgmt_tls_verify).pack(side="left")
        
        # Copy from Upload tab button
        self.btn_copy_from_upload = ttk.Button(options_row, text="Copy from Upload Tab", 
                                             command=self.copy_from_upload_tab)
        self.btn_copy_from_upload.pack(side="right", padx=5)
        
        # Repository & Branch Selection (Combined)
        selection_frame = ttk.LabelFrame(main_frame, text="Repository & Branch Selection")
        selection_frame.pack(fill="x", **pad)
        
        # Search row
        search_row = ttk.Frame(selection_frame)
        search_row.pack(fill="x", **pad)
        ttk.Label(search_row, text="Search:", width=12).pack(side="left")
        self.mgmt_search_entry = ttk.Entry(search_row, textvariable=self.var_search_query, width=25)
        self.mgmt_search_entry.pack(side="left", padx=5)
        self.btn_search = ttk.Button(search_row, text="Search Repos", command=self.search_repositories)
        self.btn_search.pack(side="left", padx=5)
        
        # Repository selection row
        repo_row = ttk.Frame(selection_frame)
        repo_row.pack(fill="x", **pad)
        ttk.Label(repo_row, text="Repository:", width=12).pack(side="left")
        self.mgmt_repo_combo = ttk.Combobox(repo_row, textvariable=self.var_selected_repo, 
                                          width=40, state="readonly")
        self.mgmt_repo_combo.pack(side="left", padx=5, fill="x", expand=True)
        self.mgmt_repo_combo.bind('<<ComboboxSelected>>', self.on_repo_select)
        
        # Branch selection row
        branch_row = ttk.Frame(selection_frame)
        branch_row.pack(fill="x", **pad)
        ttk.Label(branch_row, text="Branch:", width=12).pack(side="left")
        self.mgmt_branch_combo = ttk.Combobox(branch_row, textvariable=self.var_selected_branch, 
                                            width=25, state="readonly")
        self.mgmt_branch_combo.pack(side="left", padx=5)
        self.mgmt_branch_combo.bind('<<ComboboxSelected>>', self.on_branch_select)
        
        # Action section
        action_frame = ttk.LabelFrame(main_frame, text="Branch Management")
        action_frame.pack(fill="x", **pad)
        
        # Warning and action row
        warning_row = ttk.Frame(action_frame)
        warning_row.pack(fill="x", **pad)
        warning_text = "⚠️ WARNING: This will delete ALL files from the selected branch!"
        ttk.Label(warning_row, text=warning_text, foreground=THEME_COLORS["error"], 
                 font=("", 9, "bold")).pack(side="left")
        
        # Action buttons row
        btn_row = ttk.Frame(action_frame)
        btn_row.pack(fill="x", **pad)
        self.btn_wipe_branch = ttk.Button(btn_row, text="Empty Selected Branch", 
                                        command=self.wipe_branch_clicked, state="disabled")
        self.btn_wipe_branch.pack(side="left", padx=5)
        
        # Progress section
        progress_frame = ttk.LabelFrame(main_frame, text="Operation Progress")
        progress_frame.pack(fill="x", **pad)
        
        # Progress bar
        self.mgmt_progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", 
                                               length=100, mode="determinate")
        self.mgmt_progress_bar.pack(fill="x", padx=8, pady=3)
        
        # Progress text
        self.mgmt_progress_label = ttk.Label(progress_frame, text="Ready", font=("", 8))
        self.mgmt_progress_label.pack(fill="x", padx=8, pady=2)
        
        # Compact log area
        log_frame = ttk.LabelFrame(main_frame, text="Management Log")
        log_frame.pack(fill="both", expand=True, **pad)
        
        self.mgmt_txt = tk.Text(log_frame, height=8, bg=THEME_COLORS["log_bg"], 
                              fg=THEME_COLORS["log_fg"], wrap="word", font=("Consolas", 8))
        self.mgmt_txt.pack(fill="both", expand=True, side="left")
        
        mgmt_scrollbar = ttk.Scrollbar(log_frame, command=self.mgmt_txt.yview)
        mgmt_scrollbar.pack(fill="y", side="right")
        self.mgmt_txt.configure(yscrollcommand=mgmt_scrollbar.set)
        
        # Add tooltips
        ToolTip(self.btn_search, "Search for repositories (leave search field empty to list all)")
        ToolTip(self.mgmt_repo_combo, "Select a repository to load its branches")
        ToolTip(self.mgmt_branch_combo, "Select a branch to enable the empty operation")
        ToolTip(self.btn_wipe_branch, "Delete all files from the selected branch (WARNING: Destructive action)")
        ToolTip(self.btn_copy_from_upload, "Copy Gitea URL, username, password, and TLS settings from Upload tab")

    def _setup_drag_drop(self):
        """Set up drag and drop functionality for the main window"""
        # Windows specific file drop
        if os.name == 'nt':  # Windows
            try:
                self.drop_target_register("DND_Files")
                self.dnd_bind('<<Drop>>', self._on_drop)
            except Exception:
                pass  # Fallback to TkDND if available
        
        # For Linux/macOS or as fallback - use the path entry for drag indication
        self.path_entry.bind("<Enter>", lambda e: self._highlight_path_entry(True))
        self.path_entry.bind("<Leave>", lambda e: self._highlight_path_entry(False))
        
        # Since tkinter doesn't natively support drag-and-drop well across platforms,
        # we'll also accept command line arguments and advertise that method
        
    def _on_drop(self, event):
        """Handle dropped files"""
        path = event.data
        # Remove curly braces and quotes that Windows might add
        path = path.strip('{}').strip('"')
        self.var_path.set(path)
        self.log(f"Received dropped path: {path}")
        
        # Auto-detect folder name for repo name if it's blank
        if not self.var_repo.get() and os.path.exists(path):
            base_name = os.path.basename(os.path.normpath(path))
            if path.lower().endswith('.zip'):
                base_name = os.path.splitext(base_name)[0]
            self.var_repo.set(base_name)
            self.log(f"Auto-filled repository name: {base_name}")
        
        return "break"
    
    def _highlight_path_entry(self, highlight):
        """Highlight the path entry when hovering for drag and drop indication"""
        if highlight:
            self.path_entry.configure(style="Highlight.TEntry")
        else:
            self.path_entry.configure(style="TEntry")

    def toggle_secret_visibility(self):
        """Toggle visibility of password field"""
        show = "" if self.var_show_secrets.get() else "•"
        self.ent_password.config(show=show)

    def toggle_mgmt_secret_visibility(self):
        """Toggle visibility of Management tab password field"""
        show = "" if self.var_mgmt_show_secrets.get() else "•"
        self.mgmt_password_entry.config(show=show)

    def pick_path(self):
        """Open a file dialog to pick a path"""
        path = filedialog.askopenfilename(title="Select a folder or .zip",
                                          filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")])
        # If user picked a file, accept it; otherwise try directory chooser
        if path and os.path.isfile(path):
            self.var_path.set(path)
            
            # Auto-detect folder name for repo name if it's blank
            if not self.var_repo.get():
                base_name = os.path.basename(os.path.normpath(path))
                if path.lower().endswith('.zip'):
                    base_name = os.path.splitext(base_name)[0]
                self.var_repo.set(base_name)
            return
            
        d = filedialog.askdirectory(title="Select project folder")
        if d:
            self.var_path.set(d)
            
            # Auto-detect folder name for repo name if it's blank
            if not self.var_repo.get():
                base_name = os.path.basename(os.path.normpath(d))
                self.var_repo.set(base_name)

    def log(self, message):
        """Add a message to the log display"""
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        self.txt.insert("end", f"[{timestamp}] {message}\n")
        self.txt.see("end")
        self.update_idletasks()

    def clear_log(self):
        """Clear the log display"""
        self.txt.delete(1.0, "end")
        self.log("Log cleared.")

    def update_progress(self, value, text=""):
        """Update the progress bar and text"""
        self.progress_value = value
        self.progress_text = text
        self.progress_bar["value"] = value
        self.progress_label.config(text=text)
        self.update_idletasks()

    def save_current_preferences(self):
        """Save current URL and username to preferences"""
        try:
            # Save preferences
            new_prefs = {
                'gitea_url': self.var_gitea.get().strip(),
                'username': self.var_username.get().strip(),
                'last_directory': self.var_path.get().strip(),
            }
            
            # Update preferences
            self.preferences.update(new_prefs)
            
            # Save to file
            if save_preferences(self.preferences):
                self.log("Preferences saved successfully")
            else:
                self.log("Error saving preferences")
        except Exception as e:
            error_msg = f"Error saving preferences: {str(e)}"
            self.log(f"ERROR: {error_msg}")
            logger.error(error_msg)

    # Management tab methods
    def copy_from_upload_tab(self):
        """Copy credentials from Upload tab to Management tab"""
        self.var_mgmt_gitea.set(self.var_gitea.get())
        self.var_mgmt_username.set(self.var_username.get())
        self.var_mgmt_password.set(self.var_password.get())
        self.var_mgmt_tls_verify.set(self.var_tls_verify.get())
        self.var_mgmt_show_secrets.set(self.var_show_secrets.get())
        # Update password field visibility
        self.toggle_mgmt_secret_visibility()
        self.mgmt_log("Copied credentials from Upload tab")

    def mgmt_log(self, message):
        """Add a message to the management log display"""
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        self.mgmt_txt.insert("end", f"[{timestamp}] {message}\n")
        self.mgmt_txt.see("end")
        self.update_idletasks()

    def mgmt_update_progress(self, value, text=""):
        """Update the management progress bar and text"""
        self.mgmt_progress_bar["value"] = value
        self.mgmt_progress_label.config(text=text)
        self.update_idletasks()

    def search_repositories(self):
        """Search for repositories"""
        # Get credentials from Management tab
        base_url = self.var_mgmt_gitea.get().strip()
        username = self.var_mgmt_username.get().strip()
        password = self.var_mgmt_password.get().strip()
        
        if not base_url or not username or not password:
            messagebox.showerror("Missing Credentials", 
                               "Please enter Gitea URL, Username, and Password/Token in the Management tab.\n\n" +
                               "Note: Personal Access Tokens are recommended over passwords.\n" +
                               "Create tokens in Gitea: Settings → Applications → Generate New Token")
            return
        
        query = self.var_search_query.get().strip()
        
        # Reset progress
        self.mgmt_update_progress(0, "Searching repositories...")
        self.mgmt_log(f"Searching repositories for user '{username}' with query '{query}'...")
        
        # Run search in background thread
        t = threading.Thread(target=self._search_repositories_thread, 
                           args=(base_url, username, password, query), daemon=True)
        t.start()

    def _search_repositories_thread(self, base_url, username, password, query):
        """Search repositories in background thread"""
        try:
            # Search repositories
            self.mgmt_update_progress(25, "Fetching repositories...")
            verify_tls = self.var_mgmt_tls_verify.get()
            repos = search_repos(base_url, username, password, query, verify_tls)
            
            self.mgmt_update_progress(75, "Updating display...")
            
            # Update UI in main thread
            self.after_idle(self._update_repo_list, repos)
            
            self.mgmt_update_progress(100, f"Found {len(repos)} repositories")
            self.mgmt_log(f"Found {len(repos)} repositories")
            
        except Exception as e:
            error_msg = str(e)
            self.after_idle(lambda: self.mgmt_log(f"ERROR: {error_msg}"))
            self.after_idle(lambda: self.mgmt_update_progress(0, f"Error: {error_msg}"))
            logger.error(f"Repository search failed: {error_msg}")

    def _update_repo_list(self, repos):
        """Update repository list in main thread"""
        self.selected_repos = repos
        
        # Update repository combobox
        repo_names = [repo.slug for repo in repos]
        self.mgmt_repo_combo['values'] = repo_names
        
        # Clear selections
        self.var_selected_repo.set("")
        self.var_selected_branch.set("")
        self.mgmt_branch_combo['values'] = []
        self.selected_repo = None
        self.selected_branch = None
        self.btn_wipe_branch.config(state="disabled")

    def on_repo_select(self, event):
        """Handle repository selection"""
        selected_repo_slug = self.var_selected_repo.get()
        if not selected_repo_slug:
            return
        
        # Find the selected repository object
        self.selected_repo = None
        for repo in self.selected_repos:
            if repo.slug == selected_repo_slug:
                self.selected_repo = repo
                break
        
        if not self.selected_repo:
            return
        
        # Get credentials from Management tab
        base_url = self.var_mgmt_gitea.get().strip()
        username = self.var_mgmt_username.get().strip()
        password = self.var_mgmt_password.get().strip()
        
        self.mgmt_log(f"Loading branches for {self.selected_repo.slug}...")
        
        # Load branches in background thread
        t = threading.Thread(target=self._load_branches_thread, 
                           args=(base_url, username, password, self.selected_repo), daemon=True)
        t.start()

    def _load_branches_thread(self, base_url, username, password, repo):
        """Load branches in background thread"""
        try:
            # Get branches
            verify_tls = self.var_mgmt_tls_verify.get()
            branches = list_branches(base_url, username, password, repo, verify_tls)
            
            # Update UI in main thread
            self.after_idle(self._update_branch_list, branches)
            self.after_idle(lambda: self.mgmt_log(f"Found {len(branches)} branches in {repo.slug}"))
            
        except Exception as e:
            error_msg = str(e)
            self.after_idle(lambda: self.mgmt_log(f"ERROR loading branches: {error_msg}"))
            logger.error(f"Branch loading failed: {error_msg}")

    def _update_branch_list(self, branches):
        """Update branch list in main thread"""
        self.selected_branches = branches
        
        # Update branch combobox
        branch_names = [branch.name for branch in branches]
        self.mgmt_branch_combo['values'] = branch_names
        
        # Clear branch selection
        self.var_selected_branch.set("")
        self.selected_branch = None
        self.btn_wipe_branch.config(state="disabled")

    def on_branch_select(self, event):
        """Handle branch selection"""
        selected_branch_name = self.var_selected_branch.get()
        if not selected_branch_name:
            return
        
        self.selected_branch = selected_branch_name
        
        # Enable wipe button if both repo and branch are selected
        if self.selected_repo and self.selected_branch:
            self.btn_wipe_branch.config(state="normal")
        else:
            self.btn_wipe_branch.config(state="disabled")

    def wipe_branch_clicked(self):
        """Handle wipe branch button click"""
        if not self.selected_repo or not self.selected_branch:
            messagebox.showerror("Selection Required", "Please select both a repository and a branch.")
            return
        
        # Show confirmation dialog with typed confirmation
        repo_branch = f"{self.selected_repo.slug}@{self.selected_branch}"
        
        confirm_dialog = tk.Toplevel(self)
        confirm_dialog.title("Confirm Branch Wipe")
        confirm_dialog.geometry("550x320")
        confirm_dialog.configure(bg=THEME_COLORS["bg"])
        confirm_dialog.transient(self)
        confirm_dialog.grab_set()
        confirm_dialog.resizable(False, False)
        
        # Center the dialog
        confirm_dialog.update_idletasks()
        x = (confirm_dialog.winfo_screenwidth() // 2) - (confirm_dialog.winfo_width() // 2)
        y = (confirm_dialog.winfo_screenheight() // 2) - (confirm_dialog.winfo_height() // 2)
        confirm_dialog.geometry(f"+{x}+{y}")
        
        # Main frame with padding
        main_frame = ttk.Frame(confirm_dialog)
        main_frame.pack(fill="both", expand=True, padx=20, pady=15)
        
        # Confirmation content
        ttk.Label(main_frame, text="⚠️ DESTRUCTIVE ACTION WARNING", 
                 font=("", 12, "bold"), foreground=THEME_COLORS["error"]).pack(pady=(0, 8))
        
        ttk.Label(main_frame, text=f"You are about to EMPTY the branch:", 
                 font=("", 10)).pack(pady=2)
        
        ttk.Label(main_frame, text=repo_branch, font=("", 11, "bold")).pack(pady=4)
        
        ttk.Label(main_frame, text="This will DELETE ALL FILES from this branch!", 
                 foreground=THEME_COLORS["error"], font=("", 10, "bold")).pack(pady=4)
        
        ttk.Label(main_frame, text="Type the repository name to confirm:", 
                 font=("", 10)).pack(pady=(12, 5))
        
        confirm_var = tk.StringVar()
        confirm_entry = ttk.Entry(main_frame, textvariable=confirm_var, width=30, font=("", 10))
        confirm_entry.pack(pady=4)
        confirm_entry.focus()
        
        def on_confirm():
            if confirm_var.get().strip() == self.selected_repo.name:
                confirm_dialog.destroy()
                self._execute_wipe()
            else:
                messagebox.showerror("Confirmation Failed", 
                                   f"You must type '{self.selected_repo.name}' exactly to confirm.")
        
        def on_cancel():
            confirm_dialog.destroy()
        
        # Add Enter key binding
        def on_enter_key(event):
            on_confirm()
        
        confirm_entry.bind('<Return>', on_enter_key)
        
        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        
        ttk.Button(btn_frame, text="Confirm Wipe", command=on_confirm).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="left", padx=10)

    def _execute_wipe(self):
        """Execute the branch wipe operation"""
        # Reset progress
        self.mgmt_update_progress(0, "Starting branch wipe...")
        
        # Get credentials from Management tab
        base_url = self.var_mgmt_gitea.get().strip()
        username = self.var_mgmt_username.get().strip()
        password = self.var_mgmt_password.get().strip()
        
        repo_branch = f"{self.selected_repo.slug}@{self.selected_branch}"
        self.mgmt_log(f"Starting wipe operation for {repo_branch}")
        
        # Disable wipe button during operation
        self.btn_wipe_branch.config(state="disabled")
        
        # Run wipe in background thread
        t = threading.Thread(target=self._wipe_branch_thread, 
                           args=(base_url, username, password, self.selected_repo, self.selected_branch), 
                           daemon=True)
        t.start()

    def _wipe_branch_thread(self, base_url, username, password, repo, branch):
        """Execute branch wipe in background thread"""
        try:
            wipe_branch_via_git(
                base_url=base_url,
                username=username,
                token=password,
                repo=repo,
                branch=branch,
                log_callback=lambda msg: self.after_idle(lambda: self.mgmt_log(msg)),
                progress_callback=lambda v, t: self.after_idle(lambda: self.mgmt_update_progress(v, t))
            )
            
            self.after_idle(lambda: messagebox.showinfo("Operation Complete", 
                                                      f"Branch {repo.slug}@{branch} has been emptied successfully."))
            
        except Exception as e:
            error_msg = str(e)
            self.after_idle(lambda: self.mgmt_log(f"ERROR: {error_msg}"))
            self.after_idle(lambda: self.mgmt_update_progress(0, f"Error: {error_msg}"))
            self.after_idle(lambda: messagebox.showerror("Operation Failed", f"Failed to empty branch: {error_msg}"))
            logger.error(f"Branch wipe failed: {error_msg}")
        finally:
            # Re-enable wipe button
            self.after_idle(lambda: self.btn_wipe_branch.config(state="normal" if self.selected_repo and self.selected_branch else "disabled"))

    def go_clicked(self):
        """Handle the Create & Push button click"""
        # Reset progress
        self.update_progress(0, "Starting...")
        
        # Run in a thread to keep GUI responsive
        t = threading.Thread(target=self._run_flow, daemon=True)
        self.btn_go.config(state="disabled")
        t.start()

    def _run_flow(self):
        """Run the upload flow in a background thread"""
        try:
            self._do_run_flow()
            self.update_progress(100, "Operation completed successfully!")
            messagebox.showinfo(APP_TITLE, "Done! Operation completed successfully.")
            
            # Save the last used path if successful
            self.preferences['last_directory'] = self.var_path.get().strip()
            save_preferences(self.preferences)
            
        except Exception as e:
            error_msg = str(e)
            self.update_progress(0, f"Error: {error_msg}")
            self.log(f"ERROR: {error_msg}")
            logger.error(f"Operation failed: {error_msg}")
            messagebox.showerror(APP_TITLE, f"Error: {error_msg}")
        finally:
            self.btn_go.config(state="normal")

    def _do_run_flow(self):
        """Execute the upload process"""
        # Get form values
        path = self.var_path.get().strip()
        base_url = self.var_gitea.get().strip()
        username = self.var_username.get().strip()
        password = self.var_password.get().strip()  # Can be token or password
        repo_name = self.var_repo.get().strip()
        private = self.var_private.get()
        branch = self.var_branch.get().strip()
        verify_tls = self.var_tls_verify.get()
        extract_zip = self.var_extract_zip.get()
        mode = self.var_mode.get()
        new_branch = self.var_new_branch.get().strip()
        
        # Log operation start
        logger.info(f"Starting upload operation: mode={mode}, path={path}")
        self.log(f"Starting {mode} operation for {path}")
        
        # No owner/org support in simplified version - use username
        owner = ""
        # Use simplified git identity
        git_name = username
        git_email = f"{username}@localhost"
        
        # Basic validation
        self.update_progress(5, "Validating inputs...")
        
        if not git_exists() and mode == "git_push":
            raise RuntimeError("Git is not installed or not on PATH.")

        if not base_url or not username:
            raise RuntimeError("Gitea URL and Username are required.")

        if not password:
            raise RuntimeError("Provide your password or Personal Access Token.")

        if not path:
            raise RuntimeError("Select a project folder or .zip.")

        if not os.path.exists(path):
            raise RuntimeError("Selected path does not exist.")

        cleanup_root = None
        workdir = path
        
        self.update_progress(10, "Preparing files...")

        # If .zip and extract option is on
        if os.path.isfile(path) and path.lower().endswith(".zip") and extract_zip:
            self.log("Extracting ZIP file...")
            workdir, cleanup_root = extract_zip_to_temp(
                path, self.log, 
                progress_callback=lambda v, t: self.update_progress(10 + v * 0.1, t)
            )
            self.update_progress(20, "ZIP extraction complete")

        # Determine repo name if blank
        if not repo_name:
            # If original path was a ZIP file, use ZIP filename (minus extension)
            if os.path.isfile(path) and path.lower().endswith(".zip"):
                zip_name = os.path.basename(path)
                repo_name = os.path.splitext(zip_name)[0]  # Remove .zip extension
                self.log(f"Using ZIP filename as repository name: {repo_name}")
            else:
                base = os.path.basename(os.path.normpath(workdir))
                repo_name = base or "new-repo"
                self.log(f"Using directory name as repository name: {repo_name}")
            
            # Clean up repo name (remove invalid characters)
            import re
            repo_name = re.sub(r'[^\w\-_.]', '-', repo_name)
            if not repo_name:
                repo_name = "new-repo"

        # Create remote repo using basic authentication (username/password)
        self.update_progress(25, f"Creating/verifying repository: {repo_name}")
        self.log(f"Attempting to create repository '{repo_name}' for user '{username}'")
        
        full_name = create_remote_repo(
            base_url, owner, repo_name, private, branch,
            username, "", password, verify_tls, self.log
        )
        
        owner_name = full_name.split('/')[0]
        
        # Check if we need to create a new branch
        working_branch = branch
        if new_branch:
            working_branch = new_branch
            self.log(f"New branch requested: {new_branch}")
        
        # Choose operation mode
        if mode == "git_push":
            # Git Push Mode
            self.update_progress(35, "Preparing local git repository...")
            
            # Prepare local repo
            self.log(f"Preparing local repo in: {workdir}")
            final_branch = ensure_local_repo(workdir, branch, self.log, git_name or username, git_email)
            
            # Create new branch if requested
            if new_branch:
                self.update_progress(45, f"Creating branch: {new_branch}")
                self.log(f"Creating new branch: {new_branch}")
                final_branch = create_branch(workdir, final_branch, new_branch, self.log)

            # Stage/commit any recent changes
            self.update_progress(55, "Staging and committing changes...")
            run(["git", "add", "."], cwd=workdir)
            run(["git", "commit", "-m", "Sync commit"], cwd=workdir)

            # Push without storing credentials
            self.update_progress(70, f"Pushing to {full_name}...")
            try:
                one_shot_push(workdir, full_name, final_branch, base_url, username, password, self.log)
                self.update_progress(95, "Push completed successfully")
            except RuntimeError as e:
                error_str = str(e).lower()
                if ("unexpected disconnect" in error_str or "push failed" in error_str or "hung up" in error_str 
                    or "fetch first" in error_str or "rejected" in error_str or "non-fast-forward" in error_str):
                    
                    # Determine the type of error for better user messaging
                    if "fetch first" in error_str or "rejected" in error_str:
                        self.log("Git push failed: Repository has existing content that conflicts with local changes.")
                        self.log("This usually happens when pushing to an existing repository.")
                        self.log("Trying API upload as fallback to overwrite existing files...")
                    else:
                        self.log("Git push failed due to network issues. Trying API upload as fallback...")
                    
                    self.update_progress(75, "Git push failed, switching to API upload...")
                    
                    # Fallback to API upload
                    owner_name = full_name.split('/')[0]
                    repo_name_only = full_name.split('/')[1]
                    
                    success, errors = upload_directory(
                        base_url, owner_name, repo_name_only, final_branch,
                        workdir, username, "", password, verify_tls, self.log,
                        progress_callback=lambda v, t: self.update_progress(75 + v * 0.2, t),
                        force_overwrite=True  # Force overwrite in git push fallback mode
                    )
                    
                    if success > 0:
                        self.update_progress(95, f"API upload completed: {success} files uploaded")
                        self.log(f"Successfully uploaded {success} files via API (fallback method)")
                    else:
                        raise RuntimeError("Both Git push and API upload failed")
                else:
                    raise  # Re-raise if it's not a network issue
            
        else:
            # API Upload Mode
            self.update_progress(35, f"Preparing API upload to {full_name}...")
            self.log(f"Using API to upload files to {full_name}...")
            
            success, errors = upload_directory(
                base_url, owner_name, repo_name, working_branch,
                workdir, username, "", password, verify_tls, self.log,
                progress_callback=lambda v, t: self.update_progress(35 + v * 0.6, t),
                force_overwrite=False  # Normal API mode: respect existing files
            )
            
            self.update_progress(95, f"Upload completed: {success} files uploaded, {errors} errors")
            self.log(f"Upload completed: {success} files uploaded, {errors} errors")

        # Cleanup if we extracted
        if cleanup_root and os.path.isdir(cleanup_root):
            self.update_progress(98, "Cleaning up temporary files...")
            shutil.rmtree(cleanup_root, ignore_errors=True)
            self.log("Cleaned up temporary files")

        # Complete
        self.update_progress(100, "Operation completed successfully")
        logger.info("Upload operation completed successfully")

def log_session_end():
    """Log session end marker"""
    session_end = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"SESSION ENDED: {session_end}")
    logger.info("=" * 60)

def main():
    """Main entry point"""
    # Set up logging directory
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    
    try:
        # Parse command line args
        init_path = None
        if len(sys.argv) > 1:
            # Accept first arg as path
            init_path = sys.argv[1]
        
        # Create and run app
        app = App(initial_path=init_path)
        
        # Set up graceful shutdown
        def on_closing():
            log_session_end()
            app.destroy()
        
        app.protocol("WM_DELETE_WINDOW", on_closing)
        app.mainloop()
        
    except Exception as e:
        error_msg = f"Fatal error: {str(e)}"
        logger.error(error_msg)
        print(f"ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
    finally:
        log_session_end()

if __name__ == "__main__":
    main()