from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


ENCODING = "iso-8859-15"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


DEFAULT_PROPERTIES = app_dir() / "jobExportNielsen.properties"


@dataclass(frozen=True)
class Config:
    oracle_server: str
    oracle_port: int
    oracle_username: str
    oracle_password: str
    oracle_sid: str
    oracle_connect_timeout: int
    oracle_call_timeout: int
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
            positions = [pos for pos in (line.find("="), line.find(":")) if pos >= 0]
            if positions:
                pos = min(positions)
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
    if not value:
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
    if not value:
        raise ValueError(f"Cheia {key} nu poate fi goala")
    return value


def optional_str(values: dict[str, str], key: str, default: str = "") -> str:
    return values.get(key, default).strip()


def optional_positive_int(values: dict[str, str], key: str, default: int) -> int:
    value = optional_int(values, key, default)
    if value <= 0:
        raise ValueError(f"Cheia {key} trebuie sa fie mai mare decat zero: {value!r}")
    return value


def default_iso_week_params(today: datetime | None = None) -> tuple[int, int, int]:
    current = (today or datetime.now()).date()
    reference = current - timedelta(days=7)
    monday = reference - timedelta(days=reference.isoweekday() - 1)
    sunday = monday + timedelta(days=6)
    return reference.isocalendar().week, int(monday.strftime("%Y%m%d")), int(sunday.strftime("%Y%m%d"))


def previous_month_week_params(today: date | datetime | None = None) -> list[tuple[int, int, int]]:
    current = today or datetime.now()
    current_date = current.date() if isinstance(current, datetime) else current
    first_current_month = current_date.replace(day=1)
    last_previous_month = first_current_month - timedelta(days=1)
    first_previous_month = last_previous_month.replace(day=1)
    monday = first_previous_month - timedelta(days=first_previous_month.weekday())
    last_sunday = last_previous_month + timedelta(days=6 - last_previous_month.weekday())

    result: list[tuple[int, int, int]] = []
    while monday <= last_sunday:
        sunday = monday + timedelta(days=6)
        result.append((monday.isocalendar().week, int(monday.strftime("%Y%m%d")), int(sunday.strftime("%Y%m%d"))))
        monday += timedelta(days=7)
    return result


def parse_yyyymmdd(value: str) -> date | None:
    value = value.strip()
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def load_config(path: Path) -> Config:
    values = parse_properties(path)
    default_sapt, default_start, default_final = default_iso_week_params()
    last_month = optional_str(values, "last_month", "n")
    if last_month.lower() == "y":
        p_sapt, p_data_start, p_data_final = default_sapt, default_start, default_final
    else:
        start_date = parse_yyyymmdd(values.get("p_data_start", ""))
        final_date = parse_yyyymmdd(values.get("p_data_final", ""))
        if start_date is None or final_date is None or start_date > final_date:
            p_sapt, p_data_start, p_data_final = default_sapt, default_start, default_final
        else:
            p_data_start = int(start_date.strftime("%Y%m%d"))
            p_data_final = int(final_date.strftime("%Y%m%d"))
            configured_week = values.get("p_sapt", "").strip()
            try:
                parsed_week = int(configured_week)
            except ValueError:
                parsed_week = 0
            p_sapt = parsed_week if 1 <= parsed_week <= 53 else start_date.isocalendar().week

    return Config(
        oracle_server=require_str(values, "Oracle_Server"),
        oracle_port=require_int(values, "Oracle_Port"),
        oracle_username=require_str(values, "Oracle_Username"),
        oracle_password=require_str(values, "Oracle_Password"),
        oracle_sid=require_str(values, "Oracle_Sid"),
        oracle_connect_timeout=optional_positive_int(values, "oracle_connect_timeout", 30),
        oracle_call_timeout=optional_positive_int(values, "oracle_call_timeout", 1800),
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
        smtp_port=optional_positive_int(values, "smtp_port", 25),
        smtp_security=optional_str(values, "smtp_security", "none").lower(),
        smtp_username=optional_str(values, "smtp_username"),
        smtp_password_file=optional_str(values, "smtp_password_file"),
        smtp_password_dpapi_file=optional_str(values, "smtp_password_dpapi_file"),
        smtp_from=optional_str(values, "smtp_from"),
        smtp_from_name=optional_str(values, "smtp_from_name"),
    )
