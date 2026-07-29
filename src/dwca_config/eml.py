"""Normalize published EML XML into mergeable Python mappings."""

from collections import defaultdict
from copy import deepcopy
from datetime import date
from typing import Any, Dict, Iterable, Optional
from uuid import uuid4
import xml.etree.ElementTree as ET


_NAMESPACE_PREFIXES = {
    "http://purl.org/dc/terms/": "dc",
    "http://www.w3.org/2001/XMLSchema-instance": "xsi",
    "http://www.w3.org/XML/1998/namespace": "xml",
}

EML_KEY_ORDER = (
    "languageCode",
    "datasetTitle",
    "creators",
    "metadataProviders",
    "associatedParties",
    "abstract",
    "keywordSets",
    "intellectualRights",
    "license",
    "distributions",
    "geographicCoverage",
    "taxonomicCoverage",
    "temporalCoverage",
    "maintenance",
    "contacts",
    "methods",
    "project",
    "additionalInfo",
    "bibliography",
    "externalDataSets",
    "resourceLogoUrl",
    "collection",
    "formationPeriod",
    "preservationMethods",
    "curatorialUnits",
)


def _ordered_keys(mappings: Iterable[Dict[str, Any]]) -> list:
    present = {key for mapping in mappings for key in mapping}
    ordered = [key for key in EML_KEY_ORDER if key in present]
    for mapping in mappings:
        ordered.extend(
            key for key in mapping if key in present and key not in ordered
        )
    return ordered


def _qualified_name(name: str) -> str:
    if not name.startswith("{"):
        return name
    namespace, local = name[1:].split("}", 1)
    prefix = _NAMESPACE_PREFIXES.get(namespace)
    return f"{prefix}:{local}" if prefix else local


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def _element_value(element: ET.Element) -> Any:
    attributes = {
        _qualified_name(key): value for key, value in element.attrib.items()
    }
    children = list(element)
    direct_text = _clean_text(element.text)

    if not attributes and not children:
        return direct_text

    value: Dict[str, Any] = {}
    if attributes:
        value["@attributes"] = attributes
    if direct_text:
        value["#text"] = direct_text

    grouped: Dict[str, list[Any]] = defaultdict(list)
    for child in children:
        grouped[_qualified_name(child.tag)].append(_element_value(child))
    for tag, items in grouped.items():
        value[tag] = items[0] if len(items) == 1 else items

    # Mixed-content EML paragraphs place prose around link elements. Preserve
    # the complete human-readable value in addition to the structured links.
    full_text = _clean_text("".join(element.itertext()))
    has_mixed_content = bool(direct_text) or any(
        _clean_text(child.tail) for child in children
    )
    if children and has_mixed_content and full_text:
        value["#content"] = full_text
    return value


def parse_eml(xml: str) -> Dict[str, Any]:
    """Return a namespace-normalized, YAML-safe representation of EML XML."""

    root = ET.fromstring(xml)
    return {
        "namespaces": {
            "eml": "https://eml.ecoinformatics.org/eml-2.2.0",
            "dc": "http://purl.org/dc/terms/",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        },
        _qualified_name(root.tag): _element_value(root),
    }


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _node_text(value: Any) -> str:
    if isinstance(value, dict):
        return value.get("#content", value.get("#text", ""))
    return value or ""


def _party(value: Dict[str, Any]) -> Dict[str, Any]:
    person: Dict[str, Any] = {}
    name = value.get("individualName", {})
    if isinstance(name, dict):
        if name.get("givenName"):
            person["givenName"] = name["givenName"]
        if name.get("surName"):
            person["surName"] = name["surName"]
    direct = {
        "organizationName": "organizationName",
        "positionName": "positionName",
        "phone": "phone",
        "electronicMailAddress": "email",
        "onlineUrl": "onlineUrl",
        "role": "role",
    }
    for source, target in direct.items():
        if value.get(source):
            person[target] = value[source]
    address = value.get("address")
    if isinstance(address, dict):
        person["address"] = {
            key: address[key]
            for key in (
                "deliveryPoint",
                "city",
                "administrativeArea",
                "postalCode",
                "country",
            )
            if address.get(key)
        }
    user_id = value.get("userId")
    if isinstance(user_id, dict):
        person["userId"] = {
            "value": _node_text(user_id),
            "directory": user_id.get("@attributes", {}).get("directory"),
        }
    return person


