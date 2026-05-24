import importlib.util
from pathlib import Path

from fastapi import FastAPI


def test_root_app_py_exports_fastapi_app_for_vercel():
    entrypoint = Path(__file__).resolve().parents[1] / "app.py"

    spec = importlib.util.spec_from_file_location("vercel_app_entrypoint", entrypoint)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    assert isinstance(module.app, FastAPI)


def test_runtime_requirements_file_exists_for_vercel_install():
    requirements = Path(__file__).resolve().parents[1] / "requirements.txt"

    assert requirements.exists()
    content = requirements.read_text()
    assert "fastapi" in content
    assert "httpx" in content

