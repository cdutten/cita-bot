from dataclasses import dataclass, field
from constants import DocType
from constants import Province
from constants import OperationType
from typing import Any, Optional
import sys


@dataclass
class CustomerProfile:
    name: str
    doc_type: DocType
    doc_value: str  # Passport? "123123123"; Nie? "Y1111111M"
    phone: str
    email: str
    province: Province = Province.BARCELONA
    operation_code: OperationType = OperationType.TOMA_HUELLAS
    country: str = "RUSIA"
    year_of_birth: Optional[str] = None
    offices: Optional[list] = field(default_factory=list)
    except_offices: Optional[list] = field(default_factory=list)

    anticaptcha_api_key: Optional[str] = None
    auto_captcha: bool = True
    auto_office: bool = True
    chrome_profile_name: Optional[str] = None
    chrome_profile_path: Optional[str] = None
    min_date: Optional[str] = None  # "dd/mm/yyyy"
    max_date: Optional[str] = None  # "dd/mm/yyyy"
    min_time: Optional[str] = None  # "hh:mm"
    max_time: Optional[str] = None  # "hh:mm"
    save_artifacts: bool = False
    sms_webhook_token: Optional[str] = None
    wait_exact_time: Optional[list] = None  # [[minute, second]]
    reason_or_type: str = "solicitud de asilo"

    # Internals
    bot_result: bool = False
    first_load: Optional[bool] = True  # Wait more on the first load to cache stuff
    log_settings: Optional[dict] = field(default_factory=lambda: {"stream": sys.stdout})
    recaptcha_solver: Any = None
    image_captcha_solver: Any = None
    current_solver: Any = None

    def __post_init__(self):
        if self.operation_code == OperationType.RECOGIDA_DE_TARJETA:
            assert len(self.offices) == 1, "Indicate the office where you need to pick up the card"