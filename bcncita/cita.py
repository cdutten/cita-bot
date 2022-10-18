import io
import logging
import os
import random
import re
import sys
import tempfile
import time
from base64 import b64decode
from datetime import datetime
from json.decoder import JSONDecodeError
from typing import Dict

import backoff
import requests
from anticaptchaofficial.imagecaptcha import imagecaptcha
from anticaptchaofficial.recaptchav3proxyless import recaptchaV3Proxyless
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait

from constants import DocType
from constants import OperationType
from constants import Province
from constants import CustomerProfile
from constants import Office


class Main:
    # Number of tries
    CYCLES = 144
    REFRESH_PAGE_CYCLES = 12

    DELAY = 30  # timeout for page load

    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.63 Safari/537.36"

    _driver: webdriver
    context: CustomerProfile

    def __init__(self, context: CustomerProfile):
        self.init_webdriver()
        self.context = context

    def init_webdriver(self) -> None:
        """
        Initiating the Chrome web driver with all the needed parameters
        :return:
        """
        options = webdriver.ChromeOptions()

        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--disable-gpu")
        # this parameter tells Chrome that
        # it should be run without UI (Headless)
 #       options.add_argument("--headless")

        driver = webdriver.Chrome(options=options)
        # Overwriting the navigator property to prevent detection of the bot
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": self.USER_AGENT})

        self._driver = driver

    def start_with(self, cycles: int = CYCLES):
        logging.basicConfig(
            format="%(asctime)s - %(message)s", level=logging.INFO, **self.context.log_settings  # type: ignore
        )
        if self.context.sms_webhook_token:
            self.delete_message(self.context.sms_webhook_token)

        operation_category = "icpplus"
        operation_param = "tramiteGrupo[1]"

        if self.context.province == Province.BARCELONA:
            operation_category = "icpplustieb"
            operation_param = "tramiteGrupo[0]"
        elif self.context.province in [
            Province.ALICANTE,
            Province.ILLES_BALEARS,
            Province.LAS_PALMAS,
            Province.S_CRUZ_TENERIFE,
        ]:
            operation_category = "icpco"
        elif self.context.province == Province.MADRID:
            operation_category = "icpplustiem"
        elif self.context.province == Province.MÁLAGA:
            operation_category = "icpco"
            operation_param = "tramiteGrupo[0]"
        elif self.context.province in [
            Province.MELILLA,
            Province.SEVILLA,
        ]:
            operation_param = "tramiteGrupo[0]"

        url = "https://icp.administracionelectronica.gob.es/{}/citar?p={}".format(
            operation_category, self.context.province
        )
        fast_forward_url2 = "https://icp.administracionelectronica.gob.es/{}/acInfo?{}={}".format(
            operation_category, operation_param, self.context.operation_code
        )

        success = False
        result = False
        for i in range(cycles):
            try:
                logging.info(f"\033[33m[Attempt {i + 1}/{cycles}]\033[0m")
                self._driver.set_page_load_timeout(300 if self.context.first_load else 50)

                self.select_province(url)
                self.initial_page(fast_forward_url2)
                result = self.cycle_cita()
            except TimeoutException:
                logging.error("Timeout exception")
            except Exception as e:
                logging.error(f"SMTH BROKEN: {e}")
                continue

            if result:
                success = True
                logging.info("WIN")
                break

        if not success:
            logging.error("FAIL")
            self._driver.quit()

    def toma_huellas_step2(self):
        try:
            WebDriverWait(self._driver, self.DELAY).until(
                expected_conditions.presence_of_element_located((By.ID, "txtPaisNac")))
        except TimeoutException:
            logging.error("Timed out waiting for form to load")
            return None

        # Select country
        select = Select(self._driver.find_element(By.ID, "txtPaisNac"))
        select.select_by_visible_text(self.context.country)

        # Select doc type
        if self.context.doc_type == DocType.PASSPORT:
            self._driver.find_element(By.ID, "rdbTipoDocPas").send_keys(Keys.SPACE)
        elif self.context.doc_type == DocType.NIE:
            self._driver.find_element(By.ID, "rdbTipoDocNie").send_keys(Keys.SPACE)

        # Enter doc number and name
        element = self._driver.find_element(By.ID, "txtIdCitado")
        element.send_keys(self.context.doc_value, Keys.TAB, self.context.name)

        return True

    def recogida_de_tarjeta_step2(self):
        try:
            WebDriverWait(self._driver, self.DELAY).until(
                expected_conditions.presence_of_element_located((By.ID, "txtIdCitado")))
        except TimeoutException:
            logging.error("Timed out waiting for form to load")
            return None

        # Select doc type
        if self.context.doc_type == DocType.PASSPORT:
            self._driver.find_element(By.ID, "rdbTipoDocPas").send_keys(Keys.SPACE)
        elif self.context.doc_type == DocType.NIE:
            self._driver.find_element(By.ID, "rdbTipoDocNie").send_keys(Keys.SPACE)

        # Enter doc number and name
        element = self._driver.find_element(By.ID, "txtIdCitado")
        element.send_keys(self.context.doc_value, Keys.TAB, self.context.name)

        return True

    def solicitud_asilo_step2(self):
        try:
            WebDriverWait(self._driver, self.DELAY).until(
                expected_conditions.presence_of_element_located((By.ID, "txtIdCitado")))
        except TimeoutException:
            logging.error("Timed out waiting for form to load")
            return None

        # Select doc type
        if self.context.doc_type == DocType.PASSPORT:
            self._driver.find_element(By.ID, "rdbTipoDocPas").send_keys(Keys.SPACE)
        elif self.context.doc_type == DocType.NIE:
            self._driver.find_element(By.ID, "rdbTipoDocNie").send_keys(Keys.SPACE)

        # Enter doc number and name
        element = self._driver.find_element(By.ID, "txtIdCitado")
        element.send_keys(self.context.doc_value, Keys.TAB, self.context.name, Keys.TAB, self.context.year_of_birth)

        # Select country
        select = Select(self._driver.find_element(By.ID, "txtPaisNac"))
        select.select_by_visible_text(self.context.country)

        return True

    def brexit_step2(self):
        try:
            WebDriverWait(self._driver, self.DELAY).until(
                expected_conditions.presence_of_element_located((By.ID, "txtIdCitado")))
        except TimeoutException:
            logging.error("Timed out waiting for form to load")
            return None

        # Select doc type
        if self.context.doc_type == DocType.PASSPORT:
            self._driver.find_element(By.ID, "rdbTipoDocPas").send_keys(Keys.SPACE)
        elif self.context.doc_type == DocType.NIE:
            self._driver.find_element(By.ID, "rdbTipoDocNie").send_keys(Keys.SPACE)

        # Enter doc number and name
        element = self._driver.find_element(By.ID, "txtIdCitado")
        element.send_keys(self.context.doc_value, Keys.TAB, self.context.name)

        return True

    def carta_invitacion_step2(self):
        try:
            WebDriverWait(self._driver, self.DELAY).until(
                expected_conditions.presence_of_element_located((By.ID, "txtIdCitado")))
        except TimeoutException:
            logging.error("Timed out waiting for form to load")
            return None

        # Select doc type
        if self.context.doc_type == DocType.PASSPORT:
            self._driver.find_element(By.ID, "rdbTipoDocPas").send_keys(Keys.SPACE)
        elif self.context.doc_type == DocType.DNI:
            self._driver.find_element(By.ID, "rdbTipoDocDni").send_keys(Keys.SPACE)

        # Enter doc number and name
        element = self._driver.find_element(By.ID, "txtIdCitado")
        element.send_keys(self.context.doc_value, Keys.TAB, self.context.name)

        return True

    def certificados_step2(self):
        try:
            WebDriverWait(self._driver, self.DELAY).until(
                expected_conditions.presence_of_element_located((By.ID, "txtIdCitado")))
        except TimeoutException:
            logging.error("Timed out waiting for form to load")
            return None

        # Select doc type
        if self.context.doc_type == DocType.PASSPORT:
            self._driver.find_element(By.ID, "rdbTipoDocPas").send_keys(Keys.SPACE)
        elif self.context.doc_type == DocType.NIE:
            self._driver.find_element(By.ID, "rdbTipoDocNie").send_keys(Keys.SPACE)
        elif self.context.doc_type == DocType.DNI:
            self._driver.find_element(By.ID, "rdbTipoDocDni").send_keys(Keys.SPACE)

        # Enter doc number and name
        element = self._driver.find_element(By.ID, "txtIdCitado")
        element.send_keys(self.context.doc_value, Keys.TAB, self.context.name)

        return True

    def autorizacion_de_regreso_step2(self):
        try:
            WebDriverWait(self._driver, self.DELAY).until(
                expected_conditions.presence_of_element_located((By.ID, "txtIdCitado")))
        except TimeoutException:
            logging.error("Timed out waiting for form to load")
            return None

        # Select doc type
        if self.context.doc_type == DocType.PASSPORT:
            self._driver.find_element(By.ID, "rdbTipoDocPas").send_keys(Keys.SPACE)
        elif self.context.doc_type == DocType.NIE:
            self._driver.find_element(By.ID, "rdbTipoDocNie").send_keys(Keys.SPACE)

        # Enter doc number and name
        element = self._driver.find_element(By.ID, "txtIdCitado")
        element.send_keys(self.context.doc_value, Keys.TAB, self.context.name)

        return True

    def asignacion_nie_step2(self):
        try:
            WebDriverWait(self._driver, self.DELAY).until(
                expected_conditions.presence_of_element_located((By.ID, "txtIdCitado")))
        except TimeoutException:
            logging.error("Timed out waiting for form to load")
            return None

        # Select doc type
        if self.context.doc_type == DocType.PASSPORT:
            option = self._driver.find_element(By.ID, "rdbTipoDocPas")
            if option:
                option.send_keys(Keys.SPACE)

        # Enter doc number, name and year of birth
        element = self._driver.find_element(By.ID, "txtIdCitado")
        element.send_keys(self.context.doc_value, Keys.TAB, self.context.name, Keys.TAB, self.context.year_of_birth)

        # Select country
        select = Select(self._driver.find_element(By.ID, "txtPaisNac"))
        select.select_by_visible_text(self.context.country)

        return True

    def wait_exact_time(self):
        if self.context.wait_exact_time:
            WebDriverWait(self._driver, 1200).until(
                lambda _x: [datetime.now().minute, datetime.now().second] in self.context.wait_exact_time
            )

    def body_text(self):
        try:
            WebDriverWait(self._driver, self.DELAY).until(
                expected_conditions.presence_of_element_located((By.TAG_NAME, "body")))
            return self._driver.find_element(By.TAG_NAME, "body").text
        except TimeoutException:
            logging.info("Timed out waiting for body to load")
            return ""

    def process_captcha(self):
        if self.context.auto_captcha:
            if not self.context.anticaptcha_api_key:
                logging.error("Anticaptcha API key is empty")
                return None

            if len(self._driver.find_elements(By.ID, "reCAPTCHA_site_key")) > 0:
                captcha_result = self.solve_recaptcha()
            elif len(self._driver.find_elements(By.CSS_SELECTOR, "img.img-thumbnail")) > 0:
                captcha_result = self.solve_image_captcha()
            else:
                captcha_result = True

            if not captcha_result:
                return None

        else:
            logging.info(
                "HEY, DO SOMETHING HUMANE TO TRICK THE CAPTCHA (select text, move cursor etc.) and press ENTER"
            )
            input()

        return True

    def solve_recaptcha(self):
        if not self.context.recaptcha_solver:
            site_key = self._driver.find_element(By.ID, "reCAPTCHA_site_key").get_attribute("value")
            page_action = self._driver.find_element(By.ID, "action").get_attribute("value")
            logging.info("Anticaptcha: site key: " + site_key)
            logging.info("Anticaptcha: action: " + page_action)

            self.context.recaptcha_solver = recaptchaV3Proxyless()
            self.context.recaptcha_solver.set_verbose(1)
            self.context.recaptcha_solver.set_key(self.context.anticaptcha_api_key)
            self.context.recaptcha_solver.set_website_url("https://icp.administracionelectronica.gob.es")
            self.context.recaptcha_solver.set_website_key(site_key)
            self.context.recaptcha_solver.set_page_action(page_action)
            self.context.recaptcha_solver.set_min_score(0.9)

        self.context.current_solver = type(self.context.recaptcha_solver)

        g_response = self.context.recaptcha_solver.solve_and_return_solution()
        if g_response != 0:
            logging.info("Anticaptcha: g-response: " + g_response)
            self._driver.execute_script(
                f"document.getElementById('g-recaptcha-response').value = '{g_response}'"
            )
            return True
        else:
            logging.error("Anticaptcha: " + self.context.recaptcha_solver.err_string)
            return None

    def solve_image_captcha(self):
        if not self.context.image_captcha_solver:
            self.context.image_captcha_solver = imagecaptcha()
            self.context.image_captcha_solver.set_verbose(1)
            self.context.image_captcha_solver.set_key(self.context.anticaptcha_api_key)

        self.context.current_solver = type(self.context.image_captcha_solver)
        tmp = tempfile.NamedTemporaryFile(delete=False)
        try:
            img = self._driver.find_elements(By.CSS_SELECTOR, "img.img-thumbnail")[0]
            tmp.write(b64decode(img.get_attribute("src").split(",")[1].strip()))
            tmp.close()

            captcha_result = self.context.image_captcha_solver.solve_and_return_solution(tmp.name)
            if captcha_result != 0:
                logging.info("Anticaptcha: captcha text: " + captcha_result)
                element = self._driver.find_element(By.ID, "captcha")
                element.send_keys(captcha_result)
                return True
            else:
                logging.error("Anticaptcha: " + self.context.image_captcha_solver.err_string)
                return None
        finally:
            os.unlink(tmp.name)

    def find_best_date_slots(self):
        try:
            els = self._driver.find_elements(By.CSS_SELECTOR, "[id^=lCita_]")
            dates = sorted([*map(lambda x: x.text, els)])
            best_date = self.find_best_date(dates)
            if best_date:
                return dates.index(best_date) + 1
        except Exception as e:
            logging.error(e)

        return None

    def find_best_date(self, dates):
        if not self.context.min_date and not self.context.max_date:
            return dates[0]

        pattern = re.compile(r"\d{2}/\d{2}/\d{4}")
        date_format = "%d/%m/%Y"

        for date in dates:
            try:
                found = pattern.findall(date)[0]
                if found:
                    appt_date = datetime.strptime(found, date_format)
                    if self.context.min_date:
                        if appt_date < datetime.strptime(self.context.min_date, date_format):
                            continue
                    if self.context.max_date:
                        if appt_date > datetime.strptime(self.context.max_date, date_format):
                            continue

                    return date
            except Exception as e:
                logging.error(e)
                continue

        logging.info(
            f"Nothing found for dates {self.context.min_date} - {self.context.max_date}, {self.context.min_time} - {self.context.max_time}, skipping"
        )
        return None

    def select_office(self):
        if not self.context.auto_office:
            logging.info("Select office and press ENTER")
            input()
            return True
        else:
            el = self._driver.find_element(By.ID, "idSede")
            select = Select(el)
            if self.context.save_artifacts:
                offices_path = os.path.join(os.getcwd(), f"offices-{datetime.now()}.html".replace(":", "-"))
                with io.open(offices_path, "w", encoding="utf-8") as f:
                    f.write(el.get_attribute("innerHTML"))

            if self.context.offices:
                for office in self.context.offices:
                    try:
                        select.select_by_value(office.value)
                        return True
                    except Exception as e:
                        logging.error(e)
                        if self.context.operation_code == OperationType.RECOGIDA_DE_TARJETA:
                            return None

            for i in range(5):
                options = list(filter(lambda o: o.get_attribute("value") != "", select.options))
                default_count = len(select.options)
                first_element = 0 if len(options) == default_count else 1
                select.select_by_index(random.randint(first_element, default_count - 1))
                if el.get_attribute("value") not in self.context.except_offices:  # type: ignore
                    return True
                continue

            return None

    def office_selection(self):
        self._driver.execute_script("enviar('solicitud');")

        for i in range(self.REFRESH_PAGE_CYCLES):
            resp_text = self.body_text()

            if "Seleccione la oficina donde solicitar la cita" in resp_text:
                logging.info("[Step 2/6] Office selection")

                # Office selection:
                time.sleep(0.3)
                try:
                    WebDriverWait(self._driver, self.DELAY).until(
                        expected_conditions.presence_of_element_located((By.ID, "btnSiguiente"))
                    )
                except TimeoutException:
                    logging.error("Timed out waiting for offices to load")
                    return None

                res = self.select_office()
                if res is None:
                    time.sleep(5)
                    self._driver.refresh()
                    continue

                btn = self._driver.find_element(By.ID, "btnSiguiente")
                btn.send_keys(Keys.ENTER)
                return True
            elif "En este momento no hay citas disponibles" in resp_text:
                time.sleep(5)
                self._driver.refresh()
                continue
            else:
                logging.info("[Step 2/6] Office selection -> No offices")
                return None

    def phone_mail(self):
        try:
            WebDriverWait(self._driver, self.DELAY).until(
                expected_conditions.presence_of_element_located((By.ID, "txtTelefonoCitado"))
            )
            logging.info("[Step 3/6] Contact info")
        except TimeoutException:
            logging.error("Timed out waiting for contact info page to load")
            return None

        element = self._driver.find_element(By.ID, "txtTelefonoCitado")
        element.send_keys(self.context.phone)

        try:
            element = self._driver.find_element(By.ID, "emailUNO")
            element.send_keys(self.context.email)

            element = self._driver.find_element(By.ID, "emailDOS")
            element.send_keys(self.context.email)
        except Exception:
            pass

        self.add_reason()

        self._driver.execute_script("enviar();")

        return self.cita_selection()

    def confirm_appointment(self):
        self._driver.find_element(By.ID, "chkTotal").send_keys(Keys.SPACE)
        self._driver.find_element(By.ID, "enviarCorreo").send_keys(Keys.SPACE)

        btn = self._driver.find_element(By.ID, "btnConfirmar")
        btn.send_keys(Keys.ENTER)

        resp_text = self.body_text()
        ctime = datetime.now()

        if "CITA CONFIRMADA Y GRABADA" in resp_text:
            self.context.bot_result = True
            code = self._driver.find_element(By.ID, "justificanteFinal").text
            logging.info(f"[Step 6/6] Justificante cita: {code}")
            if self.context.save_artifacts:
                image_name = f"CONFIRMED-CITA-{ctime}.png".replace(":", "-")
                self._driver.save_screenshot(image_name)
                # TODO: fix saving to PDF
                # btn = driver.find_element(By.ID, "btnImprimir")
                # btn.send_keys(Keys.ENTER)
                # # Give some time to save appointment pdf
                # time.sleep(5)

            return True
        elif "Lo sentimos, el código introducido no es correcto" in resp_text:
            logging.error("Incorrect code entered")
        else:
            error_name = f"error-{ctime}.png".replace(":", "-")
            self._driver.save_screenshot(error_name)

        return None

    @staticmethod
    def log_backoff(details):
        logging.error(f"Unable to load the initial page, backing off {details['wait']:0.1f} seconds")

    @backoff.on_exception(
        backoff.constant,
        TimeoutException,
        interval=350,
        max_tries=(10 if os.environ.get("CITA_TEST") else None),
        on_backoff=log_backoff,
        logger=None,
    )
    def initial_page(self, fast_forward_url2):
        self._driver.get(fast_forward_url2)

        WebDriverWait(self._driver, 10).until(
            expected_conditions.text_to_be_present_in_element_value((By.ID, "prov_selecc"), "Barcelona")
        )
        self.context.first_load = False

    def cycle_cita(self):
        # 1. Instructions page:
        try:
            WebDriverWait(self._driver, self.DELAY).until(
                expected_conditions.presence_of_element_located((By.ID, "btnEntrar")))
        except TimeoutException:
            logging.error("Timed out waiting for Instructions page to load")
            return None

        if os.environ.get("CITA_TEST") and self.context.operation_code == OperationType.TOMA_HUELLAS:
            logging.info("Instructions page loaded")
            return True

        self._driver.find_element(By.ID, "btnEntrar").send_keys(Keys.ENTER)

        # 2. Personal info:
        logging.info("[Step 1/6] Personal info")
        success = False
        if self.context.operation_code == OperationType.TOMA_HUELLAS:
            success = self.toma_huellas_step2()
        elif self.context.operation_code == OperationType.RECOGIDA_DE_TARJETA:
            success = self.recogida_de_tarjeta_step2()
        elif self.context.operation_code == OperationType.SOLICITUD_ASILO:
            success = self.solicitud_asilo_step2()
        elif self.context.operation_code == OperationType.BREXIT:
            success = self.brexit_step2()
        elif self.context.operation_code == OperationType.CARTA_INVITACION:
            success = self.carta_invitacion_step2()
        elif self.context.operation_code in [
            OperationType.CERTIFICADOS_NIE,
            OperationType.CERTIFICADOS_NIE_NO_COMUN,
            OperationType.CERTIFICADOS_RESIDENCIA,
            OperationType.CERTIFICADOS_UE,
        ]:
            success = self.certificados_step2()
        elif self.context.operation_code == OperationType.AUTORIZACION_DE_REGRESO:
            success = self.autorizacion_de_regreso_step2()
        elif self.context.operation_code == OperationType.ASIGNACION_NIE:
            success = self.asignacion_nie_step2()

        if not success:
            return None

        time.sleep(2)
        self._driver.find_element(By.ID, "btnEnviar").send_keys(Keys.ENTER)

        try:
            WebDriverWait(self._driver, 7).until(
                expected_conditions.presence_of_element_located((By.ID, "btnConsultar")))
        except TimeoutException:
            logging.error("Timed out waiting for Solicitar page to load")

        try:
            self.wait_exact_time()
        except TimeoutException:
            logging.error("Timed out waiting for exact time")
            return None

        # 3. Solicitar cita:
        selection_result = self.office_selection()
        if selection_result is None:
            return None

        # 4. Contact info:
        return self.phone_mail()

    def cita_selection(self):
        """
        # 5. Cita selection

        :return:
        """
        resp_text = self.body_text()

        if "DISPONE DE 5 MINUTOS" in resp_text:
            logging.info("[Step 4/6] Cita attempt -> selection hit!")
            if self.context.save_artifacts:
                self._driver.save_screenshot(f"citas-{datetime.now()}.png".replace(":", "-"))

            position = self.find_best_date_slots()
            if not position:
                return None

            time.sleep(2)
            success = self.process_captcha()
            if not success:
                return None

            try:
                self._driver.find_elements(By.CSS_SELECTOR, "input[type='radio'][name='rdbCita']")[
                    position - 1
                    ].send_keys(Keys.SPACE)
            except Exception as e:
                logging.error(e)
                pass

            self._driver.execute_script("envia();")
            time.sleep(0.5)
            self._driver.switch_to.alert.accept()
        elif "Seleccione una de las siguientes citas disponibles" in resp_text:
            logging.info("[Step 4/6] Cita attempt -> selection hit!")
            if self.context.save_artifacts:
                self._driver.save_screenshot(f"citas-{datetime.now()}.png".replace(":", "-"))

            try:
                date_els = self._driver.find_elements(
                    By.CSS_SELECTOR, "#CitaMAP_HORAS thead [class^=colFecha]"
                )
                dates = sorted([*map(lambda x: x.text, date_els)])
                slots: Dict[str, list] = {}
                slot_table = self._driver.find_element(By.CSS_SELECTOR, "#CitaMAP_HORAS tbody")
                for row in slot_table.find_elements(By.CSS_SELECTOR, "tr"):
                    appt_time = row.find_elements(By.TAG_NAME, "th")[0].text
                    if self.context.min_time:
                        if appt_time < self.context.min_time:
                            continue
                    if self.context.max_time:
                        if appt_time > self.context.max_time:
                            break

                    for idx, cell in enumerate(row.find_elements(By.TAG_NAME, "td")):
                        try:
                            if slots.get(dates[idx]):
                                continue
                            slot = cell.find_element(By.CSS_SELECTOR, "[id^=HUECO]").get_attribute(
                                "id"
                            )
                            slots[dates[idx]] = [slot]
                        except Exception:
                            # TODO: This could be covering errors
                            pass

                best_date = self.find_best_date(sorted(slots))
                if not best_date:
                    return None
                slot = slots[best_date][0]

                time.sleep(2)
                success = self.process_captcha()
                if not success:
                    return None

                self._driver.execute_script(f"confirmarHueco({{id: '{slot}'}}, {slot[5:]});")
                self._driver.switch_to.alert.accept()
            except Exception as e:
                logging.error(e)
                return None
        else:
            logging.info("[Step 4/6] Cita attempt -> missed selection")
            return None

        # 6. Confirmation
        resp_text = self.body_text()

        if "Debe confirmar los datos de la cita asignada" in resp_text:
            logging.info("[Step 5/6] Cita attempt -> confirmation hit!")
            if self.context.current_solver == recaptchaV3Proxyless:
                self.context.recaptcha_solver.report_correct_recaptcha()

            try:
                sms_verification = self._driver.find_element(By.ID, "txtCodigoVerificacion")
            except Exception as e:
                logging.error(e)
                sms_verification = None
                pass

            if self.context.sms_webhook_token:
                if sms_verification:
                    code = self.get_code()
                    if code:
                        logging.info(f"Received code: {code}")
                        sms_verification = self._driver.find_element(By.ID, "txtCodigoVerificacion")
                        sms_verification.send_keys(code)

                self.confirm_appointment()

                if self.context.save_artifacts:
                    self._driver.save_screenshot(f"FINAL-SCREEN-{datetime.now()}.png".replace(":", "-"))

                if self.context.bot_result:
                    self._driver.quit()
                    sys.exit(0)
                return None
            else:
                if not sms_verification:
                    self.confirm_appointment()

                logging.info("Press Any button to CLOSE browser")
                input()
                self._driver.quit()
                sys.exit(0)

        else:
            logging.info("[Step 5/6] Cita attempt -> missed confirmation")
            if self.context.current_solver == recaptchaV3Proxyless:
                self.context.recaptcha_solver.report_incorrect_recaptcha()
            elif self.context.current_solver == imagecaptcha:
                self.context.image_captcha_solver.report_incorrect_image_captcha()

            if self.context.save_artifacts:
                self._driver.save_screenshot(f"failed-confirmation-{datetime.now()}.png".replace(":", "-"))
            return None

    @staticmethod
    def get_messages(sms_webhook_token):
        try:
            url = f"https://webhook.site/token/{sms_webhook_token}/requests?page=1&sorting=newest"
            return requests.get(url).json()["data"]
        except JSONDecodeError:
            raise Exception("sms_webhook_token is incorrect")

    @staticmethod
    def delete_message(sms_webhook_token, message_id=""):
        url = f"https://webhook.site/token/{sms_webhook_token}/request/{message_id}"
        requests.delete(url)

    def get_code(self):
        for i in range(60):
            messages = self.get_messages(self.context.sms_webhook_token)
            if not messages:
                time.sleep(5)
                continue

            content = messages[0].get("text_content")
            match = re.search("CODIGO (.*), DE", content)
            if match:
                self.delete_message(self.context.sms_webhook_token, messages[0].get("uuid"))
                return match.group(1)

        return None

    def add_reason(self):
        try:
            if self.context.operation_code == OperationType.SOLICITUD_ASILO:
                element = self._driver.find_element(By.ID, "txtObservaciones")
                element.send_keys(self.context.reason_or_type)
        except Exception as e:
            logging.error(e)

    def select_province(self, url):
        if self.context.first_load:
            self._driver.delete_all_cookies()

        self._driver.get(url)
        try:
            WebDriverWait(self._driver, 5).until(
                expected_conditions.title_is("Proceso automático para la solicitud de cita previa")
            )
        finally:
            self._driver.quit()


if __name__ == '__main__':
    # Execute when the module is not initialized from an import statement.
    customer = CustomerProfile(
        auto_captcha=False,
        # Enable anti-captcha plugin (if False, you have to solve reCaptcha manually and press ENTER in the Terminal)
        auto_office=True,
        save_artifacts=True,  # Record available offices / take available slots screenshot
        province=Province.BARCELONA,
        operation_code=OperationType.RECOGIDA_DE_TARJETA,
        doc_type=DocType.NIE,  # DocType.NIE or DocType.PASSPORT
        doc_value="T1111111R",  # NIE or Passport number, no spaces.
        country="RUSIA",
        name="BORIS JOHNSON",  # Your Name
        phone="600000000",  # Phone number (use this format, please)
        email="myemail@here.com",  # Email
        # Offices in order of preference
        # This selects specified offices one by one or a random one if not found.
        # For recogida only the first specified office will be attempted or none
        offices=[Office.BARCELONA_MALLORCA],
    )
    main = Main(customer)
    main.start_with()
