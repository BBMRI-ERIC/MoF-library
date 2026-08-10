#!/usr/bin/env python3
"""
Example: convert a CSV table into a MIABIS-on-FHIR Bundle using `miabis_model`.

A single, self-contained script that reads a delimited table and drives the
model classes (SampleDonor, Condition, Sample, Biobank, CollectionOrganization,
Collection) to build one FHIR R4 Bundle. Meant as a readable starting point you
copy and adapt -- for a full production ETL (CSV/XML/JSON inputs, value maps,
Blaze upload, incremental sync) see https://github.com/BBMRI-cz/fhir-module.

It emits the full MIABIS hierarchy so the Bundle is self-contained and can be
validated against the IG on its own (see examples/README.md):
    JuristicPerson (Organization)
      └─ Biobank (Organization)
           └─ CollectionOrganization (Organization)
                └─ Collection (Group)  ──member──▶ Specimen
    Patient ◀── Condition.subject, Specimen.subject

Every resource gets a UUID id, the bundle entry fullUrl is `urn:uuid:<id>`, and
links are `ResourceType/<id>`. Business identifiers (which may contain ':') stay
in `.identifier`, never in `id`.

The CONFIG block below is keyed to the sample schema in examples/sample_data.csv;
edit it to match YOUR columns, coded values, and organization metadata.

Setup:   pip install MIABIS-on-FHIR
Run:     python examples/csv_to_miabis.py examples/sample_data.csv -o bundle.json
Then optionally validate bundle.json against the IG (see examples/README.md).
"""

import argparse
import csv
import json
import sys
import uuid
from datetime import datetime

from miabis_model import (Sample, SampleDonor, Condition, Gender,
                          StorageTemperature, Biobank, Collection)
from miabis_model import _CollectionOrganization as CollectionOrganization

# ─────────────────────────────── CONFIG ────────────────────────────────────
COLUMNS = {
    "donor_id":         "patient_pseudonym",
    "sex":              "sex",
    "birth_year":       "birth_year",
    "sample_id":        "sample_ID",
    "material_type":    "sampling_type",
    "diagnosis":         "diagnosis",          # comma-separated ICD-10; linked to the sample
    "patient_diagnosis": "patient_diagnosis",  # comma-separated ICD-10; no sample for these
    "storage_temp":     "storage_temperature",
    "sampling_date":    "sampling_date",
    "diagnosis_date":   "date_of_diagnosis",
}

CSV_SEPARATOR   = ";"
DIAGNOSIS_SPLIT = ","
DATE_FORMAT     = "%d.%m.%Y"     # e.g. 16.10.2017
YEAR_FORMAT     = "%Y"           # birth_year is year-only

GENDER_MAP = {
    "f": Gender.FEMALE,
    "m": Gender.MALE,
}

STORAGE_TEMP_MAP = {
    "-20": StorageTemperature.TEMPERATURE_MINUS_18_TO_MINUS_35,
}

# Sample-level detailed type. Valid: WholeBlood, Serum, Plasma, DNA, RNA, Urine,
# Saliva, BuffyCoat, TissueFreshFrozen, TissueFixed, Other, ... (run to see full list)
MATERIAL_TYPE_MAP = {
    "blood-serum":  "Serum",
    "whole-blood":  "WholeBlood",
    "tissue-other": "Other",
}

# The Collection resource uses a COARSER material vocabulary than a Sample, e.g.:
# Blood, BuffyCoat, DNA, RNA, Plasma, Serum, TissueFrozen, TissueFFPE, Urine, Other, ...
COLLECTION_MATERIAL_MAP = {
    "Serum":      "Serum",
    "WholeBlood": "Blood",
    "Other":      "Other",
}

# Static org metadata for the parent hierarchy (all samples belong here).
COLLECTION_ID = "bbmri:example-collection-id"

JURISTIC_PERSON = {"id": "example-juristic-person", "name": "Example Juristic Person"}

BIOBANK = {
    "id": "bbmri-eric:ID:example-biobank",
    "name": "Example Biobank",
    "country": "CZ",
    "contact_name": "Jane",
    "contact_surname": "Doe",
    "contact_email": "contact@example.org",
    "description": "Example biobank generated from CSV.",
}

