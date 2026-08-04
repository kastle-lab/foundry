import argparse
from pathlib import Path
from typing import Any

import yaml
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD


def local_name(uri: URIRef) -> str:
    """
    Return the readable final part of a URI.

    Example:
    https://example.org/ontology/Agent
    becomes:
    Agent
    """
    text = str(uri)

    if "#" in text:
        return text.rsplit("#", 1)[-1]

    return text.rstrip("/").rsplit("/", 1)[-1]


def lower_first(text: str) -> str:
    """
    Lowercase the first character.

    LearningObjective becomes learningObjective.
    """
    if not text:
        return text

    return text[0].lower() + text[1:]


def load_graph(path: Path) -> Graph:
    """
    Load an RDF, OWL, or Turtle ontology.

    RDFLib first attempts automatic format detection.
    If that fails, RDF/XML and Turtle are tried explicitly.
    """
    formats_to_try = [None, "xml", "turtle"]

    errors: list[str] = []

    for file_format in formats_to_try:
        try:
            graph = Graph()
            graph.parse(path, format=file_format)
            return graph
        except Exception as error:
            errors.append(str(error))

    error_message = "\n".join(errors)

    raise RuntimeError(
        f"Could not read ontology file: {path}\n{error_message}"
    )


def all_named_classes(graph: Graph) -> set[URIRef]:
    """
    Collect named ontology classes.

    Classes may be declared as owl:Class, rdfs:Class,
    or appear in subclass relationships.
    """
    classes: set[URIRef] = set()

    for class_uri in graph.subjects(RDF.type, OWL.Class):
        if isinstance(class_uri, URIRef):
            classes.add(class_uri)

    for class_uri in graph.subjects(RDF.type, RDFS.Class):
        if isinstance(class_uri, URIRef):
            classes.add(class_uri)

    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if isinstance(child, URIRef):
            classes.add(child)

        if isinstance(parent, URIRef):
            classes.add(parent)

    return classes


def resolve_class(graph: Graph, class_value: str) -> URIRef:
    """
    Find a class using either:

    1. Its full URI
    2. Its local name, such as Agent or LearningObjective
    """
    if class_value.startswith(("http://", "https://", "urn:")):
        class_uri = URIRef(class_value)

        if class_uri in all_named_classes(graph):
            return class_uri

        raise ValueError(
            f"The class URI was not found in the ontology: {class_value}"
        )

    matching_classes = [
        class_uri
        for class_uri in all_named_classes(graph)
        if local_name(class_uri) == class_value
    ]

    if not matching_classes:
        raise ValueError(
            f"Class '{class_value}' was not found in the ontology."
        )

    if len(matching_classes) > 1:
        choices = "\n".join(
            f"- {class_uri}"
            for class_uri in sorted(matching_classes, key=str)
        )

        raise ValueError(
            f"More than one class has the name '{class_value}'. "
            f"Use the complete URI instead:\n{choices}"
        )

    return matching_classes[0]


def namespace_from_uri(uri: URIRef) -> str:
    """
    Return the namespace portion of a URI.
    """
    text = str(uri)

    if "#" in text:
        return text.rsplit("#", 1)[0] + "#"

    return text.rsplit("/", 1)[0] + "/"


def compact_uri(
    uri: URIRef,
    graph: Graph,
    ontology_namespace: str,
    ontology_prefix: str,
) -> str:
    """
    Convert a full URI into a compact prefix form.

    Example:
    https://example.org/ontology/Agent
    becomes:
    ont:Agent
    """
    text = str(uri)

    known_namespaces = {
        ontology_namespace: ontology_prefix,
        str(XSD): "xsd",
        str(RDFS): "rdfs",
        str(RDF): "rdf",
        str(OWL): "owl",
    }

    for prefix, namespace in graph.namespaces():
        if prefix:
            known_namespaces[str(namespace)] = str(prefix)

    # Check the longest namespaces first.
    sorted_namespaces = sorted(
        known_namespaces.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )

    for namespace, prefix in sorted_namespaces:
        if text.startswith(namespace):
            remaining_text = text[len(namespace):]

            if remaining_text:
                return f"{prefix}:{remaining_text}"

    return text


