import datetime
import unittest

import pytest as pytest
import requests.exceptions
from requests.exceptions import HTTPError

from blaze_client import NonExistentResourceException
from blaze_client.blaze_client import BlazeClient
from miabis_model import Biobank
from miabis_model import Collection
from miabis_model import Condition
from miabis_model import Gender
from miabis_model import Network
from miabis_model import Sample
from miabis_model import SampleDonor
from miabis_model import StorageTemperature
from miabis_model import _NetworkOrganization
from miabis_model.collection_organization import _CollectionOrganization
from miabis_model.observation import _Observation
from miabis_model.util.parsing_util import get_nested_value, parse_reference_id


class TestBlazeService(unittest.TestCase):
    example_donor = SampleDonor("donorId", Gender.MALE, datetime.datetime(year=2015, month=10, day=20), "Other")
    example_samples = [Sample("sampleId", "donorId", "Urine", datetime.datetime(year=2001, month=10, day=20),
                              storage_temperature=StorageTemperature.TEMPERATURE_LN, diagnoses_with_observed_datetime=[
            ("C50", datetime.datetime(year=2022, month=10, day=20)),
            ("C51", datetime.datetime(year=2021, month=10, day=20))], sample_collection_id="collectionId"),
                       Sample("sampleId2", "donorId", "Nail", datetime.datetime(year=2020, month=11, day=21),
                              storage_temperature=StorageTemperature.TEMPERATURE_ROOM,
                              diagnoses_with_observed_datetime=[
                                  ("C50", datetime.datetime(year=2020, month=10, day=20)),
                                  ("C45", datetime.datetime(year=2019, month=10, day=20))],
                              sample_collection_id="collectionId")
                       ]
    example_observations = [_Observation("C50", "sampleId", "donorId", datetime.datetime(year=2022, month=10, day=20)),
                            _Observation("C51", "sampleId", "donorId", datetime.datetime(year=2022, month=10, day=20)),
                            _Observation("C50", "sampleId2", "donorId", datetime.datetime(year=2020, month=11, day=21)),
                            _Observation("C45", "sampleId2", "donorId", datetime.datetime(year=2020, month=11, day=21))]

    example_condition = Condition("donorId")

    example_biobank = Biobank("biobankId", "biobankName", "CZ", "ContactName", "ContactSurname",
                              "email", "juristic_person", "description", infrastructural_capabilities=["SampleStorage"],
                              organisational_capabilities=["RecontactDonors"],
                              bioprocessing_and_analysis_capabilities=["Genomics"])

    example_collection = Collection(identifier="collectionId", name="collectionName", managing_biobank_id="biobankId",
                                    contact_name="contactName", contact_surname="contactSurname",
                                    contact_email="contactEmail", country="cz", genders=[Gender.MALE],
                                    material_types=["Urine"], inclusion_criteria=["Sex"],
                                    alias="collectionAlias", url="urlExample.com", description="description",
                                    dataset_type="LifeStyle", sample_source="Human",
                                    sample_collection_setting="Environment", collection_design=["CaseControl"],
                                    use_and_access_conditions=["CommercialUse"], publications=["publication"])

    example_network = Network(identifier="networkId", name="networkName", contact_email="contactEmail", country="cz",
                              juristic_person="juristicPerson",
                              members_collections_ids=["collectionId"],
                              members_biobanks_ids=["biobankId"], contact_name="contactName",
                              contact_surname="contactSurname", common_collaboration_topics=["Charter"],
                              description="description")

    example_collection_org = _CollectionOrganization("collectionId", "collectionOrgName", "biobankId", "contactName",
                                                     "contactSurname", "contactEmail", "cz", "alias", "url",
                                                     "description",
                                                     "LifeStyle", "Human", "Environment", ["CaseControl"],
                                                     ["CommercialUse"], ["publication"])

    example_network_org = _NetworkOrganization(identifier="networkId", name="networkName", contact_email="contactEmail",
                                               contact_surname="contactSurname", contact_name="contactName",
                                               country="cz", common_collaboration_topics=["Charter"],
                                               juristic_person="juristicPerson", description="description")

    @pytest.fixture(autouse=True)
    def run_around_tests(self):
        self.blaze_service = BlazeClient("http://localhost:8080/fhir", "", "")
        yield
        try:
            pass
            donor_fhir_id = self.blaze_service.get_fhir_id("Patient", self.example_donor.identifier)
            if donor_fhir_id is not None:
                if not self.blaze_service.delete_donor(donor_fhir_id):
                    raise Exception("could not delete patient")
            for sample in self.example_samples:
                sample_fhir_id = self.blaze_service.get_fhir_id("Specimen", sample.identifier)
                if sample_fhir_id is not None:
                    self.blaze_service.delete_sample(sample_fhir_id)
            biobank_fhir_id = self.blaze_service.get_fhir_id("Organization", self.example_biobank.identifier)
            if biobank_fhir_id is not None:
                if not self.blaze_service.delete_biobank(biobank_fhir_id):
                    raise Exception("could not delete biobank")
            collection_org_fhir_id = self.blaze_service.get_fhir_id("Organization",
                                                                    self.example_collection_org.identifier)
            if collection_org_fhir_id is not None:
                if not self.blaze_service._delete_collection_organization(collection_org_fhir_id):
                    raise Exception("could not delete collection organization")
            network_org_fhir_id = self.blaze_service.get_fhir_id("Organization", self.example_network_org.identifier)
            if network_org_fhir_id is not None:
                if not self.blaze_service._delete_network_organization(network_org_fhir_id):
                    raise Exception("could not delete network organization")
        except NonExistentResourceException:
            pass

    def test_upload_sample_chain(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        self.assertTrue(self.blaze_service.is_resource_present_in_blaze("Specimen", sample_fhir_id))
        self.assertIsNotNone(self.blaze_service._get_observation_fhir_ids_belonging_to_sample(sample_fhir_id))

    def test_get_resource_by_search_parameter(self):
        self.blaze_service.upload_donor(self.example_donor)
        self.blaze_service.upload_sample(self.example_samples[0])
        self.blaze_service.upload_sample(self.example_samples[1])
        samples = self.blaze_service.get_resource_by_search_parameter("Specimen", "sample-collection-id",
                                                                      "collectionId")
        self.assertTrue(len(samples["entry"]))

    def test_is_resource_present_in_blaze_true(self):
        donor_fhir_id = self.blaze_service.upload_donor(self.example_donor)
        self.assertTrue(self.blaze_service.is_resource_present_in_blaze("Patient", donor_fhir_id))

    def test_blaze_service_unreachable_raises_httpError(self):
        blaze_service = BlazeClient("https://badUrl", "", "")
        with self.assertRaises(requests.exceptions.ConnectionError):
            blaze_service.upload_donor(self.example_donor)

    def test_is_resource_present_in_blaze_false(self):
        self.assertFalse(self.blaze_service.is_resource_present_in_blaze("Patient", "nonexistentId"))

    def test_is_resource_present_in_blaze_with_search_param_true(self):
        self.blaze_service.upload_donor(self.example_donor)
        self.assertTrue(
            self.blaze_service.is_resource_present_in_blaze("Patient", self.example_donor.identifier, "identifier"))

    def test_is_resource_present_in_blaze_with_search_param_false(self):
        self.assertFalse(
            self.blaze_service.is_resource_present_in_blaze("Patient", "nonexistentIdentifier", "identifier"))

    def test_get_fhir_resource_as_json_existing(self):
        donor_fhir_id = self.blaze_service.upload_donor(self.example_donor)
        donor_json = self.blaze_service.get_fhir_resource_as_json("Patient", donor_fhir_id)
        self.assertIsNotNone(donor_json)

    def test_get_fhir_resource_as_json_non_existing(self):
        non_existing_json = self.blaze_service.get_fhir_resource_as_json("Patient", "nonexistentId")
        self.assertIsNone(non_existing_json)

    def test_get_fhir_id_existing(self):
        donor_fhir_id = self.blaze_service.upload_donor(self.example_donor)
        donor_fhir_id_from_function = self.blaze_service.get_fhir_id("Patient", self.example_donor.identifier)
        self.assertEqual(donor_fhir_id, donor_fhir_id_from_function)

    def test_get_fhir_id_non_existing(self):
        non_existent_fhir_id = self.blaze_service.get_fhir_id("Patient", "nonexistentId")
        self.assertIsNone(non_existent_fhir_id)

    def test_get_identifier_by_fhir_id_existing(self):
        donor_fhir_id = self.blaze_service.upload_donor(self.example_donor)
        donor_identifier = self.blaze_service.get_identifier_by_fhir_id("Patient", donor_fhir_id)
        self.assertEqual(self.example_donor.identifier, donor_identifier)

    def test_get_identifier_by_fhir_id_non_existing(self):
        donor_identifier = self.blaze_service.get_identifier_by_fhir_id("Patient", "NonexistentId")
        self.assertIsNone(donor_identifier)

    def test_upload_donor(self):
        donor_id = self.blaze_service.upload_donor(self.example_donor)
        self.assertIsNotNone(donor_id)

    def test_update_donor(self):
        donor_id = self.blaze_service.upload_donor(self.example_donor)
        different_patient = SampleDonor("donorId", Gender.FEMALE, datetime.datetime(year=2015, month=10, day=20),
                                        "Other")
        updated_fhir_id = self.blaze_service.update_donor(different_patient)
        updated_patient = self.blaze_service.build_donor_from_json(updated_fhir_id)
        self.assertEqual(updated_patient.gender, different_patient.gender)

    def test_donor_from_json(self):
        donor_id = self.blaze_service.upload_donor(self.example_donor)
        donor = self.blaze_service.build_donor_from_json(donor_id)
        self.assertEqual(donor.identifier, self.example_donor.identifier)
        self.assertEqual(donor.gender, self.example_donor.gender)
        self.assertEqual(donor.date_of_birth, self.example_donor.date_of_birth)
        self.assertEqual(donor.dataset_type, self.example_donor.dataset_type)
        self.assertEqual(donor.donor_fhir_id, donor_id)

    def test_donor_from_json_nonexistent_id_raises_nonexistent_exception(self):
        donor_id = self.blaze_service.upload_donor(self.example_donor)
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service.build_donor_from_json("nonexistentId")

    def test_update_donor_private(self):
        donor_id = self.blaze_service.upload_donor(self.example_donor)
        self.assertIsNotNone(donor_id)
        updated_donor = SampleDonor("new_donor_identifier", Gender.MALE, datetime.datetime(year=2022, month=10, day=20),
                                    "Other")
        updated_donor._donor_fhir_id = donor_id
        updated_donor_fhir = updated_donor.to_fhir()
        updated_donor_fhir = updated_donor.add_fhir_id_to_donor(updated_donor_fhir)
        updated_bool = self.blaze_service._update_fhir_resource("Patient", donor_id, updated_donor_fhir.as_json())
        self.assertTrue(updated_bool)
        updated_donor_resource = self.blaze_service.build_donor_from_json(donor_id)
        self.assertEqual(updated_donor.identifier, updated_donor_resource.identifier)
        self.blaze_service.delete_donor(donor_id)

    def test_delete_donor(self):
        donor_fhir_id = self.blaze_service.upload_donor(self.example_donor)
        deleted = self.blaze_service.delete_donor(donor_fhir_id)
        self.assertTrue(deleted)

    def test_delete_donor_with_nonexistent_id_raises_nonexistent_exception(self):
        donor_fhir_id = self.blaze_service.upload_donor(self.example_donor)
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service.delete_donor("nonexistentId")

    def test_upload_sample(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        sample_fhir_id2 = self.blaze_service.upload_sample(self.example_samples[1])
        self.assertTrue(self.blaze_service.is_resource_present_in_blaze("Specimen", sample_fhir_id))
        self.assertTrue(self.blaze_service.is_resource_present_in_blaze("Specimen", sample_fhir_id2))
        self.assertIsNotNone(sample_fhir_id)

    def test_upload_sample_with_nonexistent_donor_raises_exception(self):
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service.upload_sample(self.example_samples[0])

    def test_build_sample_from_json(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        build_sample = self.blaze_service.build_sample_from_json(sample_fhir_id)
        self.assertEqual(build_sample.identifier, self.example_samples[0].identifier)
        self.assertEqual(build_sample.donor_identifier, self.example_samples[0].donor_identifier)
        self.assertEqual(build_sample.sample_fhir_id, sample_fhir_id)
        self.assertEqual(build_sample.material_type, self.example_samples[0].material_type)
        self.assertEqual(build_sample.storage_temperature, self.example_samples[0].storage_temperature)
        self.assertEqual(build_sample.collected_datetime, self.example_samples[0].collected_datetime)

    def test_build_sample_from_json_nonexistent_id_raises_nonexistent_exception(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        with self.assertRaises(NonExistentResourceException):
            build_sample = self.blaze_service.build_sample_from_json("nonexistentId")

    def test_update_sample_only_material_type_different(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        different_sample = Sample("sampleId", "donorId", "Serum", datetime.datetime(year=2001, month=10, day=20),
                                  storage_temperature=StorageTemperature.TEMPERATURE_LN,
                                  diagnoses_with_observed_datetime=[
                                      ("C50", datetime.datetime(year=2022, month=10, day=20)),
                                      ("C51", datetime.datetime(year=2021, month=10, day=20))],
                                  sample_collection_id="collection_id")
        updated = self.blaze_service.update_sample(different_sample)
        self.assertTrue(updated)
        updated_sample = self.blaze_service.build_sample_from_json(sample_fhir_id)
        self.assertEqual(updated_sample.material_type, different_sample.material_type)
        self.blaze_service.delete_sample(sample_fhir_id)

    def test_update_sample_different_observation(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        different_sample = Sample("sampleId", "donorId", "Urine", datetime.datetime(year=2001, month=10, day=20),
                                  storage_temperature=StorageTemperature.TEMPERATURE_LN,
                                  diagnoses_with_observed_datetime=[
                                      ("C52", datetime.datetime(year=2020, month=10, day=20)),
                                      ("C51", datetime.datetime(year=2021, month=10, day=20))],
                                  sample_collection_id="collection_id")
        updated = self.blaze_service.update_sample(different_sample)
        self.assertTrue(updated)
        updated_sample = self.blaze_service.build_sample_from_json(sample_fhir_id)
        for diagnosis_with_datetime in updated_sample.diagnoses_icd10_code_with_observed_datetime:
            self.assertIn(diagnosis_with_datetime, different_sample.diagnoses_icd10_code_with_observed_datetime)
        self.blaze_service.delete_sample(sample_fhir_id)

    def test_update_sample(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        update_sample = self.blaze_service.build_sample_from_json(sample_fhir_id)
        update_sample.identifier = "new_sample_id"
        update_sample_fhir = update_sample.add_fhir_id_to_fhir_representation(update_sample.to_fhir())
        updated = self.blaze_service._update_fhir_resource("Specimen", sample_fhir_id, update_sample_fhir.as_json())
        updated_resource = self.blaze_service.build_sample_from_json(sample_fhir_id)
        self.assertTrue(updated)
        self.assertEqual(updated_resource.identifier, update_sample.identifier)
        self.blaze_service.delete_sample(sample_fhir_id)

    def test_update_sample_with_bad_json_resource_raises_http_error(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        with self.assertRaises(HTTPError):
            self.blaze_service._update_fhir_resource("Specimen", sample_fhir_id, self.example_donor.to_fhir().as_json())

    def test_delete_sample(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        deleted = self.blaze_service.delete_sample(sample_fhir_id)
        self.assertFalse(self.blaze_service.is_resource_present_in_blaze("Specimen", "sampleId", "identifier"))
        self.assertTrue(deleted)

    def test_delete_nonexistent_sample_raises_exception(self):
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service.delete_sample("nonexistendId")

    def test_upload_observation(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        observation_fhir_ids = self.blaze_service._get_observation_fhir_ids_belonging_to_sample(sample_fhir_id)
        self.assertIsNotNone(observation_fhir_ids)

    def test_upload_observation_with_nonexistent_sample_riases_nonexistentresource_exception(self):
        self.blaze_service.upload_donor(self.example_donor)
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service._upload_observation(self.example_observations[0])

    def test_upload_observation_with_nonexistent_donor_riases_nonexistentresource_exception(self):
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service._upload_observation(self.example_observations[0])

    def test_build_observation_from_json(self):
        donor_fhir_id = self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        obs_fhir_id1 = self.blaze_service._upload_observation(self.example_observations[0])
        build_observation = self.blaze_service._build_observation_from_json(obs_fhir_id1)
        self.assertEqual(build_observation.observation_fhir_id, obs_fhir_id1)
        self.assertEqual(build_observation.sample_fhir_id, sample_fhir_id)
        self.assertEqual(build_observation.patient_fhir_id, donor_fhir_id)
        self.assertEqual(build_observation.diagnosis_observed_datetime,
                         self.example_observations[0].diagnosis_observed_datetime)
        self.assertEqual(build_observation.icd10_code, self.example_observations[0].icd10_code)

    def test_build_observation_from_json_nonexistent_fhir_id_raises_nonexistent_exception(self):
        donor_fhir_id = self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        obs_fhir_id1 = self.blaze_service._upload_observation(self.example_observations[0])
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service._build_observation_from_json("nonexistentId")

    def test_update_observation(self):
        self.blaze_service.upload_donor(self.example_donor)
        self.blaze_service.upload_sample(self.example_samples[0])
        obs_fhir_id1 = self.blaze_service._upload_observation(self.example_observations[0])
        update_observation = self.blaze_service._build_observation_from_json(obs_fhir_id1)
        update_observation.icd10_code = "C34"
        update_observation_fhir = update_observation.add_fhir_id_to_observation(update_observation.to_fhir())
        updated = self.blaze_service._update_fhir_resource("Observation", obs_fhir_id1,
                                                           update_observation_fhir.as_json())
        self.assertTrue(updated)
        updated_observation = self.blaze_service._build_observation_from_json(obs_fhir_id1)
        self.assertEqual(updated_observation.icd10_code, update_observation.icd10_code)
        self.blaze_service._delete_observation(obs_fhir_id1)

    def test_delete_observation(self):
        self.blaze_service.upload_donor(self.example_donor)
        self.blaze_service.upload_sample(self.example_samples[0])
        observation_fhir_id = self.blaze_service._upload_observation(self.example_observations[0])
        deleted = self.blaze_service._delete_observation(observation_fhir_id)
        self.assertTrue(deleted)
        self.assertFalse(self.blaze_service.is_resource_present_in_blaze("Observation", observation_fhir_id))

    def test_delete_observation_with_nonexistent_fhir_id_raises_nonexistent_exception(self):
        self.blaze_service.upload_donor(self.example_donor)
        self.blaze_service.upload_sample(self.example_samples[0])
        observation_fhir_id = self.blaze_service._upload_observation(self.example_observations[0])
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service._delete_observation("nonexistentId")

    def test_upload_condition(self):
        self.blaze_service.upload_donor(self.example_donor)
        condition_fhir_id = self.blaze_service.upload_condition(self.example_condition)
        self.assertIsNotNone(condition_fhir_id)

    def test_upload_condition_with_nonexistent_donor_raises_nonexistent_exception(self):
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service.upload_condition(self.example_condition)

    def test_get_condition_by_patient_fhir_id_ok(self):
        donor_fhir_id = self.blaze_service.upload_donor(self.example_donor)
        condition_fhir_id = self.blaze_service.upload_condition(self.example_condition)
        self.assertEqual(condition_fhir_id, self.blaze_service.get_condition_by_patient_fhir_id(donor_fhir_id))

    def test_get_condition_by_patient_fhir_id_false(self):
        donor_fhir_id = self.blaze_service.upload_donor(self.example_donor)
        condition_fhir_id = self.blaze_service.upload_condition(self.example_condition)
        self.assertIsNone(self.blaze_service.get_condition_by_patient_fhir_id("nonexistentId"))

    def test_build_condition_from_json(self):
        donor_id = self.blaze_service.upload_donor(self.example_donor)
        condition_fhir_id = self.blaze_service.upload_condition(self.example_condition)
        self.assertIsNotNone(condition_fhir_id)
        build_condition = self.blaze_service.build_condition_from_json(condition_fhir_id)
        self.assertEqual(build_condition.condition_fhir_id, condition_fhir_id)
        self.assertEqual(build_condition.patient_fhir_id, donor_id)

    def test_build_condition_from_json_with_nonexistent_fhir_id_raises_nonexistent_exception(self):
        self.blaze_service.upload_donor(self.example_donor)
        self.blaze_service.upload_condition(self.example_condition)
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service.build_condition_from_json("nonexistentId")

    def test_update_condition(self):
        self.blaze_service.upload_donor(self.example_donor)
        condition_fhir_id = self.blaze_service.upload_condition(self.example_condition)
        self.assertIsNotNone(condition_fhir_id)
        update_condition = self.blaze_service.build_condition_from_json(condition_fhir_id)
        update_condition.icd_10_code = "C51"
        update_condition_fhir = update_condition.add_fhir_id_to_condition(update_condition.to_fhir())
        updated = self.blaze_service._update_fhir_resource("Condition", condition_fhir_id,
                                                           update_condition_fhir.as_json())
        self.assertTrue(updated)
        updated_condition = self.blaze_service.build_condition_from_json(condition_fhir_id)
        self.assertEqual(update_condition.icd_10_code, updated_condition.icd_10_code)
        self.blaze_service.delete_condition(condition_fhir_id)

    def test_delete_condition_with_no_diagnosis_reports(self):
        self.blaze_service.upload_donor(self.example_donor)
        self.blaze_service.upload_sample(self.example_samples[0])
        condition_fhir_id = self.blaze_service.upload_condition(self.example_condition)
        deleted = self.blaze_service.delete_condition(condition_fhir_id)
        self.assertTrue(deleted)
        self.assertFalse(self.blaze_service.is_resource_present_in_blaze("Condition", condition_fhir_id))

    def test_delete_condition_with_nonexistent_fhir_id_raises_noexistent_exception(self):
        self.blaze_service.upload_donor(self.example_donor)
        self.blaze_service.upload_sample(self.example_samples[0])
        self.blaze_service.upload_condition(self.example_condition)
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service.delete_condition("nonexistendId")

    def test_get_observation_fhir_ids_belonging_to_sample(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        obs_fhir_id1 = self.blaze_service._upload_observation(self.example_observations[0])
        obs_fhir_id2 = self.blaze_service._upload_observation(self.example_observations[1])
        obs_fhir_ids = self.blaze_service._get_observation_fhir_ids_belonging_to_sample(sample_fhir_id)
        self.assertTrue(len(obs_fhir_ids) != 0)
        self.assertIn(obs_fhir_id1, obs_fhir_ids)
        self.assertIn(obs_fhir_id2, obs_fhir_ids)

    def test_upload_donor_and_sample_full_chain(self):
        donor_fhir_id = self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_ids = []
        for sample in self.example_samples:
            sample_fhir_ids.append(self.blaze_service.upload_sample(sample))
        condition_fhir_id = self.blaze_service.upload_condition(self.example_condition)
        observation_fhir_ids = []
        for sample_fhir_id in sample_fhir_ids:
            self.assertIsNotNone(sample_fhir_id)
            observation_fhir_ids.extend(
                self.blaze_service._get_observation_fhir_ids_belonging_to_sample(sample_fhir_id))
        self.assertIsNotNone(donor_fhir_id)
        self.assertIsNotNone(observation_fhir_ids)
        self.assertEqual(4, len(observation_fhir_ids))
        self.assertIsNotNone(condition_fhir_id)
        observations_for_first_sample = self.blaze_service._get_observation_fhir_ids_belonging_to_sample(
            sample_fhir_ids[0])
        observations_for_second_sample = self.blaze_service._get_observation_fhir_ids_belonging_to_sample(
            sample_fhir_ids[1])
        for obs_sample_1 in observations_for_first_sample:
            self.assertIn(obs_sample_1, observation_fhir_ids)
        for obs_sample_2 in observations_for_second_sample:
            self.assertIn(obs_sample_2, observation_fhir_ids)

    def test_upload_biobank(self):
        biobank_fhir_id = self.blaze_service.upload_biobank(self.example_biobank)
        self.assertIsNotNone(biobank_fhir_id)
        self.assertTrue(self.blaze_service.is_resource_present_in_blaze("Organization", biobank_fhir_id))

    def test_update_biobank(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        different_biobank = Biobank("biobankId", "DifferentName", "CZ", "ContactName", "ContactSurname",
                                    "email", "juristic_person", "description",
                                    infrastructural_capabilities=["SampleStorage"],
                                    organisational_capabilities=["RecontactDonors"],
                                    bioprocessing_and_analysis_capabilities=["Genomics"])
        updated_fhir_id = self.blaze_service.update_biobank(different_biobank)
        updated_biobank = self.blaze_service.build_biobank_from_json(updated_fhir_id)
        self.assertEqual(updated_biobank.name, different_biobank.name)

    def test_build_biobank_from_json(self):
        biobank_fhir_id = self.blaze_service.upload_biobank(self.example_biobank)
        biobank = self.blaze_service.build_biobank_from_json(biobank_fhir_id)
        self.assertEqual(biobank_fhir_id, biobank.biobank_fhir_id)
        self.assertEqual(self.example_biobank.identifier, biobank.identifier)
        self.assertEqual(self.example_biobank.name, biobank.name)
        self.assertEqual(self.example_biobank.contact_surname, biobank.contact_surname)
        self.assertEqual(self.example_biobank.country, biobank.country)
        self.assertEqual(self.example_biobank.contact_email, biobank.contact_email)
        self.assertEqual(self.example_biobank.juristic_person.name, biobank.juristic_person.name)
        self.assertEqual(self.example_biobank.contact_name, biobank.contact_name)
        self.assertEqual(self.example_biobank.alias, biobank.alias)
        self.assertEqual(self.example_biobank.description, biobank.description)
        self.assertEqual(self.example_biobank.organisational_capabilities, biobank.organisational_capabilities)

    def test_build_biobank_from_json_with_nonexistent_id_raises_nonexistent_exception(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        with self.assertRaises(NonExistentResourceException):
            self.blaze_service.build_biobank_from_json("nonexistentId")

    def test_upload_collection(self):
        biobank_fhir_id = self.blaze_service.upload_biobank(self.example_biobank)
        collection_fhir_id = self.blaze_service.upload_collection(self.example_collection)
        self.assertIsNotNone(collection_fhir_id)
        self.assertTrue(self.blaze_service.is_resource_present_in_blaze("Group", collection_fhir_id))

    def test_update_collection(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        self.blaze_service.upload_donor(self.example_donor)
        collection_fhir_id = self.blaze_service.upload_collection(self.example_collection)
        sample_fhir_id = self.blaze_service.upload_sample(self.example_samples[0])
        self.blaze_service.add_already_present_samples_to_existing_collection([sample_fhir_id], collection_fhir_id)
        different_collection = Collection(identifier="collectionId", name="DifferentName",
                                          managing_biobank_id="biobankId",
                                          contact_name="contactName", contact_surname="contactSurname",
                                          contact_email="contactEmail", country="cz", genders=[Gender.MALE],
                                          material_types=["Urine"], inclusion_criteria=["Sex"],
                                          alias="collectionAlias", url="urlExample.com",
                                          description="differentDescription",
                                          dataset_type="LifeStyle", sample_source="Human",
                                          sample_collection_setting="Environment", collection_design=["CaseControl"],
                                          use_and_access_conditions=["CommercialUse"], publications=["publication"])
        already_present_collection = self.blaze_service.build_collection_from_json(collection_fhir_id)
        updated_fhir_id = self.blaze_service.update_collection(different_collection)
        updated_collection = self.blaze_service.build_collection_from_json(updated_fhir_id)
        self.assertEqual(updated_collection.name, different_collection.name)
        self.assertEqual(updated_collection.description, different_collection.description)
        self.assertEqual(already_present_collection.diagnoses, updated_collection.diagnoses)
        self.assertEqual(already_present_collection.storage_temperatures, updated_collection.storage_temperatures)

    def test_delete_collection(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        collection_fhir_id = self.blaze_service.upload_collection(self.example_collection)
        self.assertTrue(self.blaze_service.is_resource_present_in_blaze("Group", collection_fhir_id))
        deleted = self.blaze_service.delete_collection(collection_fhir_id)
        self.assertTrue(deleted)
        self.assertFalse(self.blaze_service.is_resource_present_in_blaze("Group", collection_fhir_id))

    def test_build_collection_from_json(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        collection_fhir_id = self.blaze_service.upload_collection(self.example_collection)
        collection = self.blaze_service.build_collection_from_json(collection_fhir_id)
        self.assertEqual(self.example_collection.name, collection.name)
        self.assertEqual(self.example_collection.identifier, collection.identifier)
        self.assertEqual([], collection.sample_ids)
        self.assertEqual(self.example_collection.number_of_subjects, collection.number_of_subjects)
        self.assertEqual(self.example_collection.inclusion_criteria, collection.inclusion_criteria)
        self.assertEqual(self.example_collection.diagnoses, collection.diagnoses)
        self.assertEqual(self.example_collection.material_types, collection.material_types)
        self.assertEqual(self.example_collection.storage_temperatures, collection.storage_temperatures)
        self.assertEqual(self.example_collection.genders, collection.genders)
        self.assertEqual(self.example_collection.age_range_low, collection.age_range_low)
        self.assertEqual(self.example_collection.age_range_high, collection.age_range_high)
        self.assertEqual(collection_fhir_id, collection.collection_fhir_id)
        # self.assertEqual(collection_org_fhir_id, collection.managing_collection_org_fhir_id)
        self.assertEqual(self.example_collection.managing_collection_org_id, collection.managing_collection_org_id)

    def test_build_network_organization_from_json(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        self.blaze_service.upload_collection(self.example_collection)
        network_fhir_id = self.blaze_service.upload_network(self.example_network)
        network_json = self.blaze_service.get_fhir_resource_as_json("Group", network_fhir_id)
        network_org_fhir_id = parse_reference_id(get_nested_value(network_json, ["managingEntity", "reference"]))
        network_org = self.blaze_service._build_network_org_from_json(network_org_fhir_id)
        self.assertEqual(network_org.network_org_fhir_id, network_org_fhir_id)
        self.assertEqual(network_org.name, self.example_network_org.name)
        self.assertEqual(network_org.identifier, self.example_network_org.identifier)
        self.assertEqual(network_org.contact_name, self.example_network_org.contact_name)
        self.assertEqual(network_org.description, self.example_network_org.description)
        self.assertEqual(network_org.contact_surname, self.example_network_org.contact_surname)
        self.assertEqual(network_org.contact_email, self.example_network_org.contact_email)
        self.assertEqual(network_org.country, self.example_network_org.country)
        self.assertEqual(network_org.juristic_person.name, self.example_network_org.juristic_person.name)
        self.assertEqual(network_org.common_collaboration_topics, self.example_network_org.common_collaboration_topics)

    def test_upload_network(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        self.blaze_service.upload_collection(self.example_collection)
        network_id = self.blaze_service.upload_network(self.example_network)
        self.assertTrue(self.blaze_service.is_resource_present_in_blaze("Group", network_id))
        self.assertIsNotNone(network_id)

    def test_update_network(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        self.blaze_service.upload_collection(self.example_collection)
        network_id = self.blaze_service.upload_network(self.example_network)
        different_network = Network(identifier="networkId", name="differentName", contact_email="contactEmail",
                                    country="SK", juristic_person="juristicPerson",
                                    members_collections_ids=["collectionId"],
                                    members_biobanks_ids=["biobankId"], contact_name="contactName",
                                    contact_surname="differentSurname", common_collaboration_topics=["Charter"],
                                    description="description")
        updated_fhir_id = self.blaze_service.update_network(different_network)
        updated_network = self.blaze_service.build_network_from_json(updated_fhir_id)
        self.assertEqual(updated_network.country, different_network.country)
        self.assertEqual(updated_network.contact_surname, different_network.contact_surname)
        self.assertEqual(updated_network.name, different_network.name)

    def test_delete_network(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        self.blaze_service.upload_collection(self.example_collection)
        network_fhir_id = self.blaze_service.upload_network(self.example_network)
        deleted = self.blaze_service.delete_network(network_fhir_id)
        self.assertTrue(deleted)
        self.assertFalse(self.blaze_service.is_resource_present_in_blaze("Group", network_fhir_id))

    def test_upload_network_private(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        self.blaze_service.upload_collection(self.example_collection)
        network_fhir_id = self.blaze_service.upload_network(self.example_network)
        self.assertIsNotNone(network_fhir_id)
        self.assertTrue(self.blaze_service.is_resource_present_in_blaze("Group", network_fhir_id))

    def test_build_network_from_json(self):
        biobank_fhir_id = self.blaze_service.upload_biobank(self.example_biobank)
        collection_fhir_id = self.blaze_service.upload_collection(self.example_collection)
        network_fhir_id = self.blaze_service.upload_network(self.example_network)
        network = self.blaze_service.build_network_from_json(network_fhir_id)
        self.assertEqual(network_fhir_id, network.network_fhir_id)
        # self.assertEqual(network_org_fhir_id, network.managing_network_org_fhir_id)
        self.assertIn(biobank_fhir_id, network.members_biobanks_fhir_ids)
        self.assertIn(collection_fhir_id, network.members_collections_fhir_ids)
        self.assertEqual(self.example_network.name, network.name)
        self.assertEqual(self.example_network.identifier, network.identifier)
        self.assertEqual(self.example_network.managing_network_org_id, network.managing_network_org_id)
        self.assertEqual(self.example_network.members_collections_ids, network.members_collections_ids)
        self.assertEqual(self.example_network.members_biobanks_ids, network.members_biobanks_ids)

    def test_delete_biobank(self):
        biobank_fhir_id = self.blaze_service.get_fhir_id("Organization", self.example_biobank.identifier)
        if biobank_fhir_id is not None:
            deleted = self.blaze_service.delete_biobank(biobank_fhir_id)
            self.assertTrue(deleted)

    def test_add_existing_sample_to_collection(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id1 = self.blaze_service.upload_sample(self.example_samples[0])
        sample_fhir_id2 = self.blaze_service.upload_sample(self.example_samples[1])
        self.blaze_service.upload_biobank(self.example_biobank)
        collection_fhir_id = self.blaze_service.upload_collection(self.example_collection)
        self.blaze_service.upload_network(self.example_network)
        updated = self.blaze_service.add_already_present_samples_to_existing_collection(
            [sample_fhir_id1, sample_fhir_id2], collection_fhir_id)
        self.assertTrue(updated)
        updated_collection = self.blaze_service.build_collection_from_json(collection_fhir_id)
        self.assertEqual(updated_collection.number_of_subjects, 1)
        self.assertIn(sample_fhir_id1, updated_collection.sample_fhir_ids)
        self.assertIn(sample_fhir_id2, updated_collection.sample_fhir_ids)
        self.assertIn(self.example_samples[0].storage_temperature, updated_collection.storage_temperatures)
        self.assertIn(self.example_samples[1].storage_temperature, updated_collection.storage_temperatures)
        self.assertIn(self.example_donor.gender, updated_collection.genders)
        self.assertIn(self.example_observations[0].icd10_code, updated_collection.diagnoses)
        self.assertIn(self.example_observations[1].icd10_code, updated_collection.diagnoses)

    def test_update_collection_values_after_deleting_sample(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id1 = self.blaze_service.upload_sample(self.example_samples[0])
        new_sample = Sample("newSampleId", "newDonorId", "Nail", datetime.datetime(year=2020, month=11, day=21),
                            storage_temperature=StorageTemperature.TEMPERATURE_OTHER,
                            diagnoses_with_observed_datetime=[("B22", datetime.datetime(year=2019, month=10, day=20))],
                            sample_collection_id="collectionId")
        new_donor = SampleDonor("newDonorId", Gender.FEMALE, datetime.datetime(year=1980, month=10, day=20), "Other")
        new_donor_fhir_id = self.blaze_service.upload_donor(new_donor)
        new_sample_fhir_id = self.blaze_service.upload_sample(new_sample)
        self.blaze_service.upload_biobank(self.example_biobank)
        collection_fhir_id = self.blaze_service.upload_collection(self.example_collection)
        updated = self.blaze_service.add_already_present_samples_to_existing_collection(
            [sample_fhir_id1, new_sample_fhir_id], collection_fhir_id)
        self.assertTrue(updated)

        updated_collection = self.blaze_service.build_collection_from_json(collection_fhir_id)

        self.assertEqual(updated_collection.number_of_subjects, 2)

        self.assertIn(sample_fhir_id1, updated_collection.sample_fhir_ids)
        self.assertIn(new_sample_fhir_id, updated_collection.sample_fhir_ids)

        self.assertEqual(
            new_sample._observations[0].diagnosis_observed_datetime.year - new_donor.date_of_birth.year,
            updated_collection.age_range_high)
        self.assertEqual(
            self.example_samples[0]._observations[
                1].diagnosis_observed_datetime.year - self.example_donor.date_of_birth.year,
            updated_collection.age_range_low)

        self.assertIn(self.example_samples[0].storage_temperature, updated_collection.storage_temperatures)
        self.assertIn(new_sample.storage_temperature, updated_collection.storage_temperatures)

        self.assertIn(self.example_donor.gender, updated_collection.genders)
        self.assertIn(new_donor.gender, updated_collection.genders)

        self.assertIn(self.example_observations[0].icd10_code, updated_collection.diagnoses)
        self.assertIn(new_sample.diagnoses_icd10_code_with_observed_datetime[0][0], updated_collection.diagnoses)

        self.blaze_service.delete_donor(new_donor_fhir_id)
        update_collection = self.blaze_service.update_collection_values(collection_fhir_id)
        self.assertTrue(update_collection)

        updated_collection = self.blaze_service.build_collection_from_json(collection_fhir_id)

        self.assertEqual(updated_collection.number_of_subjects, 1)

        self.assertEqual(
            self.example_samples[0]._observations[
                1].diagnosis_observed_datetime.year - self.example_donor.date_of_birth.year,
            updated_collection.age_range_low)

        self.assertEqual(
            self.example_samples[0]._observations[
                0].diagnosis_observed_datetime.year - self.example_donor.date_of_birth.year,
            updated_collection.age_range_high)

        self.assertIn(sample_fhir_id1, updated_collection.sample_fhir_ids)
        self.assertNotIn(new_sample_fhir_id, updated_collection.sample_fhir_ids)

        self.assertIn(self.example_samples[0].storage_temperature, updated_collection.storage_temperatures)
        self.assertNotIn(new_sample.storage_temperature, updated_collection.storage_temperatures)

        self.assertIn(self.example_donor.gender, updated_collection.genders)
        self.assertNotIn(new_donor.gender, updated_collection.genders)

        self.assertIn(self.example_samples[0].diagnoses_icd10_code_with_observed_datetime[0][0],
                      updated_collection.diagnoses)
        self.assertNotIn(new_sample.diagnoses_icd10_code_with_observed_datetime[0][0], updated_collection.diagnoses)

    def test_delete_sample_present_in_collection(self):
        self.blaze_service.upload_donor(self.example_donor)
        sample_fhir_id1 = self.blaze_service.upload_sample(self.example_samples[0])
        self.blaze_service._upload_observation(self.example_observations[0])
        self.blaze_service.upload_biobank(self.example_biobank)
        collection_fhir_id = self.blaze_service.upload_collection(self.example_collection)
        updated = self.blaze_service.add_already_present_samples_to_existing_collection(
            [sample_fhir_id1], collection_fhir_id)
        self.assertTrue(updated)
        deleted = self.blaze_service.delete_sample(sample_fhir_id1)
        self.assertTrue(deleted)

    def test_delete_all_resources(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        self.blaze_service.upload_collection(self.example_collection)
        self.blaze_service.upload_network(self.example_network)
        self.blaze_service.upload_donor(self.example_donor)
        self.blaze_service.upload_sample(self.example_samples[0])
        self.blaze_service.upload_sample(self.example_samples[1])
        deleted_everything = self.blaze_service.delete_all_resources(self.example_biobank.identifier)
        self.assertTrue(deleted_everything)

    def test_delete_all_resources_removes_juristic_person(self):
        self.blaze_service.upload_biobank(self.example_biobank)
        self.blaze_service.upload_donor(self.example_donor)
        juristic_person_name = self.example_biobank.juristic_person.name
        self.assertIsNotNone(self.blaze_service._get_juristic_person_organization_by_name(juristic_person_name))
        deleted_everything = self.blaze_service.delete_all_resources(self.example_biobank.identifier)
        self.assertTrue(deleted_everything)
        self.assertIsNone(self.blaze_service._get_juristic_person_organization_by_name(juristic_person_name))
