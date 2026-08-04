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
        self.smtp_host = (settings.smtp_host or "smtp.gmail.com").strip()
        self.smtp_port = str(settings.smtp_port or "587").strip()
        self.smtp_username = (settings.smtp_username or "").strip()
        self.smtp_password = (settings.smtp_password or "").replace(" ", "").strip()
        self.email_from = (settings.email_from or self.smtp_username).strip()
    
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
    
    def _send_via_resend(self, api_key: str, recipients: list[str], subject: str, html: str) -> Tuple[bool, Optional[str]]:
        """Send email via Resend HTTP API (Port 443 - HTTPS)."""
        import json
        import urllib.request
        logger.info("Sending email via Resend HTTPS API (Port 443)...")
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": self.email_from or "onboarding@resend.dev",
            "to": recipients,
            "subject": subject,
            "html": html
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status in (200, 201):
                    logger.info("Email sent successfully via Resend!")
                    return True, None
                return False, f"Resend API returned HTTP status {resp.status}"
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Resend API error: {err_msg}")
            return False, f"Resend API error: {err_msg}"

    def _send_via_brevo(self, api_key: str, recipients: list[str], subject: str, html: str) -> Tuple[bool, Optional[str]]:
        """Send email via Brevo HTTP API (Port 443 - HTTPS)."""
        import json
        import urllib.request
        logger.info("Sending email via Brevo HTTPS API (Port 443)...")
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "api-key": api_key.strip(),
            "Content-Type": "application/json"
        }
        payload = {
            "sender": {"email": self.email_from or self.smtp_username or "noreply@automatedreport.com", "name": "Report Generator"},
            "to": [{"email": r} for r in recipients],
            "subject": subject,
            "htmlContent": html
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status in (200, 201):
                    logger.info("Email sent successfully via Brevo!")
                    return True, None
                return False, f"Brevo API returned HTTP status {resp.status}"
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Brevo API error: {err_msg}")
            return False, f"Brevo API error: {err_msg}"

    def send_report(self, recipients: list[str], report_data: Dict[str, Any], repo_url: str = "") -> Tuple[bool, Optional[str]]:
        """
        Send analysis report via email (supporting HTTP APIs over port 443 and fallback SMTP).
        
        Args:
            recipients: List of email addresses
            report_data: Report data dictionary
            repo_url: Repository URL for subject line
        
        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        subject = f"Daily Code Analysis Report - {datetime.now().strftime('%Y-%m-%d')}"
        html_content = self.create_report_html(report_data)

        # 1. Check if Resend HTTP API key is configured
        resend_key = (settings.resend_api_key or os.environ.get("RESEND_API_KEY") or "").strip()
        if resend_key:
            return self._send_via_resend(resend_key, recipients, subject, html_content)

        # 2. Check if Brevo HTTP API key is configured
        brevo_key = (settings.brevo_api_key or os.environ.get("BREVO_API_KEY") or "").strip()
        if brevo_key:
            return self._send_via_brevo(brevo_key, recipients, subject, html_content)

        # 3. Fallback to standard SMTP
        if not self.smtp_username or not self.smtp_password:
            err = "SMTP credentials missing. Configure SMTP_USERNAME/SMTP_PASSWORD or RESEND_API_KEY in Render environment."
            logger.error(err)
            return False, err

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_from or self.smtp_username
            msg['To'] = ', '.join(recipients)
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            primary_port = int(self.smtp_port) if self.smtp_port and self.smtp_port.isdigit() else 587
            ports_to_try = [(primary_port, primary_port == 465)]
            if primary_port != 465:
                ports_to_try.append((465, True))

            last_error = None
            orig_getaddrinfo = socket.getaddrinfo
            def getaddrinfo_ipv4(host, p, family=0, type=0, proto=0, flags=0):
                return orig_getaddrinfo(host, p, socket.AF_INET, type, proto, flags)

            try:
                socket.getaddrinfo = getaddrinfo_ipv4
                for port, is_ssl in ports_to_try:
                    server_class = smtplib.SMTP_SSL if is_ssl else smtplib.SMTP
                    logger.info(f"Connecting to SMTP server {self.smtp_host}:{port} using {'SSL' if is_ssl else 'TLS/Plain'} (IPv4)...")
                    try:
                        with server_class(self.smtp_host, port, timeout=10) as server:
                            if not is_ssl:
                                server.starttls()
                            logger.info(f"Attempting SMTP login for {self.smtp_username}...")
                            server.login(self.smtp_username, self.smtp_password)
                            logger.info(f"Sending email message to: {msg['To']}")
                            server.send_message(msg)
                        logger.info("Email sent successfully!")
                        return True, None
                    except Exception as try_err:
                        last_error = str(try_err)
                        logger.warning(f"SMTP connection to port {port} failed: {last_error}")
                        if port == primary_port and len(ports_to_try) > 1:
                            logger.info("Retrying automatically over SSL port 465...")
                            continue
                        break
            finally:
                socket.getaddrinfo = orig_getaddrinfo

            if "timed out" in str(last_error).lower():
                detailed_msg = "Render Free Tier blocks outbound SMTP ports 587 & 465. Set RESEND_API_KEY or BREVO_API_KEY in Render Environment variables to send emails over HTTPS port 443."
                logger.error(detailed_msg)
                return False, detailed_msg

            return False, last_error
            
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Failed to send email: {err_msg}", exc_info=True)
            return False, err_msg