COLLECTION_ORG = {
    "id": "bbmri-eric:ID:example-collection-org",
    "name": "Example Collection Organization",
    "country": "CZ",
    "contact_name": "Jane",
    "contact_surname": "Doe",
    "contact_email": "contact@example.org",
    "description": "Example collection organization generated from CSV.",
}

COLLECTION = {
    "name": "Example Collection",
    "description": "Example collection generated from CSV.",
    "country": "CZ",
    "contact_name": "Jane",
    "contact_surname": "Doe",
    "contact_email": "contact@example.org",
}
# ────────────────────────────────────────────────────────────────────────────

_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # fixed namespace -> deterministic ids


def fid(key):
    """Deterministic UUID for a logical key -> valid FHIR resource id."""
    return str(uuid.uuid5(_NS, key))


def _date(value, fmt):
    value = (value or "").strip()
    return datetime.strptime(value, fmt) if value else None


def _entry(resource, resource_uuid):
    """Bundle entry with a UUID id and an absolute urn:uuid: fullUrl."""
    obj = resource.as_json()
    obj["id"] = resource_uuid
    return {"fullUrl": f"urn:uuid:{resource_uuid}", "resource": obj}


def convert(csv_path):
    entries = []
    seen_donors = set()
    seen_conditions = set()
    errors = []

    sample_uuids = []
    agg_genders, agg_materials = set(), set()
    agg_storage, agg_diagnoses = set(), set()

    with open(csv_path, newline="", encoding="utf-8") as fh:
        for lineno, row in enumerate(csv.DictReader(fh, delimiter=CSV_SEPARATOR), start=2):
            try:
                donor_id  = row[COLUMNS["donor_id"]].strip()
                sample_id = row[COLUMNS["sample_id"]].strip()
                donor_uuid = fid(f"Patient/{donor_id}")

                # ── Donor (deduped) ─────────────────────────────────────────
                if donor_id not in seen_donors:
                    raw_sex = row[COLUMNS["sex"]].strip().lower()
                    gender = GENDER_MAP.get(raw_sex)
                    if gender is None:
                        raise ValueError(f"unmapped sex value {raw_sex!r}")
                    birth = _date(row.get(COLUMNS["birth_year"]), YEAR_FORMAT)
                    donor = SampleDonor(donor_id, gender=gender, birth_date=birth)
                    entries.append(_entry(donor.to_fhir(), donor_uuid))
                    seen_donors.add(donor_id)
                    agg_genders.add(gender)

                # ── Diagnoses ───────────────────────────────────────────────
                # The IG splits these by whether the biobank holds a sample:
                #   Observation — diagnosis linked to THIS sample; written below,
                #                 once the specimen it references exists
                #   Condition   — diagnosis of the patient with no sample for it,
                #                 taken from a separate column
                # Consumers query the two differently, so a code in the wrong
                # place is invisible to them.
                dx_date = _date(row.get(COLUMNS["diagnosis_date"]), DATE_FORMAT)
                codes = [c.strip() for c in
                         (row.get(COLUMNS["diagnosis"]) or "").split(DIAGNOSIS_SPLIT) if c.strip()]
                diagnoses = [(code, dx_date) for code in codes]
                agg_diagnoses.update(codes)

                patient_codes = [c.strip() for c in
                                 (row.get(COLUMNS["patient_diagnosis"]) or "").split(DIAGNOSIS_SPLIT)
                                 if c.strip()]
                agg_diagnoses.update(patient_codes)

                for code in patient_codes:
                    key = (donor_id, code)
                    if key in seen_conditions:
                        continue
                    seen_conditions.add(key)
                    cond = Condition(patient_identifier=donor_id, icd_10_code=code)
                    entries.append(_entry(cond.to_fhir(donor_uuid),
                                          fid(f"Condition/{donor_id}/{code}")))

                # ── Sample ──────────────────────────────────────────────────
                raw_mat = row[COLUMNS["material_type"]].strip()
                material_type = MATERIAL_TYPE_MAP.get(raw_mat, raw_mat)
                agg_materials.add(COLLECTION_MATERIAL_MAP.get(material_type, "Other"))

                raw_temp = row.get(COLUMNS["storage_temp"], "").strip()
                storage_temp = STORAGE_TEMP_MAP.get(raw_temp) if raw_temp else None
                if raw_temp and storage_temp is None:
                    raise ValueError(f"unmapped storage_temperature {raw_temp!r}")
                if storage_temp is not None:
                    agg_storage.add(storage_temp)

                sample = Sample(
                    identifier=sample_id,
                    donor_identifier=donor_id,
                    material_type=material_type,
                    collected_datetime=_date(row.get(COLUMNS["sampling_date"]), DATE_FORMAT),
                    storage_temperature=storage_temp,
                    diagnoses_with_observed_datetime=diagnoses or None,
                    sample_collection_id=COLLECTION_ID,
                )
                sample_uuid = fid(f"Specimen/{sample_id}")
                entries.append(_entry(sample.to_fhir(donor_uuid, COLLECTION_ID), sample_uuid))
                sample_uuids.append(sample_uuid)

                # Sample-linked diagnoses. Sample built these from
                # diagnoses_with_observed_datetime; each one needs the specimen's
                # id, so they are written after the specimen itself.
                for i, observation in enumerate(sample.observations):
                    entries.append(_entry(observation.to_fhir(donor_uuid, sample_uuid),
                                          fid(f"Observation/{sample_id}/{i}")))

            except Exception as exc:
                errors.append(f"  row {lineno}: {exc}")

    # ── Parent hierarchy (only if we produced any samples) ──────────────────
    parents = []
    if sample_uuids:
        jp_uuid = fid("Organization/juristic-person")
        bb_uuid = fid("Organization/biobank")
        co_uuid = fid("Organization/collection-org")
        cl_uuid = fid("Group/collection")

        biobank = Biobank(
            BIOBANK["id"], BIOBANK["name"], BIOBANK["country"],
            BIOBANK["contact_name"], BIOBANK["contact_surname"], BIOBANK["contact_email"],
            JURISTIC_PERSON["name"], BIOBANK["description"],
        )
        collection_org = CollectionOrganization(
            COLLECTION_ORG["id"], COLLECTION_ORG["name"], BIOBANK["id"],
            COLLECTION_ORG["contact_name"], COLLECTION_ORG["contact_surname"],
            COLLECTION_ORG["contact_email"], COLLECTION_ORG["country"],
            description=COLLECTION_ORG["description"],
        )
        collection = Collection(
            identifier=COLLECTION_ID, name=COLLECTION["name"], managing_biobank_id=BIOBANK["id"],
            contact_name=COLLECTION["contact_name"], contact_surname=COLLECTION["contact_surname"],
            contact_email=COLLECTION["contact_email"], country=COLLECTION["country"],
            genders=list(agg_genders), description=COLLECTION["description"],
            material_types=list(agg_materials),
            storage_temperatures=list(agg_storage) or None,
            diagnoses=list(agg_diagnoses) or None,
        )
        parents = [
            _entry(biobank.juristic_person.to_fhir(), jp_uuid),
            _entry(biobank.to_fhir(jp_uuid), bb_uuid),
            _entry(collection_org.to_fhir(bb_uuid), co_uuid),
            _entry(collection.to_fhir(co_uuid, sample_uuids), cl_uuid),
        ]

    return parents + entries, errors


def main():
    ap = argparse.ArgumentParser(description="CSV -> MIABIS-on-FHIR Bundle")
    ap.add_argument("csv_path")
    ap.add_argument("-o", "--out", default="miabis_bundle.json")
    args = ap.parse_args()

    entries, errors = convert(args.csv_path)
    if errors:
        print(f"{len(errors)} row(s) skipped:", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)

    bundle = {"resourceType": "Bundle", "type": "collection", "entry": entries}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2)
    print(f"Wrote {len(entries)} resources to {args.out}")


if __name__ == "__main__":
    main()
