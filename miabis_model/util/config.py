class FHIRConfig:
    BASE_URL = "https://fhir.bbmri-eric.eu"

    MEMBER_V5_EXTENSION = "http://hl7.org/fhir/5.0/StructureDefinition/extension-Group.member.entity"
    DIAGNOSIS_CODE_SYSTEM = "http://hl7.org/fhir/sid/icd-10"

    DONOR_URLS = {
        "resource": "/Patient",
        "meta_profile": "/StructureDefinition/miabis-sample-donor",
        "extensions": {
            "dataset_type": "/StructureDefinition/miabis-dataset-type-extension"
        },
        "value_sets": {
            "dataset_type": "/ValueSet/miabis-dataset-type-vs"
        },
        "code_systems": {
            "dataset_type": "/CodeSystem/miabis-dataset-type-CS"
        }
    }

    SAMPLE_URLS = {
        "resource": "/Specimen",
        "meta_profile": "/StructureDefinition/miabis-sample",
        "extensions": {
            "storage_temperature": "/StructureDefinition/miabis-sample-storage-temperature-extension",
            "sample_collection_id": "/StructureDefinition/miabis-sample-collection-extension"
        },
        "value_sets": {
            "detailed_sample_type": "/ValueSet/miabis-detailed-sample-type-vs",
            "storage_temperature": "/ValueSet/miabis-storage-temperature-vs"
        },
        "code_systems": {
            "detailed_sample_type": "/CodeSystem/miabis-detailed-samply-type-cs",
            "storage_temperature": "/CodeSystem/miabis-storage-temperature-cs"
        }
    }

    OBSERVATION_URLS = {
        "resource": "/Observation",
        "meta_profile": "/StructureDefinition/miabis-observation",
        "value_sets": {
            "diagnosis": "/ValueSet/miabis-diagnosis-vs"
        }
    }

    DIAGNOSIS_REPORT_URLS = {
        "resource": "/DiagnosticReport",
        "meta_profile": "/StructureDefinition/miabis-diagnosis-report"
    }

    CONDITION_URLS = {
        "resource": "/Condition",
        "meta_profile": "/StructureDefinition/miabis-condition",
        "value_sets": {
            "diagnosis": "/ValueSet/miabis-diagnosis-vs"
        }
    }

    COLLECTION_URLS = {
        "resource": "/Group",
        "meta_profile": "/StructureDefinition/miabis-collection",
        "extensions": {
            "number_of_subjects": "/StructureDefinition/miabis-number-of-subjects-extension",
            "inclusion_criteria": "/StructureDefinition/miabis-inclusion-criteria-extension",
        },
        "value_sets": {},
        "code_systems": {
            "inclusion_criteria": "/CodeSystem/miabis-inclusion-criteria-cs",
            "characteristic": "/CodeSystem/miabis-characteristicCS",
            "gender": "http://hl7.org/fhir/administrative-gender",
            "storage_temperature": "/CodeSystem/miabis-storage-temperature-cs",
            "material_type": "/CodeSystem/miabis-collection-sample-type-cs",
        }
    }

    COLLECTION_ORGANIZATION_URLS = {
        "resource": "/Organization",
        "meta_profile": "/StructureDefinition/miabis-collection-organization",
        "extensions": {
            "dataset_type": "/StructureDefinition/miabis-collection-dataset-type-extension",
            "sample_source": "/StructureDefinition/miabis-sample-source-extension",
            "sample_collection_setting": "/StructureDefinition/miabis-sample-collection-setting-extension",
            "collection_design": "/StructureDefinition/miabis-collection-design-extension",
            "use_and_access": "/StructureDefinition/miabis-use-and-access-conditions-extension",
            "publications": "/StructureDefinition/miabis-publications-extension",
            "description": "/StructureDefinition/miabis-organization-description-extension"
        },
        "code_systems": {
            "dataset_type": "/CodeSystem/miabis-collection-dataset-typeCS",
            "sample_source": "/CodeSystem/miabis-sample-source-cs",
            "sample_collection_setting": "/CodeSystem/miabis-sample-collection-setting-cs",
            "collection_design": "/CodeSystem/miabis-collection-design-cs",
            "use_and_access": "/CodeSystem/miabis-use-and-access-conditions-cs"
        }
    }

    NETWORK_URLS = {
        "resource": "/Group",
        "meta_profile": "/StructureDefinition/miabis-network"
    }

    JURISTIC_PERSON_URLS = {
        "resource": "/Organization",
        "meta_profile": "/StructureDefinition/miabis-juristic-person"
    }

    NETWORK_ORGANIZATION_URLS = {
        "resource": "/Organization",
        "meta_profile": "/StructureDefinition/miabis-network-organization",
        "extensions": {
            "juristic_person": "/StructureDefinition/miabis-juristic-person-extension",
            "common_collaboration_topics": "/StructureDefinition/miabis-common-collaboration-topics-extension",
            "description": "/StructureDefinition/miabis-organization-description-extension"
        },
        "code_systems": {
            "common_collaboration_topics": "/CodeSystem/miabis-common-collaboration-topics-cs"
        }
    }

    BIOBANK_URLS = {
        "resource": "/Organization",
        "meta_profile": "/StructureDefinition/miabis-biobank",
        "extensions": {
            "infrastructural_capabilities": "/StructureDefinition/miabis-infrastructural-capabilities-extension",
            "organisational_capabilities": "/StructureDefinition/miabis-organisational-capabilities-extension",
            "bioprocessing_and_analysis_capabilities": "/StructureDefinition/miabis-bioprocessing-and-analytical-capabilities-extension",
            "quality_management_standard": "/StructureDefinition/miabis-quality-management-standard-extension",
            "juristic_person": "/StructureDefinition/miabis-juristic-person-extension",
            "description": "/StructureDefinition/miabis-organization-description-extension"
        },
        "code_systems": {
            "infrastructural_capabilities": "/CodeSystem/miabis-infrastructural-capabilities-cs",
            "organisational_capabilities": "/CodeSystem/miabis-organisational-capabilities-cs",
            "bioprocessing_and_analysis_capabilities": "/CodeSystem/miabis-bioprocessing-and-analytical-capabilities-cs",

        }

    }

    @classmethod
    def get_resource_path(cls, resource_name: str) -> str | None:
        resource_dict = getattr(cls, f"{resource_name.upper()}_URLS", None)
        if resource_dict:
            resource_path = resource_dict.get("resource", "")
            return resource_path
        return None

    @classmethod
    def get_meta_profile_url(cls, resource_name: str) -> str | None:
        resource_dict = getattr(cls, f"{resource_name.upper()}_URLS", None)
        if resource_dict:
            base_url = cls.BASE_URL
            meta_profile_path = resource_dict.get("meta_profile", "")
            return f"{base_url}{meta_profile_path}"
        return None

    @classmethod
    def get_extension_url(cls, resource_name: str, extension_name: str) -> str | None:
        resource_dict = getattr(cls, f"{resource_name.upper()}_URLS", None)
        if resource_dict:
            base_url = cls.BASE_URL
            extension_path = resource_dict.get("extensions", {}).get(extension_name)
            if extension_path is not None:
                return f"{base_url}{extension_path}"
        return None

    @classmethod
    def get_value_set_url(cls, resource_name: str, value_set_name: str) -> str | None:
        resource_dict = getattr(cls, f"{resource_name.upper()}_URLS", None)
        if resource_dict:
            base_url = cls.BASE_URL
            value_set_path = resource_dict.get("value_sets", {}).get(value_set_name)
            if value_set_path is not None:
                return f"{base_url}{value_set_path}"
        return None

    @classmethod
    def get_code_system_url(cls, resource_name: str, code_system_name: str) -> str | None:
        resource_dict = getattr(cls, f"{resource_name.upper()}_URLS", None)
        if resource_dict:
            base_url = cls.BASE_URL
            code_system_path = resource_dict.get("code_systems", {}).get(code_system_name)
            if code_system_path is not None:
                if code_system_path.startswith("http://") or code_system_path.startswith("https://"):
                    return code_system_path
                return f"{base_url}{code_system_path}"
        return None
