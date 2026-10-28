"""
Contract tests for tools/farm_map_editor.html.

The editor's pure functions (between CORE-START and CORE-END) run in node;
their output must load with the Python farm map model.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from src.layout.farm_map import FarmMap

EDITOR = Path("tools/farm_map_editor.html")
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")

SCRIPT = r"""
const Core = require(process.argv[2]);
// ruler: tile edge 40 px along x (↘: +20, +10 per... ), image 800x600
const A = [400, 100], n = 10, m = 8;
const ex = [20, 10], ey = [-20, 10];
const B = [A[0] + n * ex[0], A[1] + n * ex[1]];
const C = [A[0] + m * ey[0], A[1] + m * ey[1]];
const bg = Core.calibrate(A, B, C, n, m, 800, 600);

// the ruler corner A stays on a tile corner after normalisation
const tA = Core.pxToTile(bg, A[0], A[1]);
const roundTrip = Core.tileToPx(bg, 3, 4);
const back = Core.pxToTile(bg, roundTrip[0], roundTrip[1]);

const state = {
  bg, imgW: 800, imgH: 600,
  fixed: [{ id: 'farmhouse', name: 'Farmhouse', rect: [Math.round(tA[0]), Math.round(tA[1]), 3, 3] },
          { id: 'mine', name: '', rect: null }],
  expansions: [{ id: 'main_1', section: 'main', number: 1, unlocked: true, cells: [[2, 2, 4, 3], [6, 2, 1, 1]] },
               { id: 'base', section: 'base', number: null, unlocked: true, cells: [[10, 10, 5, 5]] }],
  zones: [{ id: 'pond', kind: 'blocked', cells: [[2, 2, 1, 1]] }, { id: 'garden', kind: 'design', cells: [[3, 3, 1, 1]] }],
};
const map = Core.toFarmMap(state, 'farm_background.png');
const again = Core.toFarmMap(Object.assign(Core.fromFarmMap(map), { imgW: 800, imgH: 600 }), 'farm_background.png');

// moving a rect to a shifted calibration keeps its physical place
const shifted = { origin: [bg.origin[0] + 2 * ex[0], bg.origin[1] + 2 * ex[1]], ex, ey };
const moved = Core.moveRect(bg, shifted, [5, 5, 2, 3]);

const crop = Core.cropBox(bg, [[2, 2, 4, 3]], 1, 800, 600);
const zip = Core.zip([{ name: 'a.txt', data: new TextEncoder().encode('hello') },
                      { name: 'dir/b.json', data: new TextEncoder().encode('{"x": 1}') }]);
