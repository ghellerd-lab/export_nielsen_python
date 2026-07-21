from __future__ import annotations

import argparse
import mimetypes
import urllib.parse
import webbrowser
import shutil
import smtplib
import ssl
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


DEFAULT_PROPERTIES = app_dir() / "jobExportNielsen.properties"
ENCODING = "iso-8859-15"


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


@dataclass(frozen=True)
class Config:
    oracle_server: str
    oracle_port: int
    oracle_username: str
    oracle_password: str
    oracle_sid: str
    p_id_societate: int
    p_soc_name: str
    p_sapt: int
    p_id_gestiune_start: int
    p_id_gestiune_final: int
    p_data_start: int
    p_data_final: int
    last_month: str
    articole: str
    send_email: str
    email: str
    email_cc: str
    email_method: str
    smtp_server: str
    smtp_port: int
    smtp_security: str
    smtp_username: str
    smtp_password_file: str
    smtp_password_dpapi_file: str
    smtp_from: str
    smtp_from_name: str

    @property
    def v_sapt_name(self) -> str:
        return f"{self.p_data_start}-{self.p_data_final}_sapt{self.p_sapt}"

    @property
    def export_name(self) -> str:
        return f"{self.p_soc_name}_{self.v_sapt_name}"

    @property
    def export_articole_enabled(self) -> bool:
        return self.articole.strip().lower() == "y"

    @property
    def send_email_enabled(self) -> bool:
        return self.send_email.strip().lower() == "y"

    @property
    def last_month_enabled(self) -> bool:
        return self.last_month.strip().lower() == "y"


