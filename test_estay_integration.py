"""Headless integration tests for the embedded NRA stay-declaration generator."""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from nap_stay import eStayGen as stay


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class StayIntegrationTests(unittest.TestCase):
    def test_location_catalogues_from_original_excel_files(self):
        self.assertTrue(stay.DOMAIN_DICT)
        self.assertTrue(stay.MUNICIPALITY_DICT)
        self.assertTrue(stay.CITY_DICT)
        for name in ("domain.xlsx", "municipality.xlsx", "city.xlsx"):
            self.assertTrue(os.path.isfile(stay.resource_path("data/" + name)))

    def test_original_xml_generator_preserves_declaration_fields(self):
        source = """<root>
            <declarationReference><ukn_eADD>00001234</ukn_eADD></declarationReference>
            <fuel><fuelAmount>1250.50</fuelAmount><fuelKNCode>27102011</fuelKNCode></fuel>
            <transport>
              <storage><type>other_no_ESFP</type></storage>
              <transporter><bgCompany><eik>001234567</eik></bgCompany></transporter>
              <transportation><tugcistern>CA1234AB</tugcistern></transportation>
            </transport>
            <receiverPerson><bgPerson>
              <egn>0012345678</egn><firstName>Иван</firstName><lastName>Иванов</lastName>
            </bgPerson></receiverPerson>
        </root>"""
        with tempfile.TemporaryDirectory() as directory:
            source_path = os.path.join(directory, "edp.xml")
            target_path = os.path.join(directory, "stay.xml")
            with open(source_path, "w", encoding="utf-8") as file:
                file.write(source)
            with (
                patch.object(stay, "date_entry", Value("09.10.2026"), create=True),
                patch.object(stay, "region_code_var", Value("SOF"), create=True),
                patch.object(stay, "municipality_code_var", Value("SOF46"), create=True),
                patch.object(stay, "city_code_var", Value("68134"), create=True),
                patch.object(stay, "address_entry", Value("ул. Примерна"), create=True),
                patch.object(stay, "number_entry", Value("12"), create=True),
            ):
                result = stay.convert_xml(source_path, target_path)
            self.assertEqual(result, target_path)
            root = ET.parse(target_path).getroot()
            expected = {
                "declarationReference/ukn_eADD": "00001234",
                "declarationReference/date": "09.10.2026",
                "fuel/fuelAmount": "1250.50",
                "fuel/fuelKNCode": "27102011",
                "transport/location/domain": "SOF",
                "transport/location/municipality": "SOF46",
                "transport/location/city": "68134",
                "transport/storage/address": "ул. Примерна",
                "transport/storage/addressNumber": "12",
                "transport/transporter/bgCompany/eik": "001234567",
                "transport/transportation/tugcistern": "CA1234AB",
                "transport/transportation/drivers/bgPerson/egn": "0012345678",
                "deliverPerson/bgPerson/firstName": "Иван",
                "receiverPerson/bgPerson/lastName": "Иванов",
            }
            self.assertEqual(root.tag, "stayTransportDeclaration")
            for key, value in expected.items():
                with self.subTest(xpath=key):
                    self.assertEqual(root.findtext(key), value)

    def test_migrate_existing_saved_addresses(self):
        with tempfile.TemporaryDirectory() as folder:
            legacy = os.path.join(folder, "saved_addresses.json")
            with open(legacy, "w", encoding="utf-8") as file:
                file.write('[{"company": "Transport One"}]')
            with patch("nap_stay.eStayGen.os.getcwd", return_value=folder):
                with patch.dict(os.environ, {"LOCALAPPDATA": os.path.join(folder, "new_storage")}):
                    target = stay.saved_addresses_path()
            with open(target, encoding="utf-8") as file:
                self.assertIn("Transport One", file.read())


if __name__ == "__main__":
    unittest.main()