def class_and_parents(
    graph: Graph,
    class_uri: URIRef,
) -> set[URIRef]:
    """
    Return the class and all named parent classes.

    This allows inherited properties to be included.
    """
    found_classes = {class_uri}
    classes_to_check = [class_uri]

    while classes_to_check:
        current_class = classes_to_check.pop()

        for parent in graph.objects(
            current_class,
            RDFS.subClassOf,
        ):
            if not isinstance(parent, URIRef):
                continue

            if parent not in found_classes:
                found_classes.add(parent)
                classes_to_check.append(parent)

    return found_classes


def properties_for_class(
    graph: Graph,
    class_uri: URIRef,
) -> list[tuple[URIRef, URIRef, str]]:
    """
    Find object and datatype properties applicable to a class.

    Returned values contain:

    property URI
    range URI
    property kind: object or datatype
    """
    applicable_classes = class_and_parents(
        graph,
        class_uri,
    )

    results: set[tuple[URIRef, URIRef, str]] = set()

    property_types = (
        (OWL.ObjectProperty, "object"),
        (OWL.DatatypeProperty, "datatype"),
    )

    for property_type, property_kind in property_types:
        for property_uri in graph.subjects(
            RDF.type,
            property_type,
        ):
            if not isinstance(property_uri, URIRef):
                continue

            domains = {
                domain
                for domain in graph.objects(
                    property_uri,
                    RDFS.domain,
                )
                if isinstance(domain, URIRef)
            }

            if not domains.intersection(applicable_classes):
                continue

            for range_uri in graph.objects(
                property_uri,
                RDFS.range,
            ):
                if isinstance(range_uri, URIRef):
                    results.add(
                        (
                            property_uri,
                            range_uri,
                            property_kind,
                        )
                    )

    return sorted(
        results,
        key=lambda item: (
            str(item[0]),
            str(item[1]),
            item[2],
        ),
    )


def find_inverse(
    graph: Graph,
    property_uri: URIRef,
) -> URIRef | None:
    """
    Find an owl:inverseOf relationship when declared.
    """
    candidates = list(
        graph.objects(
            property_uri,
            OWL.inverseOf,
        )
    )

    candidates.extend(
        graph.subjects(
            OWL.inverseOf,
            property_uri,
        )
    )

    for candidate in candidates:
        if isinstance(candidate, URIRef):
            return candidate

    return None


def make_resource_uri(
    class_uri: URIRef,
    resource_prefix: str,
) -> str:
    """
    Create a draft instance URI from a class name.

    Agent becomes res:agent.
    LearningObjective becomes res:learningObjective.
    """
    return (
        f"{resource_prefix}:"
        f"{lower_first(local_name(class_uri))}"
    )


