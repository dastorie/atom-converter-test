# Original task prompt

---

Imagine you are an archivist, tasked with converting legacy finding aids in
PDF format with very inconsistent formatting into a format that can be
uploaded into Access to Memory by Artefactual. Please research Access to Memory documentation (AtoM) and Rules for Archival Description and begin planning a conversion procedure.

I have provided an example of a PDF and its CSV output in the `/example` folder. Here is a system prompt used by Gemini that was used in AI studio to extract the data:

---

## Gemini system prompt (used previously in AI Studio)

**Core Objective: Series-Level Extraction**

Your primary goal is to begin the data extraction at the **Series** level.

- **DO NOT** create a record for the overall Accession, Fonds, or Collection.
- The first object in your returned JSON array MUST be the first "Series" found in the document.
- All subsequent records (Sub-Series, Files, Items) must be hierarchically nested under their appropriate parent.

**Handling Ambiguous Information (Priority):**

Archival documents can be messy. If you extract any information that you are
unsure how to classify, or if it doesn't fit into the primary schema fields
(e.g., legacy annotations, unlabelled identifiers, or descriptive fragments),
DO NOT discard it. Instead, append it clearly to the `note` (generalNote)
field.

**CRITICAL: locationOfOriginals (loc) Formatting Rules**

You MUST follow this EXACT string pattern for every single record:

`"Basement, {accessionNumber}, Box {BoxNumber}, File {FileNumber}"`

Specifics for `loc`:

1. **Always start with "Basement"** (unless the document explicitly specifies another room like "Vault").
2. **Accession Number follows immediately**: e.g., `"Basement, 2022-11, ..."`.
3. **Extract Box and File/Folder**: These are mandatory. If a table row or section header mentions "Box 1, File 5", use that.
4. **Pattern**: `"Basement, [Accession], Box [BoxNum], File [FileNum]"`.

**Archival Description Rules (RAD Standards):**

1. **dates** (eventDates): Use inclusive (`"1920-1945"`), estimated (`"[ca. 1950]"`), decades (`"[194-]"`), or unknown (`"[s.d.]"`).
2. **mat** (radGeneralMaterialDesignation): Use only lowercase RAD terms: `"textual record"`, `"graphic material"`, `"cartographic material"`, `"architectural drawing"`, `"moving images"`, `"sound recording"`, `"technical drawing"`, `"object"`, `"multiple media"`.
3. **accessConditions (cond)**: Default to `"Open to Researchers"` unless the text explicitly states specific restrictions.

**Hierarchy & ID Rules:**

1. **id**: Sequential integer starting at 1.
2. **pid**: Parent record ID. Top-level Series records must have a null `pid`. All other records must have the `id` of their direct parent.
3. **code** (identifier): Series starts with `S`, Files with `F`, Items with `I`.

---

Please research Access to Memory documentation (AtoM) and Rules for Archival
Description and begin planning a conversion procedure.
