from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

# The execution environment used for repository preparation may not have laspy.
# Parser/validation tests do not need real LAS I/O, so provide a minimal import stub.
sys.modules.setdefault("laspy", types.SimpleNamespace())

import crop_height


def test_parser_defaults():
    parser = crop_height.build_parser()
    args = parser.parse_args(["--input", "in", "--shp", "plots.shp", "--output", "out.csv"])
    assert args.id_field == "Id"
    assert args.cell == 0.10
    assert args.dtm_pct == 5.0
    assert args.dsm_pct == 99.0
    assert args.border_ratio == 0.20
    assert args.recursive is False


def test_main_rejects_missing_input(tmp_path, capsys):
    shp = tmp_path / "plots.shp"
    shp.touch()
    rc = crop_height.main([
        "--input", str(tmp_path / "missing"),
        "--shp", str(shp),
        "--output", str(tmp_path / "out.csv"),
    ])
    captured = capsys.readouterr()
    assert rc != 0
    assert "input" in captured.err.lower()


def test_main_rejects_missing_shapefile(tmp_path, capsys):
    input_dir = tmp_path / "las"
    input_dir.mkdir()
    rc = crop_height.main([
        "--input", str(input_dir),
        "--shp", str(tmp_path / "missing.shp"),
        "--output", str(tmp_path / "out.csv"),
    ])
    captured = capsys.readouterr()
    assert rc != 0
    assert "shapefile" in captured.err.lower()


def test_divide_reports_missing_id_field(monkeypatch, tmp_path):
    class FakeGdf:
        columns = ["plot_id", "geometry"]

    monkeypatch.setattr(crop_height.gpd, "read_file", lambda _: FakeGdf())
    try:
        crop_height.divide("dummy.las", "plots.shp", id_field="Id")
    except ValueError as exc:
        message = str(exc)
        assert "Id" in message
        assert "plot_id" in message
    else:
        raise AssertionError("Expected ValueError for missing ID field")


def test_classification_reports_missing_required_class(monkeypatch, tmp_path):
    class FakeLas:
        classification = __import__("numpy").array([2, 2], dtype=int)
        header = types.SimpleNamespace(point_format=3, version="1.2", scale=[0.001, 0.001, 0.001], offset=[0, 0, 0])
        points = __import__("numpy").array([1, 2])

    class FakeCreated:
        def __init__(self):
            self.header = types.SimpleNamespace(scale=None, offset=None)
            self.points = None
        def write(self, _):
            pass

    monkeypatch.setattr(crop_height.laspy, "read", lambda _: FakeLas(), raising=False)
    monkeypatch.setattr(crop_height.laspy, "create", lambda **_: FakeCreated(), raising=False)

    try:
        crop_height.classification(str(tmp_path / "1_output.las"))
    except ValueError as exc:
        assert "class 1" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError when class 1 is missing")


def test_validate_accepts_single_las_file(tmp_path):
    las_file = tmp_path / "example.las"
    las_file.touch()
    shp = tmp_path / "plots.shp"
    shp.touch()
    parser = crop_height.build_parser()
    args = parser.parse_args([
        "--input", str(las_file),
        "--shp", str(shp),
        "--output", str(tmp_path / "out.csv"),
    ])
    assert crop_height._validate_args(args) is None