def flatten_eml(document: Dict[str, Any]) -> Dict[str, Any]:
    """Map normalized XML structure to the readable template/YAML contract."""

    root = document["eml"]
    dataset = root["dataset"]
    gbif = root.get("additionalMetadata", {}).get("metadata", {}).get("gbif", {})
    attributes = root.get("@attributes", {})
    flat: Dict[str, Any] = {
        "languageCode": attributes.get("xml:lang", dataset.get("language")),
        "alternateIdentifiers": [
            _node_text(item)
            for item in _as_list(dataset.get("alternateIdentifier"))
        ],
        "datasetTitle": _node_text(dataset.get("title")),
        "creators": [_party(item) for item in _as_list(dataset.get("creator"))],
        "metadataProviders": [
            _party(item) for item in _as_list(dataset.get("metadataProvider"))
        ],
        "associatedParties": [
            _party(item) for item in _as_list(dataset.get("associatedParty"))
        ],
        "abstract": _node_text(dataset.get("abstract", {}).get("para")),
        "publicationDate": {"automatic": True},
        "contacts": [_party(item) for item in _as_list(dataset.get("contact"))],
        "resourceLogoUrl": _node_text(gbif.get("resourceLogoUrl")),
        "formationPeriod": _node_text(gbif.get("formationPeriod")),
        "preservationMethods": _as_list(gbif.get("specimenPreservationMethod")),
    }

    keyword_sets = []
    for value in _as_list(dataset.get("keywordSet")):
        keyword_sets.append(
            {
                "keywords": _as_list(value.get("keyword")),
                "thesaurus": _node_text(value.get("keywordThesaurus")),
            }
        )
    flat["keywordSets"] = keyword_sets

    rights = dataset.get("intellectualRights", {}).get("para", {})
    rights_value: Dict[str, Any] = {"text": _node_text(rights)}
    if isinstance(rights, dict) and isinstance(rights.get("ulink"), dict):
        link = rights["ulink"]
        rights_value["link"] = {
            "url": link.get("@attributes", {}).get("url"),
            "title": _node_text(link.get("citetitle")),
        }
    flat["intellectualRights"] = rights_value

    licensed = dataset.get("licensed")
    if isinstance(licensed, dict):
        flat["license"] = {
            "name": licensed.get("licenseName"),
            "url": licensed.get("url"),
            "identifier": licensed.get("identifier"),
        }

    flat["distributions"] = [
        {
            "scope": item.get("@attributes", {}).get("scope"),
            "function": item.get("online", {})
            .get("url", {})
            .get("@attributes", {})
            .get("function"),
            "url": _node_text(item.get("online", {}).get("url")),
        }
        for item in _as_list(dataset.get("distribution"))
    ]

    coverage = dataset.get("coverage", {})
    geographic = coverage.get("geographicCoverage")
    if isinstance(geographic, dict):
        bounds = geographic.get("boundingCoordinates", {})
        flat["geographicCoverage"] = {
            "description": _node_text(geographic.get("geographicDescription")),
            "west": _node_text(bounds.get("westBoundingCoordinate")),
            "east": _node_text(bounds.get("eastBoundingCoordinate")),
            "north": _node_text(bounds.get("northBoundingCoordinate")),
            "south": _node_text(bounds.get("southBoundingCoordinate")),
        }
    taxonomic = coverage.get("taxonomicCoverage")
    if isinstance(taxonomic, dict):
        flat["taxonomicCoverage"] = {
            "description": _node_text(
                taxonomic.get("generalTaxonomicCoverage")
            ),
            "classifications": [
                {
                    "rankName": _node_text(item.get("taxonRankName")),
                    "rankValue": _node_text(item.get("taxonRankValue")),
                    "commonName": _node_text(item.get("commonName")),
                }
                for item in _as_list(
                    taxonomic.get("taxonomicClassification")
                )
            ],
        }
    temporal = coverage.get("temporalCoverage")
    if isinstance(temporal, dict):
        dates = temporal.get("rangeOfDates", {})
        flat["temporalCoverage"] = {
            "beginDate": _node_text(dates.get("beginDate", {}).get("calendarDate")),
            "endDate": _node_text(dates.get("endDate", {}).get("calendarDate")),
        }

    maintenance = dataset.get("maintenance")
    if isinstance(maintenance, dict):
        flat["maintenance"] = {
            "description": _node_text(
                maintenance.get("description", {}).get("para")
            ),
            "frequency": _node_text(
                maintenance.get("maintenanceUpdateFrequency")
            ),
        }

    methods = dataset.get("methods")
    if isinstance(methods, dict):
        flat["methods"] = {
            "steps": [
                _node_text(item.get("description", {}).get("para"))
                for item in _as_list(methods.get("methodStep"))
            ]
        }
    if dataset.get("additionalInfo") is not None:
        flat["additionalInfo"] = _node_text(dataset["additionalInfo"])

    bibliography = gbif.get("bibliography", {}).get("citation")
    flat["bibliography"] = [
        {
            "text": _node_text(item),
            "identifier": (
                item.get("@attributes", {}).get("identifier")
                if isinstance(item, dict)
                else None
            ),
        }
        for item in _as_list(bibliography)
    ]

    external = []
    for item in _as_list(gbif.get("physical")):
        defined = item.get("dataFormat", {}).get("externallyDefinedFormat", {})
        url = item.get("distribution", {}).get("online", {}).get("url", {})
        external.append(
            {
                "name": _node_text(item.get("objectName")),
                "characterEncoding": _node_text(item.get("characterEncoding")),
                "formatName": _node_text(defined.get("formatName")),
                "formatVersion": _node_text(defined.get("formatVersion")),
                "function": (
                    url.get("@attributes", {}).get("function")
                    if isinstance(url, dict)
                    else None
                ),
                "url": _node_text(url),
            }
        )
    flat["externalDataSets"] = external

    collection = gbif.get("collection")
    if isinstance(collection, dict):
        flat["collection"] = {
            "parentIdentifier": _node_text(
                collection.get("parentCollectionIdentifier")
            ),
            "identifier": _node_text(collection.get("collectionIdentifier")),
            "name": _node_text(collection.get("collectionName")),
        }

    units = []
    for item in _as_list(gbif.get("jgtiCuratorialUnit")):
        value = {"unitType": _node_text(item.get("jgtiUnitType"))}
        count = item.get("jgtiUnits")
        if count is not None:
            value["units"] = _node_text(count)
            if isinstance(count, dict):
                value["uncertainty"] = count.get("@attributes", {}).get(
                    "uncertaintyMeasure"
                )
        else:
            ranges = item.get("jgtiUnitRange", {})
            value["beginRange"] = _node_text(ranges.get("beginRange"))
            value["endRange"] = _node_text(ranges.get("endRange"))
        units.append(value)
    flat["curatorialUnits"] = units

    citation = gbif.get("citation")
    if citation is not None:
        flat["gbifMetadata"] = {
            "hierarchyLevel": _node_text(gbif.get("hierarchyLevel")) or "dataset",
            "citation": {
                "text": _node_text(citation),
                "identifier": (
                    citation.get("@attributes", {}).get("identifier")
                    if isinstance(citation, dict)
                    else ""
                ),
            },
        }

    return {
        key: value
        for key, value in flat.items()
        if value not in (None, "", [], {})
    }