def build_node(
    graph: Graph,
    class_uri: URIRef,
    ontology_namespace: str,
    ontology_prefix: str,
    resource_prefix: str,
    maximum_depth: int,
    current_depth: int,
    path: tuple[URIRef, ...],
) -> dict[str, Any]:
    """
    Recursively create one Foundry-style YAML object.
    """
    node: dict[str, Any] = {
        "type": compact_uri(
            class_uri,
            graph,
            ontology_namespace,
            ontology_prefix,
        ),
        "uri": make_resource_uri(
            class_uri,
            resource_prefix,
        ),
    }

    if current_depth >= maximum_depth:
        return node

    connections: list[dict[str, Any]] = []

    for property_uri, range_uri, property_kind in properties_for_class(
        graph,
        class_uri,
    ):
        connection: dict[str, Any] = {
            "p": compact_uri(
                property_uri,
                graph,
                ontology_namespace,
                ontology_prefix,
            )
        }

        inverse_property = find_inverse(
            graph,
            property_uri,
        )

        if inverse_property is not None:
            connection["inv"] = compact_uri(
                inverse_property,
                graph,
                ontology_namespace,
                ontology_prefix,
            )

        if property_kind == "datatype":
            connection["o"] = {
                "datatype": compact_uri(
                    range_uri,
                    graph,
                    ontology_namespace,
                    ontology_prefix,
                )
            }

        elif range_uri in path:
            # Stop recursion when the same class appears again.
            connection["o"] = {
                "type": compact_uri(
                    range_uri,
                    graph,
                    ontology_namespace,
                    ontology_prefix,
                ),
                "uri": make_resource_uri(
                    range_uri,
                    resource_prefix,
                ),
            }

        else:
            connection["o"] = build_node(
                graph=graph,
                class_uri=range_uri,
                ontology_namespace=ontology_namespace,
                ontology_prefix=ontology_prefix,
                resource_prefix=resource_prefix,
                maximum_depth=maximum_depth,
                current_depth=current_depth + 1,
                path=path + (range_uri,),
            )

        connections.append(connection)

    if connections:
        node["connections"] = connections

    return node


def collect_predicates(value: Any) -> set[str]:
    """
    Collect every predicate stored under a YAML 'p' key.
    """
    predicates: set[str] = set()

    if isinstance(value, dict):
        predicate_value = value.get("p")

        if isinstance(predicate_value, list):
            predicates.update(
                str(item)
                for item in predicate_value
            )

        elif predicate_value is not None:
            predicates.add(str(predicate_value))

        for child in value.values():
            predicates.update(
                collect_predicates(child)
            )

    elif isinstance(value, list):
        for child in value:
            predicates.update(
                collect_predicates(child)
            )

    return predicates


def merge_root_nodes(
    root_nodes: list[dict[str, Any]],
    root_class_uris: list[URIRef],
    graph: Graph,
    ontology_namespace: str,
    ontology_prefix: str,
    resource_prefix: str,
) -> dict[str, Any]:
    """
    Combine multiple requested root classes into one root node.
    """
    root = root_nodes[0]

    if len(root_class_uris) == 1:
        return root

    root["type"] = [
        compact_uri(
            class_uri,
            graph,
            ontology_namespace,
            ontology_prefix,
        )
        for class_uri in root_class_uris
    ]

    root["uri"] = make_resource_uri(
        root_class_uris[0],
        resource_prefix,
    )

    merged_connections: list[dict[str, Any]] = []
    seen_connections: set[str] = set()

    for root_node in root_nodes:
        for connection in root_node.get(
            "connections",
            [],
        ):
            marker = yaml.safe_dump(
                connection,
                sort_keys=True,
            )

            if marker not in seen_connections:
                seen_connections.add(marker)
                merged_connections.append(connection)

    if merged_connections:
        root["connections"] = merged_connections

    return root


def compare_with_mapping(
    generated_mapping: dict[str, Any],
    comparison_file: Path,
) -> list[str]:
    """
    Compare predicate names with an existing YAML mapping.

    This is not complete semantic equivalence.
    """
    expected_mapping = yaml.safe_load(
        comparison_file.read_text(
            encoding="utf-8-sig"
        )
    )

    generated_predicates = collect_predicates(
        generated_mapping.get("root", {})
    )

    expected_predicates = collect_predicates(
        expected_mapping.get("root", {})
    )

    matched = generated_predicates & expected_predicates
    missing = expected_predicates - generated_predicates
    additional = generated_predicates - expected_predicates

    return [
        f"Generated unique predicates: {len(generated_predicates)}",
        f"Expected unique predicates: {len(expected_predicates)}",
        f"Matched unique predicates: {len(matched)}",
        f"Missing expected predicates: {len(missing)}",
        f"Additional ontology predicates: {len(additional)}",
        "",
        "Missing expected predicates:",
        *(
            [f"- {item}" for item in sorted(missing)]
            or ["- None"]
        ),
    ]


