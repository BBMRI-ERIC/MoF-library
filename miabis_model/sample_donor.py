from datetime import datetime
from typing import Self

from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.meta import Meta
from fhirclient.models.patient import Patient

from miabis_model.gender import Gender
from miabis_model.incorrect_json_format import IncorrectJsonFormatException
from miabis_model.util.config import FHIRConfig
from miabis_model.util.constants import DONOR_DATASET_TYPE
from miabis_model.util.parsing_util import get_nested_value
from miabis_model.util.util import create_fhir_identifier, create_codeable_concept_extension


class SampleDonor:
    """Class representing a sample donor/patient as defined by the MIABIS on FHIR profile."""

    def __init__(self, identifier: str, gender: Gender = None, birth_date: datetime = None,
                 dataset_type: str = None):
        """
        :param identifier: Sample donor identifier
        :param gender: Gender of the donor
        :param birth_date: Date of birth of the donor
        :param datasetType: Dataset that the donor belongs to
        """
        if not isinstance(identifier, str):
            raise TypeError("Identifier must be string")
        self._identifier = identifier
        if gender is not None and not isinstance(gender, Gender):
            raise TypeError("Gender must be from a list of values: " + str(Gender.list()))
        self._gender = gender
        if birth_date is not None and not isinstance(birth_date, datetime):
            raise TypeError("Date of birth must be a datetime.")
        self._date_of_birth = birth_date
        if dataset_type is not None and dataset_type not in DONOR_DATASET_TYPE:
            raise ValueError(f"bad dataset type: has to be one of the following: {DONOR_DATASET_TYPE}")
        self._dataset_type = dataset_type
        self._donor_fhir_id = None

    @property
    def identifier(self) -> str:
        """Institutional identifier"""
        return self._identifier

    @property
    def gender(self) -> Gender:
        return self._gender

    @identifier.setter
    def identifier(self, identifier: str):
        if not isinstance(identifier, str):
            raise TypeError("Identifier must be string")
        self._identifier = identifier

    @gender.setter
    def gender(self, gender: Gender):
        if not isinstance(gender, Gender):
            raise TypeError("Gender must be from a list of values: " + str(Gender.list()))
        self._gender = gender

    @property
    def date_of_birth(self) -> datetime | None:
        if self._date_of_birth is not None:
            return self._date_of_birth
        else:
            return None

    @date_of_birth.setter
    def date_of_birth(self, birth_date: datetime):
        if not isinstance(birth_date, datetime):
            raise TypeError("Date of birth must be a datetime.")
        self._date_of_birth = birth_date

    @property
    def dataset_type(self) -> str:
        return self._dataset_type

    @dataset_type.setter
    def dataset_type(self, dataset_type: str):
        if dataset_type not in DONOR_DATASET_TYPE:
            raise ValueError(f"bad dataset type: has to be one of the following: {DONOR_DATASET_TYPE}")
        self._dataset_type = dataset_type

    @property
    def donor_fhir_id(self) -> str:
        return self._donor_fhir_id

    @classmethod
    def from_json(cls, donor_json: dict) -> Self:
        """
        Build MoFSampleDonor instance from json representation of this fhir resource
        :param donor_json: json to be build from
        :return: MoFSampleDonor instance
        """
        try:
            donor_id = get_nested_value(donor_json, ["id"])
            donor_identifier = get_nested_value(donor_json, ["identifier", 0, "value"])
            gender = cls._parse_gender(donor_json)
            birth_date = cls._parse_date_birth(donor_json)
            dataset_type = get_nested_value(donor_json, ["extension", 0, "valueCodeableConcept", "coding", 0, "code"])
            instance = cls(donor_identifier, gender, birth_date, dataset_type)
            instance._donor_fhir_id = donor_id
            return instance
        except KeyError:
            raise IncorrectJsonFormatException("Error occured when parsing json into the MoFSampleDonor")

    @staticmethod
    def _parse_gender(data: dict) -> Gender | None:
        gender = get_nested_value(data, ["gender"])
        if gender is not None:
            gender = Gender.from_string(gender)
        return gender

    @staticmethod
    def _parse_date_birth(data: dict) -> datetime | None:
        date_string = get_nested_value(data, ["birthDate"])
        if date_string is not None:
            return datetime.strptime(date_string, "%Y-%m-%d")
        return None

    def to_fhir(self) -> Patient:
        """Return sample donor representation in FHIR"""
        fhir_patient = Patient()
        fhir_patient.meta = Meta()
        fhir_patient.meta.profile = [FHIRConfig.get_meta_profile_url("donor")]
        fhir_patient.identifier = [create_fhir_identifier(self.identifier)]
        extensions: list[Extension] = []
        if self.gender is not None:
            fhir_patient.gender = self._gender.name.lower()
        if self.date_of_birth is not None:
            fhir_patient.birthDate = FHIRDate()
            fhir_patient.birthDate.date = self.date_of_birth.date()
        if self.dataset_type is not None:
            extensions.append(
                create_codeable_concept_extension(FHIRConfig.get_extension_url("donor", "dataset_type"),
                                                  FHIRConfig.get_code_system_url("donor", "dataset_type"),
                                                  self.dataset_type))
        if extensions:
            fhir_patient.extension = extensions
        return fhir_patient

    def add_fhir_id_to_donor(self, donor: Patient) -> Patient:
        """Add FHIR id to the FHIR representation of the donor. FHIR ID is necessary for updating the
        resource on the server.This method should only be called if the Donor object was created by the
        from_json method. Otherwise,the donor_fhir_id attribute is None, as the FHIR ID is generated by the server
        and is not known in advance."""
        donor.id = self.donor_fhir_id
        return donor

    def __eq__(self, other):
        if not isinstance(other, SampleDonor):
            return False

        return self.identifier == other.identifier and \
            self.gender == other.gender and \
            self.date_of_birth == other.date_of_birth and \
            self.dataset_type == other.dataset_type

    def __hash__(self):
        return hash(self.identifier)
