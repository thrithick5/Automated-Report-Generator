import os
import google.generativeai as genai
from app.config import settings
from typing import Dict, Any
import json


class CodeAnalyzer:
    """Analyzes code using Google Gemini AI."""
    
    def __init__(self):
        self.model = None
        self._configured = False

    def _ensure_configured(self):
        if not self._configured:
            genai.configure(api_key=settings.gemini_api_key)
            # Use gemini-flash-latest (stable Gemini 1.5 Flash) to avoid experimental quota issues
            self.model = genai.GenerativeModel('gemini-flash-latest')
            self._configured = True
    
    def read_file_safely(self, file_path: str, max_size: int = 100000) -> str:
        """Read file content safely with size limit."""
        try:
            file_size = os.path.getsize(file_path)
            if file_size > max_size:
                return f"[File too large: {file_size} bytes]"
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            return f"[Error reading file: {str(e)}]"
    
    def prepare_code_summary(self, repo_path: str, max_files: int = 20) -> str:
        """
        Prepare a summary of code files for analysis.
        Limits to most important files to stay within token limits.
        """
        from app.services.git_manager import GitManager
        
        git_manager = GitManager()
        
        # Focus on common code file extensions
        extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb']
        files = git_manager.get_file_list(repo_path, extensions)
        
        # Limit number of files
        files = files[:max_files]
        
        code_summary = []
        for file_path in files:
            rel_path = os.path.relpath(file_path, repo_path)
            content = self.read_file_safely(file_path)
            code_summary.append(f"### File: {rel_path}\n```\n{content[:2000]}\n```\n")
        
        return "\n".join(code_summary)
    
    def prepare_code_summary(self, repo_path: str, max_files: int = 20) -> str:
        """
        Prepare a summary of code files for analysis.
        Limits to most important files to stay within token limits.
        
        DO NOT include any instructions, examples, or caveats. Only return a
        clean markdown-formatted list of files with their contents. 
        Each file section must follow the format:
        ```path/to/file.ext
        <file contents>
        ```
        If a file is too large (> max_size), include this exact text:
        [File too large: X bytes]
        Do not add any explanations, notes, or formatting beyond the requirements
        above.
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
            result.append(f'**{rel_path}**\n```\n{content}\n```')
        
        return '\n\n'.join(result)

    def analyze_code(self, repo_path: str) -> Dict[str, Any]:
        """
        Analyze code repository using Gemini AI.

        Returns:
            Dict containing analysis results with metrics and summary
        """
        self._ensure_configured()
        code_summary = self.prepare_code_summary(repo_path)

        gemini_prompt = f"""You are an expert software architect and developer. Analyze the provided repository and provide a structured JSON with the following sections:

[CODE_SUMMARY]

JSON structure must include:
- summary: Overall code quality and main issues. Summarize the most significant findings, especially those that impact reliability, security, and maintainability. Include a brief overview of the codebase's quality and maturity.
- metrics: Numeric scores and counts. Provide: critical (critical security risks, bugs, and issues that could cause outages), warnings (style improvements, best practice violations, and other quality issues), complexity (max complexity metric across files), quality_score (overall 0-100) based on critical issues.
- issues: Specific findings with severity and code locations. List up to 10 issues with: file (relative path), severity (critical/high/medium/warning/low), description (clear text stating the problem, including location and impact).
- recommendations: Actionable improvements. 2-4 items for enhancing code quality, fixing critical issues, and preventing regressions. Include code samples only where necessary.

IMPORTANT RULES:
- output only valid JSON, no markdown, no extra text
- keep the summary concise but comprehensive
- for each issue include the exact code location where applicable
- prioritize critical issues first
- always focus on genuine problems, not false positives

Return ONLY a valid JSON object matching this structure.""".replace("[CODE_SUMMARY]", code_summary)

        try:
            response = self.model.generate_content(gemini_prompt)
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]

            result = json.loads(response_text.strip())
            return {
                "summary": result.get("summary", "Analysis completed"),
                "metrics": {
                    "critical": result.get("metrics", {}).get("critical", 0),
                    "warnings": result.get("metrics", {}).get("warnings", 0),
                    "complexity": result.get("metrics", {}).get("complexity", 0),
                    "quality_score": result.get("metrics", {}).get("quality_score", 0)
                },
                "issues": result.get("issues", []),
                "recommendations": result.get("recommendations", [])
            }
        except Exception as e:
            raise Exception(f"Analysis failed: {e}")

        try:
            response = self.model.generate_content(prompt)
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            result = json.loads(response_text.strip())
            return result
            
        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            return {
                "summary": "Analysis completed but response format was invalid.",
                "metrics": {
                    "critical": 0,
                    "warnings": 0,
                    "complexity": 50,
                    "quality_score": 70
                },
                "issues": [],
                "recommendations": ["Unable to parse detailed analysis"]
            }
        except Exception as e:
            raise Exception(f"Analysis failed: {str(e)}")
