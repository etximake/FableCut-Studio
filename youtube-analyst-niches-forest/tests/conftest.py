import os
import pytest
from pathlib import Path


@pytest.fixture(autouse=True, scope="session")
def isolate_test_directories(tmp_path_factory):
    """
    Cô lập các thư mục EXPORTS_DIR và TEMP_DIR trong lúc chạy pytest
    để không làm rác thư mục temp/ hay fablecut-data/media/.
    """
    test_exports = tmp_path_factory.mktemp("test_exports")
    test_temp = tmp_path_factory.mktemp("test_temp")

    os.environ["EXPORTS_DIR"] = str(test_exports)

    from src.core.config import settings
    from src.api import routes

    orig_temp_dir = settings.TEMP_DIR
    settings.TEMP_DIR = test_temp

    if hasattr(routes, "preprocessor"):
        routes.preprocessor.temp_dir = test_temp
    if hasattr(routes, "downloader"):
        routes.downloader.temp_dir = test_temp

    yield

    settings.TEMP_DIR = orig_temp_dir
    os.environ.pop("EXPORTS_DIR", None)