def parse_properties(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    with path.open("r", encoding=ENCODING) as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            separator_positions = [pos for pos in (line.find("="), line.find(":")) if pos >= 0]
            if not separator_positions:
                continue
            pos = min(separator_positions)
            values[line[:pos].strip()] = line[pos + 1 :].strip()
    return values


def require_int(values: dict[str, str], key: str) -> int:
    try:
        return int(values[key])
    except KeyError as exc:
        raise ValueError(f"Lipseste cheia obligatorie din properties: {key}") from exc
    except ValueError as exc:
        raise ValueError(f"Cheia {key} trebuie sa fie numar intreg: {values[key]!r}") from exc


def optional_int(values: dict[str, str], key: str, default: int) -> int:
    value = values.get(key, "").strip()
    if value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Cheia {key} trebuie sa fie numar intreg: {value!r}") from exc


def require_str(values: dict[str, str], key: str) -> str:
    try:
        value = values[key]
    except KeyError as exc:
        raise ValueError(f"Lipseste cheia obligatorie din properties: {key}") from exc
    if value == "":
        raise ValueError(f"Cheia {key} nu poate fi goala")
    return value


def optional_str(values: dict[str, str], key: str, default: str = "") -> str:
    return values.get(key, default).strip()


def optional_port(values: dict[str, str], key: str, default: int) -> int:
    return optional_int(values, key, default)


def default_iso_week_params(today: datetime | None = None) -> tuple[int, int, int]:
    current = (today or datetime.now()).date()
    reference = current - timedelta(days=7)
    monday = reference - timedelta(days=reference.isoweekday() - 1)
    sunday = monday + timedelta(days=6)
    iso_week = reference.isocalendar().week
    return iso_week, int(monday.strftime("%Y%m%d")), int(sunday.strftime("%Y%m%d"))


def previous_month_week_params(today: date | datetime | None = None) -> list[tuple[int, int, int]]:
    """Returneaza toate saptamanile L-D care intersecteaza luna precedenta."""
    current = today or datetime.now()
    current_date = current.date() if isinstance(current, datetime) else current
    first_current_month = current_date.replace(day=1)
    last_previous_month = first_current_month - timedelta(days=1)
    first_previous_month = last_previous_month.replace(day=1)

    first_monday = first_previous_month - timedelta(days=first_previous_month.weekday())
    last_sunday = last_previous_month + timedelta(days=6 - last_previous_month.weekday())

    result: list[tuple[int, int, int]] = []
    monday = first_monday
    while monday <= last_sunday:
        sunday = monday + timedelta(days=6)
        result.append(
            (
                monday.isocalendar().week,
                int(monday.strftime("%Y%m%d")),
                int(sunday.strftime("%Y%m%d")),
            )
        )
        monday += timedelta(days=7)
    return result


def load_config(path: Path) -> Config:
    values = parse_properties(path)
    default_sapt, default_data_start, default_data_final = default_iso_week_params()
    last_month = optional_str(values, "last_month", "n")
    if last_month.lower() == "y":
        # Aceste valori vor fi inlocuite pentru fiecare saptamana a lunii precedente.
        # Nu le validam, deoarece last_month=y trebuie sa le ignore complet.
        p_sapt = default_sapt
        p_data_start = default_data_start
        p_data_final = default_data_final
    else:
        p_sapt = optional_int(values, "p_sapt", default_sapt)
        p_data_start = optional_int(values, "p_data_start", default_data_start)
        p_data_final = optional_int(values, "p_data_final", default_data_final)
    return Config(
        oracle_server=require_str(values, "Oracle_Server"),
        oracle_port=require_int(values, "Oracle_Port"),
        oracle_username=require_str(values, "Oracle_Username"),
        oracle_password=require_str(values, "Oracle_Password"),
        oracle_sid=require_str(values, "Oracle_Sid"),
        p_id_societate=require_int(values, "p_id_societate"),
        p_soc_name=require_str(values, "p_soc_name"),
        p_sapt=p_sapt,
        p_id_gestiune_start=require_int(values, "p_id_gestiune_start"),
        p_id_gestiune_final=require_int(values, "p_id_gestiune_final"),
        p_data_start=p_data_start,
        p_data_final=p_data_final,
        last_month=last_month,
        articole=optional_str(values, "articole", "n"),
        send_email=optional_str(values, "send_email", "n"),
        email=optional_str(values, "email"),
        email_cc=optional_str(values, "email_cc"),
        email_method=optional_str(values, "email_method", "auto").lower(),
        smtp_server=optional_str(values, "smtp_server"),
        smtp_port=optional_port(values, "smtp_port", 25),
        smtp_security=optional_str(values, "smtp_security", "none").lower(),
        smtp_username=optional_str(values, "smtp_username"),
        smtp_password_file=optional_str(values, "smtp_password_file"),
        smtp_password_dpapi_file=optional_str(values, "smtp_password_dpapi_file"),
        smtp_from=optional_str(values, "smtp_from"),
        smtp_from_name=optional_str(values, "smtp_from_name"),
    )


def connect_oracle(config: Config):
    try:
        import oracledb
    except ImportError as exc:
        raise RuntimeError(
            "Lipseste modulul Python 'oracledb'. Instaleaza-l cu: pip install oracledb"
        ) from exc

    dsn = oracledb.makedsn(config.oracle_server, config.oracle_port, sid=config.oracle_sid)
    return oracledb.connect(
        user=config.oracle_username,
        password=config.oracle_password,
        dsn=dsn,
    )


def first_column_rows(cursor, query: str, params: dict[str, int]) -> Iterable[str]:
    cursor.execute(query, params)
    for row in cursor:
        if row[0] is not None:
            yield str(row[0])


def write_lines(path: Path, lines: Iterable[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    count = 0
    with path.open("w", encoding=ENCODING, errors="replace", newline="\n") as handle:
        for line in lines:
            handle.write(line)
            handle.write("\n")
            count += 1

    if count == 0 and path.exists():
        path.unlink()
    return count


def export_articole(connection, config: Config, export_dir: Path) -> int:
    path = export_dir / f"ARTICOLE_{config.export_name}.csv"
    query = """
        SELECT * FROM TABLE(PKG_EXPORTURI_NIELSEN.export_articol_perioada(
            :p_id_societate,
            :p_data_start,
            :p_data_final,
            :p_sapt
        ))
    """
    params = {
        "p_id_societate": config.p_id_societate,
        "p_data_start": config.p_data_start,
        "p_data_final": config.p_data_final,
        "p_sapt": config.p_sapt,
    }
    with connection.cursor() as cursor:
        return write_lines(path, first_column_rows(cursor, query, params))


def get_gestiuni(connection, config: Config) -> list[int]:
    query = """
        SELECT * FROM TABLE(PKG_EXPORTURI_NIELSEN.determinare_gestiuni_perioada(
            :p_id_societate,
            :p_id_gestiune_start,
            :p_id_gestiune_final,
            :p_data_start,
            :p_data_final
        ))
    """
    params = {
        "p_id_societate": config.p_id_societate,
        "p_id_gestiune_start": config.p_id_gestiune_start,
        "p_id_gestiune_final": config.p_id_gestiune_final,
        "p_data_start": config.p_data_start,
        "p_data_final": config.p_data_final,
    }
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return [int(row[0]) for row in cursor if row[0] is not None]


def export_vanzari_magazin(connection, config: Config, export_dir: Path, id_gestiune: int) -> int:
    path = export_dir / f"{config.export_name}_id_mag_{id_gestiune}.csv"
    query = """
        SELECT * FROM TABLE(PKG_EXPORTURI_NIELSEN.vanzari_magazine_perioada(
            :v_id_gestiune,
            :p_sapt,
            :p_data_start,
            :p_data_final
        ))
    """
    params = {
        "v_id_gestiune": id_gestiune,
        "p_sapt": config.p_sapt,
        "p_data_start": config.p_data_start,
        "p_data_final": config.p_data_final,
    }
    with connection.cursor() as cursor:
        return write_lines(path, first_column_rows(cursor, query, params))


def archive_export(export_dir: Path, zip_path: Path) -> int:
    if not export_dir.exists():
        raise FileNotFoundError(f"Nu exista folderul de export: {export_dir}")

    files = [path for path in export_dir.iterdir() if path.is_file()]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, arcname=path.name)
    return len(files)


def rename_existing_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(f"{path.stem}_vechi_{timestamp}{path.suffix}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_vechi_{timestamp}_{counter}{path.suffix}")
        counter += 1
    path.rename(candidate)
    return candidate


def append_log(base_dir: Path, job_name: str, message: str = "null") -> None:
    log_path = base_dir / "Log.csv"
    timestamp = datetime.now().strftime(" %d/%m/%Y  %H:%M:%S")
    with log_path.open("a", encoding=ENCODING, errors="replace", newline="") as handle:
        handle.write(f"{timestamp}{job_name} {message} \n")


def split_addresses(value: str) -> list[str]:
    normalized = value.replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def resolve_config_path(raw_path: str, root_dir: Path) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = root_dir / path
    return path


def hide_windows_path(path: Path) -> None:
    if sys.platform != "win32" or not path.exists():
        return
    subprocess.run(
        ["attrib", "+h", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def read_smtp_password(config: Config, root_dir: Path) -> str:
    if config.smtp_password_dpapi_file:
        password_path = resolve_config_path(config.smtp_password_dpapi_file, root_dir)
        hide_windows_path(password_path.parent)
        script = r"""
param([string]$Path)
$secure = Get-Content -LiteralPath $Path | ConvertTo-SecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / "read_smtp_password.ps1"
            script_path.write_text(script, encoding="utf-8")
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    "-Path",
                    str(password_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"Nu am putut decripta parola SMTP DPAPI: {detail}")
        return completed.stdout.rstrip("\r\n")

    if not config.smtp_password_file:
        return ""
    password_path = resolve_config_path(config.smtp_password_file, root_dir)
    try:
        return password_path.read_text(encoding="utf-8").splitlines()[0].strip()
    except IndexError:
        return ""


def send_zip_email_outlook(
    recipients: list[str],
    cc_recipients: list[str],
    subject: str,
    body: str,
    zip_path: Path,
) -> None:
    script = r"""
param(
    [string]$To,
    [string]$Cc,
    [string]$Subject,
    [string]$Body,
    [string]$Attachment
)
$outlook = New-Object -ComObject Outlook.Application
$mail = $outlook.CreateItem(0)
$mail.To = $To
$mail.CC = $Cc
$mail.Subject = $Subject
$mail.Body = $Body
[void]$mail.Attachments.Add($Attachment)
$mail.Send()
"""
    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = Path(temp_dir) / "send_nielsen_email.ps1"
        script_path.write_text(script, encoding="utf-8")
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                "-To",
                "; ".join(recipients),
                "-Cc",
                "; ".join(cc_recipients),
                "-Subject",
                subject,
                "-Body",
                body,
                "-Attachment",
                str(zip_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"Nu am putut trimite email prin Outlook local: {detail}")


def open_outlook365_compose(
    recipients: list[str],
    cc_recipients: list[str],
    subject: str,
    body: str,
    zip_path: Path,
) -> None:
    query = urllib.parse.urlencode(
        {
            "to": ";".join(recipients),
            "cc": ";".join(cc_recipients),
            "subject": subject,
            "body": f"{body}\n\nAtasament de adaugat manual: {zip_path}",
        }
    )
    webbrowser.open(f"https://outlook.office.com/mail/deeplink/compose?{query}")
    raise RuntimeError(
        "Outlook 365 Web a fost deschis, dar nu poate trimite automat atasamentul "
        "folosind doar credentialele salvate in browser. Pentru trimitere automata "
        "foloseste Outlook local clasic sau SMTP/Graph configurat explicit."
    )


def send_zip_email(config: Config, root_dir: Path, zip_path: Path) -> None:
    if not config.send_email_enabled:
        log("Email sarit: send_email nu este y")
        return

    recipients = split_addresses(config.email)
    cc_recipients = split_addresses(config.email_cc)
    if not recipients:
        raise ValueError("send_email=y, dar parametrul email este gol")

    subject = f"Export Nielsen {config.p_soc_name} {config.v_sapt_name}"
    body = (
        f"Buna ziua,\n\n"
        f"Atasat exportul Nielsen pentru {config.p_soc_name}.\n"
        f"Perioada: {config.p_data_start}-{config.p_data_final}, saptamana {config.p_sapt}.\n\n"
        f"Mesaj generat automat."
    )

    message = EmailMessage()
    message["Subject"] = subject
    sender = config.smtp_from or config.smtp_username
    if sender:
        message["From"] = f"{config.smtp_from_name} <{sender}>" if config.smtp_from_name else sender
    message["To"] = ", ".join(recipients)
    if cc_recipients:
        message["Cc"] = ", ".join(cc_recipients)
    message.set_content(body)

    content_type, _ = mimetypes.guess_type(zip_path.name)
    maintype, subtype = (content_type or "application/zip").split("/", 1)
    message.add_attachment(
        zip_path.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=zip_path.name,
    )

    method = config.email_method or "auto"
    if method not in {"auto", "outlook", "outlook365", "smtp"}:
        raise ValueError(f"email_method trebuie sa fie auto, outlook, outlook365 sau smtp. Valoare primita: {config.email_method}")

    if method == "outlook365":
        open_outlook365_compose(recipients, cc_recipients, subject, body, zip_path)

    if method in {"auto", "outlook"}:
        send_zip_email_outlook(recipients, cc_recipients, subject, body, zip_path)
        log(f"Email trimis catre: {', '.join(recipients)}")
        if cc_recipients:
            log(f"Email CC trimis catre: {', '.join(cc_recipients)}")
        return

    if not config.smtp_server:
        raise ValueError("send_email=y prin SMTP, dar smtp_server este gol")

    if not sender:
        raise ValueError("send_email=y prin SMTP, dar smtp_from sau smtp_username este gol")

    password = read_smtp_password(config, root_dir)
    security = config.smtp_security.lower()
    all_recipients = recipients + cc_recipients

    if security == "ssl":
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, timeout=60, context=context) as smtp:
            if config.smtp_username:
                smtp.login(config.smtp_username, password)
            smtp.send_message(message, from_addr=sender, to_addrs=all_recipients)
    else:
        with smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=60) as smtp:
            if security in {"starttls", "tls"}:
                smtp.starttls(context=ssl.create_default_context())
            elif security not in {"none", ""}:
                raise ValueError(f"smtp_security trebuie sa fie ssl, starttls sau none. Valoare primita: {config.smtp_security}")
            if config.smtp_username:
                smtp.login(config.smtp_username, password)
            smtp.send_message(message, from_addr=sender, to_addrs=all_recipients)

    log(f"Email trimis catre: {', '.join(recipients)}")
    if cc_recipients:
        log(f"Email CC trimis catre: {', '.join(cc_recipients)}")


def run_period(config: Config, root_dir: Path) -> Path:
    export_dir = root_dir / config.export_name
    zip_path = root_dir / f"{config.export_name}.zip"

    log(f"Export: {config.export_name}")
    log(f"Folder rezultat: {export_dir}")
    log(f"ZIP rezultat: {zip_path}")
    log("Parametri utilizati:")
    log(f"  Oracle_Server={config.oracle_server}")
    log(f"  Oracle_Port={config.oracle_port}")
    log(f"  Oracle_Username={config.oracle_username}")
    log("  Oracle_Password=***")
    log(f"  Oracle_Sid={config.oracle_sid}")
    log(f"  p_id_societate={config.p_id_societate}")
    log(f"  p_soc_name={config.p_soc_name}")
    log(f"  p_sapt={config.p_sapt}")
    log(f"  p_id_gestiune_start={config.p_id_gestiune_start}")
    log(f"  p_id_gestiune_final={config.p_id_gestiune_final}")
    log(f"  p_data_start={config.p_data_start}")
    log(f"  p_data_final={config.p_data_final}")
    log(f"  last_month={config.last_month or 'n'}")
    log(f"  articole={config.articole}")
    log(f"  send_email={config.send_email or 'n'}")
    log(f"  email={config.email}")
    log(f"  email_cc={config.email_cc}")
    log(f"  email_method={config.email_method or 'auto'}")

    log(f"Conectare Oracle: {config.oracle_server}:{config.oracle_port}/{config.oracle_sid}")
    with connect_oracle(config) as connection:
        log("Conexiune Oracle OK")
        if config.export_articole_enabled:
            log("Generez fisierul ARTICOLE")
            articole_count = export_articole(connection, config, export_dir)
            log(f"ARTICOLE: {articole_count} linii")
        else:
            log("ARTICOLE sarit: articole diferit de y")

        log("Determin lista de gestiuni/magazine")
        gestiuni = get_gestiuni(connection, config)
        log(f"Gestiuni gasite: {len(gestiuni)}")

        for index, id_gestiune in enumerate(gestiuni, start=1):
            log(f"Generez vanzari magazin {index}/{len(gestiuni)}: id_mag={id_gestiune}")
            rows = export_vanzari_magazin(connection, config, export_dir, id_gestiune)
            log(f"id_mag={id_gestiune}: {rows} linii")

    renamed_zip = rename_existing_file(zip_path)
    if renamed_zip is not None:
        log(f"ZIP existent redenumit: {renamed_zip}")

    log("Creez arhiva ZIP")
    archived_files = archive_export(export_dir, zip_path)
    log(f"ZIP creat: {zip_path} ({archived_files} fisiere)")
    try:
        send_zip_email(config, root_dir, zip_path)
    finally:
        if export_dir.exists():
            shutil.rmtree(export_dir)
            log(f"Folder CSV sters: {export_dir}")
    log("Export terminat cu succes")
    return zip_path


def run(properties_path: Path, base_dir: Path | None) -> int:
    log(f"Citesc configuratia: {properties_path}")
    config = load_config(properties_path)
    root_dir = base_dir or properties_path.parent

    if config.last_month_enabled:
        periods = previous_month_week_params()
        log(f"last_month=y: generez {len(periods)} exporturi saptamanale pentru luna precedenta")
        for index, (week, start, final) in enumerate(periods, start=1):
            log(f"Perioada lunara {index}/{len(periods)}: saptamana {week}, {start}-{final}")
            run_period(
                replace(config, p_sapt=week, p_data_start=start, p_data_final=final),
                root_dir,
            )
    else:
        run_period(config, root_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Nielsen in Python, echivalent job Talend.")
    parser.add_argument(
        "--properties",
        type=Path,
        default=DEFAULT_PROPERTIES,
        help="Calea catre jobExportNielsen.properties.",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Folderul in care se creeaza folderul de export, ZIP-ul si Log.csv. Implicit: folderul properties.",
    )
    args = parser.parse_args(argv)

    try:
        return run(args.properties, args.base_dir)
    except Exception as exc:
        effective_base_dir = args.base_dir or args.properties.parent
        try:
            append_log(effective_base_dir, "ExportNielsen", str(exc))
        except Exception:
            pass
        log(f"EROARE: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
