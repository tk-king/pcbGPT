import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import sexpdata
from tqdm.auto import tqdm

from backend.config import KICAD_FOOTPRINT_PATH, KICAD_SYMBOL_PATH
from backend.data.Component.KiCadComponent import KiCadComponent
from backend.runtime_paths import datasets_dir

logger = logging.getLogger(__name__)


class ParseError(Exception):
    pass


def parse_kicad_symbol_lib_file(symbol_file: Path) -> List[KiCadComponent]:
    logger.info("Parsing symbol file %s", symbol_file)
    if not symbol_file.exists():
        raise FileNotFoundError(f"No such file: {symbol_file}")

    try:
        file_content = symbol_file.read_text(encoding="utf-8")
    except Exception as exc:
        raise ParseError(f"Failed to read file: {symbol_file}") from exc

    try:
        sexp_file = sexpdata.loads(file_content)
    except Exception as exc:
        raise ParseError(f"Cannot parse S-expression from {symbol_file}: {exc}") from exc

    library_dict = _build_library_dict(sexp_file)
    _resolve_extends_in_library(library_dict)
    base_names_by_symbol = _collect_base_names(library_dict)

    components: List[KiCadComponent] = []
    library_name = symbol_file.stem

    for symbol_name, symbol_data in library_dict.items():
        flattened = _flatten_symbol(symbol_name, symbol_data)
        pins_raw = flattened["pins"]
        graphics = flattened["graphics"]
        pins = _format_pins(pins_raw)
        bbox = _compute_bounding_box(pins_raw, graphics)
        component = KiCadComponent(
            name=symbol_name,
            library=library_name,
            description=flattened.get("description") or "",
            pins=pins,
            base_names=base_names_by_symbol.get(symbol_name, []),
            extends=flattened.get("extends"),
            datasheet=flattened.get("datasheet"),
            keywords=flattened.get("keywords"),
            fp_filters=flattened.get("fp_filters") or "",
            default_footprint=flattened.get("footprint"),
            pin_geometries=pins_raw,
            graphics=graphics,
            bbox=bbox,
        )
        components.append(component)

    logger.debug("Parsed %d components from %s", len(components), symbol_file)
    return components


def parse_and_store_components() -> List[KiCadComponent]:
    logger.info(
        "Parsing KiCad components from %s and %s",
        KICAD_SYMBOL_PATH,
        KICAD_FOOTPRINT_PATH,
    )

    if not KICAD_SYMBOL_PATH:
        raise ValueError("KICAD_SYMBOL_PATH is not configured")

    symbol_root = Path(KICAD_SYMBOL_PATH)
    if not symbol_root.exists():
        raise FileNotFoundError(f"KICAD_SYMBOL_PATH does not exist: {symbol_root}")

    all_files = sorted(symbol_root.glob("*.kicad_sym"))
    logger.info("Found %d symbol files to parse", len(all_files))

    components: List[KiCadComponent] = []
    for symbol_file in tqdm(all_files, desc="Parsing KiCad symbols"):
        try:
            components.extend(parse_kicad_symbol_lib_file(symbol_file))
        except Exception:
            logger.exception("Failed to parse %s", symbol_file)
    logger.info("Parsed %d components in total", len(components))
    print("Total components parsed:", len(components))
    save_path = datasets_dir() / "kicad_symbols.jsonl"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    json_symbols = [component.model_dump_json() for component in components]
    with save_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(json_symbols))
    logger.info("Saved parsed components to %s", save_path)
    return components


def _build_library_dict(sexp_file: List[Any]) -> Dict[str, Dict[str, Any]]:
    if not isinstance(sexp_file, list) or not sexp_file:
        raise ParseError("Invalid top-level structure in symbol file")

    library_dict: Dict[str, Dict[str, Any]] = {}
    for item in sexp_file[1:]:
        if not isinstance(item, list) or len(item) < 2:
            continue
        if _key(item[0]) != "symbol":
            continue

        symbol_name = str(item[1])
        logger.debug("Parsing symbol '%s'", symbol_name)
        symbol_body = item[2:]
        library_dict[symbol_name] = _parse_symbol_body(symbol_name, symbol_body)

    return library_dict


