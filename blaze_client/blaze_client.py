import datetime
from typing import Generator, Any

import requests
from fhirclient.models.bundle import Bundle, BundleEntry, BundleEntryRequest
from requests import Response
from requests.adapters import HTTPAdapter, Retry

from miabis_model.biobank import Biobank
from miabis_model.collection import Collection
from miabis_model.collection_organization import _CollectionOrganization
from miabis_model.condition import Condition
from miabis_model.juristic_person import _JuristicPerson
from miabis_model.network import Network
from miabis_model.network_organization import _NetworkOrganization
from miabis_model.observation import _Observation
from miabis_model.sample import Sample
from miabis_model.sample_donor import SampleDonor
from miabis_model.util.parsing_util import get_nested_value, parse_reference_id, \
    get_material_type_from_detailed_material_type
from blaze_client.NonExistentResourceException import NonExistentResourceException


class BlazeClient:
    """Class for handling communication with a blaze server,
    be it for CRUD operations, creating objects from json, etc."""

    def __init__(self, blaze_url: str, blaze_username: str, blaze_password: str):
        """
        :param blaze_url: url of the blaze server
        :param blaze_username: blaze username
        :param blaze_password: blaze password
        """
        self._blaze_url = blaze_url
        self._blaze_username = blaze_username
        self._blaze_password = blaze_password
        retries = Retry(total=5,
                        backoff_factor=0.1,
                        status_forcelist=[500, 502, 503, 504])
        session = requests.Session()
        session.mount('http://', HTTPAdapter(max_retries=retries))
        header = {"Prefer": "handling=strict"}
        session.headers.update(header)
        session.auth = (blaze_username, blaze_password)
        self._session = session

    def is_resource_present_in_blaze(self, resource_type: str, search_value: str, search_param: str = None) -> bool:
        """Check if a resource is present in the blaze.
        The search parameter needs to confront to the searchable parameters defined by FHIR for each resource.
        if search_param is None, this method checks the existence of resource by FHIR id.
        :param resource_type: type of the resource
        :param search_param: parameter by which the resource is searched
        :param search_value: actual value by which the search is done
        :return True if the resource is present, false otherwise
        :raises HTTPError: if the request to blaze fails"""
        if search_param is None:
            response = self._session.get(f"{self._blaze_url}/{resource_type.capitalize()}/{search_value}")
            if response.status_code < 200 or response.status_code > 200:
                return False
            if response.status_code == 200:
                return True
        response = self._session.get(f"{self._blaze_url}/{resource_type.capitalize()}",
                                     params={
                                         search_param: search_value
                                     })
        self.__raise_for_status_extract_diagnostics_message(response)
        if response.json()["total"] == 0:
            return False
        return True

    def get_fhir_resource_as_json(self, resource_type: str, resource_fhir_id: str) -> dict | None:
        """Get a FHIR resource from blaze as a json.
        :param resource_type: the type of the resource
        :param resource_fhir_id: the fhir id of the resource
        :return: json representation of the resource, or None if such resource is not present.
        :raises HTTPError: if the request to blaze fails
        """
        response = self._session.get(f"{self._blaze_url}/{resource_type.capitalize()}/{resource_fhir_id}")
        if response.status_code == 404:
            return None
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.json()

    def get_resource_by_search_parameter(self, resource_type: str, search_parameter: str,
                                         search_value: str) -> dict | None:
        """Get a FHIR resource(s) by searching through defined search parameter.
        :param resource_type: the type of the resource
        :param search_parameter: the name of the search parameter to use
        :param search_value: value to search by
        :return: List of json representation of the resource(s), or None if such resource(s) are not present.
        :raises HTTPError: if the request to blaze fails"""
        response = self._session.get(
            f"{self._blaze_url}/{resource_type.capitalize()}", params={
                search_parameter: search_value
            }
        )
        if response.status_code == 404:
            return None
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.json()

    def get_fhir_id(self, resource_type: str, resource_identifier: str) -> str | None:
        """get the fhir id of a resource in blaze.
            :param resource_type: the type of the resource
            :param resource_identifier: the identifier of the resource (usually given by the organization)
            :return: the fhir id of the resource in blaze, or None if the resource was not found
            :raises HTTPError: if the request to blaze fails
            """
        response = self._session.get(f"{self._blaze_url}/{resource_type.capitalize()}",
                                     params={
                                         "identifier": resource_identifier
                                     })
        self.__raise_for_status_extract_diagnostics_message(response)
        response_json = response.json()
        if response_json["total"] == 0:
            return None
        return get_nested_value(response_json, ["entry", 0, "resource", "id"])

    def get_identifier_by_fhir_id(self, resource_type: str, resource_fhir_id: str) -> str | None:
        """get the identifier of a resource in blaze.
            :param resource_type: the type of the resource
            :param resource_fhir_id: the fhir id of the resource
            :return: the identifier of the resource in blaze, None if resource with resource_fhir_id does not exists
            :raises HTTPError: if the request to blaze fails
            """
        response = self._session.get(f"{self._blaze_url}/{resource_type.capitalize()}/{resource_fhir_id}")
        if response.status_code == 404:
            return None
        self.__raise_for_status_extract_diagnostics_message(response)
        response_json = response.json()
        return get_nested_value(response_json, ["identifier", 0, "value"])

    def _get_observation_fhir_ids_belonging_to_sample(self, sample_fhir_id: str) -> list[str]:
        """get all observations linked to a specific sample
        :param sample_fhir_id: fhir id of a sample for which the observations should be retrieved
        :return list of fhir ids linked to a specific sample
        :raises HTTPError: if the request to blaze fails"""
        response = self._session.get(f"{self._blaze_url}/Observation",
                                     params={
                                         "specimen": sample_fhir_id
                                     })
        self.__raise_for_status_extract_diagnostics_message(response)
        observations_fhir_ids = []
        response_json = response.json()
        if response_json["total"] == 0:
            return observations_fhir_ids
        for entry in response_json["entry"]:
            obs_fhir_id = get_nested_value(entry, ["resource", "id"])
            if obs_fhir_id is not None:
                observations_fhir_ids.append(obs_fhir_id)
        return observations_fhir_ids

    def get_condition_by_patient_fhir_id(self, patient_fhir_id: str):
        response = self._session.get(f"{self._blaze_url}/Condition",
                                     params={
                                         "subject": patient_fhir_id
                                     })
        self.__raise_for_status_extract_diagnostics_message(response)
        response_json = response.json()
        if response_json["total"] == 0:
            return None
        return get_nested_value(response_json, ["entry", 0, "resource", "id"])

    def _update_fhir_resource(self, resource_type: str, resource_fhir_id: str, resource_json: dict) -> bool:
        """Update a FHIR resource in blaze.
        :param resource_type: the type of the resource
        :param resource_fhir_id: the fhir id of the resource
        :param resource_json: the json representation of the resource
        :return: True if the resource was updated successfully
        :raises NonExistentResourceException: if the resource cannot be found
        :raises HTTPError: if the request to blaze fails
        """
        response = self._session.put(f"{self._blaze_url}/{resource_type.capitalize()}/{resource_fhir_id}",
                                     json=resource_json)
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 201

    def upload_donor(self, donor: SampleDonor) -> str:
        """Upload a donor to blaze.
            :param donor: the donor to upload
            :raises HTTPError: if the request to blaze fails
            :return: the fhir id of the uploaded donor
            :raises HTTPError: if the request to blaze fails
            """
        response = self._session.post(f"{self._blaze_url}/Patient", json=donor.to_fhir().as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.json()["id"]

    def update_donor(self, donor: SampleDonor) -> str:
        """
        Update donor resource present in the blaze store.
        Uses PUT method
        :param donor: donor to be updated
        :return: fhir id of the updated donor
        """
        if not self.is_resource_present_in_blaze("Patient", donor.identifier, "identifier"):
            raise NonExistentResourceException(f"cannot update donor. Donor with identifier {donor.identifier} "
                                               f"is not present in the blaze store")
        existing_donor_fhir_id = self.get_fhir_id("Patient", donor.identifier)
        existing_donor = self.build_donor_from_json(existing_donor_fhir_id)
        if existing_donor == donor:
            return existing_donor.donor_fhir_id
        donor._donor_fhir_id = existing_donor.donor_fhir_id
        donor_fhir = donor.add_fhir_id_to_donor(donor.to_fhir())
        self._update_fhir_resource("Patient", existing_donor_fhir_id, donor_fhir.as_json())
        return existing_donor.donor_fhir_id

    def upload_sample(self, sample: Sample):
        donor_fhir_id = sample.subject_fhir_id or self.get_fhir_id("Patient", sample.donor_identifier)
        if donor_fhir_id is None:
            raise NonExistentResourceException(
                f"Cannot upload sample. Donor with (organizational) "
                f"identifier: {sample.donor_identifier} is not present in the blaze store.")
        sample_bundle = sample.build_bundle_for_upload(donor_fhir_id)
        response = self._session.post(f"{self._blaze_url}", json=sample_bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        response_json = response.json()
        return self.__get_id_from_bundle_response(response_json, "Specimen")

    def update_sample(self, sample: Sample) -> str:
        """
        Update sample along with observation and diagnosis report that are already preent in the blaze store.
        :param sample: sample to be updated
        Uses PUT method
        :return: fhir id of updated sample (fhir id will be changed after update of sample),
        """
        if not self.is_resource_present_in_blaze("Specimen", sample.identifier, "identifier"):
            raise NonExistentResourceException(f"Cannot update sample. Sample with identifier {sample.identifier}"
                                               f" is not present in the blaze store.")
        existing_sample_fhir_id = self.get_fhir_id("Specimen", sample.identifier)
        existing_sample = self.build_sample_from_json(existing_sample_fhir_id)
        if existing_sample == sample:
            return existing_sample.sample_fhir_id
        sample._sample_fhir_id = existing_sample.sample_fhir_id
        sample._subject_fhir_id = existing_sample.subject_fhir_id
        same_observations = sample.compare_observations(existing_sample)

        if same_observations:
            sample_fhir = sample.to_fhir()
            sample.add_fhir_id_to_fhir_representation(sample_fhir)
            self._update_fhir_resource("Specimen", sample.sample_fhir_id, sample_fhir.as_json())
        else:
            sample_fhir = sample.to_fhir()
            sample.add_fhir_id_to_fhir_representation(sample_fhir)
            self._update_fhir_resource("Specimen", sample.sample_fhir_id, sample_fhir.as_json())
            for observation in existing_sample.observations:
                self._delete_observation(observation.observation_fhir_id)
            for observation in sample.observations:
                self._upload_observation(observation)
        return sample.sample_fhir_id

    def _upload_sample(self, sample: Sample) -> str:
        """Upload a sample to blaze.
            :param sample: the sample to upload
            :raises HTTPError: if the request to blaze fails
            :return: the fhir id of the uploaded sample
            :raises HTTPError: if the request to blaze fails
            """
        donor_fhir_id = sample.subject_fhir_id or self.get_fhir_id("Patient", sample.donor_identifier)
        if donor_fhir_id is None:
            raise NonExistentResourceException(
                f"Cannot upload sample. Donor with (organizational) "
                f"identifier: {sample.donor_identifier} is not present in the blaze store.")
        response = self._session.post(f"{self._blaze_url}/Specimen", json=sample.to_fhir(donor_fhir_id).as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.json()["id"]

    def _upload_observation(self, observation: _Observation) -> str:
        """Upload an observation to blaze.
            :param observation: the observation to upload
            :raises HTTPError: if the request to blaze fails
            :return: the fhir id of the uploaded observation
            """
        patient_fhir_id = observation.patient_fhir_id or self.get_fhir_id("Patient", observation.patient_identifier)
        sample_fhir_id = observation.sample_fhir_id or self.get_fhir_id("Specimen", observation.sample_identifier)
        if patient_fhir_id is None:
            raise NonExistentResourceException(f"Cannot upload observation. Donor with (organizational) identifier: "
                                               f"{observation.patient_identifier} is not present in the blaze store.")
        if sample_fhir_id is None:
            raise NonExistentResourceException(f"Cannot upload observation. Sample with (organizational) identifier: "
                                               f"{observation.sample_identifier} is not present in the blaze store.")
        response = self._session.post(f"{self._blaze_url}/Observation",
                                      json=observation.to_fhir(patient_fhir_id, sample_fhir_id).as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.json()["id"]

    def upload_condition(self, condition: Condition) -> str:
        """Upload a condition to blaze.
            :param condition: the condition to upload
            :raises HTTPError: if the request to blaze fails
            :raises NonExistentResourceException: if the resource cannot be found
            :return: the fhir id of the uploaded condition
            """
        donor_fhir_id = condition.patient_fhir_id or self.get_fhir_id("Patient", condition.patient_identifier)
        if donor_fhir_id is None:
            raise NonExistentResourceException(
                f"Cannot upload Condition. Donor with (organizational) identifier: "
                f"{condition.patient_identifier} is not present in the blaze store.")
        condition_json = condition.to_fhir(donor_fhir_id).as_json()
        response = self._session.post(f"{self._blaze_url}/Condition", json=condition_json)
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.json()["id"]

    def upload_biobank(self, biobank: Biobank) -> str:
        """Upload a biobank to blaze.
        :param biobank: the biobank to upload
        :raises HTTPError: if the request to blaze fails
        :return: the fhir id of the uploaded biobank"""

        juristic_person = self._get_juristic_person_organization_by_name(biobank.juristic_person.name)
        if juristic_person is None:
            upload_json = biobank.build_bundle_for_upload()
            response = self._session.post(f"{self._blaze_url}", json=upload_json.as_json())
            self.__raise_for_status_extract_diagnostics_message(response)
            biobank_id = self.__get_id_from_bundle_response(response.json(), "Organization")
        else:
            upload_json = biobank.to_fhir(get_nested_value(juristic_person, ["id"]))
            response = self._session.post(f"{self._blaze_url}/Organization", json=upload_json.as_json())
            self.__raise_for_status_extract_diagnostics_message(response)
            biobank_id = response.json()["id"]

        return biobank_id

    def update_biobank(self, biobank: Biobank) -> str:
        """
        Update biobank resource already present in the blaze store
        :param biobank: biobank to be updated
        :return: fhir id of the biobank
        """
        if not self.is_resource_present_in_blaze("Organization", biobank.identifier, "identifier"):
            raise NonExistentResourceException(f"Cannot update biobank. Biobank with identifier {biobank.identifier} "
                                               f"is not present in the blaze store.")
        biobank_fhir_id = self.get_fhir_id("Organization", biobank.identifier)
        existing_biobank = self.build_biobank_from_json(biobank_fhir_id)
        if existing_biobank == biobank:
            return biobank_fhir_id
        biobank._biobank_fhir_id = existing_biobank.biobank_fhir_id
        biobank_fhir = biobank.add_fhir_id_to_biobank(biobank.to_fhir(existing_biobank.juristic_person.fhir_id))
        self._update_fhir_resource("Organization", biobank_fhir_id, biobank_fhir.as_json())
        return biobank_fhir_id

    def upload_collection(self, collection: Collection) -> str:
        """
        Upload collection to blaze (as collection is made of Collection and Collection Organization,
        two resources are uploaded via bundle.)
        :param collection:
        :return: id of the collection
        """
        managing_biobank_fhir_id = self.get_fhir_id("Organization", collection.managing_biobank_id)
        if managing_biobank_fhir_id is None:
            raise NonExistentResourceException(
                f"Cannot upload Network Organization. Biobank with (organizational) identifier: "
                f"{collection.managing_biobank_id} is not present in the blaze store.")
        sample_fhir_ids = collection.sample_fhir_ids
        if sample_fhir_ids is None:
            sample_fhir_ids = []
            if collection.sample_ids is not None:
                for sample_id in collection.sample_ids:
                    sample_fhir_id = self.get_fhir_id("Specimen", sample_id)
                    if sample_fhir_id is None:
                        raise NonExistentResourceException(
                            f"Cannot upload Collection. Sample with (organizational) identifier: "
                            f"{sample_id} is not present in the blaze store.")
                    sample_fhir_ids.append(sample_fhir_id)
        collection_bundle = collection.build_bundle_for_upload(managing_biobank_fhir_id, sample_fhir_ids)
        response = self._session.post(f"{self._blaze_url}", json=collection_bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        response_json = response.json()
        return self.__get_id_from_bundle_response(response_json, "Group")

    def update_collection(self, collection: Collection) -> str:
        """
        update collection resource that is already present in the blaze store.
        :param collection: collection to be updated
        :return: fhir id of the collection
        """
        if not self.is_resource_present_in_blaze("Group", collection.identifier, "identifier"):
            raise NonExistentResourceException(f"cannot update collection. Collection with identifier "
                                               f"{collection.identifier} is not present in the blaze store")
        collection_fhir_id = self.get_fhir_id("Group", collection.identifier)
        existing_collection = self.build_collection_from_json(collection_fhir_id)
        if collection == existing_collection:
            return collection_fhir_id
        existing_collection.name = collection.name
        existing_collection.managing_collection_org_id = collection.managing_collection_org_id
        existing_collection.inclusion_criteria = collection.inclusion_criteria

        collection_organization = collection.collection_organization
        collection_organization._collection_org_fhir_id = existing_collection.collection_organization. \
            collection_org_fhir_id
        collection_organization._managing_biobank_fhir_id = existing_collection.collection_organization. \
            managing_biobank_fhir_id
        collection_organization_fhir = collection_organization.add_fhir_id_to_collection_organization(
            collection_organization.to_fhir())

        self._update_fhir_resource("Organization", collection_organization.collection_org_fhir_id,
                                   collection_organization_fhir.as_json())

        collection_to_update = existing_collection.add_fhir_id_to_collection(existing_collection.to_fhir())

        self._update_fhir_resource("Group", collection_fhir_id, collection_to_update.as_json())
        return collection_fhir_id

    def _upload_juristic_person(self, juristic_person: _JuristicPerson) -> str:
        """
        Upload a juristic person (organization resource) to blaze.
        :param juristic_person: juristic_person resource to upload
         :raises: HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        :return: the fhir id of uploaded juristic person
        """
        response = self._session.post(f"{self._blaze_url}/Organization", json=juristic_person.to_fhir().as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.json()["id"]

    def upload_network(self, network: Network) -> str:
        """
        Upload network to blaze (as network is made of Network and Network Organization,
        two resources are uploaded via bundle.)
        :param network: Network Object
        :return: network fhir id
        """
        biobank_members_fhir_ids = network.members_biobanks_fhir_ids
        collection_members_fhir_ids = network.members_collections_fhir_ids

        biobank_ids = network.members_biobanks_ids or []
        if biobank_members_fhir_ids is None:
            biobank_members_fhir_ids = []
            for biobank_member_id in biobank_ids:
                member_fhir_id = self.get_fhir_id("Organization", biobank_member_id)
                if member_fhir_id is None:
                    raise NonExistentResourceException(
                        f"Cannot upload Network. Biobank with (organizational) identifier: "
                        f"{biobank_member_id} is not present in the blaze store.")
                biobank_members_fhir_ids.append(member_fhir_id)

        collection_ids = network.members_collections_ids or []
        if collection_members_fhir_ids is None:
            collection_members_fhir_ids = []
            for collection_member_id in collection_ids:
                member_fhir_id = self.get_fhir_id("Group", collection_member_id)
                if member_fhir_id is None:
                    raise NonExistentResourceException(
                        f"Cannot upload Network. Collection with (organizational) identifier: "
                        f"{collection_member_id} is not present in the blaze store.")
                collection_members_fhir_ids.append(member_fhir_id)

        juristic_person_fhir_id = None
        juristic_person = self._get_juristic_person_organization_by_name(
            network.network_organization.juristic_person.name)
        if juristic_person is not None:
            juristic_person_fhir_id = juristic_person.get("id", None)
        network_bundle = network.build_bundle_for_upload(juristic_person_fhir_id, collection_members_fhir_ids,
                                                         biobank_members_fhir_ids)
        response = self._session.post(f"{self._blaze_url}", json=network_bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        response_json = response.json()
        return self.__get_id_from_bundle_response(response_json, "Group")

    def update_network(self, network: Network) -> str:
        """
        Update network resource that is already present in the blaze store
        :param network: network to be updated
        :return: fhir id of the network
        """
        if not self.is_resource_present_in_blaze("Group", network.identifier, "identifier"):
            raise NonExistentResourceException(f"cannot update network. Network with identifier {network.identifier} "
                                               f"is not present in the blaze store")
        network_fhir_id = self.get_fhir_id("Group", network.identifier)
        existing_network = self.build_network_from_json(network_fhir_id)
        if existing_network == network:
            return network_fhir_id
        existing_network.name = network.name
        existing_network.managing_network_org_id = network.managing_network_org_id
        existing_network.members_biobanks_ids = network.members_biobanks_ids
        existing_network.members_collections_ids = network.members_collections_ids

        network_organization = network.network_organization
        network_organization._network_org_fhir_id = existing_network.network_organization.network_org_fhir_id
        network_organization_fhir = network_organization.add_fhir_id_to_network(
            network_organization.to_fhir(existing_network.network_organization.juristic_person.fhir_id))

        self._update_fhir_resource("Organization", network_organization.network_org_fhir_id,
                                   network_organization_fhir.as_json())
        network_to_update = existing_network.add_fhir_id_to_network(existing_network.to_fhir())

        self._update_fhir_resource("Group", network_fhir_id, network_to_update.as_json())
        return network_fhir_id

    def build_donor_from_json(self, donor_fhir_id: str) -> SampleDonor:
        """Build Donor Object from json representation
        :param donor_fhir_id: FHIR ID of the Patient resource
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        :return SampleDonor Object"""
        if not self.is_resource_present_in_blaze("Patient", donor_fhir_id):
            raise NonExistentResourceException(f"Patient with fhir id {donor_fhir_id} is not present in blaze store")
        donor_json = self.get_fhir_resource_as_json("Patient", donor_fhir_id)
        donor = SampleDonor.from_json(donor_json)
        return donor

    def build_sample_from_json(self, sample_fhir_id: str) -> Sample:
        """Build Sample Object from json representation
        :param sample_fhir_id: FHIR ID of the Specimen resource
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        :return Sample Object"""
        if not self.is_resource_present_in_blaze("Specimen", sample_fhir_id):
            raise NonExistentResourceException(f"Sample with FHIR ID {sample_fhir_id} is not present in blaze store")

        observation_fhir_ids = self._get_observation_fhir_ids_belonging_to_sample(sample_fhir_id)

        sample_json = self.get_fhir_resource_as_json("Specimen", sample_fhir_id)
        observation_jsons = []
        for observation_fhir_id in observation_fhir_ids:
            observation_jsons.append(self.get_fhir_resource_as_json("Observation", observation_fhir_id))
        donor_fhir_id = parse_reference_id(get_nested_value(sample_json, ["subject", "reference"]))
        donor_id = self.get_identifier_by_fhir_id("Patient", donor_fhir_id)
        sample = Sample.from_json(sample_json, observation_jsons, donor_id)
        return sample

    def _build_observation_from_json(self, observation_fhir_id: str) -> _Observation:
        """Build Observation Object from json representation
        :param observation_fhir_id: FHIR ID of the Observation resource
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        :return Observation Object"""
        if not self.is_resource_present_in_blaze("Observation", observation_fhir_id):
            raise NonExistentResourceException(
                f"Observation with FHIR ID {observation_fhir_id} is not present in blaze store")
        observation_json = self.get_fhir_resource_as_json("Observation", observation_fhir_id)
        patient_fhir_id = parse_reference_id(get_nested_value(observation_json, ["subject", "reference"]))
        sample_fhir_id = parse_reference_id(get_nested_value(observation_json, ["specimen", "reference"]))
        patient_identifier = self.get_identifier_by_fhir_id("Patient", patient_fhir_id)
        sample_identifier = self.get_identifier_by_fhir_id("Specimen", sample_fhir_id)
        observation = _Observation.from_json(observation_json, patient_identifier, sample_identifier)
        return observation

    def build_condition_from_json(self, condition_fhir_id: str) -> Condition:
        """Build Condition object from json representation
        :param condition_fhir_id: FHIR ID of the Condition resource
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        :return Condition Object"""
        if not self.is_resource_present_in_blaze("Condition", condition_fhir_id):
            raise NonExistentResourceException(
                f"Condition with FHIR ID {condition_fhir_id} is not present in blaze store")
        condition_json = self.get_fhir_resource_as_json("Condition", condition_fhir_id)
        patient_fhir_id = parse_reference_id(get_nested_value(condition_json, ["subject", "reference"]))
        patient_identifier = self.get_identifier_by_fhir_id("Patient", patient_fhir_id)
        condition = Condition.from_json(condition_json, patient_identifier)
        return condition

    def build_collection_from_json(self, collection_fhir_id: str) -> Collection:
        """Build a collection object from a json representation.
        Does not add samples which are alredy deleted from blaze
        :param collection_fhir_id: FHIR ID of the Collection resource
        :return: Collection object
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        """
        if not self.is_resource_present_in_blaze("Group", collection_fhir_id):
            raise NonExistentResourceException(
                f"Collection with FHIR ID {collection_fhir_id} is not present in blaze store")

        collection_json = self.get_fhir_resource_as_json("Group", collection_fhir_id)

        collection_org_fhir_id = parse_reference_id(
            get_nested_value(collection_json, ["managingEntity", "reference"]))
        collection_org_json = self.get_fhir_resource_as_json("Organization", collection_org_fhir_id)

        managing_biobank_fhir_id = parse_reference_id(get_nested_value(collection_org_json, ["partOf", "reference"]))
        managing_biobank_identifier = self.get_identifier_by_fhir_id("Organization", managing_biobank_fhir_id)

        already_present_sample_fhir_ids = self.__get_all_sample_fhir_ids_belonging_to_collection(collection_fhir_id)
        only_existing_samples = list(
            filter(lambda s: self.is_resource_present_in_blaze("Specimen", s), already_present_sample_fhir_ids))

        already_present_sample_ids = [self.get_identifier_by_fhir_id("Specimen", sample_fhir_id) for sample_fhir_id in
                                      only_existing_samples]

        collection = Collection.from_json(collection_json, collection_org_json, managing_biobank_identifier,
                                          already_present_sample_ids)
        collection._sample_fhir_ids = only_existing_samples
        return collection

    def _build_collection_organization_from_json(self, collection_organization_fhir_id: str) -> _CollectionOrganization:
        """Build a CollectionOrganization object from a json representation
        :param collection_organization_fhir_id: FHIR ID of the collection resource
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        :return CollectionOrganization Object"""
        if not self.is_resource_present_in_blaze("Organization", collection_organization_fhir_id):
            raise NonExistentResourceException(
                f"CollectionOrganization with FHIR ID {collection_organization_fhir_id} is not present in blaze store")
        collection_org_json = self.get_fhir_resource_as_json("Organization", collection_organization_fhir_id)
        managing_biobank_fhir_id = parse_reference_id(get_nested_value(collection_org_json, ["partOf", "reference"]))
        managing_biobank_identifier = self.get_identifier_by_fhir_id("Organization", managing_biobank_fhir_id)
        collection_organization = _CollectionOrganization.from_json(collection_org_json, managing_biobank_identifier)
        return collection_organization

    def build_network_from_json(self, network_fhir_id: str) -> Network:
        """Build a Network object form a json representation
        :param network_fhir_id: FHIR ID of the network resource
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        :return Network Object"""

        if not self.is_resource_present_in_blaze("Group", network_fhir_id):
            raise NonExistentResourceException(f"Network with FHIR ID {network_fhir_id} is not present in blaze store")
        network_json = self.get_fhir_resource_as_json("Group", network_fhir_id)

        network_org_fhir_id = parse_reference_id(
            get_nested_value(network_json, ["managingEntity", "reference"]))

        network_org_json = self.get_fhir_resource_as_json("Organization", network_org_fhir_id)

        juristic_person_fhir_id = parse_reference_id(get_nested_value(network_org_json, ["partOf", "reference"]))
        juristic_person_json = self.get_fhir_resource_as_json("Organization", juristic_person_fhir_id)

        collection_fhir_ids, biobank_fhir_ids = self.__get_all_members_belonging_to_network(network_json)
        collection_identifiers = [self.get_identifier_by_fhir_id("Group", collection_fhir_id) for collection_fhir_id in
                                  collection_fhir_ids]
        biobank_identifiers = [self.get_identifier_by_fhir_id("Organization", biobank_fhir_id) for biobank_fhir_id in
                               biobank_fhir_ids]
        network = Network.from_json(network_json, network_org_json, juristic_person_json, collection_identifiers,
                                    biobank_identifiers)
        return network

    def _build_network_org_from_json(self, network_org_fhir_id: str) -> _NetworkOrganization:
        """Build a NetworkOrganization object from a json representation
        :param network_org_fhir_id: FHIR ID of the network organization resource
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        :return NetworkOrganisation object"""
        if not self.is_resource_present_in_blaze("Organization", network_org_fhir_id):
            raise NonExistentResourceException(
                f"NetworkOrganization with FHIR ID {network_org_fhir_id} is not present in blaze store")
        network_org_json = self.get_fhir_resource_as_json("Organization", network_org_fhir_id)
        juristic_person_fhir_id = parse_reference_id(get_nested_value(network_org_json, ["partOf", "reference"]))
        juristic_person_json = self.get_fhir_resource_as_json("Organization", juristic_person_fhir_id)
        network_org = _NetworkOrganization.from_json(network_org_json, juristic_person_json)
        return network_org

    def build_biobank_from_json(self, biobank_fhir_id: str) -> Biobank:
        """Build a Biobank object from a json representation
        :param biobank_fhir_id: FHIR ID of the biobank resource
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        :return Biobank object"""
        if not self.is_resource_present_in_blaze("Organization", biobank_fhir_id):
            raise NonExistentResourceException(f"Biobank with FHIR ID {biobank_fhir_id} is not present in blaze store")
        biobank_json = self.get_fhir_resource_as_json("Organization", biobank_fhir_id)
        juristic_person_fhir_id = parse_reference_id(get_nested_value(biobank_json, ["partOf", "reference"]))
        juristic_person_json = self.get_fhir_resource_as_json("Organization", juristic_person_fhir_id)
        biobank = Biobank.from_json(biobank_json, juristic_person_json)
        return biobank

    def add_already_present_samples_to_existing_collection(self, sample_fhir_ids: list[str],
                                                           collection_fhir_id: str) -> bool:
        """Add samples already present in blaze to the collection
        :param sample_fhir_ids: FHIR IDs of samples to add to collection
        :param collection_fhir_id: FHIR ID of collection
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        :return: Bool indicating outcome of this operation"""
        collection = self.build_collection_from_json(collection_fhir_id)
        sample_generator_for_characteristics = (self.build_sample_from_json(sample_fhir_id) for sample_fhir_id in
                                                sample_fhir_ids)

        collection = self.__update_collection_characteristics_from_samples(sample_generator_for_characteristics,
                                                                           collection)
        already_present_samples_set = set(collection.sample_fhir_ids)
        for sample_fhir_id in sample_fhir_ids:
            if sample_fhir_id not in already_present_samples_set:
                already_present_samples_set.add(sample_fhir_id)
        collection._sample_fhir_ids = list(already_present_samples_set)
        collection = collection.add_fhir_id_to_collection(collection.to_fhir())
        return self._update_fhir_resource("Group", collection_fhir_id, collection.as_json())

    def update_collection_values(self, collection_fhir_id) -> bool:
        """Recalculate characteristics of a collection.
        :param collection_fhir_id: FHIR ID of collection
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        :return: Bool indicating if the collection was updated or not"""
        collection = self.build_collection_from_json(collection_fhir_id)
        sample_fhir_ids = collection.sample_fhir_ids
        present_samples = (self.build_sample_from_json(sample_fhir_id) for sample_fhir_id in collection.sample_fhir_ids)
        collection._sample_fhir_ids = []
        collection.age_range_low = None
        collection.age_range_high = None
        collection.storage_temperatures = []
        collection.material_types = []
        collection.genders = []
        collection.diagnoses = []
        collection.number_of_subjects = 0
        collection = self.__update_collection_characteristics_from_samples(present_samples, collection)
        collection._sample_fhir_ids = sample_fhir_ids
        collection_fhir = collection.add_fhir_id_to_collection(collection.to_fhir())
        return self._update_fhir_resource("Group", collection.collection_fhir_id, collection_fhir.as_json())

    def __update_collection_characteristics_from_samples(self, samples: Generator[Sample, Any, None],
                                                         collection: Collection) -> Collection:
        """update the characteristics for collection with new values from the samples.
        :param samples: the samples to calculate the characteristics from
        :param collection_fhir_id: the fhir id of the collection
        :return: updated collection object
        :raises HTTPError: if the request to blaze fails
        :raises NonExistentResourceException: if the resource cannot be found
        """
        already_present_samples = (self.build_sample_from_json(sample_fhir_id) for sample_fhir_id in
                                   collection.sample_fhir_ids)
        donor_fhir_ids = set([sample.subject_fhir_id for sample in already_present_samples])
        count_of_new_subjects = 0
        for sample in samples:
            if sample.donor_identifier not in donor_fhir_ids:
                count_of_new_subjects += 1
                donor_fhir_ids.add(sample.donor_identifier)
            donor = self.build_donor_from_json(sample.subject_fhir_id)
            sample_material_type = get_material_type_from_detailed_material_type(sample.material_type)
            if donor.gender not in collection.genders:
                collection.genders.append(donor.gender)
            if sample.storage_temperature is not None and \
                    sample.storage_temperature not in collection.storage_temperatures:
                collection.storage_temperatures.append(sample.storage_temperature)
            if sample_material_type is not None and sample_material_type not in collection.material_types:
                collection.material_types.append(sample_material_type)
            sample_diagnoses = [diag_with_date[0] for diag_with_date in
                                sample.diagnoses_icd10_code_with_observed_datetime]
            for diagnosis in sample_diagnoses:
                if diagnosis is not None and diagnosis not in collection.diagnoses:
                    collection.diagnoses.append(diagnosis)
            diag_observed_at = [diag_with_date[1] for diag_with_date in
                                sample.diagnoses_icd10_code_with_observed_datetime if diag_with_date[1] is not None]
            ages_at_diagnosis = self.__get_age_at_the_time_of_diagnosis(diag_observed_at, donor.donor_fhir_id)
            for age in ages_at_diagnosis:
                if collection.age_range_low is None:
                    collection.age_range_low = age
                else:
                    collection.age_range_low = min(age, collection.age_range_low)
                if collection.age_range_high is None:
                    collection.age_range_high = age
                else:
                    collection.age_range_high = max(age, collection.age_range_high)
        if collection.number_of_subjects is None:
            collection.number_of_subjects = count_of_new_subjects
        else:
            collection.number_of_subjects += count_of_new_subjects
        return collection

    def _get_juristic_person_organization_by_name(self, name: str) -> dict | None:
        """
        Get juristic_person in json representation with specified name, if such exists
        :param name: name of the juristic person
        :raises HTTPError: if the request to blaze fails
        :return: json representation of juristic person
        """
        response = self._session.get(f"{self._blaze_url}/Organization",
                                     params={
                                         "name": name
                                     })
        self.__raise_for_status_extract_diagnostics_message(response)
        response_json = response.json()
        if response_json.get("entry") is None:
            return None
        return get_nested_value(response_json, ["entry", 0, "resource"])

    def get_collection_fhir_id_by_sample_fhir_identifier(self, sample_fhir_id: str) -> str | None:
        """Get Collection FHIR id which contains provided sample FHIR ID, if there is one
        :param sample_fhir_id: FHIR ID of the sample
        :return: collection FHIR id if there is collection which contains this sample, None otherwise"""
        return self.__get_group_fhir_id_by_resource_fhir_identifier(sample_fhir_id)

    def get_network_fhir_id_by_member_fhir_identifier(self, member_fhir_id: str) -> str | None:
        """Get Network FHIR id which contains provided member FHIR ID (either collection resource of biobank resource),
         if there is one
        :param member_fhir_id: FHIR ID of the member of network
        :return: network FHIR id if there is network which contains this member, None otherwise"""
        return self.__get_group_fhir_id_by_resource_fhir_identifier(member_fhir_id)

    def __get_group_fhir_id_by_resource_fhir_identifier(self, resource_fhir_id: str) -> str | None:
        """Get Group FHIR id which contains provided FHIR_ID or resource, if there is one
        :param resource_fhir_id: FHIR ID of the resource
        :return: Group resource FHIR ID if there is group which
        contains reference to resource_fhir_id, none otherwise"""
        response = self._session.get(f"{self._blaze_url}/Group",
                                     params={
                                         "groupMember": resource_fhir_id
                                     })
        self.__raise_for_status_extract_diagnostics_message(response)
        response_json = response.json()
        return get_nested_value(response_json, ["entry", 0, "resource", "id"])

    def __get_age_at_the_time_of_diagnosis(self, diagnosis_observed_datetime: list[datetime.datetime],
                                           donor_fhir_id: str) -> list[int]:
        """get age of donor at the time that the diagnosis was set"""
        ages_at_diagnosis = []

        donor = self.build_donor_from_json(donor_fhir_id)
        if donor.date_of_birth is None:
            return ages_at_diagnosis
        donor_birthdate = donor.date_of_birth

        for observed_datetime in diagnosis_observed_datetime:
            age_at_diagnosis = observed_datetime.year - donor_birthdate.year
            ages_at_diagnosis.append(age_at_diagnosis)
        return ages_at_diagnosis

    def delete_donor(self, donor_fhir_id: str, part_of_bundle: bool = False) -> list[BundleEntry] | bool:
        """Delete a donor from blaze.
        BEWARE: Deleting a donor will also delete all related samples and diagnosis reports.
        :param donor_fhir_id: the fhir id of the donor to delete
        :param part_of_bundle: bool indicating if this operation is part of larger bundle or not
        :return: if part_of_bundle = True, this function returns list of BundleEntries to be using in a larger Bundle.
        otherwise, it will create its own bundle, and return True if deletion was successful, False otherwise
        :raises HTTPError: if the request to blaze fails
        """
        entries = []
        if not self.is_resource_present_in_blaze("Patient", donor_fhir_id):
            raise NonExistentResourceException(
                f"Cannot delete Donor with FHIR id {donor_fhir_id} because donor is not present in the blaze store.")
        patient_entry = self.__create_delete_bundle_entry("Patient", donor_fhir_id)
        entries.append(patient_entry)
        sample_fhir_ids = self.__get_all_sample_fhir_ids_belonging_to_patient(donor_fhir_id)
        delete_from_collection = self.__delete_sample_references_from_collections(sample_fhir_ids)
        if not delete_from_collection:
            if part_of_bundle:
                return []
            return False
        condition_fhir_id = self.__get_condition_fhir_id_by_donor_identifier(donor_fhir_id)
        for sample_fhir_id in sample_fhir_ids:
            sample_entries = self.delete_sample(sample_fhir_id, True, True)
            entries.extend(sample_entries)
        if condition_fhir_id is not None:
            condition_entries = self.delete_condition(condition_fhir_id, True)
            entries.extend(condition_entries)
        if part_of_bundle:
            return entries
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 204

    def __delete_sample_references_from_collections(self, sample_fhir_ids: list[str]) -> bool:
        """
        :param sample_fhir_ids:
        :return:
        """
        entries = []
        collection_sample_fhir_ids_map = {}
        for sample_fhir_id in sample_fhir_ids:
            collection_fhir_id = self.get_collection_fhir_id_by_sample_fhir_identifier(sample_fhir_id)
            if collection_fhir_id is None:
                continue
            if collection_fhir_id not in collection_sample_fhir_ids_map:

                collection_sample_fhir_ids_map[collection_fhir_id] = set()
                collection_sample_fhir_ids_map[collection_fhir_id].add(sample_fhir_id)
            else:
                collection_sample_fhir_ids_map[collection_fhir_id].add(sample_fhir_id)
        for collection_fhir_id, sample_fhir_ids_set in collection_sample_fhir_ids_map.items():
            updated_collection = self.__delete_samples_from_collection(collection_fhir_id, list(sample_fhir_ids_set))
            entries.append(self.__create_bundle_entry_for_updating_collection(updated_collection))
        if entries is None:
            return True
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return 200 <= response.status_code < 300

    def delete_condition(self, condition_fhir_id: str, part_of_bundle: bool = False) -> list[BundleEntry] | bool:
        """Delete a condition from blaze.
        :param condition_fhir_id: the fhir id of the condition to delete
        :param part_of_bundle: bool indicating if this operation is part of larger bundle or not
        :return: if part_of_bundle = True, this function returns list of BundleEntries to be using in a larger Bundle.
        otherwise, it will create its own bundle, and return True if deletion was successful, False otherwise
        :raises HTTPError: if the request to blaze fails
        """
        entries = []
        if not self.is_resource_present_in_blaze("Condition", condition_fhir_id):
            raise NonExistentResourceException(
                f"Cannot delete Condition with FHIR id {condition_fhir_id} because "
                f"condition is not present in the blaze store.")
        condition_entry = self.__create_delete_bundle_entry("Condition", condition_fhir_id)
        entries.append(condition_entry)
        if part_of_bundle:
            return entries
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 204

    def delete_sample(self, sample_fhir_id: str, part_of_bundle: bool = False,
                      part_of_deleting_patient: bool = False) -> list[BundleEntry] | bool:
        """Delete a sample from blaze. BEWARE: Deleting a sample will also delete all related diagnosis reports and
        observations.
        :param sample_fhir_id: the fhir id of the sample to delete
        :param part_of_bundle: bool indicating if this operation is part of larger bundle or not
        :param part_of_deleting_patient: bool indicating if deleting sample is part of
        deleting patient(and his condition), or not.
        :return: if part_of_bundle = True, this function returns list of BundleEntries to be using in a larger Bundle.
        otherwise, it will create its own bundle, and return True if deletion was successful, False otherwise
        :raises HTTPError: if the request to blaze fails
        """
        entries = []
        if not self.is_resource_present_in_blaze("Specimen", sample_fhir_id):
            raise NonExistentResourceException(
                f"Cannot delete Sample with FHIR id {sample_fhir_id} because"
                f"sample is not present in the blaze store.")
        specimen_entry = self.__create_delete_bundle_entry("Specimen", sample_fhir_id)
        entries.append(specimen_entry)
        if not part_of_deleting_patient:
            self.__delete_sample_references_from_collections([sample_fhir_id])
        observations_linked_to_sample_fhir_ids = self._get_observation_fhir_ids_belonging_to_sample(sample_fhir_id)
        set_observations_linked_to_sample = set(observations_linked_to_sample_fhir_ids)
        observation_fhir_ids = self._get_observation_fhir_ids_belonging_to_sample(sample_fhir_id)
        for observation_fhir_id in observation_fhir_ids:
            if observation_fhir_id not in set_observations_linked_to_sample:
                observation_entries = self._delete_observation(observation_fhir_id, True)
                entries.extend(observation_entries)
        for observation_fhir_id in observations_linked_to_sample_fhir_ids:
            observation_entries = self._delete_observation(observation_fhir_id, True)
            entries.extend(observation_entries)
        if part_of_bundle:
            return entries
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 204

    def _delete_observation(self, observation_fhir_id: str, part_of_bundle: bool = False) -> list[BundleEntry] | bool:
        """Delete an observation from blaze.
        :param observation_fhir_id: the fhir id of the observation to delete
        :param part_of_bundle: bool indicating if this operation is part of larger bundle or not
        :return: if part_of_bundle = True, this function returns list of BundleEntries to be using in a larger Bundle.
        otherwise, it will create its own bundle, and return True if deletion was successful, False otherwise
        :raises HTTPError: if the request to blaze fails
        """
        entries = []
        if not self.is_resource_present_in_blaze("Observation", observation_fhir_id):
            raise NonExistentResourceException(
                f"Cannot delete Observation with FHIR id {observation_fhir_id} "
                f"because observation is not present in the blaze store.")
        entry = self.__create_delete_bundle_entry("Observation", observation_fhir_id)
        entries.append(entry)
        if part_of_bundle:
            return entries
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 204

    def delete_collection(self, collection_fhir_id: str, part_of_bundle=False) -> list[BundleEntry] | bool:
        """delete collection from the blaze store
        :param collection_fhir_id: FHIR ID of collection resource to be deleted
        :param part_of_bundle: bool indicating if this operation is part of larger bundle or not
        :return: if part_of_bundle = True, this function returns list of BundleEntries to be using in a larger Bundle.
        otherwise, it will create its own bundle, and return True if deletion was successful, False otherwise
        """
        entries = []
        collection_json = self.get_fhir_resource_as_json("Group", collection_fhir_id)
        collection_organization_fhir_id = parse_reference_id(
            get_nested_value(collection_json, ["managingEntity", "reference"]))
        collection_entries = self._delete_collection_organization(collection_organization_fhir_id, True)
        entries.extend(collection_entries)
        if part_of_bundle:
            return entries
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 204

    def _delete_collection(self, collection_fhir_id: str, part_of_bundle: bool = False) -> list[BundleEntry] | bool:
        """Delete collection from blaze.
        :param collection_fhir_id: FHIR ID of the collection to be deleted
        :param part_of_bundle: bool indicating if this operation is part of larger bundle or not
        :return: if part_of_bundle = True, this function returns list of BundleEntries to be using in a larger Bundle.
        otherwise, it will create its own bundle, and return True if deletion was successful, False otherwise """
        entries = []
        if not self.is_resource_present_in_blaze("Group", collection_fhir_id):
            raise NonExistentResourceException(
                f"Cannot delete Collection with FHIR ID {collection_fhir_id} "
                f"because collection is not present in the blaze store")
        collection_entry = self.__create_delete_bundle_entry("Group", collection_fhir_id)
        entries.append(collection_entry)
        network_group_fhir_id = self.__get_network_fhir_id_by_member(collection_fhir_id)
        if network_group_fhir_id is not None:
            self.__delete_member_reference_from_network(network_group_fhir_id, collection_fhir_id)
        if part_of_bundle:
            return entries
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 204

    def __delete_member_reference_from_network(self, network_fhir_id: str, member_fhir_id: str) -> bool:
        """Delete a collection reference from network
        :param network_fhir_id: FHIR ID of the network
        :param collection_fhir_id: FHIR ID of the collection to be deleted
        :return: True if the reference was deleted sucessfully, false otherwise"""
        network = self.build_network_from_json(network_fhir_id)
        if member_fhir_id in network.members_collections_fhir_ids:
            network.members_collections_fhir_ids.remove(member_fhir_id)
        if member_fhir_id in network.members_biobanks_fhir_ids:
            network.members_biobanks_fhir_ids.remove(member_fhir_id)
        update_network_fhir = network.add_fhir_id_to_network(network.to_fhir())
        return self._update_fhir_resource("Group", network_fhir_id, update_network_fhir.as_json())

    def __delete_samples_from_collection(self, collection_fhir_id: str, sample_fhir_ids: list[str]) -> Collection:
        collection = self.build_collection_from_json(collection_fhir_id)
        sample_fhir_ids_set = set(collection.sample_fhir_ids)
        for sample_fhir_id in sample_fhir_ids:
            if sample_fhir_id in sample_fhir_ids_set:
                sample_fhir_ids_set.remove(sample_fhir_id)
        collection._sample_fhir_ids = list(sample_fhir_ids_set)
        return collection

    def _delete_collection_organization(self, collection_organization_fhir_id: str, part_of_bundle: bool = False) \
            -> list[BundleEntry] | bool:
        """delete collection organization from blaze store. WARNING: deleting collection organization
        will result in deleting collection resource as well
        :param collection_organization_fhir_id: FHIR ID of collection organization resource to be deleted
        :param part_of_bundle: bool indicating if this operation is part of larger bundle or not
        :return: if part_of_bundle = True, this function returns list of BundleEntries to be using in a larger Bundle.
        otherwise, it will create its own bundle, and return True if deletion was successful, False otherwise """
        entries = []
        if not self.is_resource_present_in_blaze("Organization", collection_organization_fhir_id):
            raise NonExistentResourceException(f"Cannot delete CollectionOrganization with FHIR ID "
                                               f"{collection_organization_fhir_id} because this resource is not "
                                               f"present in the blaze store")
        collection_org_entry = self.__create_delete_bundle_entry("Organization", collection_organization_fhir_id)
        entries.append(collection_org_entry)
        collection_response = self._session.get(
            f"{self._blaze_url}/Group",
            params={
                "managing-entity": collection_organization_fhir_id
            })
        response_json = collection_response.json()
        if response_json["total"] != 0:
            for entry in response_json["entry"]:
                collection_fhir_id = get_nested_value(entry, ["resource", "id"])
                collection_entries = self._delete_collection(collection_fhir_id, True)
                entries.extend(collection_entries)
        if part_of_bundle:
            return entries
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 204

    def delete_network(self, network_fhir_id: str, part_of_bundle: bool = False) -> list[BundleEntry] | bool:
        """delete network from blaze store.
        :param network_fhir_id: FHIR ID of network resource to be deleted
        :param part_of_bundle: bool indicating if this operation is part of larger bundle or not
        :return: if part_of_bundle = True, this function returns list of BundleEntries to be using in a larger Bundle.
        otherwise, it will create its own bundle, and return True if deletion was successful, False otherwise """
        entries = []
        if not self.is_resource_present_in_blaze("Group", network_fhir_id):
            raise NonExistentResourceException(f"Cannot delete Network with FHIR ID {network_fhir_id} because "
                                               f"this resource is not present in the blaze store")
        network_json = self.get_fhir_resource_as_json("Group", network_fhir_id)
        network_org_fhir_id = parse_reference_id(get_nested_value(network_json, ["managingEntity", "reference"]))
        network_entries = self._delete_network_organization(network_org_fhir_id, True)
        entries.extend(network_entries)
        if part_of_bundle:
            return entries
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 204

    def _delete_network(self, network_fhir_id: str, part_of_bundle: bool = False) -> list[BundleEntry] | bool:
        """delete network from blaze store.
        :param network_fhir_id: FHIR ID of network resource to be deleted
        :param part_of_bundle: bool indicating if this operation is part of larger bundle or not
        :return: if part_of_bundle = True, this function returns list of BundleEntries to be using in a larger Bundle.
        otherwise, it will create its own bundle, and return True if deletion was successful, False otherwise """
        entries = []
        if not self.is_resource_present_in_blaze("Group", network_fhir_id):
            raise NonExistentResourceException(f"Cannot delete Network with FHIR ID {network_fhir_id} because "
                                               f"this resource is not present in the blaze store")
        network_entry = self.__create_delete_bundle_entry("Group", network_fhir_id)
        entries.append(network_entry)

        if part_of_bundle:
            return entries
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 204

    def _delete_network_organization(self, network_organization_fhir_id: str, part_of_bundle: bool = False) \
            -> list[BundleEntry] | bool:
        """delete network organization from blaze store. BEWARE: deleting network organization will
        result in deleting network resource as well
        :param network_organization_fhir_id: FHIR ID of network organization resource to be deleted
        :param part_of_bundle: bool indicating if this operation is part of larger bundle or not
        :return: if part_of_bundle = True, this function returns list of BundleEntries to be using in a larger Bundle.
        otherwise, it will create its own bundle, and return True if deletion was successful, False otherwise """
        entries = []
        if not self.is_resource_present_in_blaze("Organization", network_organization_fhir_id):
            raise NonExistentResourceException(f"Cannot delete Network Organization with FHIR ID"
                                               f" {network_organization_fhir_id} because this resource is not present "
                                               f"in the blaze store")
        network_org_entry = self.__create_delete_bundle_entry("Organization", network_organization_fhir_id)
        entries.append(network_org_entry)
        network_response = self._session.get(
            f"{self._blaze_url}/Group",
            params={
                "managing-entity": network_organization_fhir_id
            })
        response_json = network_response.json()
        if response_json["total"] != 0:
            for entry in response_json["entry"]:
                network_fhir_id = get_nested_value(entry, ["resource", "id"])
                network_entries = self._delete_network(network_fhir_id, True)
                entries.extend(network_entries)
        if part_of_bundle:
            return entries
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 204

    def delete_biobank(self, biobank_fhir_id: str, part_of_bundle: bool = False) -> list[BundleEntry] | bool:
        """delete biobank from blaze store. BEWARE: deleting biobank will result in
        deleting all connected collections and networks asw well
        :param biobank_fhir_id: FHIR ID of biobank resource to be deleted
        :param part_of_bundle: bool indicating if this operation is part of larger bundle or not
        :return: if part_of_bundle = True, this function returns list of BundleEntries to be using in a larger Bundle.
        otherwise, it will create its own bundle, and return True if deletion was successful, False otherwise """
        entries = []
        if not self.is_resource_present_in_blaze("Organization", biobank_fhir_id):
            raise NonExistentResourceException(f"Cannot delete Biobank with FHIR ID"
                                               f" {biobank_fhir_id} because this resource is not present "
                                               f"in the blaze store")

        network_group_fhir_id = self.__get_network_fhir_id_by_member(biobank_fhir_id)
        if network_group_fhir_id is not None:
            self.__delete_member_reference_from_network(network_group_fhir_id, biobank_fhir_id)

        biobank_entry = self.__create_delete_bundle_entry("Organization", biobank_fhir_id)
        entries.append(biobank_entry)
        response = self._session.get(f"{self._blaze_url}/Organization",
                                     params={
                                         "partof": biobank_fhir_id
                                     })
        response_json = response.json()
        if response_json["total"] != 0:
            for entry in response_json["entry"]:
                resource = entry["resource"]
                resource_type: str = get_nested_value(resource, ["meta", "profile", 0])
                if resource_type.endswith("collection-organization"):
                    entries.extend(self._delete_collection_organization(resource["id"], True))
                else:
                    entries.extend(self._delete_network_organization(resource["id"], True))
        if part_of_bundle:
            return entries
        bundle = self.__create_bundle(entries)
        response = self._session.post(f"{self._blaze_url}", json=bundle.as_json())
        self.__raise_for_status_extract_diagnostics_message(response)
        return response.status_code == 200 or response.status_code == 204

    def delete_all_resources(self, biobank_id: str):
        """Just as name says.DELETES EVERYTHING!!!"""

        biobank_fhir_id = self.get_fhir_id("Organization", biobank_id)
        biobank_json = self.get_fhir_resource_as_json("Organization", biobank_fhir_id)
        juristic_person_reference = get_nested_value(biobank_json or {}, ["partOf", "reference"])
        juristic_person_fhir_id = None
        if juristic_person_reference is not None:
            juristic_person_fhir_id = parse_reference_id(juristic_person_reference)
        deleted_biobank = self.delete_biobank(biobank_fhir_id)
        if not deleted_biobank:
            return False
        response = self._session.get(f"{self._blaze_url}/Patient")
        while response.status_code == 200:
            response_json = response.json()
            for entry in response_json.get("entry", []):
                patient_id = get_nested_value(entry, ["resource", "id"])
                deleted_patient = self.delete_donor(patient_id)
                if not deleted_patient:
                    return False
            links = response_json.get("link", [])
            link_relations = [link.get("relation") for link in links]
            if "next" not in link_relations:
                break
            next_index = link_relations.index("next")
            url = links[next_index].get("url")
            url_after_fhir = url.find("/fhir")
            if url_after_fhir == -1:
                break
            next_link = self._blaze_url + url[url_after_fhir + len("/fhir"):]
            response = self._session.get(url=next_link)
        if juristic_person_fhir_id is not None:
            self._delete_juristic_person_if_unused(juristic_person_fhir_id)
        return True

    def _delete_juristic_person_if_unused(self, juristic_person_fhir_id: str) -> bool:
        """Delete a juristic person Organization, unless other organizations still belong to it.
        :param juristic_person_fhir_id: FHIR ID of the juristic person resource
        :return: True if the resource was deleted, False otherwise"""
        if not self.is_resource_present_in_blaze("Organization", juristic_person_fhir_id):
            return False
        response = self._session.get(f"{self._blaze_url}/Organization",
                                     params={
                                         "partof": juristic_person_fhir_id
                                     })
        self.__raise_for_status_extract_diagnostics_message(response)
        if response.json().get("entry") is not None:
            return False
        delete_response = self._session.delete(f"{self._blaze_url}/Organization/{juristic_person_fhir_id}")
        self.__raise_for_status_extract_diagnostics_message(delete_response)
        return True

    @staticmethod
    def __get_all_members_belonging_to_network(network_json: dict) -> tuple[list[str], list[str]]:
        """Get all members which belong to the network
        :param network_json: json representation of network
        :return tuple containing list of collection FHIR IDs,
        and list of organization FHIR ids belonging to this network"""
        collection_fhir_ids = []
        biobank_fhir_ids = []
        for extension in network_json.get("extension", []):
            if extension["url"] == "http://hl7.org/fhir/5.0/StructureDefinition/extension-Group.member.entity":
                resource_type, reference = get_nested_value(extension, ["valueReference", "reference"]).split("/")
                if resource_type == "Group":
                    collection_fhir_ids.append(reference)
                else:
                    biobank_fhir_ids.append(reference)
        return collection_fhir_ids, biobank_fhir_ids

    def __get_network_fhir_id_by_member(self, group_member_fhir_id: str) -> str | None:
        """
        Returns FHIR id of network, that a member is part of, if there is any, None otherwise
        :param group_member_fhir_id: fhir id of member to search by
        :return: FHIR id of Network | None
        """
        response = self._session.get(f"{self._blaze_url}/Group",
                                     params={
                                         "groupMember": group_member_fhir_id
                                     })
        self.__raise_for_status_extract_diagnostics_message(response)
        response_json = response.json()
        if response_json.get("total") == 0:
            return None
        return get_nested_value(response_json, ["entry", 0, "resource", "id"])

    def __get_all_sample_fhir_ids_belonging_to_collection(self, collection_fhir_id: str) -> list[str]:
        """Get all sample fhir ids which belong to collection.
        :param collection_fhir_id: id of collection from which we want to get samples.
        :raises: HTTPError if the requests to blaze fails
        :return: list of FHIR ids of samples that belong to this collection."""
        sample_fhir_ids = []
        collection_identifier = self.get_identifier_by_fhir_id("Group", collection_fhir_id)
        next_url = self._session.get(f"{self._blaze_url}/Specimen",
                                     params={
                                         "sample-collection-id": collection_identifier
                                     })
        while next_url.status_code == 200:
            samples_json = next_url.json()
            for sample_json in samples_json.get("entry", []):
                sample_fhir_id = get_nested_value(sample_json, ["resource", "id"])
                if sample_fhir_id is not None:
                    sample_fhir_ids.append(sample_fhir_id)
            links = samples_json.get("link", [])
            link_relations = [link.get("relation") for link in links]
            if "next" not in link_relations:
                break
            next_index = link_relations.index("next")
            url = links[next_index].get("url")
            url_after_fhir = url.find("/fhir")
            if url_after_fhir == -1:
                break
            next_link = self._blaze_url + url[url_after_fhir + len("/fhir"):]
            next_url = self._session.get(url=next_link)
        return sample_fhir_ids

    def __get_all_sample_fhir_ids_belonging_to_patient(self, patient_fhir_id: str) -> list[str]:
        """Get all sample fhir ids which belong to patient.
        :param patient_fhir_id: id of patient from which we want to get samples.
        :raises: HTTPError if the requests to blaze fails
        :return: list of FHIR ids of samples that belong to this patient."""
        sample_fhir_ids = []
        response = self._session.get(f"{self._blaze_url}/Specimen?patient={patient_fhir_id}")
        self.__raise_for_status_extract_diagnostics_message(response)
        response_json = response.json()
        if response_json["total"] == 0:
            return sample_fhir_ids
        for entry in response_json['entry']:
            sample_fhir_id = get_nested_value(entry["resource"], ["id"])
            sample_fhir_ids.append(sample_fhir_id)
        return sample_fhir_ids

    def __get_condition_fhir_id_by_donor_identifier(self, patient_identifier: str) -> str | None:
        response = self._session.get(f"{self._blaze_url}/Condition",
                                     params={
                                         "subject": patient_identifier
                                     })
        self.__raise_for_status_extract_diagnostics_message(response)
        response_json = response.json()
        if response_json["total"] == 0:
            return None
        return get_nested_value(response_json, ["entry", 0, "resource", "id"])

    @staticmethod
    def __raise_for_status_extract_diagnostics_message(response: Response):
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            try:
                error_details = response.json()
                if 'issue' in error_details:
                    for issue in error_details['issue']:
                        diagnostics = issue.get('diagnostics', 'No diagnostics available')
                        http_err.args = (f"{http_err.args[0]} - Diagnostics: {diagnostics}",)
            except ValueError:
                pass
            raise

    @staticmethod
    def __create_bundle(entries: list[BundleEntry]) -> Bundle:
        """Create a bundle used for deleting multiple FHIR resources in a transaction"""
        bundle = Bundle()
        bundle.type = "transaction"
        bundle.entry = entries
        return bundle

    @staticmethod
    def __create_delete_bundle_entry(resource_type: str, resource_fhir_id: str) -> BundleEntry:
        entry = BundleEntry()
        entry.request = BundleEntryRequest()
        entry.request.method = "DELETE"
        entry.request.url = f"{resource_type.capitalize()}/{resource_fhir_id}"
        return entry

    @staticmethod
    def __create_bundle_entry_for_updating_collection(collection: Collection) -> BundleEntry:
        collection_fhir = collection.add_fhir_id_to_collection(collection.to_fhir())
        collection_entry = BundleEntry()
        collection_entry.resource = collection_fhir
        collection_entry.request = BundleEntryRequest()
        collection_entry.request.method = "PUT"
        collection_entry.request.url = f"Group/{collection.collection_fhir_id}"
        return collection_entry

    def __get_id_from_bundle_response(self, response: dict, resource_type: str) -> str:
        for entry in response.get("entry", []):
            full_url: str = get_nested_value(entry, ["response", "location"])
            split_url = full_url.split("/")
            if resource_type in split_url:
                resource_type_index = split_url.index(resource_type)
                if resource_type_index + 1 < len(split_url):
                    return split_url[resource_type_index + 1]
