import os
import sys

from bcncita import CustomerProfile, try_cita
from bcncita.constants.doc_type import DocType
from bcncita.constants.office import Office
from bcncita.constants.operation_type import OperationType
from bcncita.constants.province import Province

if __name__ == "__main__":
    customer = CustomerProfile(
        anticaptcha_api_key="... your key here ...",
        auto_captcha=False,
        auto_office=True,
        chrome_driver_path="/usr/local/bin/chromedriver",
        save_artifacts=True,
        province=Province.BARCELONA,
        operation_code=OperationType.TOMA_HUELLAS,
        doc_type=DocType.PASSPORT,
        doc_value="1100123123",
        country="RUSIA",
        name="BORIS JOHNSON",
        phone="600000000",
        email="myemail@here.com",
        offices=[Office.BARCELONA, Office.MATARO],
    )
    if "--autofill" not in sys.argv:
        try_cita(context=customer, cycles=200)  # Try 200 times
    else:
        from mako.template import Template

        tpl = Template(
            filename=os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "bcncita/template/autofill.mako"
            )
        )
        print(tpl.render(ctx=customer))  # Autofill for Chrome


# In Terminal run:
#   python3 example2.py
# or:
#   python3 example2.py --autofill
