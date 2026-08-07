import uuid
from typing import Self

from fhirclient.models.bundle import Bundle
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.meta import Meta
from fhirclient.models.organization import Organization

from miabis_model.incorrect_json_format import IncorrectJsonFormatException
from miabis_model.juristic_person import _JuristicPerson
from miabis_model.util.config import FHIRConfig
from miabis_model.util.constants import BIOBANK_BIOPROCESSING_AND_ANALYTICAL_CAPABILITIES, \
    BIOBANK_INFRASTRUCTURAL_CAPABILITIES, \
    BIOBANK_ORGANISATIONAL_CAPABILITIES, DEFINITION_BASE_URL
from miabis_model.util.parsing_util import get_nested_value, parse_contact
from miabis_model.util.util import create_fhir_identifier, create_contact, create_country_of_residence, \
    create_codeable_concept_extension, create_string_extension, create_post_bundle_entry, create_bundle


class Biobank:
    """Class representing a biobank as defined by the MIABIS on FHIR profile."""

    def __init__(self, identifier: str, name: str, country: str, contact_name: str, contact_surname: str,
                 contact_email: str, juristic_person: str, description: str, alias: str = None, url: str = None,
                 infrastructural_capabilities: list[str] = None,
                 organisational_capabilities: list[str] = None,
                 bioprocessing_and_analysis_capabilities: list[str] = None,
                 quality__management_standards: list[str] = None):
        """
        :param identifier: Biobank identifier same format as in the BBMRI-ERIC directory.
        :param name: name of the biobank
        :param alias: acronym of the biobank
        :param country: country of residence of the biobank
        :param contact_name: name of the contact person
        :param contact_surname: surname of the contact person
        :param contact_email: email of the contact person
        :param infrastructural_capabilities: The technical infrastructural capabilities that
        the biobank can offer to the clients. Available values in the constants.py file
        :param organisational_capabilities: The organisational capabilities and services that
        the biobank can provide to support clients. Available values in the constants.py file
        :param bioprocessing_and_analysis_capabilities: The bioprocessing and analytical services
        that the biobank can offer to the clients. Available values in the constants.py file
        :param quality__management_standards: The standards that the biobank is certified or accredited for.
        :param juristic_person: The legal entity that is responsible for the biobank.
        Available values in the constants.py file
        """
        self.identifier = identifier
        self.name = name
        self.alias = alias
        self.country = country
        self.contact_name = contact_name
        self.contact_surname = contact_surname
        self.contact_email = contact_email
        self.juristic_person = _JuristicPerson(juristic_person)
        self.quality__management_standards = quality__management_standards
        self.infrastructural_capabilities = infrastructural_capabilities
        self.organisational_capabilities = organisational_capabilities
        self.description = description
        self.url = url
        self.bioprocessing_and_analysis_capabilities = bioprocessing_and_analysis_capabilities
        self._biobank_fhir_id = None

    @property
    def identifier(self) -> str:
        return self._identifier

    @identifier.setter
    def identifier(self, identifier: str):
        if not isinstance(identifier, str):
            raise TypeError("Identifier must be a string.")
        self._identifier = identifier

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str):
        if not isinstance(name, str):
            raise TypeError("Name must be a string.")
        self._name = name

    @property
    def alias(self) -> str:
        return self._alias

    @alias.setter
    def alias(self, alias: str):
        if alias is not None and not isinstance(alias, str):
            raise TypeError("Alias must be a string.")
        self._alias = alias

    @property
    def country(self) -> str:
        return self._country

    @country.setter
    def country(self, country: str):
        if not isinstance(country, str):
            raise TypeError("Country must be a string.")
        self._country = country

    @property
    def contact_name(self) -> str:
        return self._contact_name

    @contact_name.setter
    def contact_name(self, contact_name: str):
        if not isinstance(contact_name, str):
            raise TypeError("Contact name must be a string.")
        self._contact_name = contact_name

    @property
    def contact_surname(self) -> str:
        return self._contact_surname

    @contact_surname.setter
    def contact_surname(self, contact_surname: str):
        if not isinstance(contact_surname, str):
            raise TypeError("Contact surname must be a string.")
        self._contact_surname = contact_surname

    @property
    def contact_email(self) -> str:
        return self._contact_email

    @contact_email.setter
    def contact_email(self, contact_email: str):
        if not isinstance(contact_email, str):
            raise TypeError("Contact email must be a string.")
        self._contact_email = contact_email

    @property
    def url(self) -> str:
        return self._url

    @url.setter
    def url(self, url: str):
        if url is not None and not isinstance(url, str):
            raise TypeError("Url must be a string.")
        self._url = url

    @property
    def infrastructural_capabilities(self) -> list[str]:
        return self._infrastructural_capabilities

    @infrastructural_capabilities.setter
    def infrastructural_capabilities(self, infrastructural_capabilities: list[str]):
        for capability in infrastructural_capabilities if infrastructural_capabilities is not None else []:
            if capability not in BIOBANK_INFRASTRUCTURAL_CAPABILITIES:
                raise ValueError(f"{capability} is not a valid code for infrastructural capabilities")
        self._infrastructural_capabilities = infrastructural_capabilities

    @property
    def organisational_capabilities(self) -> list[str]:
        return self._organisational_capabilities

    @organisational_capabilities.setter
    def organisational_capabilities(self, organisational_capabilities: list[str]):
        for capability in organisational_capabilities if organisational_capabilities is not None else []:
            if capability not in BIOBANK_ORGANISATIONAL_CAPABILITIES:
                raise ValueError(f"{capability} is not a valid code for organisational capabilities")
        self._organisational_capabilities = organisational_capabilities

    @property
    def bioprocessing_and_analysis_capabilities(self) -> list[str]:
        return self._bioprocessing_and_analysis_capabilities

    @bioprocessing_and_analysis_capabilities.setter
    def bioprocessing_and_analysis_capabilities(self, bioprocessing_and_analysis_capabilities: list[str]):
        for capability in bioprocessing_and_analysis_capabilities if bioprocessing_and_analysis_capabilities is not None else []:
            if capability not in BIOBANK_BIOPROCESSING_AND_ANALYTICAL_CAPABILITIES:
                raise ValueError(f"{capability} is not a valid code for bioprocessing and analysis capabilities")
        self._bioprocessing_and_analysis_capabilities = bioprocessing_and_analysis_capabilities

    @property
    def quality__management_standards(self) -> list[str]:
        return self._quality__management_standards

    @quality__management_standards.setter
    def quality__management_standards(self, quality__management_standards: list[str]):
        self._quality__management_standards = quality__management_standards

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, description: str):
        if description is not None and not isinstance(description, str):
            raise TypeError("Description must be a string.")
        self._description = description

    @property
    def biobank_fhir_id(self) -> str:
        return self._biobank_fhir_id

    @classmethod
    def from_json(cls, biobank_json: dict, juristic_person_json: dict) -> Self:
        """
        Parse a json into a MoFBiobank object.
        :param juristic_person_json: json representation of juristic person responsible for this biobank.
        :param biobank_json: json representation of the biobank.
        :return: MoFBiobank object.
        """
        try:
            biobank_fhir_id = get_nested_value(biobank_json, ["id"])
            identifier = get_nested_value(biobank_json, ["identifier", 0, "value"])
            name = get_nested_value(biobank_json, ["name"])
            alias = get_nested_value(biobank_json, ["alias", 0])
            country = get_nested_value(biobank_json, ["address", 0, "country"])
            contact = parse_contact(biobank_json.get("contact", [{}])[0])
            extensions = get_nested_value(biobank_json, ["extension"])
            parsed_extension = cls.__parse_extensions(extensions)
            infrastructural_capabilities = parsed_extension["infrastructural_capabilities"]
            organisational_capabilities = parsed_extension["organisational_capabilities"]
            bioprocessing = parsed_extension["bioprocessing_and_analysis_capabilities"]
            quality_standards = parsed_extension["quality_management_standards"]
            description = parsed_extension["description"]
            juristic_person_fhir_id = get_nested_value(juristic_person_json, ["id"])
            juristic_person_name = get_nested_value(juristic_person_json, ["name"])
            instance = cls(identifier, name, country, contact["name"], contact["surname"], contact["email"],
                           juristic_person_name, description, alias,
                           infrastructural_capabilities=infrastructural_capabilities,
                           organisational_capabilities=organisational_capabilities,
                           bioprocessing_and_analysis_capabilities=bioprocessing,
                           quality__management_standards=quality_standards)
            instance._biobank_fhir_id = biobank_fhir_id
            instance.juristic_person._fhir_id = juristic_person_fhir_id
            return instance
        except KeyError:
            raise IncorrectJsonFormatException("Error occurred when parsing json into MoFBiobank")

    @staticmethod
    def __parse_extensions(extensions: list) -> dict:

        """
        Parse the extensions from the json into a dictionary.
        :param extensions: list of extensions in the json.
        :return: dictionary with the extensions.
        """

        parsed_extension = {"infrastructural_capabilities": [], "organisational_capabilities": [],
                            "bioprocessing_and_analysis_capabilities": [], "quality_management_standards": [],
                            "juristic_person": None, "description": None}
        infrastruct_url = FHIRConfig.get_extension_url("biobank", "infrastructural_capabilities")
        org_capability_url = FHIRConfig.get_extension_url("biobank", "organisational_capabilities")
        bioprocess__url = FHIRConfig.get_extension_url("biobank", "bioprocessing_and_analysis_capabilities")
        quality_url = FHIRConfig.get_extension_url("biobank", "quality_management_standard")
        description_url = FHIRConfig.get_extension_url("biobank", "description")
        for extension in extensions:
            ext_type = extension["url"].replace(f"{DEFINITION_BASE_URL}/", "", 1)
            extension_url = extension["url"]
            if extension_url == infrastruct_url:
                value = get_nested_value(extension, ["valueCodeableConcept", "coding", 0, "code"])
                if value is not None:
                    parsed_extension["infrastructural_capabilities"].append(value)
            elif extension_url == org_capability_url:
                value = get_nested_value(extension, ["valueCodeableConcept", "coding", 0, "code"])
                if value is not None:
                    parsed_extension["organisational_capabilities"].append(value)
            elif extension_url == bioprocess__url:
                value = get_nested_value(extension, ["valueCodeableConcept", "coding", 0, "code"])
                if value is not None:
                    parsed_extension["bioprocessing_and_analysis_capabilities"].append(value)
            elif extension_url == quality_url:
                value = get_nested_value(extension, ["valueString"])
                if value is not None:
                    parsed_extension["quality_management_standards"].append(value)
            elif extension_url == description_url:
                value = get_nested_value(extension, ["valueString"])
                if value is not None:
                    parsed_extension["description"] = value
            else:
                continue
        for key, value in parsed_extension.items():
            if isinstance(value, list) and value == []:
                parsed_extension[key] = None
        return parsed_extension

    def to_fhir(self, juristic_person_fhir_id: str = None) -> Organization:
        """Return biobank representation in FHIR"""
        juristic_person_fhir_id = juristic_person_fhir_id or self.juristic_person.fhir_id
        if juristic_person_fhir_id is None:
            raise ValueError("Managing biobank FHIR id must be provided either as an argument or as a property.")

        fhir_organization = Organization()
        fhir_organization.meta = Meta()
        fhir_organization.meta.profile = [FHIRConfig.get_meta_profile_url("biobank")]
        fhir_organization.identifier = [create_fhir_identifier(self.identifier)]
        fhir_organization.identifier[0].system = "http://www.bbmri-eric.eu/"
        fhir_organization.name = self.name
        fhir_organization.partOf = FHIRReference()
        fhir_organization.partOf.reference = f"Organization/{juristic_person_fhir_id}"
        if self.alias is not None:
            fhir_organization.alias = [self.alias]
        fhir_organization.contact = [create_contact(self.contact_name, self.contact_surname, self.contact_email)]
        fhir_organization.address = [create_country_of_residence(self.country)]
        extensions = []
        if self.infrastructural_capabilities is not None:
            for capability in self.infrastructural_capabilities:
                extensions.append(
                    create_codeable_concept_extension(
                        FHIRConfig.get_extension_url("biobank", "infrastructural_capabilities"),
                        FHIRConfig.get_code_system_url("biobank", "infrastructural_capabilities"),
                        capability))
        if self.organisational_capabilities is not None:
            for capability in self.organisational_capabilities:
                extensions.append(
                    create_codeable_concept_extension(
                        FHIRConfig.get_extension_url("biobank", "organisational_capabilities"),
                        FHIRConfig.get_code_system_url("biobank", "organisational_capabilities"),
                        capability))
        if self.bioprocessing_and_analysis_capabilities is not None:
            for capability in self.bioprocessing_and_analysis_capabilities:
                extensions.append(
                    create_codeable_concept_extension(
                        FHIRConfig.get_extension_url("biobank", "bioprocessing_and_analysis_capabilities"),
                        FHIRConfig.get_code_system_url("biobank", "bioprocessing_and_analysis_capabilities"),
                        capability))
        if self.quality__management_standards is not None:
            for standard in self.quality__management_standards:
                extensions.append(
                    create_string_extension(
                        FHIRConfig.get_extension_url("biobank", "quality_management_standard"),
                        standard))
        if self.description is not None:
            extensions.append(create_string_extension(
                FHIRConfig.get_extension_url("biobank", "description"),
                self.description))
        if extensions:
            fhir_organization.extension = extensions
        return fhir_organization

    def build_bundle_for_upload(self) -> Bundle:

        juristic_person_temporary_id = str(uuid.uuid4())
        biobank_temporary_id = str(uuid.uuid4())
        biobank_fhir = self.to_fhir(juristic_person_temporary_id)
        biobank_fhir.partOf.reference = juristic_person_temporary_id
        juristic_person_fhir = self.juristic_person.to_fhir()
        biobank_entry = create_post_bundle_entry("Organization", biobank_fhir, biobank_temporary_id)
        juristic_person_entry = create_post_bundle_entry("Organization", juristic_person_fhir,
                                                         juristic_person_temporary_id)
        bundle = create_bundle([biobank_entry, juristic_person_entry])
        return bundle

    def add_fhir_id_to_biobank(self, biobank: Organization) -> Organization:
        """Add FHIR id to the FHIR representation of the Biobank. FHIR ID is necessary for updating the
                resource on the server.This method should only be called if the Biobank object was created by the
                from_json method. Otherwise,the biobank_report_fhir_id attribute is None,
                as the FHIR ID is generated by the server and is not known in advance."""
        biobank.id = self.biobank_fhir_id
        return biobank

    def __eq__(self, other):
        if not isinstance(other, Biobank):
            return False
        return self.identifier == other.identifier and \
            self.name == other.name and \
            self.alias == other.alias and \
            self.country == other.country and \
            self.contact_name == other.contact_name and \
            self.contact_surname == other.contact_surname and \
            self.contact_email == other.contact_email and \
            self.juristic_person.name == other.juristic_person.name and \
            self.quality__management_standards == other.quality__management_standards and \
            self.infrastructural_capabilities == other.infrastructural_capabilities and \
            self.organisational_capabilities == other.organisational_capabilities and \
            self.description == other.description and \
            self.bioprocessing_and_analysis_capabilities == other.bioprocessing_and_analysis_capabilities
