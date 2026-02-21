import os
import google.generativeai as genai
from app.config import settings
from typing import Dict, Any
import json


class CodeAnalyzer:
    """Analyzes code using Google Gemini AI."""
    
    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        # Use gemini-flash-latest (stable Gemini 1.5 Flash) to avoid experimental quota issues
        self.model = genai.GenerativeModel('gemini-flash-latest')
    
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
    
    def analyze_code(self, repo_path: str) -> Dict[str, Any]:
        """
        Analyze code repository using Gemini AI.
        
        Returns:
            Dict containing analysis results with metrics and summary
        """
        code_summary = self.prepare_code_summary(repo_path)
        
        prompt = f"""You are a senior code reviewer. Analyze the following code repository and provide a structured assessment.

{code_summary}

Please provide your analysis in the following JSON format:
{{
    "summary": "A brief overall summary of the code quality and structure",
    "metrics": {{
        "critical": <number of critical issues found>,
        "warnings": <number of warnings/minor issues>,
        "complexity": <average complexity score 0-100>,
        "quality_score": <overall quality percentage 0-100>
    }},
    "issues": [
        {{
            "file": "filename",
            "severity": "critical/warning/info",
            "description": "issue description"
        }}
    ],
    "recommendations": [
        "recommendation 1",
        "recommendation 2"
    ]
}}

Focus on:
- Code structure and organization
- Potential bugs and security issues
- Code complexity and maintainability
- Best practices adherence

Respond ONLY with valid JSON, no additional text."""

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
