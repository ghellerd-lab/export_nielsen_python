from __future__ import annotations

import mimetypes
import smtplib
import ssl
import subprocess
import sys
import tempfile
import urllib.parse
import webbrowser
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from nielsen_config import Config


def split_addresses(value: str) -> list[str]:
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def resolve_config_path(raw_path: str, root_dir: Path) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else root_dir / path


def hide_windows_path(path: Path) -> None:
    if sys.platform == "win32" and path.exists():
        subprocess.run(["attrib", "+h", str(path)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)


def read_smtp_password(config: Config, root_dir: Path) -> str:
    if config.smtp_password_dpapi_file:
        password_path = resolve_config_path(config.smtp_password_dpapi_file, root_dir)
        hide_windows_path(password_path.parent)
        script = r"""
param([string]$Path)
$secure = Get-Content -LiteralPath $Path | ConvertTo-SecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / "read_smtp_password.ps1"
            script_path.write_text(script, encoding="utf-8")
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path),
                 "-Path", str(password_path)], capture_output=True, text=True, timeout=60)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"Nu am putut decripta parola SMTP DPAPI: {detail}")
        return completed.stdout.rstrip("\r\n")
    if not config.smtp_password_file:
        return ""
    lines = resolve_config_path(config.smtp_password_file, root_dir).read_text(encoding="utf-8").splitlines()
    return lines[0].strip() if lines else ""


def send_zip_email_outlook(recipients: list[str], cc_recipients: list[str], subject: str,
                           body: str, zip_path: Path) -> None:
    script = r"""
param([string]$To,[string]$Cc,[string]$Subject,[string]$Body,[string]$Attachment)
$outlook = New-Object -ComObject Outlook.Application
$mail = $outlook.CreateItem(0)
$mail.To = $To; $mail.CC = $Cc; $mail.Subject = $Subject; $mail.Body = $Body
[void]$mail.Attachments.Add($Attachment)
$mail.Send()
"""
    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = Path(temp_dir) / "send_nielsen_email.ps1"
        script_path.write_text(script, encoding="utf-8")
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path),
             "-To", "; ".join(recipients), "-Cc", "; ".join(cc_recipients), "-Subject", subject,
             "-Body", body, "-Attachment", str(zip_path)], capture_output=True, text=True, timeout=120)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"Nu am putut trimite email prin Outlook local: {detail}")


def open_outlook365_compose(recipients: list[str], cc_recipients: list[str], subject: str,
                            body: str, zip_path: Path) -> None:
    query = urllib.parse.urlencode({"to": ";".join(recipients), "cc": ";".join(cc_recipients),
                                    "subject": subject, "body": f"{body}\n\nAtasament de adaugat manual: {zip_path}"})
    webbrowser.open(f"https://outlook.office.com/mail/deeplink/compose?{query}")
    raise RuntimeError("Outlook 365 Web a fost deschis, dar atasamentul nu poate fi trimis automat")


def send_zip_email(config: Config, root_dir: Path, zip_path: Path, log: Callable[[str], None]) -> None:
    if not config.send_email_enabled:
        log("Email sarit: send_email nu este y")
        return
    recipients, cc_recipients = split_addresses(config.email), split_addresses(config.email_cc)
    if not recipients:
        raise ValueError("send_email=y, dar parametrul email este gol")
    subject = f"Export Nielsen {config.p_soc_name} {config.v_sapt_name}"
    body = (f"Buna ziua,\n\nAtasat exportul Nielsen pentru {config.p_soc_name}.\n"
            f"Perioada: {config.p_data_start}-{config.p_data_final}, saptamana {config.p_sapt}.\n\nMesaj generat automat.")
    method = config.email_method or "auto"
    if method not in {"auto", "outlook", "outlook365", "smtp"}:
        raise ValueError(f"email_method invalid: {config.email_method}")
    if method == "outlook365":
        open_outlook365_compose(recipients, cc_recipients, subject, body, zip_path)
    if method in {"auto", "outlook"}:
        send_zip_email_outlook(recipients, cc_recipients, subject, body, zip_path)
    else:
        sender = config.smtp_from or config.smtp_username
        if not config.smtp_server or not sender:
            raise ValueError("Pentru SMTP sunt obligatorii smtp_server si smtp_from sau smtp_username")
        message = EmailMessage()
        sender_header = f"{config.smtp_from_name} <{sender}>" if config.smtp_from_name else sender
        message["Subject"], message["From"], message["To"] = subject, sender_header, ", ".join(recipients)
        if cc_recipients:
            message["Cc"] = ", ".join(cc_recipients)
        message.set_content(body)
        content_type, _ = mimetypes.guess_type(zip_path.name)
        maintype, subtype = (content_type or "application/zip").split("/", 1)
        message.add_attachment(zip_path.read_bytes(), maintype=maintype, subtype=subtype, filename=zip_path.name)
        password = read_smtp_password(config, root_dir)
        all_recipients = recipients + cc_recipients
        if config.smtp_security == "ssl":
            with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, timeout=60,
                                   context=ssl.create_default_context()) as smtp:
                if config.smtp_username:
                    smtp.login(config.smtp_username, password)
                smtp.send_message(message, from_addr=sender, to_addrs=all_recipients)
        else:
            with smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=60) as smtp:
                if config.smtp_security in {"starttls", "tls"}:
                    smtp.starttls(context=ssl.create_default_context())
                elif config.smtp_security not in {"none", ""}:
                    raise ValueError(f"smtp_security invalid: {config.smtp_security}")
                if config.smtp_username:
                    smtp.login(config.smtp_username, password)
                smtp.send_message(message, from_addr=sender, to_addrs=all_recipients)
    log(f"Email trimis catre: {', '.join(recipients)}")
