# Examples

## `csv_to_miabis.py` — CSV table → MIABIS-on-FHIR Bundle

A minimal, self-contained example of using `miabis_model` to turn a delimited
table into a FHIR R4 Bundle. It reads a CSV and builds the full MIABIS hierarchy
(JuristicPerson → Biobank → CollectionOrganization → Collection → Patient /
Condition / Observation / Specimen), so the resulting Bundle is self-contained.

It is a starting point to copy and adapt, not a production tool. For a full ETL
(CSV/XML/JSON inputs, value maps, Blaze upload, incremental sync) see
[`fhir-module`](https://github.com/BBMRI-cz/fhir-module).

### The two places a diagnosis can go

This is the part that is easiest to get wrong, so the example keeps them in
separate columns:

| Column | Becomes | Meaning |
|---|---|---|
| `diagnosis` | `Observation`, referencing the specimen | the diagnosis this sample relates to |
| `patient_diagnosis` | `Condition` | a diagnosis of the patient the biobank holds **no** sample for |

Consumers query the two differently — a sample locator reads the Observations — so
a code put in the wrong one is invisible to them. If your source data does not
distinguish the two, diagnoses that arrived with a sample belong on `Observation`.

### Install

```bash
pip install MIABIS-on-FHIR
```

### Run

```bash
python examples/csv_to_miabis.py examples/sample_data.csv -o bundle.json
```

`sample_data.csv` is a 3-row semicolon-separated sample. The `CONFIG` block at the
top of the script maps its columns and coded values to the model; edit it to match
your own table (column names, `;` vs `,` separator, date formats, and the
gender / storage-temperature / material-type value maps).

### Validate the conversion output

Because the emitted Bundle is self-contained, you can validate it against the
MIABIS-on-FHIR IG with the official [HL7 FHIR validator](https://github.com/hapifhir/org.hl7.fhir.core/releases)
— a quick way to check that your conversion produces conformant resources:

```bash
java -jar validator_cli.jar bundle.json \
  -version 4.0.1 \
  -ig <miabis-on-fhir-ig-package> \
  -output report.json
```

- Supply the IG package via `-ig`: either a locally built copy of the
  [MIABIS-on-FHIR IG](https://github.com/BBMRI-cz/miabis-on-fhir) (`fsh-generated/resources`)
  or the published package. The canonical base `https://fhir.bbmri-eric.eu` is not
  a live endpoint, so the validator cannot auto-resolve the profiles without it.
- Tip: add `-tx n/a` to skip the terminology server for a fast structural check
  (full terminology validation of ICD-10 codes can be very slow).

Validating the output this way is the recommended way to catch mapping mistakes
(wrong codes, missing required fields) before uploading to a FHIR store.
