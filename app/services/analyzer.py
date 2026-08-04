import os
import json
import requests
from typing import Dict, Any
from app.config import settings


class CodeAnalyzer:
    """Analyzes code repositories using Mistral AI (Codestral / Mistral models)."""

    def __init__(self):
        pass

    def _get_api_key(self) -> str:
        key = settings.mistral_api_key or os.environ.get("MISTRAL_API_KEY") or settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise Exception("MISTRAL_API_KEY environment variable is not configured.")
        return key

    def prepare_code_summary(self, repo_path: str, max_files: int = 20) -> str:
        """
        Prepare a clean summary of code files for analysis.
        """
        from app.services.git_manager import GitManager

        git_manager = GitManager()
        extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb']
        files = git_manager.get_file_list(repo_path, extensions)
        files = files[:max_files]

        result = []
        for file_path in files:
            rel_path = os.path.relpath(file_path, repo_path)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                content = f'[Error reading file: {file_path}]'
            result.append(f'**{rel_path}**\n```\n{content[:3000]}\n```')

        return '\n\n'.join(result)

    def analyze_code(self, repo_path: str, model_name: str = "codestral-latest") -> Dict[str, Any]:
        """
        Analyze code repository using Mistral AI.

        Returns:
            Dict containing analysis results with metrics and summary
        """
        api_key = self._get_api_key()
        code_summary = self.prepare_code_summary(repo_path)

        prompt = f"""You are an expert software architect and security engineer. Analyze the provided code repository and return a structured JSON evaluation.

Repository Code Files:
{code_summary}

Required JSON Format:
{{
  "summary": "High-level summary of code quality, architectural health, and key findings.",
  "metrics": {{
    "critical": 0,
    "warnings": 0,
    "complexity": 0,
    "quality_score": 85
  }},
  "issues": [
    {{
      "file": "path/to/file",
      "severity": "critical|warning|info",
      "description": "Clear explanation of the problem."
    }}
  ],
  "recommendations": [
    "Actionable recommendation 1",
    "Actionable recommendation 2"
  ]
}}

IMPORTANT RULES:
- Output ONLY valid JSON matching the exact schema above. No markdown code blocks, no extra commentary.
- Prioritize critical security vulnerabilities, bugs, and maintainability concerns.
"""

        # Map legacy model names if passed
        if "gemini" in model_name.lower():
            model_name = "codestral-latest"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        try:
            url = "https://api.mistral.ai/v1/chat/completions"
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()

            data = response.json()
            response_text = data['choices'][0]['message']['content'].strip()

            # Clean response if wrapped in code fence
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]

            result = json.loads(response_text.strip())
            return {
                "summary": result.get("summary", "Analysis completed."),
                "metrics": {
                    "critical": result.get("metrics", {}).get("critical", 0),
                    "warnings": result.get("metrics", {}).get("warnings", 0),
                    "complexity": result.get("metrics", {}).get("complexity", 50),
                    "quality_score": result.get("metrics", {}).get("quality_score", 80)
                },
                "issues": result.get("issues", []),
                "recommendations": result.get("recommendations", [])
            }
        except Exception as e:
            raise Exception(f"Mistral API analysis failed: {str(e)}")