console.log(JSON.stringify({
  bg, tA, back, map, same: JSON.stringify(map) === JSON.stringify(again), moved, crop,
  rect: Core.rectFromTiles([5.7, 2.1], [3.2, 4.9]), snake: Core.toSnake("Maggie's Workbench"),
  zip: Buffer.from(zip).toString('base64'),
  merged: Core.mergeCells([[0, 0, 2, 1]], [[2, 0, 1, 1], [0, 0, 1, 1]]),
  erased: Core.mergeCells([[0, 0, 3, 1]], [], [[1, 0, 1, 1]]),
  outline: Core.outlineSegments([[0, 0, 2, 1], [2, 0, 1, 1]]).length,
  cropped: (() => {
    const c = Core.cropMap(state, 1);
    const s2 = Object.assign({}, state, c);
    return { bg: c.bg, map: Core.toFarmMap(s2, 'farm_background.png'),
             farmhouse: Core.tileToPx(c.bg, ...c.fixed[0].rect.slice(0, 2)),
             farmhouseBefore: Core.tileToPx(bg, ...state.fixed[0].rect.slice(0, 2)) };
  })(),
  current: (() => {
    const t = { bg, imgW: 800, imgH: 600, expansions: [], zones: [],
      fixed: [{ id: 'farmhouse', name: '', rect: [1, 1, 4, 4] }],
      current: [{ id: 'bakery', rect: [8, 1, 3, 3], count: 1 }, { id: 'field', rect: null, count: 12 }] };
    const m = Core.toFarmMap(t, 'farm_background.png');
    // a map from before v1.3: barn and silo in `fixed`, the barn measured
    const old = Core.fromFarmMap({ width: 20, height: 20, fixed: [
      { id: 'farmhouse', x: 1, y: 1, width: 4, height: 4 },
      { id: 'barn', movable: true, x: 8, y: 1, width: 3, height: 3 },
      { id: 'silo', x: null, y: null, width: null, height: null }] });
    const layout = { blocks: [{ items: [
      { id: 'bakery', rect: [0, 0, 3, 3], rotated: false },
      { id: 'ice_cream_maker', rect: [0, 0, 2, 3], rotated: true }] }] };
    const sizes = Core.layoutSizes(layout);
    return { map: m, back: Core.toFarmMap(Object.assign(Core.fromFarmMap(m), { imgW: 800, imgH: 600 }), 'farm_background.png'),
             old: Core.toFarmMap(Object.assign(old, { bg: null }), null),
             sizes, ok: Core.sizeWarning('ice_cream_maker', [5, 5, 2, 3], sizes.ice_cream_maker),
             bad: Core.sizeWarning('bakery', [5, 5, 2, 2], sizes.bakery),
             free: Core.sizeWarning('windmill', [5, 5, 2, 2], sizes.windmill) };
  })(),
  align: (() => {
    // overlay = map shrunk to a third, turned 90 degrees, shifted by (50, 20)
    const truth = [0, 1 / 3, -1 / 3, 0, 50, 20];
    const r = [[30, 60], [300, 90], [120, 400]];
    const pts = {};
    r.forEach((p, i) => { pts['r' + (i + 1)] = p; pts['m' + (i + 1)] = Core.applyAffine(truth, p); });
    const start = [1, 0, 0, 1, 0, 0];
    const one = Core.alignOverlay({ r1: pts.r1, m1: pts.m1 }, start);
    const two = Core.alignOverlay({ r1: pts.r1, m1: pts.m1, r2: pts.r2, m2: pts.m2 }, start);
    return {
      none: Core.alignOverlay({ r1: pts.r1 }, start),
      one, oneHit: Core.applyAffine(one, pts.r1), m1: pts.m1,
      two, three: Core.alignOverlay(pts, start), truth,
      fit: Core.fitAffine(200, 100, [10, 20, 100, 100]),
    };
  })(),
  affine: (() => {
    // overlay drawn at half size, shifted by (100, 50)
    const src = [[0, 0], [200, 0], [0, 100]], dst = src.map(p => [p[0] / 2 + 100, p[1] / 2 + 50]);
    const m = Core.affine3(src, dst);
    return { m, p: Core.applyAffine(m, [40, 60]), back: Core.applyAffine(Core.invertAffine(m), [120, 80]) };
  })(),
}));
"""


def _run_core(tmp: Path, script: str, *args: str) -> dict:
    """Run *script* in node with the editor core as argv[2]; returns its JSON output."""
    html = EDITOR.read_text(encoding="utf-8")
    core = html.split("// CORE-START", 1)[1].split("// CORE-END", 1)[0]
    core = core.split("\n", 1)[1]  # drop the rest of the marker line
    (tmp / "core.js").write_text(core, encoding="utf-8")
    (tmp / "run.js").write_text(script, encoding="utf-8")
    out = subprocess.run(
        [NODE, str(tmp / "run.js"), str(tmp / "core.js"), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


@pytest.fixture(scope="module")
def result(tmp_path_factory) -> dict:
    return _run_core(tmp_path_factory.mktemp("editor"), SCRIPT)


def test_calibration_covers_image_and_keeps_ruler_on_grid(result: dict) -> None:
    bg = result["bg"]
    assert bg["ex"] == [20, 10] and bg["ey"] == [-20, 10]
    assert bg["width"] > 0 and bg["height"] > 0
    tx, ty = result["tA"]
    assert abs(tx - round(tx)) < 1e-9 and abs(ty - round(ty)) < 1e-9
    assert result["back"] == pytest.approx([3, 4])


def test_exported_json_loads_in_python(result: dict) -> None:
    fm = FarmMap.model_validate(result["map"])
    assert fm.bounded and fm.background is not None
    assert fm.background.image == "farm_background.png"
    assert fm.background.image_width == 800
    assert [f.id for f in fm.placed_fixed] == ["farmhouse"]
    assert fm.fixed[0].name == "Farmhouse"
    assert [(z.id, z.kind) for z in fm.zones] == [
        ("pond", "blocked"),
        ("garden", "design"),
    ]
    assert len(fm.usable_tiles()) == 4 * 3 + 1 + 25 - 1
    assert result["same"], "toFarmMap(fromFarmMap(x)) must round-trip"


def test_current_farm_round_trip(result: dict) -> None:
    cur = result["current"]
    fm = FarmMap.model_validate(cur["map"])
    assert [f.id for f in fm.placed_fixed] == ["farmhouse"]
    assert [(c.id, c.x, c.count) for c in fm.current] == [
        ("bakery", 8, 1),
        ("field", None, 12),
    ]
    assert cur["back"] == cur["map"]


def test_old_fixed_barn_and_silo_move_to_current(result: dict) -> None:
    old = result["current"]["old"]
    assert [f["id"] for f in old["fixed"]] == ["farmhouse"]
    assert "movable" not in old["fixed"][0]
    # the measured barn becomes a current item, the unmeasured silo is dropped
    assert old["current"] == [{"id": "barn", "x": 8, "y": 1, "width": 3, "height": 3}]


def test_current_sizes_from_the_layout(result: dict) -> None:
    cur = result["current"]
    # a rotated layout item is offered at its stored (data) size
    assert cur["sizes"] == {"bakery": [3, 3], "ice_cream_maker": [3, 2]}
    assert cur["ok"] is None  # rotated size accepted
    assert "3x3 in the layout" in cur["bad"]
    assert cur["free"] is None  # not in the layout: no check


def test_geometry_helpers(result: dict) -> None:
    assert result["moved"] == [3, 5, 2, 3]
    assert result["rect"] == [3, 2, 3, 3]
    assert result["snake"] == "maggie_s_workbench"
    x, y, w, h = result["crop"]
    assert x >= 0 and y >= 0 and x + w <= 800 and y + h <= 600 and w > 0 and h > 0


def test_zip_writer_produces_valid_archive(result: dict) -> None:
    import base64

    data = base64.b64decode(result["zip"])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert zf.testzip() is None
        assert zf.read("a.txt") == b"hello"
        assert json.loads(zf.read("dir/b.json")) == {"x": 1}


def test_affine_from_three_points(result: dict) -> None:
    aff = result["affine"]
    assert aff["m"] == pytest.approx([0.5, 0, 0, 0.5, 100, 50])
    assert aff["p"] == pytest.approx([120, 80])
    assert aff["back"] == pytest.approx([40, 60])


def test_overlay_snaps_closer_after_each_pair(result: dict) -> None:
    a = result["align"]
    assert a["none"] == [1, 0, 0, 1, 0, 0]  # an r point without its m: unchanged
    # 1 pair: only moved, so r1 lands on m1 and the scale stays
    assert a["one"][:4] == [1, 0, 0, 1]
    assert a["oneHit"] == pytest.approx(a["m1"])
    # the true map is a similarity: 2 pairs already find it, 3 pairs too
    assert a["two"] == pytest.approx(a["truth"])
    assert a["three"] == pytest.approx(a["truth"])
    # a 200x100 overlay fitted into a 100x100 box: half size, centred vertically
    assert a["fit"] == pytest.approx([0.5, 0, 0, 0.5, 10, 45])


def test_merge_and_erase_cells(result: dict) -> None:
    # touching and overlapping rectangles become one 3x1 bar
    assert result["merged"] == [[0, 0, 3, 1]]
    # erasing the middle tile leaves two single tiles
    assert result["erased"] == [[0, 0, 1, 1], [2, 0, 1, 1]]
    # the bar has 4 border segments: inner edges are not drawn
    assert result["outline"] == 4


def test_crop_keeps_the_farm_in_place(result: dict) -> None:
    c = result["cropped"]
    fm = FarmMap.model_validate(c["map"])
    # the content (plots at 2..15, a 3x3 house) plus a 1-tile margin
    assert fm.width < result["bg"]["width"] and fm.height < result["bg"]["height"]
    assert fm.zones[0].cells == [(1, 1, 1, 1)]
    # same physical spot: the pixel of the farmhouse corner is unchanged
    assert c["farmhouse"] == pytest.approx(c["farmhouseBefore"])


LAYOUT_SCRIPT = r"""
const Core = require(process.argv[2]);
const payload = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
const plain = Core.fromLayout(payload);
let error = null;
try { Core.fromLayout({ width: 10, fixed: [] }); } catch (e) { error = e.message; }
const same = { width: payload.map.width, height: payload.map.height };
console.log(JSON.stringify({
  plain,
  combined: JSON.stringify(Core.fromLayout({ summary: {}, layout: payload })) === JSON.stringify(plain),
  error,
  fits: Core.layoutMismatch(plain, same),
  other: Core.layoutMismatch(plain, { width: same.width - 1, height: same.height }),
  noMap: Core.layoutMismatch(plain, null),
  unbounded: Core.layoutMismatch(Object.assign({}, plain, { map: { bounded: false } }), same),
  // same size, but the map was cropped: the farmhouse stands one tile further
  shifted: Core.layoutMismatch(plain, same, plain.fixed.map(f => ({ id: f.id, rect: [f.rect[0] - 1, ...f.rect.slice(1)] }))),
  sameFixed: Core.layoutMismatch(plain, same, plain.fixed),
  stored: Core.isLayoutOverlay(JSON.parse(JSON.stringify(plain))),
  oldStored: Core.isLayoutOverlay({ map: plain.map, blocks: plain.blocks }),
}));
"""


@pytest.mark.skipif(
    not Path("data/locations.json").exists(), reason="data/locations.json not found"
)
def test_layout_overlay_reads_the_layout_json(tmp_path: Path) -> None:
    from src.layout.describe import layout_to_dict
    from src.layout.farm_map import FixedItem
    from src.layout.planner import plan_layout
    from src.loaders.json_loader import load_data

    farm_map = FarmMap(
        width=60,
        height=60,
        fixed=[FixedItem(id="farmhouse", x=27, y=27, width=4, height=3)],
    )
    layout = plan_layout(
        load_data("data", 15), level=15, farm_map=farm_map, design=True
    )
    payload = layout_to_dict(layout)
    (tmp_path / "layout.json").write_text(json.dumps(payload), encoding="utf-8")
    out = _run_core(tmp_path, LAYOUT_SCRIPT, str(tmp_path / "layout.json"))

    plain = out["plain"]
    assert out["combined"], "combined.json must give the same overlay as its layout"
    assert out["error"] == "Not a layout.json or combined.json file"
    assert plain["map"] == {"bounded": True, "width": 60, "height": 60}
    placed = [b for b in payload["blocks"] if b["frame"]]
    assert [b["id"] for b in plain["blocks"]] == [b["id"] for b in placed]
    first, src = plain["blocks"][0], placed[0]
    f = src["frame"]
    assert first["frame"] == [f["x"], f["y"], f["width"], f["height"]]
    assert len(first["items"]) == len(src["items"])
    assert first["items"][0]["id"] == src["items"][0]["location_id"]

    # paths and the decoration band: the same tiles as few rects
    def tiles(cells: list) -> set:
        return {
            (x + i, y + j) for x, y, w, h in cells for i in range(w) for j in range(h)
        }

    design = payload["design"]
    assert design["paths"]
    assert tiles(plain["paths"]) == {tuple(t) for t in design["paths"]}
    assert tiles(plain["decorations"]) == {tuple(t) for t in design["decorations"]}
    assert design["main_paths"]
    assert tiles(plain["mainPaths"]) == {tuple(t) for t in design["main_paths"]}

    # same map size: no warning; another size or no farm map: a warning, never a shift
    assert out["fits"] is None and out["noMap"] is None
    assert "60x60" in out["other"] and "59x60" in out["other"]
    assert "unbounded" in out["unbounded"]
    assert plain["fixed"] == [{"id": "farmhouse", "rect": [27, 27, 4, 3]}]
    assert out["sameFixed"] is None and "farmhouse" in out["shifted"]
    # a stored overlay is restored only in the current shape
    assert out["stored"] is True and out["oldStored"] is False


TEMPLATE_SCRIPT = r"""
const Core = require(process.argv[2]);
const state = {
  current: [
    { id: 'dairy', rect: [10, 10, 4, 4] },
    { id: 'cow_pasture', rect: [15, 10, 4, 4] },
    { id: 'bakery', rect: [18, 18, 3, 3] },   // sticks out of the cut
    { id: 'apple_tree', count: 3 },           // count only, no rect
  ],
  zones: [
    { kind: 'design', cells: [[14, 8, 1, 8], [10, 14, 20, 1]] },
    { kind: 'blocked', cells: [[10, 10, 2, 2]] },
  ],
};
const cut = Core.cutTemplate(state, [10, 10, 9, 5]);
const tpl = Core.toTemplate(cut);
let error = null;
try { Core.toTemplate({ frame: null, buildings: [], decorations: [] }); } catch (e) { error = e.message; }
const overlap = { frame: [0, 0, 6, 6], decorations: [],
  buildings: [{ id: 'dairy', rect: [0, 0, 3, 3] }, { id: 'bakery', rect: [2, 2, 3, 3] }, { id: 'mill', rect: [5, 5, 2, 2] }] };
