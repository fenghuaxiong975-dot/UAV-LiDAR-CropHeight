from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "desktop-app" / "WindowsFormsApp1"


def read(name):
    return (APP / name).read_text(encoding="utf-8-sig")


def test_program_opens_main_form_without_embedded_login_gate():
    text = read("Program.cs")
    assert "Application.Run(new Form2())" in text
    assert "ShowDialog()" not in text


def test_no_machine_specific_paths_or_literal_demo_password():
    text = "\n".join(
        p.read_text(encoding="utf-8-sig", errors="ignore")
        for p in APP.rglob("*") if p.is_file() and p.suffix.lower() in {".cs", ".config", ".csproj"}
    )
    forbidden = [
        "C" + ":" + "\\" + "Users" + "\\",
        "F" + ":" + "\\",
        "D" + ":" + "\\" + "fhx",
        "Feng" + "huaxiong",
        chr(34) + "123456" + chr(34),
    ]
    for item in forbidden:
        assert item not in text


def test_app_config_has_python_executable_setting():
    text = read("App.config")
    assert '<add key="PythonExe" value="python" />' in text


def test_form2_uses_cli_and_redirects_stderr():
    text = read("Form2.cs")
    assert "crop_height.py" in text
    assert "--input" in text
    assert "--shp" in text
    assert "--output" in text
    assert "RedirectStandardError = true" in text


def test_project_does_not_reference_temporary_signing_key():
    text = read("WindowsFormsApp1.csproj")
    assert "WindowsFormsApp1_TemporaryKey.pfx" not in text
    assert "<SignManifests>true</SignManifests>" not in text
