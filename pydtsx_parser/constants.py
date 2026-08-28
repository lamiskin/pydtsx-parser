"""Constants used throughout the SSIS Parser."""

# Component classification map: componentClassID -> category
# Used to classify data flow components as source, destination, or transformation.
# Components not in this map are classified as "unknown".
COMPONENT_CLASSIFICATION = {
    "Microsoft.OLEDBSource": "source",
    "Microsoft.FlatFileSource": "source",
    "Microsoft.SSISOracleSrc": "source",
    "Microsoft.OLEDBDestination": "destination",
    "Microsoft.FlatFileDestination": "destination",
    "Microsoft.DerivedColumn": "transformation",
    "Microsoft.Sort": "transformation",
    "Microsoft.MergeJoin": "transformation",
    "Microsoft.ConditionalSplit": "transformation",
}

# SSIS numeric data type codes to human-readable type names
DATA_TYPE_MAP = {
    "2": "i2",
    "3": "i4",
    "4": "r4",
    "5": "r8",
    "6": "cy",
    "7": "dbDate",
    "11": "bool",
    "20": "i8",
    "72": "guid",
    "129": "str",
    "130": "wstr",
    "131": "numeric",
    "135": "dbTimeStamp",
    "139": "numericWithPrecision",
}

# XML namespace URIs used in SSIS files
NAMESPACES = {
    "DTS": "www.microsoft.com/SqlServer/Dts",
    "SSIS": "www.microsoft.com/SqlServer/SSIS",
    "SQLTask": "www.microsoft.com/sqlserver/dts/tasks/sqltask",
}
