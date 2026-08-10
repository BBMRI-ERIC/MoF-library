import unittest

from miabis_model.util.config import FHIRConfig
from miabis_model.util.constants import DEFINITION_BASE_URL

IG_CANONICAL_ROOT = "https://fhir.bbmri-eric.eu"


class TestCanonicalUrls(unittest.TestCase):
    def test_base_url_constants_match_ig_root(self):
        self.assertEqual(IG_CANONICAL_ROOT, FHIRConfig.BASE_URL)
        self.assertEqual(IG_CANONICAL_ROOT, DEFINITION_BASE_URL)

    def test_sample_profile_matches_ig_canonical(self):
        self.assertEqual(f"{IG_CANONICAL_ROOT}/StructureDefinition/miabis-sample",
                         FHIRConfig.get_meta_profile_url("sample"))

    def test_sample_extensions_match_ig_canonical(self):
        self.assertEqual(
            f"{IG_CANONICAL_ROOT}/StructureDefinition/miabis-sample-collection-extension",
            FHIRConfig.get_extension_url("sample", "sample_collection_id"))
        self.assertEqual(
            f"{IG_CANONICAL_ROOT}/StructureDefinition/miabis-sample-storage-temperature-extension",
            FHIRConfig.get_extension_url("sample", "storage_temperature"))

    def test_detailed_sample_type_code_system_matches_ig_canonical(self):
        self.assertEqual(
            f"{IG_CANONICAL_ROOT}/CodeSystem/miabis-detailed-samply-type-cs",
            FHIRConfig.get_code_system_url("sample", "detailed_sample_type"))

    def test_biobank_description_extension_matches_ig_canonical(self):
        self.assertEqual(
            f"{IG_CANONICAL_ROOT}/StructureDefinition/miabis-organization-description-extension",
            FHIRConfig.get_extension_url("biobank", "description"))

    def test_storage_temperature_code_system_matches_ig_canonical(self):
        self.assertEqual(
            f"{IG_CANONICAL_ROOT}/CodeSystem/miabis-storage-temperature-cs",
            FHIRConfig.get_code_system_url("sample", "storage_temperature"))

    def test_gender_code_system_is_absolute_and_not_prefixed(self):
        # gender is an absolute HL7 URL and must not have BASE_URL prepended to it
        self.assertEqual("http://hl7.org/fhir/administrative-gender",
                         FHIRConfig.get_code_system_url("collection", "gender"))

    def test_relative_code_system_paths_are_still_prefixed(self):
        # counterpart to the test above: relative paths must still get BASE_URL
        self.assertEqual(
            f"{IG_CANONICAL_ROOT}/CodeSystem/miabis-collection-sample-type-cs",
            FHIRConfig.get_code_system_url("collection", "material_type"))

    def test_no_profile_or_extension_url_contains_fhir_segment(self):
        for dict_name in [name for name in dir(FHIRConfig) if name.endswith("_URLS")]:
            resource_name = dict_name[: -len("_URLS")].lower()
            profile_url = FHIRConfig.get_meta_profile_url(resource_name)
            if profile_url is not None:
                self.assertNotIn("/fhir/", profile_url)
            for extension_name in getattr(FHIRConfig, dict_name).get("extensions", {}):
                self.assertNotIn("/fhir/", FHIRConfig.get_extension_url(resource_name, extension_name))


if __name__ == "__main__":
    unittest.main()
