from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from uuid import uuid4

from backend.Circuit.Circuit import Circuit
from backend.Circuit.Component import Component
from backend.Circuit.Pin import Pin
from backend.core.exceptions import CircuitException


SCHEMATIC_VERSION = "20240108"
GENERATOR_NAME = "pcbgpt-netlist-collection"
DEFAULT_PAPER = "A3"
PIN_PITCH = 5.08  # 0.2in keeps symbols compact
SYMBOL_WIDTH = 12.0
FONT_SIZE = (1.27, 1.27)
ROTATION_ANGLE = 0

BLOCK_DISTANCE = 40.0
BLOCK_WIDTH = 25.0
BLOCK_HEIGHT = 25.0

COMPONENT_GAP = 10.0
FUNCTIONAL_BLOCK_GAP = 20.0
FUNCTIONAL_BLOCK_PADDING = 6.0
FUNCTIONAL_BLOCK_LABEL_INSET = 1.5
FUNCTIONAL_BLOCK_STROKE_WIDTH = 0.1524
ORIGIN_X = 20
ORIGIN_Y = 20
REFERENCE_LABEL_MARGIN = 2.5
VALUE_LABEL_MARGIN = 2.5
PAPER_LAYOUT_BOUNDS: Dict[str, Tuple[float, float, float, float]] = {
    "A4": (12.0, 12.0, 285.0, 198.0),
    "A3": (12.0, 12.0, 408.0, 285.0),
}


@dataclass
class BoundingBox:
    left: float    
    right: float   
    top: float     
    bottom: float  

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass
class PinGeometry:
    number: str
    name: str | None
    rel_x: float
    rel_y: float
    orientation: int
    length: float = 2.54
    hidden: bool = False


@dataclass
class SymbolDefinition:
    symbol_id: str
    width: float
    height: float
    pins: List[PinGeometry]
    symbol_name: str
    graphics: List[Dict[str, Any]]
    pin_geometries: List[Dict[str, Any]]


@dataclass
class SymbolInstance:
    definition: SymbolDefinition
    component: Component
    position: Tuple[float, float]
    # rotation: float
    uuid: str
    path_uuid: str
    pin_uuids: Dict[str, str]
    bounding_box: BoundingBox


@dataclass
class WireSegment:
    points: Tuple[Tuple[float, float], Tuple[float, float]]
    uuid: str


@dataclass
class NetLabel:
    name: str
    position: Tuple[float, float]
    justify_left: bool
    uuid: str
    rotation: float


@dataclass
class LayoutCandidate:
    placements: List[SymbolInstance]
    used_width: float
    used_height: float
    overflow_x: float
    overflow_y: float
    aspect_delta: float
    columns: int


@dataclass
class FunctionalBlockFrame:
    block_id: str
    label: str
    left: float
    top: float
    right: float
    bottom: float
    uuid: str
    label_uuid: str


def _fmt_float(value: float) -> str:
    result = f"{value:.4f}"
    result = result.rstrip("0").rstrip(".")
    return result or "0"


def _escape(value: str | None) -> str:
    if value is None:
        return ""
    return value.replace('"', r"\"")


def _natural_key(token: str) -> Sequence[tuple[int, object]]:
    parts = re.split(r"(\d+)", token)
    key: List[tuple[int, object]] = []
    for part in parts:
        if part == "":
            continue
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return key


def _estimate_text_width(text: str, font_size: float = FONT_SIZE[0]) -> float:
    """Estimate text width based on character count and font size.
    """
    if not text:
        return 0.0
    return (len(text) + 2) * font_size

