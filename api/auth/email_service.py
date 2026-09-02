"""SMTP email sending via Gmail (or any SMTP provider — just swap env vars)."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ingestion.config import Config


def send_email(to: str, subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{Config.SMTP_FROM_NAME} <{Config.SMTP_USER}>"
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
        server.starttls()
        server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        print("Login succeeded!")
        server.sendmail(Config.SMTP_USER, [to], msg.as_string())


def send_reset_email(to: str, raw_token: str):
    reset_link = f"{Config.FRONTEND_URL}/reset-password?token={raw_token}"
    html = f"""
    <p>You requested a password reset for SecOps Copilot.</p>
    <p><a href="{reset_link}">Click here to reset your password</a></p>
    <p>This link expires in 30 minutes. If you didn't request this, ignore this email.</p>
    """
    send_email(to, "Reset your SecOps Copilot password", html)