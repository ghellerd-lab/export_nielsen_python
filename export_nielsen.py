from __future__ import annotations

import argparse
import tempfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from nielsen_config import Config, DEFAULT_PROPERTIES, load_config, previous_month_week_params
from nielsen_email import send_zip_email
from nielsen_files import RunLock, append_log, archive_export, rename_existing_file
from nielsen_oracle import connect_oracle, export_articole, export_vanzari_magazin, get_gestiuni


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def run_period(config: Config, root_dir: Path) -> Path:
    zip_path = root_dir / f"{config.export_name}.zip"
    with tempfile.TemporaryDirectory(prefix=".export_nielsen_", dir=root_dir) as temp_dir:
        export_dir = Path(temp_dir)
        log(f"Export: {config.export_name}")
        log(f"Folder temporar: {export_dir}")
        log(f"ZIP rezultat: {zip_path}")
        log("Parametri utilizati:")
        log(f"  Oracle_Server={config.oracle_server}")
        log(f"  Oracle_Port={config.oracle_port}")
        log(f"  Oracle_Username={config.oracle_username}")
        log("  Oracle_Password=***")
        log(f"  Oracle_Sid={config.oracle_sid}")
        log(f"  oracle_connect_timeout={config.oracle_connect_timeout}")
        log(f"  oracle_call_timeout={config.oracle_call_timeout}")
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
                log(f"ARTICOLE: {export_articole(connection, config, export_dir)} linii")
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
        send_zip_email(config, root_dir, zip_path, log)

    log(f"Folder temporar sters: {export_dir}")
    log("Export terminat cu succes")
    return zip_path


def run(properties_path: Path, base_dir: Path | None) -> int:
    log(f"Citesc configuratia: {properties_path}")
    config = load_config(properties_path)
    root_dir = base_dir or properties_path.parent
    with RunLock(root_dir / ".export_nielsen.lock"):
        if config.last_month_enabled:
            periods = previous_month_week_params()
            log(f"last_month=y: generez {len(periods)} exporturi saptamanale pentru luna precedenta")
            for index, (week, start, final) in enumerate(periods, start=1):
                log(f"Perioada lunara {index}/{len(periods)}: saptamana {week}, {start}-{final}")
                run_period(replace(config, p_sapt=week, p_data_start=start, p_data_final=final), root_dir)
        else:
            run_period(config, root_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Nielsen in Python, echivalent job Talend.")
    parser.add_argument("--self-test-imports", action="store_true",
                        help="Verifica dependentele incluse in executabil si iese.")
    parser.add_argument("--properties", type=Path, default=DEFAULT_PROPERTIES,
                        help="Calea catre jobExportNielsen.properties.")
    parser.add_argument("--base-dir", type=Path, default=None,
                        help="Folderul in care se creeaza ZIP-ul si Log.csv. Implicit: folderul properties.")
    args = parser.parse_args(argv)
    if args.self_test_imports:
        import cryptography
        import oracledb

        log(f"Self-test importuri OK: oracledb={oracledb.__version__}, cryptography={cryptography.__version__}")
        return 0
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