console.log(JSON.stringify({
  cut, tpl, error,
  // a building over a decoration tile wins the tile
  covered: Core.toTemplate({ frame: [0, 0, 4, 4], buildings: [{ id: 'dairy', rect: [0, 0, 2, 2] }], decorations: [[0, 0, 4, 1]] }),
  back: Core.toTemplate(Core.fromTemplate(tpl, [3, 7])),
  placed: Core.fromTemplate(tpl, [3, 7]),
  warnings: Core.templateWarnings(overlap),
  overlapError: (() => { try { Core.toTemplate(overlap); } catch (e) { return e.message; } })(),
  clean: Core.templateWarnings(cut),
  bad: (() => { try { Core.fromTemplate({ width: 3 }); } catch (e) { return e.message; } })(),
}));
"""


def test_template_cut_export_and_load(tmp_path: Path) -> None:
    from src.layout.templates import DesignTemplate

    out = _run_core(tmp_path, TEMPLATE_SCRIPT)
    # only current items fully inside the cut, only design-zone tiles, clipped
    assert [b["id"] for b in out["cut"]["buildings"]] == ["dairy", "cow_pasture"]
    tpl = DesignTemplate.model_validate(out["tpl"])
    assert (tpl.width, tpl.height) == (9, 5)
    assert [(b.location_id, b.x, b.y) for b in tpl.buildings] == [
        ("dairy", 0, 0),
        ("cow_pasture", 5, 0),
    ]
    assert tpl.decoration_tiles() == {(4, y) for y in range(5)} | {
        (x, 4) for x in range(9)
    }
    assert out["error"] == "Draw the template frame first."
    covered = DesignTemplate.model_validate(out["covered"])
    assert covered.decoration_tiles() == {(2, 0), (3, 0)}
    # placing a template elsewhere and exporting it again gives the same file
    assert out["back"] == out["tpl"]
    assert out["placed"]["frame"] == [3, 7, 9, 5]
    assert out["placed"]["buildings"][0] == {"id": "dairy", "rect": [3, 7, 4, 4]}
    assert out["warnings"] == [
        "bakery overlaps another building.",
        "mill lies outside the frame (left out).",
    ]
    assert out["overlapError"] == "bakery overlaps another building."
    assert out["clean"] == []
    assert out["bad"] == "Not a design template file"


TEMPLATE_LAYOUT_SCRIPT = r"""
const Core = require(process.argv[2]);
const payload = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
console.log(JSON.stringify(Core.fromLayout(payload).blocks.map(b => ({ id: b.id, template: b.template }))));
"""


@pytest.mark.skipif(
    not Path("data/locations.json").exists(), reason="data/locations.json not found"
)
def test_layout_overlay_carries_block_templates(tmp_path: Path) -> None:
    from src.layout.describe import layout_to_dict
    from src.layout.planner import plan_layout
    from src.layout.templates import BlockTemplate, load_template
    from src.loaders.json_loader import load_data

    garden = BlockTemplate("dairy_garden", load_template("dairy_garden"), "arrange")
    layout = plan_layout(
        load_data("data", 15),
        level=15,
        farm_map=FarmMap(width=80, height=80),
        templates={"dairy_block": garden},
    )
    payload = layout_to_dict(layout)
    (tmp_path / "layout.json").write_text(json.dumps(payload), encoding="utf-8")
    blocks = {
        b["id"]: b["template"]
        for b in _run_core(
            tmp_path, TEMPLATE_LAYOUT_SCRIPT, str(tmp_path / "layout.json")
        )
    }
    src = next(b for b in payload["blocks"] if b["id"] == "dairy_block")["template"]
    assert blocks["dairy_block"] == {
        "name": "dairy_garden",
        "mode": "arrange",
        "rect": [src["x"], src["y"], src["width"], src["height"]],
        "decorations": src["decorations"],
    }
    assert all(t is None for k, t in blocks.items() if k != "dairy_block")
