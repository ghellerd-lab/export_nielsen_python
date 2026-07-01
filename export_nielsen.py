from __future__ import annotations

import argparse
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


DEFAULT_PROPERTIES = Path(__file__).resolve().with_name("jobExportNielsen.properties")
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

    @property
    def v_sapt_name(self) -> str:
        return f"{self.p_data_start}-{self.p_data_final}_sapt{self.p_sapt}"

    @property
    def export_name(self) -> str:
        return f"{self.p_soc_name}_{self.v_sapt_name}"


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


def require_str(values: dict[str, str], key: str) -> str:
    try:
        value = values[key]
    except KeyError as exc:
        raise ValueError(f"Lipseste cheia obligatorie din properties: {key}") from exc
    if value == "":
        raise ValueError(f"Cheia {key} nu poate fi goala")
    return value


def load_config(path: Path) -> Config:
    values = parse_properties(path)
    return Config(
        oracle_server=require_str(values, "Oracle_Server"),
        oracle_port=require_int(values, "Oracle_Port"),
        oracle_username=require_str(values, "Oracle_Username"),
        oracle_password=require_str(values, "Oracle_Password"),
        oracle_sid=require_str(values, "Oracle_Sid"),
        p_id_societate=require_int(values, "p_id_societate"),
        p_soc_name=require_str(values, "p_soc_name"),
        p_sapt=require_int(values, "p_sapt"),
        p_id_gestiune_start=require_int(values, "p_id_gestiune_start"),
        p_id_gestiune_final=require_int(values, "p_id_gestiune_final"),
        p_data_start=require_int(values, "p_data_start"),
        p_data_final=require_int(values, "p_data_final"),
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
    if zip_path.exists():
        zip_path.unlink()

    files = [path for path in export_dir.iterdir() if path.is_file()]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, arcname=path.name)
    return len(files)


def append_log(base_dir: Path, job_name: str, message: str = "null") -> None:
    log_path = base_dir / "Log.csv"
    timestamp = datetime.now().strftime(" %d/%m/%Y  %H:%M:%S")
    with log_path.open("a", encoding=ENCODING, errors="replace", newline="") as handle:
        handle.write(f"{timestamp}{job_name} {message} \n")


def run(properties_path: Path, base_dir: Path | None) -> int:
    log(f"Citesc configuratia: {properties_path}")
    config = load_config(properties_path)
    root_dir = base_dir or properties_path.parent
    export_dir = root_dir / config.export_name
    zip_path = root_dir / f"{config.export_name}.zip"

    log(f"Export: {config.export_name}")
    log(f"Folder rezultat: {export_dir}")
    log(f"ZIP rezultat: {zip_path}")

    log(f"Conectare Oracle: {config.oracle_server}:{config.oracle_port}/{config.oracle_sid}")
    with connect_oracle(config) as connection:
        log("Conexiune Oracle OK")
        log("Generez fisierul ARTICOLE")
        articole_count = export_articole(connection, config, export_dir)
        log(f"ARTICOLE: {articole_count} linii")

        log("Determin lista de gestiuni/magazine")
        gestiuni = get_gestiuni(connection, config)
        log(f"Gestiuni gasite: {len(gestiuni)}")

        for index, id_gestiune in enumerate(gestiuni, start=1):
            log(f"Generez vanzari magazin {index}/{len(gestiuni)}: id_mag={id_gestiune}")
            rows = export_vanzari_magazin(connection, config, export_dir, id_gestiune)
            log(f"id_mag={id_gestiune}: {rows} linii")

    log("Creez arhiva ZIP")
    archived_files = archive_export(export_dir, zip_path)
    append_log(root_dir, "ExportNielsen")
    log(f"ZIP creat: {zip_path} ({archived_files} fisiere)")
    log("Export terminat cu succes")
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
