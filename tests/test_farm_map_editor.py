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
          { id: 'silo', name: '', rect: null }],
  expansions: [{ id: 'main_1', section: 'main', number: 1, unlocked: true, cells: [[2, 2, 4, 3], [6, 2, 1, 1]] },
               { id: 'base', section: 'base', number: null, unlocked: true, cells: [[10, 10, 5, 5]] }],
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
}));
"""


@pytest.fixture(scope="module")
def result(tmp_path_factory) -> dict:
    tmp = tmp_path_factory.mktemp("editor")
    html = EDITOR.read_text(encoding="utf-8")
    core = html.split("// CORE-START", 1)[1].split("// CORE-END", 1)[0]
    core = core.split("\n", 1)[1]  # drop the rest of the marker line
    (tmp / "core.js").write_text(core, encoding="utf-8")
    (tmp / "run.js").write_text(SCRIPT, encoding="utf-8")
    out = subprocess.run(
        [NODE, str(tmp / "run.js"), str(tmp / "core.js")],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


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
    assert len(fm.usable_tiles()) == 4 * 3 + 1 + 25
    assert result["same"], "toFarmMap(fromFarmMap(x)) must round-trip"


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
