import unittest
from datetime import datetime

from miabis_model import Biobank
from miabis_model import Collection
from miabis_model import Condition
from miabis_model import Gender
from miabis_model import Sample
from miabis_model import SampleDonor
from miabis_model import StorageTemperature
from miabis_model.util.config import FHIRConfig

ADMINISTRATIVE_GENDER_SYSTEM = "http://hl7.org/fhir/administrative-gender"


def collect_coding_systems(element, systems):
    if isinstance(element, dict):
        for coding in element.get("coding", []) if isinstance(element.get("coding"), list) else []:
            systems.append(coding.get("system"))
        for value in element.values():
            collect_coding_systems(value, systems)
    elif isinstance(element, list):
        for item in element:
            collect_coding_systems(item, systems)
    return systems


def build_sample():
    return Sample(identifier="sampleId", donor_identifier="donorId", material_type="Serum",
                  storage_temperature=StorageTemperature.TEMPERATURE_ROOM,
                  collected_datetime=datetime(year=2022, month=10, day=5))


def build_biobank():
    return Biobank("biobankId", "biobankName", "CZ", "contactName", "contactSurname",
                   "contact@email.com", "juristicPerson", "description",
                   infrastructural_capabilities=["SampleStorage"],
                   organisational_capabilities=["RecontactDonors"],
                   bioprocessing_and_analysis_capabilities=["SampleProcessing"])


def build_collection():
    return Collection(identifier="collectionId", name="collectionName", managing_biobank_id="biobankId",
                      contact_name="contactName", contact_surname="contactSurname",
                      contact_email="contact@email.com", country="CZ", genders=[Gender.FEMALE],
                      description="description", material_types=["Serum"], number_of_subjects=1)


class TestEmittedCodingSystems(unittest.TestCase):
    def test_sample_type_coding_system_is_code_system(self):
        specimen = build_sample().to_fhir("donorFhirId", "collectionId").as_json()
        self.assertEqual(FHIRConfig.get_code_system_url("sample", "detailed_sample_type"),
                         specimen["type"]["coding"][0]["system"])

    def test_storage_temperature_coding_system_is_code_system(self):
        specimen = build_sample().to_fhir("donorFhirId", "collectionId").as_json()
        temperature_coding = specimen["processing"][0]["extension"][0]["valueCodeableConcept"]["coding"][0]
        self.assertEqual(FHIRConfig.get_code_system_url("sample", "storage_temperature"),
                         temperature_coding["system"])

    def test_donor_dataset_type_coding_system_is_code_system(self):
        donor = SampleDonor("donorId", Gender.FEMALE, dataset_type="Lifestyle").to_fhir().as_json()
        dataset_type_coding = donor["extension"][0]["valueCodeableConcept"]["coding"][0]
        self.assertEqual(FHIRConfig.get_code_system_url("donor", "dataset_type"),
                         dataset_type_coding["system"])

    def test_biobank_organisational_capability_coding_has_system(self):
        organization = build_biobank().to_fhir("juristicPersonFhirId").as_json()
        capability_extension_url = FHIRConfig.get_extension_url("biobank", "organisational_capabilities")
        capability_codings = [extension["valueCodeableConcept"]["coding"][0]
                              for extension in organization["extension"]
                              if extension["url"] == capability_extension_url]
        self.assertTrue(capability_codings)
        for coding in capability_codings:
            self.assertEqual(FHIRConfig.get_code_system_url("biobank", "organisational_capabilities"),
                             coding["system"])

    def test_collection_gender_coding_system_is_not_prefixed_with_base_url(self):
        group = build_collection().to_fhir("collectionOrganizationFhirId").as_json()
        gender_codings = [coding
                          for characteristic in group["characteristic"]
                          for coding in characteristic.get("valueCodeableConcept", {}).get("coding", [])
                          if coding.get("code") in Gender.list()
                          or coding.get("code") in [gender.name.lower() for gender in Gender]]
        self.assertTrue(gender_codings)
        for coding in gender_codings:
            self.assertEqual(ADMINISTRATIVE_GENDER_SYSTEM, coding["system"])

    def test_no_emitted_coding_system_points_at_a_value_set(self):
        resources = [build_sample().to_fhir("donorFhirId", "collectionId").as_json(),
                     build_biobank().to_fhir("juristicPersonFhirId").as_json(),
                     build_collection().to_fhir("collectionOrganizationFhirId").as_json(),
                     SampleDonor("donorId", Gender.FEMALE, dataset_type="Lifestyle").to_fhir().as_json()]
        for resource in resources:
            for system in collect_coding_systems(resource, []):
                self.assertIsNotNone(system)
                self.assertNotIn("/ValueSet/", system)

    def test_no_emitted_coding_system_is_a_concatenation_of_two_urls(self):
        resources = [build_sample().to_fhir("donorFhirId", "collectionId").as_json(),
                     build_biobank().to_fhir("juristicPersonFhirId").as_json(),
                     build_collection().to_fhir("collectionOrganizationFhirId").as_json()]
        for resource in resources:
            for system in collect_coding_systems(resource, []):
                self.assertEqual(1, system.count("http"))


class TestEmittedInvariants(unittest.TestCase):
    def test_condition_does_not_emit_an_empty_stage(self):
        condition = Condition("donorId", "C50.9").to_fhir("donorFhirId").as_json()
        self.assertNotIn("stage", condition)


if __name__ == "__main__":
    unittest.main()
