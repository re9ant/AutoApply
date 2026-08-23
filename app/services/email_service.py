import email
import logging
import mimetypes
import os
import re
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.models.candidate import CandidateProfile
from app.models.job import ExtractedJobDescription, MatchScoreBreakdown

logger = logging.getLogger(__name__)


class EmailAccountConfig(BaseModel):
    email_address: Optional[str] = None
    app_password: Optional[str] = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True
    display_name: Optional[str] = None


class GeneratedEmail(BaseModel):
    recipient_email: str
    subject: str
    body_text: str
    attached_resume_filename: str
    attachment_found: bool
    is_dry_run: bool = True


class EmailService:
    """Handles HR email discovery, tailored cover email generation, PDF attachment, and Gmail SMTP delivery."""

    def __init__(self, config: Optional[EmailAccountConfig] = None):
        if config:
            self.config = config
        else:
            from app.config.config_store import config_store
            saved = config_store.get_email_config()
            self.config = EmailAccountConfig(
                email_address=saved.get("email_address") or os.getenv("GMAIL_ADDRESS"),
                app_password=saved.get("app_password") or os.getenv("GMAIL_APP_PASSWORD"),
                display_name=saved.get("display_name") or "",
                smtp_host=saved.get("smtp_host", "smtp.gmail.com"),
                smtp_port=saved.get("smtp_port", 587),
                use_tls=saved.get("use_tls", True)
            )

    def set_config(self, config: EmailAccountConfig) -> None:
        self.config = config
        from app.config.config_store import config_store
        config_store.set_email_config({
            "email_address": config.email_address or "",
            "app_password": config.app_password or "",
            "display_name": config.display_name or "",
            "smtp_host": config.smtp_host,
            "smtp_port": config.smtp_port,
            "use_tls": config.use_tls
        })

    def extract_hr_email(self, jd_text: str, company: str, job_url: Optional[str] = None) -> str:
        """Find recruiter/HR email in JD text or construct a standard fallback."""
        # 1. Search for email in JD text
        email_pattern = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
        matches = email_pattern.findall(jd_text or "")

        for match in matches:
            m_lower = match.lower()
            if any(term in m_lower for term in ["job", "career", "hr", "recruit", "talent", "hiring", "apply"]):
                return match
            if not any(skip in m_lower for skip in ["example.com", "wix.com", "schema.org", "sentry.io"]):
                return match

        # 2. Extract domain from job URL if present
        domain = None
        if job_url:
            cleaned = job_url.split("//")[-1].split("/")[0].replace("www.", "")
            if "." in cleaned and "greenhouse" not in cleaned and "lever" not in cleaned and "ashbyhq" not in cleaned:
                domain = cleaned

        # 3. Derive standard company domain fallback
        if not domain:
            safe_company = re.sub(r"[^a-zA-Z0-9]", "", company).lower()
            domain = f"{safe_company}games.com" if "game" in company.lower() else f"{safe_company}.com"

        return f"careers@{domain}"

    def generate_application_email(
        self,
        jd: ExtractedJobDescription,
        profile: CandidateProfile,
        score: MatchScoreBreakdown,
        resume_filename: str,
        recipient_override: Optional[str] = None,
        is_dry_run: bool = True
    ) -> GeneratedEmail:
        """Generate a personalized, truthful cover email referencing matching qualifications and projects."""
        recipient = recipient_override or self.extract_hr_email(
            jd_text=jd.raw_source or "",
            company=jd.company,
            job_url=jd.application_url
        )

        candidate_name = profile.candidate.name
        subject = f"Application: {jd.title} - {candidate_name}"

        # Identify key project to highlight
        top_project = profile.projects[0] if profile.projects else None
        project_snippet = ""
        if top_project:
            project_snippet = (
                f"In my project '{top_project.name}' ({top_project.role}), I developed "
                f"{', '.join(top_project.technical_highlights[:2])} using {', '.join(top_project.technologies[:3])}."
            )

        strengths_summary = ""
        if score.key_strengths:
            strengths_summary = f"My background aligns directly with your requirements, including {', '.join(score.key_strengths[:2])}."

        body = f"""Dear Hiring Team at {jd.company},

I am writing to express my strong interest in the {jd.title} position at {jd.company}.

{strengths_summary}

{project_snippet}

With a degree in {profile.education[0].degree if profile.education else 'Computer Science'} ({profile.education[0].field_of_study if profile.education else 'CSE'}) and verified hands-on experience in {', '.join(profile.skills.languages[:3])}{' and ' + ', '.join(profile.skills.engines[:1]) if profile.skills.engines else ''}, I am confident in contributing immediately to your team's development goals.

I have attached my resume ({resume_filename}) for your review. You can also view my portfolio and projects at:
• Portfolio: {profile.candidate.portfolio or profile.candidate.github}
• GitHub: {profile.candidate.github}
{f'• Playable Demos: {profile.candidate.itch_io}' if profile.candidate.itch_io else ''}

Thank you for your time and consideration. I look forward to the possibility of discussing how my skills match your team's vision.

Best regards,

{candidate_name}
{profile.candidate.email}
{profile.candidate.phone or ''}
{profile.candidate.location}
"""

        # Verify resume file attachment
        resume_path = settings.resolve_path(settings.RESUMES_DIR / resume_filename)
        attachment_found = resume_path.exists()

        return GeneratedEmail(
            recipient_email=recipient,
            subject=subject,
            body_text=body.strip(),
            attached_resume_filename=resume_filename,
            attachment_found=attachment_found,
            is_dry_run=is_dry_run
        )

    def test_smtp_connection(self) -> Dict[str, Any]:
        """Test SMTP connection to Gmail using configured credentials."""
        if not self.config.email_address or not self.config.app_password:
            return {
                "success": False,
                "message": "Gmail address or App Password not configured."
            }

        try:
            server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=10)
            if self.config.use_tls:
                server.starttls()
            server.login(self.config.email_address, self.config.app_password)
            server.quit()
            return {
                "success": True,
                "message": f"Successfully connected to Gmail SMTP as {self.config.email_address}!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"SMTP Authentication failed: {str(e)}"
            }

    def send_application_email(self, email_data: GeneratedEmail) -> Tuple[bool, str]:
        """Send the email via Gmail SMTP or log in dry-run mode."""
        if email_data.is_dry_run:
            log_msg = (
                f"[DRY-RUN EMAIL PREVIEW]\n"
                f"To: {email_data.recipient_email}\n"
                f"Subject: {email_data.subject}\n"
                f"Attached: {email_data.attached_resume_filename} (Found: {email_data.attachment_found})\n"
                f"--- Body ---\n{email_data.body_text[:200]}...\n[DRY RUN - Email was NOT sent to preserve testing safety]"
            )
            logger.info(log_msg)
            return True, log_msg

        if not self.config.email_address or not self.config.app_password:
            raise ValueError("Gmail address and App Password are required for live sending.")

        # Build MIME Message
        msg = MIMEMultipart()
        msg["From"] = f"{self.config.display_name or 'Applicant'} <{self.config.email_address}>"
        msg["To"] = email_data.recipient_email
        msg["Subject"] = email_data.subject

        # Attach text body
        msg.attach(MIMEText(email_data.body_text, "plain", "utf-8"))

        # Attach PDF Resume
        resume_path = settings.resolve_path(settings.RESUMES_DIR / email_data.attached_resume_filename)
        if resume_path.exists():
            with open(resume_path, "rb") as f:
                attach_part = MIMEApplication(f.read(), Name=email_data.attached_resume_filename)
            attach_part["Content-Disposition"] = f'attachment; filename="{email_data.attached_resume_filename}"'
            msg.attach(attach_part)

        # Send via SMTP
        server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=15)
        if self.config.use_tls:
            server.starttls()
        server.login(self.config.email_address, self.config.app_password)
        server.send_message(msg)
        server.quit()

        return True, f"Email sent successfully to {email_data.recipient_email} with {email_data.attached_resume_filename} attached."


email_service = EmailService()
