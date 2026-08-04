import smtplib
import socket
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from app.config import settings
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class EmailService:
    """Handles email sending operations."""
    
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.email_from = settings.email_from
    
    def create_report_html(self, report_data: Dict[str, Any]) -> str:
        """Create HTML email template for the report."""
        
        metrics = report_data.get('metrics', {})
        summary = report_data.get('summary', 'No summary available')
        issues = report_data.get('issues', [])
        recommendations = report_data.get('recommendations', [])
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                          color: white; padding: 30px; border-radius: 10px; }}
                .metrics {{ display: flex; justify-content: space-around; margin: 30px 0; }}
                .metric-card {{ text-align: center; padding: 20px; border-radius: 8px; 
                               background: #f8f9fa; }}
                .metric-value {{ font-size: 36px; font-weight: bold; }}
                .metric-label {{ color: #6c757d; margin-top: 5px; }}
                .section {{ margin: 30px 0; }}
                .section-title {{ font-size: 20px; font-weight: bold; margin-bottom: 15px; 
                                 border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
                .issue {{ padding: 10px; margin: 10px 0; border-left: 4px solid #dc3545; 
                         background: #f8d7da; }}
                .warning {{ border-left-color: #ffc107; background: #fff3cd; }}
                .footer {{ text-align: center; color: #6c757d; margin-top: 40px; 
                          padding-top: 20px; border-top: 1px solid #dee2e6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Daily Code Analysis Report</h1>
                    <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                </div>
                
                <div class="metrics">
                    <div class="metric-card">
                        <div class="metric-value" style="color: #dc3545;">{metrics.get('critical', 0)}</div>
                        <div class="metric-label">Critical Issues</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" style="color: #ffc107;">{metrics.get('warnings', 0)}</div>
                        <div class="metric-label">Warnings</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" style="color: #007bff;">{metrics.get('complexity', 0)}</div>
                        <div class="metric-label">Complexity</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" style="color: #28a745;">{metrics.get('quality_score', 0)}%</div>
                        <div class="metric-label">Quality Score</div>
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-title">📝 Summary</div>
                    <p>{summary}</p>
                </div>
                
                <div class="section">
                    <div class="section-title">⚠️ Issues Found</div>
                    {''.join([f'<div class="issue {("warning" if issue.get("severity") == "warning" else "")}"><strong>{issue.get("file", "Unknown")}</strong>: {issue.get("description", "No description")}</div>' for issue in issues[:10]])}
                    {f'<p><em>... and {len(issues) - 10} more issues</em></p>' if len(issues) > 10 else ''}
                </div>
                
                <div class="section">
                    <div class="section-title">💡 Recommendations</div>
                    <ul>
                        {''.join([f'<li>{rec}</li>' for rec in recommendations])}
                    </ul>
                </div>
                
                <div class="footer">
                    <p>Powered by AI Code Report Generator | Gemini 1.5 Flash</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def send_report(self, recipients: list[str], report_data: Dict[str, Any], repo_url: str = "") -> Tuple[bool, Optional[str]]:
        """
        Send analysis report via email.
        
        Args:
            recipients: List of email addresses
            report_data: Report data dictionary
            repo_url: Repository URL for subject line
        
        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        if not self.smtp_username or not self.smtp_password:
            err = "SMTP_USERNAME or SMTP_PASSWORD environment variable is missing on server."
            logger.error(err)
            return False, err

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Daily Code Analysis Report - {datetime.now().strftime('%Y-%m-%d')}"
            msg['From'] = self.email_from or self.smtp_username
            msg['To'] = ', '.join(recipients)
            
            # Create HTML content
            html_content = self.create_report_html(report_data)
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Check if port is standard SSL (465) or TLS (587/others)
            port = int(self.smtp_port) if self.smtp_port else 587
            is_ssl = port == 465
            server_class = smtplib.SMTP_SSL if is_ssl else smtplib.SMTP
            
            # Force IPv4 socket resolution to prevent 'Network is unreachable' IPv6 errors on cloud hosts like Render
            orig_getaddrinfo = socket.getaddrinfo
            def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
                return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

            logger.info(f"Connecting to SMTP server {self.smtp_host}:{port} using {'SSL' if is_ssl else 'TLS/Plain'} (IPv4)...")
            try:
                socket.getaddrinfo = getaddrinfo_ipv4
                with server_class(self.smtp_host, port, timeout=20) as server:
                    if not is_ssl:
                        server.starttls()
                    logger.info(f"Attempting SMTP login for {self.smtp_username}...")
                    server.login(self.smtp_username, self.smtp_password)
                    logger.info(f"Sending email message to: {msg['To']}")
                    server.send_message(msg)
            finally:
                socket.getaddrinfo = orig_getaddrinfo
            
            logger.info("Email sent successfully!")
            return True, None
            
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Failed to send email: {err_msg}", exc_info=True)
            return False, err_msg