def _parse_symbol_body(name: str, body: List[Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "name": name,
        "extends": None,
        "resolved_extends": None,
        "properties": {},
        "description": None,
        "datasheet": None,
        "keywords": None,
        "fp_filters": None,
        "footprint": None,
        "graphics": [],
        "pins": [],
        "sub_symbols": [],
        "is_power": False,
    }

    for elem in body:
        if not isinstance(elem, list) or not elem:
            continue

        key = _key(elem[0])
        if key == "property" and len(elem) >= 3:
            prop_name = str(elem[1])
            prop_value = str(elem[2])
            result["properties"][prop_name] = prop_value

            prop_name_lower = prop_name.lower()
            if prop_name_lower == "description":
                result["description"] = prop_value
            elif prop_name_lower == "datasheet":
                result["datasheet"] = prop_value
            elif prop_name_lower == "footprint":
                result["footprint"] = prop_value
            elif prop_name_lower in {"keywords", "ki_keywords"}:
                if result["keywords"]:
                    result["keywords"] = f"{result['keywords']} {prop_value}"
                else:
                    result["keywords"] = prop_value
            elif prop_name_lower == "ki_fp_filters":
                result["fp_filters"] = prop_value

        elif key == "extends" and len(elem) >= 2:
            result["extends"] = str(elem[1])

        elif key == "pin":
            pin_data = _parse_pin(elem)
            if pin_data:
                result["pins"].append(pin_data)

        elif key == "power":
            result["is_power"] = True

        elif key in {"rectangle", "circle", "arc", "polyline", "text", "bezier"}:
            shape = _parse_graphic_element(elem)
            if shape:
                result["graphics"].append(shape)

        elif key == "symbol" and len(elem) >= 2:
            child_sym_name = str(elem[1])
            child_body = elem[2:]
            sub_symbol = _parse_subsymbol(child_sym_name, child_body)
            result["sub_symbols"].append(sub_symbol)

    return result


def _parse_subsymbol(name: str, body: List[Any]) -> Dict[str, Any]:
    sub_data = {"sub_name": name, "pins": [], "graphics": []}
    for elem in body:
        if not isinstance(elem, list) or not elem:
            continue

        key = _key(elem[0])
        if key == "pin":
            pin_data = _parse_pin(elem)
            if pin_data:
                sub_data["pins"].append(pin_data)
        elif key in {"rectangle", "circle", "arc", "polyline", "text", "bezier"}:
            shape = _parse_graphic_element(elem)
            if shape:
                sub_data["graphics"].append(shape)
    return sub_data


def _parse_pin(pin_list: List[Any]) -> Optional[Dict[str, Any]]:
    try:
        pin_func = "passive"
        if len(pin_list) > 1 and hasattr(pin_list[1], "value"):
            pin_func = pin_list[1].value().lower()
        x = 0.0
        y = 0.0
        orientation = 0.0
        length = 2.54
        pin_name = "~"
        pin_number = ""
        hidden = False

        for item in pin_list[2:]:
            if not isinstance(item, list) or not item:
                continue

            sub_key = _key(item[0])
            if sub_key == "at":
                if len(item) >= 3:
                    x = float(item[1])
                    y = float(item[2])
                if len(item) == 4:
                    orientation = float(item[3])
            elif sub_key == "length" and len(item) >= 2:
                length = float(item[1])
            elif sub_key == "hide":
                hidden = len(item) == 1 or (
                    len(item) >= 2 and _key(item[1]) in {"yes", "true", "1"}
                )
            elif sub_key == "name" and len(item) >= 2:
                pin_name = str(item[1])
            elif sub_key == "number" and len(item) >= 2:
                pin_number = str(item[1])

        # Compute the outer end of the pin line for geometry purposes.
        # KiCad uses degrees; 0 is +X, 90 is +Y, etc.
        try:
            from math import cos, radians, sin

            angle_rad = radians(orientation)
            end_x = x + length * cos(angle_rad)
            end_y = y + length * sin(angle_rad)
        except Exception:
            end_x = x
            end_y = y

        return {
            "function": pin_func,
            "name": pin_name,
            "number": pin_number,
            "x": x,
            "y": y,
            "orientation": orientation,
            "length": length,
            "hidden": hidden,
            "end_x": end_x,
            "end_y": end_y,
        }
    except Exception as exc:
        logger.warning("Error parsing pin: %s", exc)
        return None


def _parse_graphic_element(elem: List[Any]) -> Optional[Dict[str, Any]]:
    if not elem:
        return None

    shape_type = _key(elem[0])
    shape_data: Dict[str, Any] = {
        "shape_type": shape_type,
        "points": [],
        "start": None,
        "end": None,
        "center": None,
        "radius": None,
        "stroke_width": 0.254,
        "stroke_type": "default",
        "fill_type": "none",
    }

    for sub in elem[1:]:
        if not isinstance(sub, list) or not sub:
            continue

        sub_key = _key(sub[0])
        if sub_key == "start" and len(sub) >= 3:
            shape_data["start"] = [float(sub[1]), float(sub[2])]
        elif sub_key == "center" and len(sub) >= 3:
            shape_data["center"] = [float(sub[1]), float(sub[2])]
        elif sub_key == "end" and len(sub) >= 3:
            shape_data["end"] = [float(sub[1]), float(sub[2])]
        elif sub_key == "mid" and len(sub) >= 3:
            shape_data["mid"] = [float(sub[1]), float(sub[2])]
        elif sub_key == "radius" and len(sub) >= 2:
            shape_data["radius"] = float(sub[1])
        elif sub_key == "pts":
            points = []
            for point in sub[1:]:
                if isinstance(point, list) and len(point) == 3 and _key(point[0]) == "xy":
                    points.append((float(point[1]), float(point[2])))
            shape_data["points"] = points
        elif sub_key == "stroke":
            for stroke_item in sub[1:]:
                if isinstance(stroke_item, list) and len(stroke_item) >= 2:
                    stroke_key = _key(stroke_item[0])
                    if stroke_key == "width":
                        shape_data["stroke_width"] = float(stroke_item[1])
                    elif stroke_key == "type":
                        shape_data["stroke_type"] = str(stroke_item[1])
        elif sub_key == "fill":
            for fill_item in sub[1:]:
                if isinstance(fill_item, list) and len(fill_item) >= 2:
                    fill_key = _key(fill_item[0])
                    if fill_key == "type":
                        shape_data["fill_type"] = str(fill_item[1])

    return shape_data


def _compute_bounding_box(
    pins: List[Dict[str, Any]], graphics: List[Dict[str, Any]]
) -> Optional[Dict[str, float]]:
    """
    Compute a simple axis-aligned bounding box over all pin
    and graphics coordinates present in the symbol.
    """
    xs: List[float] = []
    ys: List[float] = []

    # Pin anchor and tip positions.
    for pin in pins:
        x = pin.get("x")
        y = pin.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            xs.append(float(x))
            ys.append(float(y))

        end_x = pin.get("end_x")
        end_y = pin.get("end_y")
        if isinstance(end_x, (int, float)) and isinstance(end_y, (int, float)):
            xs.append(float(end_x))
            ys.append(float(end_y))

    # Graphic primitives.
    for shape in graphics:
        for key in ("start", "end", "center", "mid"):
            pt = shape.get(key)
            if (
                isinstance(pt, (list, tuple))
                and len(pt) == 2
                and all(isinstance(c, (int, float)) for c in pt)
            ):
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))

        for pt in shape.get("points", []):
            if (
                isinstance(pt, (list, tuple))
                and len(pt) == 2
                and all(isinstance(c, (int, float)) for c in pt)
            ):
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))

        # If we have a circle center + radius, approximate extents.
        center = shape.get("center")
        radius = shape.get("radius")
        if (
            isinstance(center, (list, tuple))
            and len(center) == 2
            and all(isinstance(c, (int, float)) for c in center)
            and isinstance(radius, (int, float))
        ):
            cx, cy = float(center[0]), float(center[1])
            r = float(radius)
            xs.extend([cx - r, cx + r])
            ys.extend([cy - r, cy + r])

    if not xs or not ys:
        return None

    return {
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
    }


