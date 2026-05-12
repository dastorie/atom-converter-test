REPOSITORY = "University of Regina Archives & Special Collections"
INSTITUTION_IDENTIFIER = "URASC"
LANGUAGE = "en"
ACCESS_CONDITIONS = "Open to Researchers"
DESCRIPTION_STATUS = "Draft"

RAD_GMD_TERMS = frozenset({
    "textual record",
    "graphic material",
    "cartographic material",
    "architectural drawing",
    "moving images",
    "sound recording",
    "technical drawing",
    "object",
    "multiple media",
})

LEVELS_OF_DESCRIPTION = ("Series", "Sub-Series", "File", "Item")

CSV_COLUMNS = (
    "legacyId",
    "parentId",
    "qubitParentSlug",
    "identifier",
    "accessionNumber",
    "title",
    "radGeneralMaterialDesignation",
    "levelOfDescription",
    "repository",
    "extentAndMedium",
    "archivalHistory",
    "scopeAndContent",
    "physicalCharacteristics",
    "acquisition",
    "arrangement",
    "language",
    "locationOfOriginals",
    "accessConditions",
    "accruals",
    "institutionIdentifier",
    "descriptionStatus",
    "generalNote",
    "eventDates",
)
