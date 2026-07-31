import os
import shutil
import tempfile
from typing import Optional, List, Tuple

try:
    from git import Repo, GitCommandError
except ImportError:
    # GitPython raises ImportError at import time when the `git` executable is
    # not available (e.g. on serverless platforms like Vercel). The app must
    # still load; git operations fail only when actually invoked.
    Repo = None
    GitCommandError = Exception


class GitManager:
    """Manages Git repository operations."""
    
    def __init__(self, base_path: Optional[str] = None):
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
    
    def get_repo_name(self, url: str) -> str:
        """Extract repository name from URL."""
        # Handle both HTTPS and SSH URLs
        name = url.rstrip('/').split('/')[-1]
        if name.endswith('.git'):
            name = name[:-4]
        return name
    
    def clone_or_pull(self, url: str, branch: str = "main") -> Tuple[str, bool]:
        """
        Clone repository if it doesn't exist, otherwise pull latest changes.
        
        Returns:
            tuple: (repo_path, is_new_clone)
        """
        if Repo is None:
            raise RuntimeError(
                "Git is not available in this environment (the `git` executable "
                "was not found). Repository cloning is disabled."
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
