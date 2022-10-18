import logging
import os
import unittest

from bcncita import Main
from constants import DocType
from constants import Office
from constants import OperationType
from constants import Province
from constants import CustomerProfile


class TestBot(unittest.TestCase):
    def test_cita(self):
        params = {
            "auto_office": True,
            "auto_captcha": True,
            "name": "BORIS JOHNSON",
            "doc_type": DocType.PASSPORT,
            "doc_value": "132435465",
            "phone": "600000000",
            "email": "ghtvgdr@affecting.org",
        }

        customer = CustomerProfile(
            **params,
            province=Province.BARCELONA,
            operation_code=OperationType.BREXIT,
            offices=[Office.BARCELONA],
        )

        main = Main(customer)

        with self.assertLogs(None, level=logging.INFO) as logs:
            main.start_with(cycles=1)

        self.assertIn("INFO:root:\x1b[33m[Attempt 1/1]\x1b[0m", logs.output)
        self.assertIn("INFO:root:[Step 1/6] Personal info", logs.output)
        self.assertIn("INFO:root:[Step 2/6] Office selection", logs.output)
        self.assertIn("INFO:root:[Step 3/6] Contact info", logs.output)
        self.assertIn("INFO:root:[Step 4/6] Cita attempt -> selection hit!", logs.output)

    def test_select_province_given_barcelona_as_province(self):
        params = {
            "auto_office": True,
            "auto_captcha": True,
            "name": "BORIS JOHNSON",
            "doc_type": DocType.PASSPORT,
            "doc_value": "132435465",
            "phone": "600000000",
            "email": "ghtvgdr@affecting.org",
        }

        customer = CustomerProfile(
            **params,
            province=Province.BARCELONA,
            operation_code=OperationType.BREXIT,
            offices=[Office.BARCELONA],
        )

        operation_category = "icpplustieb"

        url = "https://icp.administracionelectronica.gob.es/{}/citar?p={}".format(
            operation_category, customer.province
        )

        main = Main(customer)
        main.select_province(url)

    def test_inital_page_given_barcelona_as_province(self):
        params = {
            "auto_office": True,
            "auto_captcha": True,
            "name": "BORIS JOHNSON",
            "doc_type": DocType.PASSPORT,
            "doc_value": "132435465",
            "phone": "600000000",
            "email": "ghtvgdr@affecting.org",
        }

        customer = CustomerProfile(
            **params,
            province=Province.BARCELONA,
            operation_code=OperationType.BREXIT,
            offices=[Office.BARCELONA],
        )

        operation_category = "icpplustieb"
        operation_param = "tramiteGrupo[0]"

        url = "https://icp.administracionelectronica.gob.es/{}/acInfo?{}={}".format(
            operation_category, operation_param, customer.operation_code
        )

        main = Main(customer)
        main.initial_page(url)
        main._driver.quit()


if __name__ == "__main__":
    if not os.environ.get("CITA_TEST"):
        os._exit(0)
    unittest.main()