def _resolve_extends_in_library(library_dict: Dict[str, Dict[str, Any]]) -> None:
    visited: Set[str] = set()
    for symbol_name in list(library_dict.keys()):
        _resolve_symbol_extends(symbol_name, library_dict, visited)


def _resolve_symbol_extends(
    sym_name: str, library_dict: Dict[str, Dict[str, Any]], visited: Set[str]
) -> None:
    if sym_name in visited:
        return

    visited.add(sym_name)
    child_data = library_dict[sym_name]
    parent_name = child_data.get("extends")

    if not parent_name:
        return

    if parent_name not in library_dict:
        logger.debug("Parent symbol '%s' not found for '%s'", parent_name, sym_name)
        child_data["resolved_extends"] = child_data.get("resolved_extends") or parent_name
        return

    _resolve_symbol_extends(parent_name, library_dict, visited)
    parent_data = library_dict[parent_name]
    _merge_parent_into_child(child_data, parent_data)
    child_data["resolved_extends"] = child_data.get("resolved_extends") or parent_name
    child_data["extends"] = None


def _merge_parent_into_child(child: Dict[str, Any], parent: Dict[str, Any]) -> None:
    for key, value in parent.get("properties", {}).items():
        child["properties"].setdefault(key, value)

    if not child["pins"]:
        child["pins"] = deepcopy(parent["pins"])

    if not child["graphics"]:
        child["graphics"] = deepcopy(parent["graphics"])

    if not child["sub_symbols"]:
        child["sub_symbols"] = deepcopy(parent["sub_symbols"])

    if parent.get("description") and not child.get("description"):
        child["description"] = parent["description"]
    if parent.get("datasheet") and not child.get("datasheet"):
        child["datasheet"] = parent["datasheet"]
    if parent.get("keywords") and not child.get("keywords"):
        child["keywords"] = parent["keywords"]
    if parent.get("fp_filters") and not child.get("fp_filters"):
        child["fp_filters"] = parent["fp_filters"]

    if parent.get("is_power"):
        child["is_power"] = True