class KiCadProjectGenerator:
    """Create a lightweight KiCad project from an in-memory Circuit."""

    def __init__(self, circuit: Circuit, project_name: str, paper: str = DEFAULT_PAPER):
        if not project_name:
            raise CircuitException("Project name is required.")
        self.circuit = circuit
        self.project_name = project_name
        self.paper = paper

    # ------------------------------------------------------------------ public API
    def generate(self, circuit_idx: int, subnet_ids: Dict[str, str], output_dir: Path | str) -> Path:
        project_dir = self._resolve_project_dir(Path(output_dir))
        project_dir.mkdir(parents=True, exist_ok=True)

        pro_path = project_dir / f"{self.project_name}.kicad_pro"
        if subnet_ids is None:
            sch_path = project_dir / f"{self.project_name}.kicad_sch"
            net_path = project_dir / f"{self.project_name}.net"
            self._write_project_file(pro_path)
        else:
            sch_path = project_dir / f"subcircuit_{circuit_idx}.kicad_sch"
            net_path = project_dir / f"subcircuit_{circuit_idx}.net"

        instances = self._place_components()
        schematic_content = self._generate_schematic(instances, subnet_ids, circuit_idx)
        sch_path.write_text(schematic_content, encoding="utf-8")
        self._write_netlist(net_path)

        return project_dir

    def generate_top_schematic(self, num_sub_circuits: int, output_dir: Path | str) -> Path:
        project_dir = self._resolve_project_dir(Path(output_dir))
        project_dir.mkdir(parents=True, exist_ok=True)

        pro_path = project_dir / f"{self.project_name}.kicad_pro"
        sch_path = project_dir / f"{self.project_name}.kicad_sch"

        schematic_content, subnet_ids = self._generate_top_schematic(num_sub_circuits)
        self._write_top_project_file(pro_path, subnet_ids)
        sch_path.write_text(schematic_content, encoding="utf-8")
        return project_dir, subnet_ids

    # ------------------------------------------------------------------ helpers
    def _resolve_project_dir(self, base: Path) -> Path:
        if base.name == self.project_name:
            return base
        return base / self.project_name
    
    def _write_top_project_file(self, path: Path, subnet_ids: Dict[str, str]) -> None:
        top_path_uuid = subnet_ids["top_path_uuid"]
        blank_project = {
            "meta": {"filename": path.name, "version": 1},
            "board": {"design_settings": {"defaults": {}}},
            "boards": [],
            "cvpcb": {},
            "erc": {},
            "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
            "net_settings": {},
            "pcbnew": {},
            "schematic": {
                "annotate_start_num": 1,
                "drawing": {"default_line_thickness": 6.0},
                "meta": {"version": 1},
                "ngspice": {"meta": {"version": 0}},
            },
            "sheets": [
                [top_path_uuid, "Root"]
            ] + [
                [subnet_ids[str(i)], f"sub Sheet {i}"]
                for i in range(len(subnet_ids) - 1)
            ],
            "text_variables": {},
        }
        path.write_text(json.dumps(blank_project, indent=2), encoding="utf-8")

    def _write_project_file(self, path: Path) -> None:
        if path.exists():
            return
        blank_project = {
            "meta": {"filename": path.name, "version": 1},
            "board": {"design_settings": {"defaults": {}}},
            "boards": [],
            "cvpcb": {},
            "erc": {},
            "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
            "net_settings": {},
            "pcbnew": {},
            "schematic": {
                "annotate_start_num": 1,
                "drawing": {"default_line_thickness": 6.0},
                "meta": {"version": 1},
                "ngspice": {"meta": {"version": 0}},
            },
            "sheets": [],
            "text_variables": {},
        }
        path.write_text(json.dumps(blank_project, indent=2), encoding="utf-8")

    def _place_components(self) -> List[SymbolInstance]:
        component_items = sorted(self.circuit.components.items(), key=lambda item: item[0])
        if not component_items:
            return []

        path_uuid = str(uuid4())
        blocks = self._component_blocks(component_items)
        if len(blocks) == 1 and blocks[0][0] is None:
            definitions = [
                (component, self._build_symbol_definition(component))
                for component in blocks[0][1]
            ]
            return self._place_component_grid(
                definitions,
                origin_x=ORIGIN_X,
                origin_y=ORIGIN_Y,
                path_uuid=path_uuid,
            )

        min_x, min_y, max_x, _ = self._paper_layout_bounds()
        row_start_x = max(ORIGIN_X, min_x)
        current_x = row_start_x
        current_y = max(ORIGIN_Y, min_y)
        row_bottom = current_y
        placements: List[SymbolInstance] = []
        for block_id, block_components in blocks:
            definitions = [
                (component, self._build_symbol_definition(component))
                for component in block_components
            ]
            block_placements = self._place_component_grid(
                definitions,
                origin_x=current_x,
                origin_y=current_y,
                path_uuid=path_uuid,
                page_margin=(
                    FUNCTIONAL_BLOCK_PADDING if block_id is not None else 0.0
                ),
            )

            _, block_right, _, block_bottom = self._placement_bounds(
                block_placements
            )
            if block_id is not None:
                block_right += FUNCTIONAL_BLOCK_PADDING
                block_bottom += FUNCTIONAL_BLOCK_PADDING

            # A block laid out in the remaining width may not fit even though the
            # same block fits at the beginning of the next row. Retry there before
            # accepting an overflowing placement.
            if block_right > max_x and current_x > row_start_x:
                current_x = row_start_x
                current_y = row_bottom + FUNCTIONAL_BLOCK_GAP
                block_placements = self._place_component_grid(
                    definitions,
                    origin_x=current_x,
                    origin_y=current_y,
                    path_uuid=path_uuid,
                    page_margin=(
                        FUNCTIONAL_BLOCK_PADDING if block_id is not None else 0.0
                    ),
                )
                _, block_right, _, block_bottom = self._placement_bounds(
                    block_placements
                )
                if block_id is not None:
                    block_right += FUNCTIONAL_BLOCK_PADDING
                    block_bottom += FUNCTIONAL_BLOCK_PADDING
                row_bottom = current_y

            placements.extend(block_placements)
            current_x = block_right + FUNCTIONAL_BLOCK_GAP
            row_bottom = max(row_bottom, block_bottom)

        return placements

    def _component_blocks(
        self, component_items: Sequence[Tuple[str, Component]]
    ) -> List[Tuple[str | None, List[Component]]]:
        ordered_block_ids = self._ordered_functional_block_ids()
        block_components: Dict[str, List[Component]] = {
            block_id: [] for block_id in ordered_block_ids
        }
        discovered_block_ids: List[str] = []
        ungrouped_components: List[Component] = []

        for _, component in component_items:
            block_id = self._component_functional_block(component)
            if block_id is None:
                ungrouped_components.append(component)
                continue
            if block_id not in block_components:
                block_components[block_id] = []
                discovered_block_ids.append(block_id)
            block_components[block_id].append(component)

        blocks: List[Tuple[str | None, List[Component]]] = []
        included_block_ids: set[str] = set()
        for block_id in ordered_block_ids + discovered_block_ids:
            if block_id in included_block_ids:
                continue
            included_block_ids.add(block_id)
            components = block_components.get(block_id, [])
            if components:
                blocks.append((block_id, components))
        if ungrouped_components:
            blocks.append((None, ungrouped_components))
        return blocks

    def _ordered_functional_block_ids(self) -> List[str]:
        block_ids: List[str] = []
        for block in getattr(self.circuit, "functional_blocks", []) or []:
            raw_id = block.get("id") if isinstance(block, dict) else block
            if raw_id is None:
                continue
            block_id = str(raw_id).strip()
            if block_id and block_id not in block_ids:
                block_ids.append(block_id)
        return block_ids

    @staticmethod
    def _component_functional_block(component: Component) -> str | None:
        block_id = getattr(component, "functional_block", None)
        if block_id is None:
            return None
        block_id = str(block_id).strip()
        return block_id or None

    def _functional_block_labels(self) -> Dict[str, str]:
        labels: Dict[str, str] = {}
        for block in getattr(self.circuit, "functional_blocks", []) or []:
            if isinstance(block, dict):
                raw_id = block.get("id")
                raw_label = block.get("label")
            else:
                raw_id = block
                raw_label = None
            if raw_id is None:
                continue
            block_id = str(raw_id).strip()
            if not block_id:
                continue
            label = str(raw_label).strip() if raw_label is not None else ""
            labels[block_id] = label or block_id.replace("_", " ").title()
        return labels

    def _place_component_grid(
        self,
        definitions: Sequence[Tuple[Component, SymbolDefinition]],
        *,
        origin_x: float,
        origin_y: float,
        path_uuid: str,
        page_margin: float = 0.0,
    ) -> List[SymbolInstance]:
        if not definitions:
            return []

        bboxes = [
            self._compute_bounding_box(component, definition)
            for component, definition in definitions
        ]

        candidate = self._select_layout_candidate(
            definitions,
            bboxes,
            path_uuid,
            origin_x=origin_x,
            origin_y=origin_y,
            page_margin=page_margin,
        )
        return candidate.placements

    def _paper_layout_bounds(self) -> Tuple[float, float, float, float]:
        return PAPER_LAYOUT_BOUNDS.get(self.paper, PAPER_LAYOUT_BOUNDS[DEFAULT_PAPER])

    def _layout_candidate(
        self,
        definitions: Sequence[Tuple[Component, SymbolDefinition]],
        bboxes: Sequence[BoundingBox],
        path_uuid: str,
        columns: int,
        *,
        origin_x: float,
        origin_y: float,
        page_margin: float = 0.0,
    ) -> LayoutCandidate:
        num_components = len(definitions)
        rows = math.ceil(num_components / columns)

        grid: List[List[int]] = [[] for _ in range(rows)]
        for idx in range(num_components):
            row = idx // columns
            grid[row].append(idx)

        min_x, min_y, max_x, max_y = self._paper_layout_bounds()
        min_x += page_margin
        min_y += page_margin
        max_x -= page_margin
        max_y -= page_margin

        col_centers: List[float] = []
        current_x = max(origin_x, min_x)
        for col_idx in range(columns):
            max_left_extent = 0.0
            for row_indices in grid:
                if col_idx < len(row_indices):
                    comp_idx = row_indices[col_idx]
                    max_left_extent = max(max_left_extent, -bboxes[comp_idx].left)

            col_center = current_x + max_left_extent
            col_centers.append(col_center)

            max_right_extent = 0.0
            for row_indices in grid:
                if col_idx < len(row_indices):
                    comp_idx = row_indices[col_idx]
                    max_right_extent = max(max_right_extent, bboxes[comp_idx].right)

            current_x = col_center + max_right_extent + COMPONENT_GAP

        placed_bounds: Dict[int, Tuple[float, float]] = {}
        placements: List[SymbolInstance] = []
        used_left = math.inf
        used_top = math.inf
        used_right = -math.inf
        used_bottom = -math.inf

        for row_idx in range(rows):
            for col_idx, comp_idx in enumerate(grid[row_idx]):
                component, definition = definitions[comp_idx]
                bbox = bboxes[comp_idx]
                center_x = col_centers[col_idx]

                if row_idx == 0:
                    top_boundary = max(origin_y, min_y)
                else:
                    if col_idx < len(grid[row_idx - 1]):
                        above_comp_idx = grid[row_idx - 1][col_idx]
                        above_comp_bottom = placed_bounds[above_comp_idx][1]
                        top_boundary = above_comp_bottom + COMPONENT_GAP
                    else:
                        top_boundary = max(origin_y, min_y)

                center_y = top_boundary + bbox.top

                abs_top = center_y - bbox.top
                abs_bottom = center_y - bbox.bottom
                placed_bounds[comp_idx] = (abs_top, abs_bottom)

                placement = SymbolInstance(
                    definition=definition,
                    component=component,
                    position=(center_x, center_y),
                    uuid=str(uuid4()),
                    path_uuid=path_uuid,
                    pin_uuids={pin.number: str(uuid4()) for pin in definition.pins},
                    bounding_box=bbox,
                )
                placements.append(placement)

                placement_left = center_x + bbox.left
                placement_right = center_x + bbox.right
                placement_top = center_y - bbox.top - REFERENCE_LABEL_MARGIN
                placement_bottom = center_y - bbox.bottom + VALUE_LABEL_MARGIN
                used_left = min(used_left, placement_left)
                used_right = max(used_right, placement_right)
                used_top = min(used_top, placement_top)
                used_bottom = max(used_bottom, placement_bottom)

        used_width = max(0.0, used_right - used_left)
        used_height = max(0.0, used_bottom - used_top)
        overflow_x = max(0.0, min_x - used_left) + max(0.0, used_right - max_x)
        overflow_y = max(0.0, min_y - used_top) + max(0.0, used_bottom - max_y)
        sheet_width = max_x - min_x
        sheet_height = max_y - min_y
        used_aspect = used_width / used_height if used_height > 0 else sheet_width / sheet_height
        sheet_aspect = sheet_width / sheet_height if sheet_height > 0 else 1.0

        return LayoutCandidate(
            placements=placements,
            used_width=used_width,
            used_height=used_height,
            overflow_x=overflow_x,
            overflow_y=overflow_y,
            aspect_delta=abs(used_aspect - sheet_aspect),
            columns=columns,
        )

    def _select_layout_candidate(
        self,
        definitions: Sequence[Tuple[Component, SymbolDefinition]],
        bboxes: Sequence[BoundingBox],
        path_uuid: str,
        *,
        origin_x: float,
        origin_y: float,
        page_margin: float = 0.0,
    ) -> LayoutCandidate:
        best_candidate: LayoutCandidate | None = None
        for columns in range(1, len(definitions) + 1):
            candidate = self._layout_candidate(
                definitions,
                bboxes,
                path_uuid,
                columns,
                origin_x=origin_x,
                origin_y=origin_y,
                page_margin=page_margin,
            )
            if best_candidate is None:
                best_candidate = candidate
                continue

            candidate_score = (
                candidate.overflow_x + candidate.overflow_y > 0.0,
                candidate.overflow_x + candidate.overflow_y,
                candidate.aspect_delta,
                candidate.used_width * candidate.used_height,
                candidate.columns,
            )
            best_score = (
                best_candidate.overflow_x + best_candidate.overflow_y > 0.0,
                best_candidate.overflow_x + best_candidate.overflow_y,
                best_candidate.aspect_delta,
                best_candidate.used_width * best_candidate.used_height,
                best_candidate.columns,
            )
            if candidate_score < best_score:
                best_candidate = candidate

        assert best_candidate is not None
        return best_candidate

    def _functional_block_frames(
        self,
        placements: Sequence[SymbolInstance],
    ) -> List[FunctionalBlockFrame]:
        block_placements: Dict[str, List[SymbolInstance]] = {}
        discovered_block_ids: List[str] = []
        for placement in placements:
            block_id = self._component_functional_block(placement.component)
            if block_id is None:
                continue
            if block_id not in block_placements:
                block_placements[block_id] = []
                discovered_block_ids.append(block_id)
            block_placements[block_id].append(placement)

        frames: List[FunctionalBlockFrame] = []
        labels = self._functional_block_labels()
        included_block_ids: set[str] = set()
        for block_id in self._ordered_functional_block_ids() + discovered_block_ids:
            if block_id in included_block_ids:
                continue
            included_block_ids.add(block_id)
            placements_for_block = block_placements.get(block_id, [])
            if not placements_for_block:
                continue
            left, right, top, bottom = self._placement_bounds(placements_for_block)
            frames.append(
                FunctionalBlockFrame(
                    block_id=block_id,
                    label=labels.get(block_id, block_id.replace("_", " ").title()),
                    left=left - FUNCTIONAL_BLOCK_PADDING,
                    top=top - FUNCTIONAL_BLOCK_PADDING,
                    right=right + FUNCTIONAL_BLOCK_PADDING,
                    bottom=bottom + FUNCTIONAL_BLOCK_PADDING,
                    uuid=str(uuid4()),
                    label_uuid=str(uuid4()),
                )
            )
        return frames

    @staticmethod
    def _placement_bounds(
        placements: Sequence[SymbolInstance],
    ) -> Tuple[float, float, float, float]:
        if not placements:
            return (ORIGIN_X, ORIGIN_X, ORIGIN_Y, ORIGIN_Y)
        left = math.inf
        right = -math.inf
        top = math.inf
        bottom = -math.inf
        for placement in placements:
            cx, cy = placement.position
            bbox = placement.bounding_box
            left = min(left, cx + bbox.left)
            right = max(right, cx + bbox.right)
            top = min(top, cy - bbox.top)
            bottom = max(bottom, cy - bbox.bottom)
        return left, right, top, bottom

    def _build_symbol_definition(self, component: Component) -> SymbolDefinition:
        pin_keys = sorted(component.pins.keys(), key=_natural_key)
        if not pin_keys:
            # create two dummy pins to keep schematic consistent
            pin_keys = ["1", "2"]

        total_pins = len(pin_keys)
        left_count = math.ceil(total_pins / 2)
        right_count = total_pins - left_count

        pins: List[PinGeometry] = []
        width = SYMBOL_WIDTH
        max_pins_per_side = max(left_count, right_count, 1)
        height = max(8.0, (max_pins_per_side - 1) * PIN_PITCH + 6.0)
        pin_geometries = []
        for pin_geometry in component.pin_geometries:
            enriched_pin_geometry = dict(pin_geometry)
            enriched_pin_geometry["hidden"] = self._pin_geometry_hidden(pin_geometry)
            pin_geometries.append(enriched_pin_geometry)

        for idx, pin_key in enumerate(pin_keys):
            pin_geometry = next(pg for pg in component.pin_geometries if pg["number"] == pin_key)
            rel_x = pin_geometry["x"]
            rel_y = pin_geometry["y"]
            orientation = pin_geometry["orientation"]
            length = pin_geometry["length"]

            pin_obj = component.pins.get(pin_key)
            pin_name = getattr(pin_obj, "name", None) if pin_obj is not None else None
            pins.append(
                PinGeometry(
                    number=pin_key,
                    name=pin_name,
                    rel_x=rel_x,
                    rel_y=rel_y,
                    orientation=orientation,
                    length=length,
                    hidden=self._pin_geometry_hidden(pin_geometry),
                )
            )
        symbol_id = self._symbol_identifier(component)
        library = component.library
        name = component.name
        symbol_name = f"{library}:{name}" if library and name else symbol_id
        return SymbolDefinition(symbol_id=symbol_id, symbol_name=symbol_name, width=width, height=height, pins=pins, graphics=component.graphics, pin_geometries=pin_geometries)

    @staticmethod
    def _pin_geometry_hidden(pin_geometry: Dict[str, Any]) -> bool:
        hidden = pin_geometry.get("hidden", False)
        if isinstance(hidden, str):
            return hidden.strip().lower() in {"1", "true", "yes"}
        return bool(hidden)


    def _compute_bounding_box(
        self, component: Component, definition: SymbolDefinition
    ) -> BoundingBox:
        """Compute the bounding box of a component including pin endpoints and net labels.
        
        The bounding box is relative to the component center point.
        Note: Reference and Value labels are NOT included in the bounding box,
        as they will be positioned after layout is determined.
        """
        # Initialize bounds from graphics shapes (symbol body)
        left = 0.0
        right = 0.0
        top = 0.0
        bottom = 0.0
        
        for graphic in definition.graphics:
            shape_type = graphic.get("shape_type", "")
            if shape_type == "text":
                continue
            points_to_check: List[Tuple[float, float]] = []            
            if graphic.get("points"):
                points_to_check.extend(graphic["points"])
            if graphic.get("start"):
                points_to_check.append(tuple(graphic["start"]))
            if graphic.get("end"):
                points_to_check.append(tuple(graphic["end"]))
            if graphic.get("mid"):
                points_to_check.append(tuple(graphic["mid"]))
            
            if graphic.get("center") and graphic.get("radius"):
                cx, cy = graphic["center"]
                r = graphic["radius"]
                points_to_check.extend([
                    (cx - r, cy),
                    (cx + r, cy),
                    (cx, cy - r),
                    (cx, cy + r),
                ])
            elif graphic.get("center"):
                points_to_check.append(tuple(graphic["center"]))
            
            for px, py in points_to_check:
                left = min(left, px)
                right = max(right, px)
                top = max(top, py)
                bottom = min(bottom, py)

        for pin in definition.pins:
            if pin.hidden:
                continue
            pin_x = pin.rel_x
            pin_y = pin.rel_y
            
            pin_obj = component.pins.get(pin.number)
            if pin_obj is not None and pin_obj.net is not None:
                net = pin_obj.net
                net_name = self._format_net_name(net.name or net.ref or "NET")
            else:
                net_name = "NET"  # Default fallback
            label_width = _estimate_text_width(net_name)

            # Pin orientation in symbol coords: 0=left, 90=down, 180=right, 270=up
            if pin.orientation == 180:  # Points right, label extends right
                right = max(right, pin_x + label_width)
            elif pin.orientation == 0:  # Points left, label extends left
                left = min(left, pin_x - label_width)
            elif pin.orientation == 270:  # Points up, label extends up
                top = max(top, pin_y + label_width)
            elif pin.orientation == 90:  # Points down, label extends down
                bottom = min(bottom, pin_y - label_width)
            
        assert left <= 0 and right >= 0 and top >= 0 and bottom <= 0

        return BoundingBox(left=left, right=right, top=top, bottom=bottom)

    def _symbol_identifier(self, component: Component) -> str:
        ref = component.ref or component.name or "U"
        ref = ref.replace(" ", "_")
        ref = re.sub(r"[^A-Za-z0-9_]", "_", ref)
        return f"pcbgpt:{ref}"
    
    def _generate_top_schematic(self, num_sub_circuits: int) -> str:
        subnet_ids = {str(i): str(uuid4()) for i in range(num_sub_circuits)}
        subnet_ids["top_path_uuid"] = str(uuid4())

        lines: List[str] = []
        indent = "  "
        lines.append(f'(kicad_sch (version {SCHEMATIC_VERSION}) (generator "{GENERATOR_NAME}")')
        lines.append("")
        lines.append(f'{indent}(uuid {subnet_ids["top_path_uuid"]})')
        lines.append("")
        lines.append(f'{indent}(paper "{self.paper}")')
        lines.append("")
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        lines.append(f"{indent}(title_block")
        lines.append(f'{indent*2}(title "{_escape(self.project_name)}")')
        lines.append(f'{indent*2}(date "{date_str}")')
        lines.append(f'{indent*2}(company "pcbgpt")')
        lines.append(f"{indent})")
        lines.append("")
        lines.append(f"{indent}(lib_symbols)")
        for i in range(num_sub_circuits):
            cols = 5
            col = i % cols
            row = i // cols
            ref_x = 20 + col * BLOCK_DISTANCE
            ref_y = 20 + row * BLOCK_DISTANCE

            lines.append(f'{indent}(sheet (at {_fmt_float(ref_x)} {_fmt_float(ref_y)}) (size {BLOCK_WIDTH} {BLOCK_HEIGHT})')
            lines.append(f"{indent*2}(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced yes) (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000))")
            lines.append(f"{indent*2}(uuid {subnet_ids[str(i)]})")
            lines.append(f'{indent*2}(property "Sheetname" "sub Sheet {i}" (at {_fmt_float(ref_x)} {_fmt_float(ref_y-1)} 0) (effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]})) (justify left bottom)))')
            lines.append(f'{indent*2}(property "Sheetfile" "subcircuit_{i}.kicad_sch" (at {_fmt_float(ref_x)} {_fmt_float(ref_y+1+BLOCK_HEIGHT)} 0) (effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]})) (justify left top)))')
            lines.append(f"{indent*2}(instances")
            lines.append(f'{indent*3}(project "{self.project_name}"')
            lines.append(f'{indent*4}(path \"/{subnet_ids["top_path_uuid"]}\" (page "{i+2}"))')
            lines.append(f"{indent*3})")
            lines.append(f"{indent*2})")
            lines.append(f"{indent})")
        lines.append(f"{indent}(sheet_instances")
        lines.append(f"{indent*2}(path \"/\" (page \"1\"))")
        lines.append(f"{indent})")
        lines.append("")
        lines.append(f"{indent}(embedded_fonts no)")
        lines.append(")")
        return "\n".join(lines), subnet_ids

    def _generate_schematic(self, placements: List[SymbolInstance], subnet_ids: Dict[str, str], circuit_idx: int) -> str:
        subnet_id = subnet_ids[str(circuit_idx)] if subnet_ids else None
        top_path_uuid = subnet_ids["top_path_uuid"] if subnet_ids else None

        lines: List[str] = []
        indent = "  "
        lines.append(f'(kicad_sch (version {SCHEMATIC_VERSION}) (generator "{GENERATOR_NAME}")')
        lines.append("")
        lines.append(f"{indent}(uuid {placements[0].path_uuid})")
        lines.append("")
        lines.append(f'{indent}(paper "{self.paper}")')
        lines.append("")
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        lines.append(f"{indent}(title_block")
        lines.append(f'{indent*2}(title "{_escape(self.project_name)}")')
        lines.append(f'{indent*2}(date "{date_str}")')
        lines.append(f'{indent*2}(company "pcbgpt")')
        lines.append(f"{indent})")
        lines.append("")
        lines.append(f"{indent}(lib_symbols")
        for placement in placements:
            lines.extend(self._symbol_definition_block(placement.definition, indent_level=2))
        lines.append(f"{indent})")
        lines.append("")

        for placement in placements:
            lines.extend(self._symbol_instance_block(placement, indent_level=1, subnet_id=subnet_id, top_path_uuid=top_path_uuid))
            lines.append("")

        for frame in self._functional_block_frames(placements):
            lines.extend(self._functional_block_frame_block(frame, indent_level=1))
            lines.append("")

        wires, labels = self._build_wires_and_labels(placements)

        for label in labels:
            justify = "left" if label.justify_left else "right"
            lines.append(
                f'{indent}(global_label "{_escape(label.name)}" '
                f'(shape input) (at {_fmt_float(label.position[0])} {_fmt_float(label.position[1])} {label.rotation}) (fields_autoplaced yes)'
            )
            lines.append(
                f"{indent*2}(effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]})) "
                f"(justify {justify}))"
            )
            lines.append(f"{indent*2}(uuid {label.uuid})")
            lines.append(f"{indent})")
        if placements:
            lines.append("")

        lines.append(f"{indent}(sheet_instances")
        lines.append(f"{indent*2}(path \"/\" (page \"1\"))")
        lines.append(f"{indent})")
        lines.append("")

        lines.append(")")
        lines.append("")

        return "\n".join(lines)

    def _functional_block_frame_block(
        self,
        frame: FunctionalBlockFrame,
        indent_level: int = 0,
    ) -> List[str]:
        indent = "  " * indent_level
        inner = "  " * (indent_level + 1)
        label_x = frame.right - FUNCTIONAL_BLOCK_LABEL_INSET
        label_y = frame.bottom - FUNCTIONAL_BLOCK_LABEL_INSET
        return [
            f"{indent}(rectangle",
            f"{inner}(start {_fmt_float(frame.left)} {_fmt_float(frame.top)})",
            f"{inner}(end {_fmt_float(frame.right)} {_fmt_float(frame.bottom)})",
            f"{inner}(stroke (width {_fmt_float(FUNCTIONAL_BLOCK_STROKE_WIDTH)}) (type dash))",
            f"{inner}(fill (type none))",
            f"{inner}(uuid {frame.uuid})",
            f"{indent})",
            f'{indent}(text "{_escape(frame.label)}" (at {_fmt_float(label_x)} {_fmt_float(label_y)} 0)',
            f"{inner}(effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]})) (justify right bottom))",
            f"{inner}(uuid {frame.label_uuid})",
            f"{indent})",
        ]

    def _symbol_definition_block(
        self, definition: SymbolDefinition, indent_level: int = 0
    ) -> List[str]:
        indent = "  " * indent_level
        inner = "  " * (indent_level + 1)
        deeper = "  " * (indent_level + 2)
        deepest = "  " * (indent_level + 3)
        lines = [
            f'{indent}(symbol "{definition.symbol_name}" (exclude_from_sim no) (in_bom yes) (on_board yes)'
        ]
        ref_y = definition.height / 2 + 3.0
        lines.append(
            f'{inner}(property "Reference" "R" (at 0 {_fmt_float(ref_y)} 0)'
        )
        lines.append(f"{deeper}(effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]})))")
        lines.append(f"{inner})")
        lines.append(
            f'{inner}(property "Value" "{definition.symbol_id.split(":")[-1]}" '
            f'(at 0 {_fmt_float(-ref_y)} 0)'
        )
        lines.append(f"{deeper}(effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]})))")
        lines.append(f"{inner})")
        lines.append(
            f'{inner}(property "Footprint" "" (at 0 {_fmt_float(-ref_y - 3)} 0)'
        )
        lines.append(f"{deeper}(effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]})) (hide yes))")
        lines.append(f"{inner})")

        lines.append(f'{inner}(symbol "{definition.symbol_name.split(":")[-1]}_0_1"')
        for graphic in definition.graphics:
            if graphic["shape_type"] == "text":
                continue
            lines.append(f"{deeper}({graphic['shape_type']}")
            if graphic['points']:
                xy_parts = " ".join(
                    f"(xy {_fmt_float(point[0])} {_fmt_float(point[1])})"
                    for point in graphic["points"]
                )
                lines.append(f"{deepest}(pts {xy_parts})")
            if graphic['start']:
                lines.append(f"{deepest}(start {_fmt_float(graphic['start'][0])} {_fmt_float(graphic['start'][1])})")
            if graphic['end']:
                lines.append(f"{deepest}(end {_fmt_float(graphic['end'][0])} {_fmt_float(graphic['end'][1])})")
            if graphic['center']:
                lines.append(f"{deepest}(center {_fmt_float(graphic['center'][0])} {_fmt_float(graphic['center'][1])})")
            if graphic['radius']:
                lines.append(f"{deepest}(radius {_fmt_float(graphic['radius'])})")
            if graphic.get("mid", None):
                lines.append(f"{deepest}(mid {_fmt_float(graphic['mid'][0])} {_fmt_float(graphic['mid'][1])})")
            lines.append(f"{deepest}(stroke (width {graphic['stroke_width']}) (type {graphic['stroke_type']}))")
            lines.append(f"{deepest}(fill (type {graphic['fill_type']}))")
            lines.append(f"{deeper})")
        lines.append(f"{inner})")
        # graphics pins definition
        lines.append(f'{inner}(symbol "{definition.symbol_name.split(":")[-1]}_1_1"')
        for pin_geometry in definition.pin_geometries:
            hide_clause = " (hide yes)" if pin_geometry.get("hidden") else ""
            lines.append(f'{deeper}(pin {pin_geometry["function"]} line (at {_fmt_float(pin_geometry["x"])} {_fmt_float(pin_geometry["y"])} {pin_geometry["orientation"]}) '
            f'(length {_fmt_float(pin_geometry["length"])}){hide_clause}')
            lines.append(f'{deepest}(name \"{_escape(pin_geometry["name"])}\" (effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]}))))')
            lines.append(f'{deepest}(number \"{_escape(pin_geometry["number"])}\" (effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]}))))')
            lines.append(f"{deeper})")
        lines.append(f"{inner})")
        lines.append(f"{indent})")
        return lines

    def _symbol_instance_block(
        self, placement: SymbolInstance, indent_level: int = 0, subnet_id: str = None, top_path_uuid: str = None
    ) -> List[str]:
        component = placement.component
        definition = placement.definition
        indent = "  " * indent_level
        inner = "  " * (indent_level + 1)
        deeper = "  " * (indent_level + 2)
        deepest = "  " * (indent_level + 3)
        lines: List[str] = [
            f'{indent}(symbol (lib_id "{definition.symbol_name}") '
            f"(at {_fmt_float(placement.position[0])} {_fmt_float(placement.position[1])} 0) (unit 1)"
        ]
        lines.append(f"{inner}(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)")
        lines.append(f"{inner}(uuid {placement.uuid})")

        ref_text = self._display_reference(component)
        ref_label_width = _estimate_text_width(ref_text)
        bbox = placement.bounding_box
        label_offset = 1.0
        ref_x = placement.position[0] + ref_label_width / 2
        ref_y = placement.position[1] - bbox.top - label_offset
        lines.append(
            f'{inner}(property "Reference" "{_escape(ref_text)}" '
            f"(at {_fmt_float(ref_x)} {_fmt_float(ref_y)} 0)"
        )
        lines.append(f"{deeper}(effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]})))")
        lines.append(f"{inner})")

        value_text = component.value or component.name or "VALUE"
        value_label_width = _estimate_text_width(value_text)
        value_x = placement.position[0] + value_label_width / 2
        value_y = placement.position[1] - bbox.bottom + label_offset
        lines.append(
            f'{inner}(property "Value" "{_escape(value_text)}" '
            f"(at {_fmt_float(value_x)} {_fmt_float(value_y)} 0)"
        )
        lines.append(f"{deeper}(effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]})))")
        lines.append(f"{inner})")

        footprint = component.footprint or ""
        lines.append(
            f'{inner}(property "Footprint" "{_escape(footprint)}" '
            f"(at {_fmt_float(placement.position[0])} {_fmt_float(value_y + 3)} 0)"
        )
        lines.append(f"{deeper}(effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]})) (hide yes))")
        lines.append(f"{inner})")

        lines.append(
            f'{inner}(property "Datasheet" "" '
            f"(at {_fmt_float(placement.position[0])} {_fmt_float(value_y + 6)} 0)"
        )
        lines.append(f"{deeper}(effects (font (size {FONT_SIZE[0]} {FONT_SIZE[1]})) (hide yes))")
        lines.append(f"{inner})")

        for pin in definition.pins:
            pin_uuid = placement.pin_uuids[pin.number]
            lines.append(f'{inner}(pin "{_escape(pin.number)}" (uuid {pin_uuid}))')

        lines.append(f"{inner}(instances")
        lines.append(f'{deeper}(project "{_escape(self.project_name)}"')
        if subnet_id and top_path_uuid:
            lines.append(
                f'{deepest}(path "/{top_path_uuid}/{subnet_id}" (reference "{_escape(ref_text)}") (unit 1))'
            )
        else:
            lines.append(
                f'{deepest}(path "/{placement.path_uuid}" (reference "{_escape(ref_text)}") (unit 1))'
            )
        lines.append(f"{deeper})")
        lines.append(f"{inner})")
        lines.append(f"{indent})")
        return lines

    def _build_wires_and_labels(
        self, placements: Sequence[SymbolInstance]
    ) -> Tuple[List[WireSegment], List[NetLabel]]:
        pin_positions: Dict[Pin, Tuple[float, float]] = {}
        stub_points: Dict[Pin, Tuple[Tuple[float, float], bool]] = {}

        for placement in placements:
            cx, cy = placement.position
            visible_pin_nets_by_geometry: Dict[
                tuple[float, float, float, float], set[object]
            ] = {}
            for pin in placement.definition.pins:
                if pin.hidden:
                    continue
                pin_obj = placement.component.pins.get(pin.number)
                if pin_obj is None or pin_obj.net is None:
                    continue
                visible_pin_nets_by_geometry.setdefault(
                    self._pin_geometry_key(pin),
                    set(),
                ).add(pin_obj.net)

            for pin in placement.definition.pins:
                pin_obj = placement.component.pins.get(pin.number)
                if pin_obj is None:
                    continue
                if (
                    pin.hidden
                    and pin_obj.net is not None
                    and pin_obj.net
                    in visible_pin_nets_by_geometry.get(
                        self._pin_geometry_key(pin),
                        set(),
                    )
                ):
                    continue
                abs_x = cx + pin.rel_x
                abs_y = cy - pin.rel_y
                pin_positions[pin_obj] = (abs_x, abs_y)
                if pin.orientation in [0, 90]:
                    stub = (abs_x, abs_y)
                    justify_left = False
                else:
                    stub = (abs_x, abs_y)
                    justify_left = True
                stub_points[pin_obj] = (stub, justify_left, pin.orientation)

        wires: List[WireSegment] = []
        labels: List[NetLabel] = []

        sorted_nets = sorted(
            self.circuit.nets.values(),
            key=lambda net: (net.name or "", net.ref or ""),
        )
        for net in sorted_nets:
            net_name = self._format_net_name(net.name or net.ref or "NET")
            seen: set[Pin] = set()
            for pin in net.pins:
                if pin in seen or pin not in pin_positions:
                    continue
                seen.add(pin)
                start = pin_positions[pin]
                stub_data = stub_points.get(pin)
                if stub_data is None:
                    continue
                end_point, justify_left, pin_orientation = stub_data
                wires.append(WireSegment(points=(start, end_point), uuid=str(uuid4())))
                labels.append(
                    NetLabel(
                        name=net_name,
                        position=end_point,
                        rotation=pin_orientation,
                        justify_left=justify_left,
                        uuid=str(uuid4()),
                    )
                )

        return wires, labels

    def _pin_geometry_key(self, pin: PinGeometry) -> tuple[float, float, float, float]:
        return (pin.rel_x, pin.rel_y, pin.orientation, pin.length)

    def _display_reference(self, component: Component) -> str:
        ref = component.ref or component.name or "U"
        if "_" in ref:
            prefix, suffix = ref.split("_", 1)
            if suffix.isdigit():
                return f"{prefix}{suffix}"
        return ref.replace("_", "")

    def _format_net_name(self, name: str) -> str:
        safe = re.sub(r"\s+", "_", name.strip())
        safe = re.sub(r"[^A-Za-z0-9_+\-]", "_", safe)
        return safe or "NET"

    def _write_netlist(self, path: Path) -> None:
        from backend.Circuit.ImporterExporter.NetlistImporterExporter import (
            NetlistImporterExporter,
        )

        exporter = NetlistImporterExporter()
        netlist = exporter.export_circuit(self.circuit)
        path.write_text(netlist, encoding="utf-8")


def generate_kicad_project(
    circuits: List[Circuit], output_dir: Path | str, project_name: str
) -> Path:
    num_sub_circuits = len(circuits)
    if num_sub_circuits == 1:
        generator = KiCadProjectGenerator(circuit=circuits[0], project_name=project_name)
        return generator.generate(circuit_idx=0, subnet_ids=None, output_dir=output_dir)
    else:
        generator = KiCadProjectGenerator(circuit=None, project_name=project_name)
        project_dir, subnet_ids = generator.generate_top_schematic(num_sub_circuits, output_dir)
        for circuit_idx, circuit in enumerate(circuits):
            generator = KiCadProjectGenerator(circuit=circuit, project_name=project_name)
            generator.generate(circuit_idx, subnet_ids, output_dir)
        return project_dir


__all__ = ["KiCadProjectGenerator", "generate_kicad_project"]
