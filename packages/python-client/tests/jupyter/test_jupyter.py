import asyncio
import os
import shutil
import subprocess
import tempfile

import notebook  # type: ignore
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from tests.conftest import find_free_port, wait_for_server


notebook_version_info = tuple(map(int, notebook.__version__.split(".")))

TEST_JUPYTER_DIR = os.path.dirname(__file__)

NOTEBOOK_NAME = "launch_widget.ipynb"


# # For debugging purposes
# def print_page(driver: webdriver.Chrome, path: str) -> None:
#     import base64
#     from selenium.webdriver.common.print_page_options import PrintOptions

#     with open(path, "wb+") as f:
#         opts = PrintOptions()
#         # opts.page_width = 40
#         # opts.page_height = 60
#         page_base64 = driver.print_page(opts)
#         raw = base64.b64decode(page_base64)
#         f.write(raw)


# @pytest.fixture
# def take_final_screenshot(browser: webdriver.Chrome):
#     try:
#         yield
#     finally:
#         print_page(browser, "final.pdf")


@pytest.fixture(scope="session")
def ensure_notebook_extension() -> None:
    if notebook_version_info >= (5, 3):
        return

    subprocess.check_call(
        [
            "jupyter",
            "nbextension",
            "install",
            "--sys-prefix",
            "--symlink",
            "--overwrite",
            "--py",
            "lmk",
        ],
    )
    subprocess.check_call(
        ["jupyter", "nbextension", "enable", "--sys-prefix", "--py", "lmk"]
    )


@pytest.fixture(scope="function")
async def notebook_server():
    port = find_free_port()

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(TEST_JUPYTER_DIR, NOTEBOOK_NAME)
        dest_path = os.path.join(tmpdir, NOTEBOOK_NAME)
        shutil.copyfile(src_path, dest_path)

        process = await asyncio.create_subprocess_exec(
            "jupyter",
            "notebook",
            "--no-browser",
            f"--port={port}",
            f"--notebook-dir={tmpdir}",
            "--NotebookApp.token=''",
            "--NotebookApp.allow_remote_access=True",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        wait = asyncio.create_task(process.wait())
        await wait_for_server(f"http://localhost:{port}", 10)

        if wait.done():
            raise RuntimeError(f"Notebook server exited with code {wait.result()}")

        try:
            yield f"http://localhost:{port}"
        finally:
            process.terminate()
            exit_code = await wait
            if exit_code != 0:
                raise RuntimeError(f"Notebook server exited with code {exit_code}")


@pytest.fixture(scope="function")
async def lab_server():
    port = find_free_port()

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(TEST_JUPYTER_DIR, NOTEBOOK_NAME)
        dest_path = os.path.join(tmpdir, NOTEBOOK_NAME)
        shutil.copyfile(src_path, dest_path)

        process = await asyncio.create_subprocess_exec(
            "jupyter",
            "lab",
            "--no-browser",
            f"--port={port}",
            f"--notebook-dir={tmpdir}",
            "--LabApp.token=''",
            "--LabApp.allow_remote_access=True",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        wait = asyncio.create_task(process.wait())
        await wait_for_server(f"http://localhost:{port}", 10)

        if wait.done():
            raise RuntimeError(f"Lab server exited with code {wait.result()}")

        try:
            yield f"http://localhost:{port}"
        finally:
            process.terminate()
            exit_code = await wait
            if exit_code != 0:
                raise RuntimeError(f"Lab server exited with code {exit_code}")


@pytest.fixture(scope="function")
def browser():
    service = webdriver.ChromeService(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")

    with webdriver.Chrome(service=service, options=options) as driver:
        yield driver


def test_jupyter_widget_notebook(
    browser: webdriver.Chrome, notebook_server: str, ensure_notebook_extension
) -> None:
    browser.set_window_size(1000, 800)
    browser.get(f"{notebook_server}/notebooks/{NOTEBOOK_NAME}")

    cell_xpath = '//div[contains(@class, "inner_cell")]'
    kernel_xpath = None
    if notebook_version_info >= (6,):
        cell_xpath = '//div[contains(@class, "cell") and contains(@class, "code_cell") and .//*[contains(text(), "import")] and .//*[contains(text(), "lmk")]]'
    if notebook_version_info >= (7,):
        cell_xpath = '//div[contains(@class, "jp-CodeMirrorEditor") and .//*[contains(text(), "import")] and .//*[contains(text(), "lmk")]]'
        kernel_xpath = '//*[(self::button or self::jp-button) and contains(@class, "jp-Toolbar-kernelName") and .//*[contains(text(), "Python 3")]]'

    cell = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.XPATH, cell_xpath)), "Cell not found"
    )
    if kernel_xpath is not None:
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.XPATH, kernel_xpath)),
            "Kernel not found",
        )

    webdriver.ActionChains(browser).pause(3).click(cell).key_down(Keys.SHIFT).send_keys(
        Keys.ENTER, Keys.ENTER
    ).key_up(Keys.SHIFT).perform()

    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.XPATH, '//h3[text() = "LMK"]')),
        "Widget not found",
    )


def test_jupyter_widget_lab(browser: webdriver.Chrome, lab_server: str) -> None:
    browser.set_window_size(1400, 800)
    browser.get(f"{lab_server}/lab/tree/{NOTEBOOK_NAME}")

    cell_xpath = '//div[contains(@class, "jp-CodeMirrorEditor") and .//*[contains(text(), "import")] and .//*[contains(text(), "lmk")]]'
    kernel_xpath = '//*[(self::button or self::jp-button) and contains(@class, "jp-Toolbar-kernelName") and .//*[contains(text(), "Python 3")]]'
    spinner_xpath = '//*[@id = "jupyterlab-splash"]'

    WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.XPATH, cell_xpath)), "Cell not found"
    )
    WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.XPATH, kernel_xpath)), "Kernel not found"
    )
    WebDriverWait(browser, 10).until_not(
        EC.visibility_of_element_located((By.XPATH, spinner_xpath)),
        "Spinner found for too long",
    )

    webdriver.ActionChains(browser).key_down(Keys.SHIFT).send_keys(
        Keys.ENTER, Keys.ENTER
    ).key_up(Keys.SHIFT).perform()

    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.XPATH, '//h3[text() = "LMK"]')),
        "Widget not found",
    )
