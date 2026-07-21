import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from export_nielsen import load_config, previous_month_week_params


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


if __name__ == "__main__":
    unittest.main()