def merge_eml(base: Any, override: Any) -> Any:
    """Merge normalized EML, treating null override values as omissions."""

    if not isinstance(base, dict) or not isinstance(override, dict):
        return deepcopy(override)
    result = deepcopy(base)
    for key, value in override.items():
        if value is None:
            result.pop(key, None)
        elif key in result:
            result[key] = merge_eml(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def common_eml_template(documents: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a majority template suitable for shared EML YAML defaults."""

    docs = list(documents)
    threshold = max(2, (len(docs) + 1) // 2)

    def template(values: list[Any]) -> Any:
        groups: Dict[str, list[Any]] = defaultdict(list)
        for value in values:
            groups[repr(value)].append(value)
        largest = max(groups.values(), key=len)
        if len(largest) >= threshold:
            return deepcopy(largest[0])

        mappings = [value for value in values if isinstance(value, dict)]
        if len(mappings) < threshold:
            return {}
        result: Dict[str, Any] = {}
        for key in _ordered_keys(mappings):
            present = [mapping[key] for mapping in mappings if key in mapping]
            if len(present) < threshold:
                continue
            shared = template(present)
            if shared != {}:
                result[key] = shared
        return result

    return template(docs)


def eml_override(base: Any, document: Any) -> Any:
    """Return the smallest override that reconstructs ``document``."""

    if base == document:
        return {}
    if isinstance(base, dict) and isinstance(document, dict):
        result: Dict[str, Any] = {}
        for key in _ordered_keys([document, base]):
            if key not in document:
                result[key] = None
            elif key not in base:
                result[key] = deepcopy(document[key])
            else:
                difference = eml_override(base[key], document[key])
                if difference != {}:
                    result[key] = difference
        return result
    return deepcopy(document)


_EML_NAMESPACE = "https://eml.ecoinformatics.org/eml-2.2.0"
_DC_NAMESPACE = "http://purl.org/dc/terms/"
_XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace("eml", _EML_NAMESPACE)
ET.register_namespace("dc", _DC_NAMESPACE)
ET.register_namespace("xsi", _XSI_NAMESPACE)


def _add(parent: ET.Element, tag: str, value: Any = None, **attributes: Any) -> ET.Element:
    element = ET.SubElement(
        parent,
        tag,
        {key: str(item) for key, item in attributes.items() if item is not None},
    )
    if value is not None:
        element.text = str(value)
    return element


def _add_party(parent: ET.Element, tag: str, party: Dict[str, Any]) -> None:
    element = _add(parent, tag)
    if party.get("givenName") or party.get("surName"):
        name = _add(element, "individualName")
        if party.get("givenName"):
            _add(name, "givenName", party["givenName"])
        if party.get("surName"):
            _add(name, "surName", party["surName"])
    for key in ("organizationName", "positionName"):
        if party.get(key):
            _add(element, key, party[key])
    address = party.get("address")
    if isinstance(address, dict) and address:
        node = _add(element, "address")
        for key in (
            "deliveryPoint",
            "city",
            "administrativeArea",
            "postalCode",
            "country",
        ):
            if address.get(key):
                _add(node, key, address[key])
    for source, tag_name in (
        ("phone", "phone"),
        ("email", "electronicMailAddress"),
        ("onlineUrl", "onlineUrl"),
    ):
        if party.get(source):
            _add(element, tag_name, party[source])
    user_id = party.get("userId")
    if isinstance(user_id, dict) and user_id.get("value"):
        _add(
            element,
            "userId",
            user_id["value"],
            directory=user_id.get("directory"),
        )
    if party.get("role"):
        _add(element, "role", party["role"])


def render_eml_document(
    metadata: Dict[str, Any],
    *,
    package_id: Optional[str] = None,
    publication_date: Optional[str] = None,
    date_stamp: Optional[str] = None,
    system: str = "dwca-config",
    scope: str = "system",
    hierarchy_level: str = "dataset",
    replaces: Optional[str] = None,
) -> str:
    """Render resolved EML metadata as a standalone GBIF-profile EML document.

    Publisher-owned state is generated when omitted: a UUID package identifier
    and today's ISO date. The input mapping is not mutated.
    """

    for required in ("datasetTitle", "creators", "abstract", "contacts"):
        if not metadata.get(required):
            raise ValueError(f"EML metadata requires {required!r}")

    language = str(metadata.get("languageCode", "eng"))
    today = date.today().isoformat()
    root = ET.Element(
        f"{{{_EML_NAMESPACE}}}eml",
        {
            f"{{{_XSI_NAMESPACE}}}schemaLocation": (
                f"{_EML_NAMESPACE} "
                "https://rs.gbif.org/schema/eml-gbif-profile/1.3/eml.xsd"
            ),
            "packageId": package_id or str(uuid4()),
            "system": system,
            "scope": scope,
            "{http://www.w3.org/XML/1998/namespace}lang": language,
        },
    )
    dataset = _add(root, "dataset")
    identifiers = []
    for identifier in (
        [metadata.get("datasetID")]
        + _as_list(metadata.get("alternateIdentifiers"))
    ):
        if identifier and identifier not in identifiers:
            identifiers.append(identifier)
    for identifier in identifiers:
        _add(dataset, "alternateIdentifier", identifier)
    _add(dataset, "title", metadata["datasetTitle"], **{
        "{http://www.w3.org/XML/1998/namespace}lang": language
    })
    for party in _as_list(metadata.get("creators")):
        _add_party(dataset, "creator", party)
    for party in _as_list(metadata.get("metadataProviders")):
        _add_party(dataset, "metadataProvider", party)
    for party in _as_list(metadata.get("associatedParties")):
        _add_party(dataset, "associatedParty", party)
    _add(dataset, "pubDate", publication_date or today)
    _add(dataset, "language", language)
    _add(_add(dataset, "abstract"), "para", metadata["abstract"])

    for keyword_set in _as_list(metadata.get("keywordSets")):
        node = _add(dataset, "keywordSet")
        for keyword in _as_list(keyword_set.get("keywords")):
            _add(node, "keyword", keyword)
        if keyword_set.get("thesaurus") is not None:
            _add(node, "keywordThesaurus", keyword_set["thesaurus"])

    inline_rights_links = []
    rights = metadata.get("intellectualRights")
    if isinstance(rights, dict):
        text = rights.get("text", "")
        para = _add(_add(dataset, "intellectualRights"), "para")
        link = rights.get("link")
        if isinstance(link, dict) and link.get("url"):
            title = link.get("title", link["url"])
            before, separator, after = text.partition(title)
            para.text = before if separator else text
            ulink = _add(para, "ulink", url=link["url"])
            citetitle = _add(ulink, "citetitle", title)
            inline_rights_links.append((ulink, citetitle))
            if separator:
                ulink.tail = after
        else:
            para.text = text

    license_value = metadata.get("license")
    if isinstance(license_value, dict):
        licensed = _add(dataset, "licensed")
        _add(licensed, "licenseName", license_value.get("name", ""))
        _add(licensed, "url", license_value.get("url", ""))
        _add(licensed, "identifier", license_value.get("identifier", ""))

    for distribution in _as_list(metadata.get("distributions")):
        node = _add(dataset, "distribution", scope=distribution.get("scope"))
        online = _add(node, "online")
        _add(
            online,
            "url",
            distribution.get("url", ""),
            function=distribution.get("function"),
        )

    coverage_values = (
        metadata.get("geographicCoverage"),
        metadata.get("taxonomicCoverage"),
        metadata.get("temporalCoverage"),
    )
    if any(isinstance(value, dict) for value in coverage_values):
        coverage = _add(dataset, "coverage")
        geographic = metadata.get("geographicCoverage")
        if isinstance(geographic, dict):
            node = _add(coverage, "geographicCoverage")
            if geographic.get("description") is not None:
                _add(node, "geographicDescription", geographic["description"])
            bounds = _add(node, "boundingCoordinates")
            for source, tag in (
                ("west", "westBoundingCoordinate"),
                ("east", "eastBoundingCoordinate"),
                ("north", "northBoundingCoordinate"),
                ("south", "southBoundingCoordinate"),
            ):
                _add(bounds, tag, geographic.get(source, ""))
        taxonomic = metadata.get("taxonomicCoverage")
        if isinstance(taxonomic, dict):
            node = _add(coverage, "taxonomicCoverage")
            _add(node, "generalTaxonomicCoverage", taxonomic.get("description", ""))
            for classification in _as_list(taxonomic.get("classifications")):
                item = _add(node, "taxonomicClassification")
                _add(item, "taxonRankName", classification.get("rankName", ""))
                _add(item, "taxonRankValue", classification.get("rankValue", ""))
                if classification.get("commonName") is not None:
                    _add(item, "commonName", classification["commonName"])
        temporal = metadata.get("temporalCoverage")
        if isinstance(temporal, dict):
            node = _add(coverage, "temporalCoverage")
            dates = _add(node, "rangeOfDates")
            _add(_add(dates, "beginDate"), "calendarDate", temporal.get("beginDate", ""))
            _add(_add(dates, "endDate"), "calendarDate", temporal.get("endDate", ""))

    maintenance = metadata.get("maintenance")
    if isinstance(maintenance, dict):
        node = _add(dataset, "maintenance")
        _add(_add(node, "description"), "para", maintenance.get("description", ""))
        if maintenance.get("frequency"):
            _add(node, "maintenanceUpdateFrequency", maintenance["frequency"])
    for party in _as_list(metadata.get("contacts")):
        _add_party(dataset, "contact", party)

    methods = metadata.get("methods")
    if isinstance(methods, dict):
        node = _add(dataset, "methods")
        for step in _as_list(methods.get("steps")):
            _add(_add(_add(node, "methodStep"), "description"), "para", step)
    if metadata.get("additionalInfo") is not None:
        _add(dataset, "additionalInfo", metadata["additionalInfo"])

    additional = _add(_add(root, "additionalMetadata"), "metadata")
    gbif = _add(additional, "gbif")
    _add(gbif, "dateStamp", date_stamp or today)
    gbif_metadata = metadata.get("gbifMetadata")
    configured_hierarchy = (
        gbif_metadata.get("hierarchyLevel")
        if isinstance(gbif_metadata, dict)
        else None
    )
    _add(gbif, "hierarchyLevel", configured_hierarchy or hierarchy_level)
    if isinstance(gbif_metadata, dict):
        citation = gbif_metadata.get("citation")
        if isinstance(citation, dict):
            _add(
                gbif,
                "citation",
                citation.get("text", ""),
                identifier=citation.get("identifier"),
            )
    bibliography = metadata.get("bibliography")
    if bibliography:
        node = _add(gbif, "bibliography")
        for citation in _as_list(bibliography):
            _add(
                node,
                "citation",
                citation.get("text", ""),
                identifier=citation.get("identifier"),
            )
    for external in _as_list(metadata.get("externalDataSets")):
        physical = _add(gbif, "physical")
        _add(physical, "objectName", external.get("name", ""))
        _add(physical, "characterEncoding", external.get("characterEncoding", ""))
        defined = _add(_add(physical, "dataFormat"), "externallyDefinedFormat")
        _add(defined, "formatName", external.get("formatName", ""))
        _add(defined, "formatVersion", external.get("formatVersion", ""))
        online = _add(_add(physical, "distribution"), "online")
        _add(online, "url", external.get("url", ""), function=external.get("function"))
    if metadata.get("resourceLogoUrl") is not None:
        _add(gbif, "resourceLogoUrl", metadata["resourceLogoUrl"])
    collection = metadata.get("collection")
    if isinstance(collection, dict):
        node = _add(gbif, "collection")
        _add(node, "parentCollectionIdentifier", collection.get("parentIdentifier", ""))
        _add(node, "collectionIdentifier", collection.get("identifier", ""))
        _add(node, "collectionName", collection.get("name", ""))
    if metadata.get("formationPeriod") is not None:
        _add(gbif, "formationPeriod", metadata["formationPeriod"])
    for method in _as_list(metadata.get("preservationMethods")):
        _add(gbif, "specimenPreservationMethod", method)
    for unit in _as_list(metadata.get("curatorialUnits")):
        node = _add(gbif, "jgtiCuratorialUnit")
        _add(node, "jgtiUnitType", unit.get("unitType", ""))
        if "units" in unit:
            _add(
                node,
                "jgtiUnits",
                unit["units"],
                uncertaintyMeasure=unit.get("uncertainty"),
            )
        else:
            ranges = _add(node, "jgtiUnitRange")
            _add(ranges, "beginRange", unit.get("beginRange", ""))
            _add(ranges, "endRange", unit.get("endRange", ""))
    if replaces:
        _add(gbif, f"{{{_DC_NAMESPACE}}}replaces", replaces)

    ET.indent(root, space="  ")
    for ulink, citetitle in inline_rights_links:
        if ulink.text is not None and not ulink.text.strip():
            ulink.text = None
        if citetitle.tail is not None and not citetitle.tail.strip():
            citetitle.tail = None
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
