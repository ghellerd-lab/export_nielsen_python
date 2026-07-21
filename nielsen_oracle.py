from __future__ import annotations

from pathlib import Path
from typing import Iterable

from nielsen_config import Config, ENCODING


def connect_oracle(config: Config):
    try:
        import oracledb
    except ImportError as exc:
        raise RuntimeError("Lipseste modulul Python 'oracledb'. Instaleaza-l cu: pip install oracledb") from exc

    connection = oracledb.connect(
        user=config.oracle_username,
        password=config.oracle_password,
        host=config.oracle_server,
        port=config.oracle_port,
        sid=config.oracle_sid,
        tcp_connect_timeout=config.oracle_connect_timeout,
    )
    connection.call_timeout = config.oracle_call_timeout * 1000
    return connection


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
    query = """SELECT * FROM TABLE(PKG_EXPORTURI_NIELSEN.export_articol_perioada(
        :p_id_societate, :p_data_start, :p_data_final, :p_sapt))"""
    params = {"p_id_societate": config.p_id_societate, "p_data_start": config.p_data_start,
              "p_data_final": config.p_data_final, "p_sapt": config.p_sapt}
    with connection.cursor() as cursor:
        return write_lines(path, first_column_rows(cursor, query, params))


def get_gestiuni(connection, config: Config) -> list[int]:
    query = """SELECT * FROM TABLE(PKG_EXPORTURI_NIELSEN.determinare_gestiuni_perioada(
        :p_id_societate, :p_id_gestiune_start, :p_id_gestiune_final, :p_data_start, :p_data_final))"""
    params = {"p_id_societate": config.p_id_societate, "p_id_gestiune_start": config.p_id_gestiune_start,
              "p_id_gestiune_final": config.p_id_gestiune_final, "p_data_start": config.p_data_start,
              "p_data_final": config.p_data_final}
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return [int(row[0]) for row in cursor if row[0] is not None]


def export_vanzari_magazin(connection, config: Config, export_dir: Path, id_gestiune: int) -> int:
    path = export_dir / f"{config.export_name}_id_mag_{id_gestiune}.csv"
    query = """SELECT * FROM TABLE(PKG_EXPORTURI_NIELSEN.vanzari_magazine_perioada(
        :v_id_gestiune, :p_sapt, :p_data_start, :p_data_final))"""
    params = {"v_id_gestiune": id_gestiune, "p_sapt": config.p_sapt,
              "p_data_start": config.p_data_start, "p_data_final": config.p_data_final}
    with connection.cursor() as cursor:
        return write_lines(path, first_column_rows(cursor, query, params))