def build_argument_parser() -> argparse.ArgumentParser:
    """
    Define terminal arguments for the program.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Generate a structural Foundry YAML root mapping "
            "from an RDF, OWL, or Turtle ontology."
        )
    )

    parser.add_argument(
        "--ontology",
        required=True,
        type=Path,
        help="Path to the RDF, OWL, or TTL ontology file.",
    )

    parser.add_argument(
        "--root-class",
        required=True,
        action="append",
        help=(
            "Root ontology class name or complete URI. "
            "Repeat this argument for multiple root classes."
        ),
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path where the generated YAML file will be written.",
    )

    parser.add_argument(
        "--ontology-prefix",
        default="ont",
        help="Prefix used for the ontology namespace. Default: ont",
    )

    parser.add_argument(
        "--resource-prefix",
        default="res",
        help="Prefix used for draft instance URIs. Default: res",
    )

    parser.add_argument(
        "--max-depth",
        type=int,
        default=4,
        help="Maximum recursive class depth. Default: 4",
    )

    parser.add_argument(
        "--compare",
        type=Path,
        help="Optional existing YAML mapping for predicate comparison.",
    )

    parser.add_argument(
        "--report",
        type=Path,
        help="Optional path for a text comparison report.",
    )

    return parser


def main() -> None:
    parser = build_argument_parser()
    arguments = parser.parse_args()

    if not arguments.ontology.exists():
        parser.error(
            f"Ontology file does not exist: {arguments.ontology}"
        )

    if arguments.max_depth < 0:
        parser.error("--max-depth must be zero or greater.")

    if arguments.compare and not arguments.compare.exists():
        parser.error(
            f"Comparison file does not exist: {arguments.compare}"
        )

    graph = load_graph(arguments.ontology)

    root_class_uris = [
        resolve_class(graph, class_value)
        for class_value in arguments.root_class
    ]

    ontology_namespace = namespace_from_uri(
        root_class_uris[0]
    )

    root_nodes = [
        build_node(
            graph=graph,
            class_uri=class_uri,
            ontology_namespace=ontology_namespace,
            ontology_prefix=arguments.ontology_prefix,
            resource_prefix=arguments.resource_prefix,
            maximum_depth=arguments.max_depth,
            current_depth=0,
            path=(class_uri,),
        )
        for class_uri in root_class_uris
    ]

    root = merge_root_nodes(
        root_nodes=root_nodes,
        root_class_uris=root_class_uris,
        graph=graph,
        ontology_namespace=ontology_namespace,
        ontology_prefix=arguments.ontology_prefix,
        resource_prefix=arguments.resource_prefix,
    )

    generated_mapping = {
        "root": root
    }

    arguments.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    arguments.output.write_text(
        yaml.safe_dump(
            generated_mapping,
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    report_lines = [
        "Ontology-to-YAML structural prototype",
        "=====================================",
        f"Ontology file: {arguments.ontology}",
        f"Ontology triples read: {len(graph)}",
        f"Root classes: {', '.join(arguments.root_class)}",
        f"Maximum depth: {arguments.max_depth}",
        f"Output file: {arguments.output}",
    ]

    if arguments.compare:
        report_lines.extend(
            [
                "",
                *compare_with_mapping(
                    generated_mapping,
                    arguments.compare,
                ),
                "",
                (
                    "This is predicate-level comparison, "
                    "not complete YAML equivalence."
                ),
                (
                    "metadata, cvs, varids, val_source, CSV matching, "
                    "repeated branches, and specialized subclasses "
                    "are not generated yet."
                ),
            ]
        )

    if arguments.report:
        arguments.report.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        arguments.report.write_text(
            "\n".join(report_lines) + "\n",
            encoding="utf-8",
        )

        print(f"Created report: {arguments.report}")

    print(f"Read {len(graph)} ontology triples.")
    print(f"Created mapping: {arguments.output}")


if __name__ == "__main__":
    main()