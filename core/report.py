"""Unified JSON diagnostic report generator conforming to schemas/diagnostic_report.json."""

import sys
import netcoop.core.report

# Ensure module singleton identity across core.report and netcoop.core.report
sys.modules[__name__] = netcoop.core.report
