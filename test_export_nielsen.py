import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from export_nielsen import RunLock, archive_export, load_config, previous_month_week_params, run_period


class PreviousMonthWeekParamsTests(unittest.TestCase):
    def test_month_aligned_to_monday_and_extended_at_end(self):
        self.assertEqual(
            previous_month_week_params(date(2026, 7, 21)),
            [
                (23, 20260601, 20260607),
                (24, 20260608, 20260614),
                (25, 20260615, 20260621),
                (26, 20260622, 20260628),
                (27, 20260629, 20260705),
            ],
        )

    def test_month_is_extended_at_both_ends_across_year_boundary(self):
        self.assertEqual(
            previous_month_week_params(date(2026, 1, 15)),
            [
                (49, 20251201, 20251207),
                (50, 20251208, 20251214),
                (51, 20251215, 20251221),
                (52, 20251222, 20251228),
                (1, 20251229, 20260104),
            ],
        )

    def test_month_starting_midweek_includes_previous_month_days(self):
        self.assertEqual(
            previous_month_week_params(date(2026, 6, 10))[0],
            (18, 20260427, 20260503),
        )

    def test_last_month_ignores_invalid_manual_period(self):
        properties = """\
Oracle_Server=db
Oracle_Port=1521
Oracle_Username=user
Oracle_Password=password
Oracle_Sid=sid
p_id_societate=1
p_soc_name=TEST
p_sapt=invalid
p_id_gestiune_start=1
p_id_gestiune_final=999
p_data_start=invalid
p_data_final=invalid
last_month=Y
"""
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "jobExportNielsen.properties"
            path.write_text(properties, encoding="iso-8859-15")
            config = load_config(path)

        self.assertTrue(config.last_month_enabled)

    def test_temporary_export_directory_is_removed_after_database_error(self):
        properties = """\
Oracle_Server=db
Oracle_Port=1521
Oracle_Username=user
Oracle_Password=password
Oracle_Sid=sid
p_id_societate=1
p_soc_name=TEST
p_sapt=1
p_id_gestiune_start=1
p_id_gestiune_final=999
p_data_start=20251229
p_data_final=20260104
articole=y
"""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "jobExportNielsen.properties"
            path.write_text(properties, encoding="iso-8859-15")
            config = load_config(path)

            with patch("export_nielsen.connect_oracle", side_effect=RuntimeError("DB indisponibila")):
                with self.assertRaisesRegex(RuntimeError, "DB indisponibila"):
                    run_period(config, root)

            self.assertEqual(list(root.glob(".export_nielsen_*")), [])

    def test_empty_export_is_rejected_without_creating_zip(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            export_dir = root / "empty"
            export_dir.mkdir()
            zip_path = root / "result.zip"

            with self.assertRaisesRegex(RuntimeError, "niciun fisier"):
                archive_export(export_dir, zip_path)

            self.assertFalse(zip_path.exists())

    def test_second_simultaneous_run_is_rejected(self):
        with TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / ".export_nielsen.lock"
            with RunLock(lock_path):
                with self.assertRaisesRegex(RuntimeError, "deja un export"):
                    with RunLock(lock_path):
                        pass


if __name__ == "__main__":
    unittest.main()
