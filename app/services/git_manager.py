import io
import os
import re
import shutil
import tarfile
import tempfile
from typing import Optional, List, Tuple

import requests

try:
    from git import Repo, GitCommandError
except ImportError:
    # GitPython raises ImportError at import time when the `git` executable is
    # not available (e.g. on serverless platforms like Vercel). The app must
    # still load; git operations fail only when actually invoked.
    Repo = None
    GitCommandError = Exception

GITHUB_URL_RE = re.compile(
    r'^(?:(?:https?|git)://(?:www\.)?|git@)github\.com[/:]'
    r'(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$'
)


class GitManager:
    """Fetches repository source code for analysis.

    GitHub repositories are downloaded as tarballs via the GitHub API, so the
    platform does not need a `git` executable (required on serverless platforms
    like Vercel). Non-GitHub repositories fall back to a real git clone when
    git is available.
    """

    def __init__(self, base_path: Optional[str] = None, github_token: Optional[str] = None):
        if base_path is None:
            if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
                base_path = "/tmp/repos"
            else:
                base_path = "./data/repos"
        self.base_path = base_path
        try:
            os.makedirs(self.base_path, exist_ok=True)
        except Exception:
            self.base_path = os.path.join(tempfile.gettempdir(), "repos")
            os.makedirs(self.base_path, exist_ok=True)
        if github_token is None:
            from app.config import settings
            github_token = settings.github_token
        self.github_token = github_token

    def get_repo_name(self, url: str) -> str:
        """Extract repository name from URL."""
        # Handle both HTTPS and SSH URLs
        name = url.rstrip('/').split('/')[-1]
        if name.endswith('.git'):
            name = name[:-4]
        return name

    @staticmethod
    def parse_github_url(url: str) -> Optional[Tuple[str, str]]:
        """Return (owner, repo) if the URL is a GitHub URL, else None."""
        match = GITHUB_URL_RE.match(url.strip())
        if not match:
            return None
        return match.group("owner"), match.group("repo")

    def download_github_repo(self, owner: str, repo: str, branch: str = "main") -> str:
        """Download a GitHub repository tarball and extract it.

        Uses the GitHub API codeload endpoint so no `git` executable is needed.
        Falls back to the branch argument for the requested ref.

        Returns:
            str: path to the extracted repository contents.
        """
        api_url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{branch}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AI-Report-Generator",
        }
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"

        try:
            response = requests.get(
                api_url, headers=headers, timeout=120, allow_redirects=True, stream=True
            )
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to download repository from GitHub: {str(e)}")

        if response.status_code == 404:
            raise Exception(
                f"Repository '{owner}/{repo}' not found. Check the repository name, "
                f"branch '{branch}', and visibility. Private repositories require "
                f"a GITHUB_TOKEN."
            )
        if response.status_code in (401, 403):
            raise Exception(
                f"GitHub rejected the download (HTTP {response.status_code}). A "
                f"valid GITHUB_TOKEN is required for private repositories."
            )
        if response.status_code >= 400:
            raise Exception(
                f"Failed to download repository from GitHub (HTTP {response.status_code})."
            )

        # The tarball extracts into a single top-level directory like "owner-repo-hash".
        repo_name = self.get_repo_name(f"{owner}/{repo}")
        dest = os.path.join(self.base_path, repo_name)
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest, exist_ok=True)

        buffer = io.BytesIO()
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                buffer.write(chunk)
        buffer.seek(0)

        try:
            with tarfile.open(fileobj=buffer, mode="r:gz") as tar:
                tar.extractall(dest)
        except tarfile.TarError as e:
            raise Exception(f"Failed to extract repository archive: {str(e)}")

        inner_dirs = [
            d for d in os.listdir(dest)
            if os.path.isdir(os.path.join(dest, d)) and not d.startswith('.')
        ]
        return os.path.join(dest, inner_dirs[0]) if len(inner_dirs) == 1 else dest

    def fetch(self, url: str, branch: str = "main") -> Tuple[str, bool]:
        """Fetch repository source. Returns (repo_path, is_fresh_download).

        GitHub URLs are downloaded as tarballs (no git required). Any other URL
        uses a git clone/pull when git is available.
        """
        github = self.parse_github_url(url)
        if github:
            return self.download_github_repo(github[0], github[1], branch), True
        return self.clone_or_pull(url, branch), True

    def clone_or_pull(self, url: str, branch: str = "main") -> Tuple[str, bool]:
        """
        Clone repository if it doesn't exist, otherwise pull latest changes.

        Returns:
            tuple: (repo_path, is_new_clone)
        """
        if Repo is None:
            raise RuntimeError(
                "Git is not available in this environment (the `git` executable "
                "was not found) and this is not a GitHub URL, so the repository "
                "cannot be fetched."
            )
        repo_name = self.get_repo_name(url)
        repo_path = os.path.join(self.base_path, repo_name)
        
        try:
            if os.path.exists(repo_path):
                # Repository exists, pull latest changes
                repo = Repo(repo_path)
                origin = repo.remotes.origin
                origin.pull(branch)
                return repo_path, False
            else:
                # Clone new repository
                Repo.clone_from(url, repo_path, branch=branch)
                return repo_path, True
        except GitCommandError as e:
            raise Exception(f"Git operation failed: {str(e)}")
    
    def delete_repo(self, url: str) -> bool:
        """Delete a cloned repository."""
        repo_name = self.get_repo_name(url)
        repo_path = os.path.join(self.base_path, repo_name)
        
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
            return True
        return False
    
    def get_file_list(self, repo_path: str, extensions: Optional[List[str]] = None) -> List[str]:
        """
        Get list of files in repository, optionally filtered by extension.
        
        Args:
            repo_path: Path to repository
            extensions: List of file extensions to include (e.g., ['.py', '.js'])
        """
        files = []
        for root, _, filenames in os.walk(repo_path):
            # Skip .git directory
            if '.git' in root:
                continue
            
            for filename in filenames:
                if extensions:
                    if any(filename.endswith(ext) for ext in extensions):
                        files.append(os.path.join(root, filename))
                else:
                    files.append(os.path.join(root, filename))
        
        return files