def _flatten_symbol(sym_name: str, sym_data: Dict[str, Any]) -> Dict[str, Any]:
    pins = list(sym_data["pins"])
    graphics = list(sym_data["graphics"])

    for sub_symbol in sym_data.get("sub_symbols", []):
        pins.extend(sub_symbol["pins"])
        graphics.extend(sub_symbol["graphics"])

    return {
        "name": sym_name,
        "properties": sym_data["properties"],
        "description": sym_data["description"],
        "datasheet": sym_data["datasheet"],
        "keywords": sym_data["keywords"],
        "fp_filters": sym_data["fp_filters"],
        "footprint": sym_data["footprint"],
        "pins": pins,
        "graphics": graphics,
        "is_power": sym_data["is_power"],
        "extends": sym_data.get("resolved_extends") or sym_data.get("extends"),
    }


def _collect_base_names(library_dict: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Collect the full parent chain for each symbol.

    For a derived symbol like `LED_Small` that extends `LED`, the resulting
    `base_names` entry is `["LED"]`. For deeper chains, the ancestry is
    returned in order from closest parent to furthest base.
    """
    base_names: Dict[str, List[str]] = {symbol_name: [] for symbol_name in library_dict}

    for symbol_name, symbol_data in library_dict.items():
        parent_name = symbol_data.get("resolved_extends") or symbol_data.get("extends")
        visited: Set[str] = set()

        while isinstance(parent_name, str) and parent_name in library_dict and parent_name not in visited:
            base_names[symbol_name].append(parent_name)
            visited.add(parent_name)
            parent_data = library_dict[parent_name]
            parent_name = parent_data.get("resolved_extends") or parent_data.get("extends")

    return base_names


def _format_pins(pin_definitions: List[Dict[str, Any]]) -> List[str]:
    formatted: List[str] = []
    for pin in pin_definitions:
        number = pin.get("number")
        name = pin.get("name")
        if number and name and name != "~":
            formatted.append(f"{number}:{name}")
        elif number:
            formatted.append(number)
        elif name and name != "~":
            formatted.append(name)
    return formatted


def _key(obj: Any) -> str:
    if hasattr(obj, "value"):
        return obj.value().lower()
    return str(obj).lower()
