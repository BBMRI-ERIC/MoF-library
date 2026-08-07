import uuid
from datetime import datetime
from typing import Self

from fhirclient.models.annotation import Annotation
from fhirclient.models.bundle import Bundle
from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.extension import Extension
from fhirclient.models.fhirdatetime import FHIRDateTime
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.meta import Meta
from fhirclient.models.specimen import Specimen, SpecimenCollection, SpecimenProcessing

from miabis_model import _Observation
from miabis_model.incorrect_json_format import IncorrectJsonFormatException
from miabis_model.storage_temperature import StorageTemperature
from miabis_model.util.config import FHIRConfig
from miabis_model.util.constants import DETAILED_MATERIAL_TYPE_CODES
from miabis_model.util.parsing_util import get_nested_value, parse_reference_id
from miabis_model.util.util import create_fhir_identifier, create_codeable_concept, \
    create_codeable_concept_extension, create_post_bundle_entry, create_bundle


class Sample:
    """Class representing a biological specimen as defined by the MIABIS on FHIR profile."""

    def __init__(self, identifier: str, donor_identifier: str, material_type: str, collected_datetime: datetime = None,
                 body_site: str = None, body_site_system: str = None, storage_temperature: StorageTemperature = None,
                 use_restrictions: str = None,
                 diagnoses_with_observed_datetime: list[tuple[str, datetime | None]] = None,
                 sample_collection_id: str = None):
        """
        :param identifier: Sample organizational identifier
        :param donor_identifier: Donor organizational identifier
        :param material_type: Sample type. E.g. tissue, plasma...
        :param collected_datetime: Date and time of sample collection
        :param body_site: The anatomical location from which the sample was collected
        :param body_site_system: The system to which the body site belongs
        :param storage_temperature: Temperature at which the sample is stored
        :param use_restrictions: Restrictions on the use of the sample
        :param diagnosis_icd10_codes:  list of icd10 codes of the diagnoses linked to this sample
        :param diagnoses_observed_datetime:  list of times when the diagnosis was first observed
        """
        self.identifier = identifier
        self.material_type = material_type
        self.collected_datetime = collected_datetime
        self.donor_identifier = donor_identifier
        self.body_site = body_site
        self.body_site_system = body_site_system
        self.storage_temperature = storage_temperature
        self.use_restrictions = use_restrictions
        self.sample_collection_id = sample_collection_id
        self._observations = []
        if diagnoses_with_observed_datetime is None:
            diagnoses_with_observed_datetime = []
        for diagnosis_code, observed_datetime in diagnoses_with_observed_datetime:
            observation = _Observation(diagnosis_code, identifier, donor_identifier, observed_datetime)
            self._observations.append(observation)
        self._subject_fhir_id = None
        self._sample_fhir_id = None
        self._observation_fhir_ids = None

    @property
    def diagnoses_icd10_code_with_observed_datetime(self) -> list[tuple[str, datetime | None]]:
        diagnoses_icd10_code_with_observed_datetime = []
        for observation in self._observations:
            diagnoses_icd10_code_with_observed_datetime.append(
                (observation.icd10_code, observation.diagnosis_observed_datetime))
        return diagnoses_icd10_code_with_observed_datetime

    @property
    def identifier(self) -> str:
        """Institutional identifier."""
        return self._identifier

    @identifier.setter
    def identifier(self, identifier: str):
        if not isinstance(identifier, str):
            raise TypeError("Identifier must be string")
        self._identifier = identifier

    @property
    def donor_identifier(self) -> str:
        """Institutional ID of donor."""
        return self._donor_identifier

    @donor_identifier.setter
    def donor_identifier(self, donor_identifier: str):
        if not isinstance(donor_identifier, str):
            raise TypeError("Identifier must be string")
        self._donor_identifier = donor_identifier

    @property
    def material_type(self) -> str:
        """Sample type. E.g. tissue, plasma..."""
        return self._material_type

    @material_type.setter
    def material_type(self, material_type: str):
        if material_type not in DETAILED_MATERIAL_TYPE_CODES:
            raise ValueError(
                f"Material type {material_type} is not valid. Valid values are: {DETAILED_MATERIAL_TYPE_CODES}")
        self._material_type = material_type

    @property
    def collected_datetime(self) -> datetime:
        """Date and time of sample collection."""
        return self._collected_datetime

    @collected_datetime.setter
    def collected_datetime(self, collected_datetime: datetime):
        if collected_datetime is not None and not isinstance(collected_datetime, datetime):
            raise TypeError("Collected datetime must be a datetime object")
        self._collected_datetime = collected_datetime

    @property
    def body_site(self) -> str:
        """The anatomical location from which the sample was collected."""
        return self._body_site

    @body_site.setter
    def body_site(self, body_site: str):
        if body_site is not None and not isinstance(body_site, str):
            raise TypeError("Body site must be a string")
        self._body_site = body_site

    @property
    def body_site_system(self) -> str:
        """The system to which the body site belongs."""
        return self._body_site_system

    @body_site_system.setter
    def body_site_system(self, body_site_system: str):
        if body_site_system is not None and not isinstance(body_site_system, str):
            raise TypeError("Body site system must be a string")
        self._body_site_system = body_site_system

    @property
    def storage_temperature(self) -> StorageTemperature:
        """Temperature at which the sample is stored."""
        return self._storage_temperature

    @storage_temperature.setter
    def storage_temperature(self, storage_temperature: StorageTemperature):
        if storage_temperature is not None and not isinstance(storage_temperature, StorageTemperature):
            raise TypeError("Storage temperature must be a StorageTemperature object")
        self._storage_temperature = storage_temperature

    @property
    def use_restrictions(self) -> str:
        """Restrictions on the use of the sample."""
        return self._use_restrictions

    @use_restrictions.setter
    def use_restrictions(self, use_restrictions: str):
        if use_restrictions is not None and not isinstance(use_restrictions, str):
            raise TypeError("Use restrictions must be a string")
        self._use_restrictions = use_restrictions

    @property
    def sample_collection_id(self) -> str:
        return self._sample_collection_id

    @sample_collection_id.setter
    def sample_collection_id(self, sample_collection_id: str):
        if sample_collection_id is not None and not isinstance(sample_collection_id, str):
            raise TypeError("sample collection id must be a string")
        self._sample_collection_id = sample_collection_id

    @property
    def subject_fhir_id(self) -> str:
        """FHIR ID of the subject to which the sample belongs."""
        return self._subject_fhir_id

    @property
    def sample_fhir_id(self) -> str:
        """FHIR ID of the sample."""
        return self._sample_fhir_id

    @property
    def observation_fhir_ids(self):
        return self._observation_fhir_ids

    @property
    def observations(self):
        return self._observations

    @classmethod
    def from_json(cls, sample_json: dict, observation_jsons: list[dict],
                  donor_identifier: str) -> Self:
        """
        Build MoFSample from FHIR json representation
        :param sample_json: json the sample should be build from
        :param donor_identifier: organizational identifier of the donor (not the FHIR id!)
        :return:
        """
        try:
            sample_fhir_id = get_nested_value(sample_json, ["id"])
            identifier = get_nested_value(sample_json, ["identifier", 0, "value"])
            material_type = get_nested_value(sample_json, ["type", "coding", 0, "code"])
            collected_datetime = cls._parse_collection_datetime(sample_json)
            body_site = get_nested_value(sample_json, ["collection", "bodySite", "coding", 0, "code"])
            body_site_system = get_nested_value(sample_json, ["collection", "bodySite", "coding", 0, "system"])
            storage_temperature = cls._parse_storage_temperature(sample_json)
            use_restrictions = get_nested_value(sample_json, ["note", 0, "text"])
            sample_collection_id = get_nested_value(sample_json, ["extension", 0, "valueIdentifier", "value"])
            observation_instances = []
            for observation_json in observation_jsons:
                observation_instances.append(_Observation.from_json(observation_json, donor_identifier, identifier))
            instance = cls(identifier=identifier, donor_identifier=donor_identifier, material_type=material_type,
                           collected_datetime=collected_datetime, body_site=body_site,
                           body_site_system=body_site_system,
                           storage_temperature=storage_temperature, use_restrictions=use_restrictions,
                           sample_collection_id=sample_collection_id)
            instance._observations = observation_instances
            instance._subject_fhir_id = parse_reference_id(get_nested_value(sample_json, ["subject", "reference"]))
            instance._sample_fhir_id = sample_fhir_id
            instance._observation_fhir_ids = [observation.observation_fhir_id for observation in observation_instances]
            return instance
        except KeyError:
            raise IncorrectJsonFormatException("Error occurred when parsing json into the MoFSample")

    @staticmethod
    def _parse_collection_datetime(sample_json: dict) -> datetime | None:
        """Parse the collection datetime from the sample JSON."""
        collection_datetime = get_nested_value(sample_json, ["collection", "collectedDateTime"])
        if collection_datetime is not None:
            collection_datetime = datetime.strptime(collection_datetime, "%Y-%m-%d")
        return collection_datetime

    @staticmethod
    def _parse_storage_temperature(sample_json: dict) -> StorageTemperature | None:
        """Parse the storage temperature from the sample JSON."""
        storage_temperature = get_nested_value(sample_json,
                                               ["processing", 0, "extension", 0, "valueCodeableConcept",
                                                "coding", 0, "code"])
        if storage_temperature is not None:
            storage_temperature = StorageTemperature(storage_temperature)
        return storage_temperature

    def to_fhir(self, subject_fhir_id: str = None, sample_collection_id: str = None) -> Specimen:
        """return sample representation in FHIR format
        :param subject_fhir_id: FHIR ID of the subject to which the sample belongs"""

        subject_fhir_id = subject_fhir_id or self.subject_fhir_id
        sample_collection_id = sample_collection_id or self.sample_collection_id

        if subject_fhir_id is None:
            raise ValueError("Subject FHIR ID must be provided either as an argument or as a property")

        if sample_collection_id is None:
            raise ValueError("collection_id must be provided either as an argument or as a property")

        specimen = Specimen()
        specimen.meta = Meta()
        specimen.meta.profile = [FHIRConfig.get_meta_profile_url("sample")]
        specimen.identifier = [create_fhir_identifier(self.identifier)]
        specimen.subject = FHIRReference()
        specimen.subject.reference = f"Patient/{subject_fhir_id}"
        specimen.type = create_codeable_concept(FHIRConfig.get_code_system_url("sample", "detailed_sample_type"),
                                                self.material_type)
        if self.sample_collection_id is not None:
            specimen.extension = [self.create_sample_collection_extension()]
        if self.collected_datetime is not None or self.body_site is not None:
            specimen.collection = SpecimenCollection()
            if self.collected_datetime is not None:
                specimen.collection.collectedDateTime = FHIRDateTime()
                specimen.collection.collectedDateTime.date = self.collected_datetime.date()
            if self.body_site is not None:
                specimen.collection.bodySite = self.__create_body_site()
        if self.storage_temperature is not None:
            specimen.processing = [SpecimenProcessing()]
            specimen.processing[0].extension = [
                create_codeable_concept_extension(
                    FHIRConfig.get_extension_url("sample", "storage_temperature"),
                    FHIRConfig.get_code_system_url("sample", "storage_temperature"),
                    self.storage_temperature.value)]
        if self.use_restrictions is not None:
            specimen.note = [Annotation()]
            specimen.note[0].text = self.use_restrictions
        return specimen

    def create_sample_collection_extension(self):
        extension = Extension()
        extension.url = FHIRConfig.get_extension_url("sample", "sample_collection_id")
        extension.valueIdentifier = create_fhir_identifier(self.sample_collection_id)
        return extension

    def add_fhir_id_to_fhir_representation(self, sample: Specimen) -> Specimen:
        """Add the FHIR ID to the FHIR representation of the sample. FHIR ID is necessary for updating the sample.
         This method should only be called if the Sample object was created by the from_json method. Otherwise,
         the sample_fhir_id attribute is None, as the FHIR ID is generated by the server and is not known in advance.
        :param sample: Sample FHIR object"""
        sample.id = self.sample_fhir_id
        return sample

    def build_bundle_for_upload(self, subject_fhir_id: str) -> Bundle:
        sample_bundle_temporary_id = str(uuid.uuid4())
        observation_temporary_ids = []
        sample_fhir = self.to_fhir(subject_fhir_id)
        observations_fhir = []
        for observation in self._observations:
            observation_temporary_ids.append(str(uuid.uuid4()))
            observation_fhir = observation.to_fhir(subject_fhir_id, sample_bundle_temporary_id)
            observation_fhir.specimen.reference = sample_bundle_temporary_id
            observations_fhir.append(observation_fhir)
        entries = [create_post_bundle_entry("Specimen", sample_fhir, sample_bundle_temporary_id)]
        entries.extend(
            [create_post_bundle_entry("Observation", observation_fhir, observation_temporary_ids[i]) for
             i, observation_fhir in enumerate(observations_fhir)])
        bundle = create_bundle(entries)
        return bundle

    def __create_body_site(self) -> CodeableConcept:
        """Create body site codeable concept."""
        body_site = CodeableConcept()
        body_site.coding = [Coding()]
        body_site.coding[0].code = self.body_site
        if self.body_site_system is not None:
            body_site.coding[0].system = self.body_site_system
        return body_site

    def __eq__(self, other):
        """Check if two samples are equal(identical)"""
        if not isinstance(other, Sample):
            return False

        observations_equal = set(self._observations) == set(other._observations)

        return self.identifier == other.identifier and \
            self.material_type == other.material_type and \
            self.collected_datetime == other.collected_datetime and \
            self.donor_identifier == other.donor_identifier and \
            self.body_site == other.body_site and \
            self.body_site_system == other.body_site_system and \
            self.storage_temperature == other.storage_temperature and \
            self.use_restrictions == other.use_restrictions and \
            observations_equal

    def compare_observations(self, other):
        if not isinstance(other, Sample):
            return False
        return set(self._observations) == set(other._observations)
