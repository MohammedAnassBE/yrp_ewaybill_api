# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

"""Regression tests for the e-Waybill print-format image helpers."""

import base64
import unittest

from yrp_ewaybill_api.ewaybill.jinja import get_ewaybill_barcode, get_qr_code


class TestEwaybillJinjaHelpers(unittest.TestCase):
	def test_qr_code_renders_png(self):
		image = base64.b64decode(get_qr_code("331234567890"))
		self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))

	def test_barcode_renders_png(self):
		image = base64.b64decode(get_ewaybill_barcode("331234567890"))
		self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))
