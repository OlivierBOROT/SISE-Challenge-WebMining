"""
Selenium bot data generator for bot detection training.

Drives the e-commerce app with several scripted bot personas, each producing
distinct behavioral signatures. The existing JS tracker captures all events
and ships batches to /ajax/track_inputs automatically; each session is tagged
with its persona name as the source (e.g. "bot_direct", "bot_linear").

Usage:
    # Run all personas once (headless)
    python scripts/selenium_bot.py

    # Run specific persona, 3 sessions, visible browser
    python scripts/selenium_bot.py --persona linear --sessions 3 --no-headless

    # Run all personas, 5 sessions each
    python scripts/selenium_bot.py --sessions 5

Available personas:
    direct   — teleports to elements, no mouse movement, JS clicks
    linear   — ActionChains with constant speed and straight-line paths
    scan     — scrolls every page systematically, never clicks
    burst    — rapid identical-interval click bursts
    cautious — slow, uniform ActionChains movement with no variance
"""

from __future__ import annotations

import argparse
import atexit
import logging
import random
import signal
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from selenium import webdriver
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ─────────────────────────────────────────────────────────────────────────────
# Graceful shutdown on Ctrl+C
# ─────────────────────────────────────────────────────────────────────────────

_active_drivers: list["webdriver.Chrome"] = []


def _cleanup_drivers() -> None:
    for driver in _active_drivers[:]:
        try:
            # Kill the chromedriver process directly — avoids urllib3 retry delays
            # that occur when Chrome is already gone.
            if driver.service.process:
                driver.service.process.kill()
        except Exception:
            pass
    _active_drivers.clear()


def _sigint_handler(signum, frame) -> None:
    logger.warning("\nInterrupted — quitting all browser sessions...")
    _cleanup_drivers()
    sys.exit(130)  # conventional exit code for Ctrl+C


atexit.register(_cleanup_drivers)
signal.signal(signal.SIGINT, _sigint_handler)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000"
BATCH_INTERVAL_SEC = 15      # must match setInterval() in tracker.js
DEFAULT_BATCHES_PER_SESSION = 4  # how many 15s batches to collect per run


@dataclass
class RunConfig:
    base_url: str = BASE_URL
    batches: int = DEFAULT_BATCHES_PER_SESSION
    headless: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Driver factory
# ─────────────────────────────────────────────────────────────────────────────

def make_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # Disable the automation banner so the page behaves more like a real browser
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=opts)
    driver.set_window_size(1280, 900)
    return driver


# ─────────────────────────────────────────────────────────────────────────────
# Base persona
# ─────────────────────────────────────────────────────────────────────────────

class BotPersona(ABC):
    """Abstract base class for all bot personas.

    Subclasses define `_run_session()` — the interaction loop for one session.
    The base class handles driver lifecycle and JS source injection.
    """

    #: Source label stored with each feature batch in the JSONL file
    source_label: str = "bot"

    def __init__(self, cfg: RunConfig):
        self.cfg = cfg

    def run(self) -> None:
        """Open browser, tag session, run interactions, then close."""
        driver = make_driver(self.cfg.headless)
        _active_drivers.append(driver)
        try:
            driver.get(self.cfg.base_url)
            self._wait_for_app(driver)
            self._inject_source(driver)
            logger.info(f"[{self.source_label}] Session started — "
                        f"{self.cfg.batches} batches × {BATCH_INTERVAL_SEC}s")
            self._run_session(driver)
            # Wait for the final batch to be sent before closing
            time.sleep(BATCH_INTERVAL_SEC + 2)
            logger.info(f"[{self.source_label}] Session complete")
        finally:
            driver.quit()
            if driver in _active_drivers:
                _active_drivers.remove(driver)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _inject_source(self, driver: webdriver.Chrome) -> None:
        """Inject source label so the JS tracker tags every POST correctly."""
        driver.execute_script(
            f"window.__TRACKER_SOURCE__ = '{self.source_label}';"
        )

    def _wait_for_app(self, driver: webdriver.Chrome, timeout: int = 10) -> None:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

    def _wait_batch(self) -> None:
        """Sleep one full batch interval so the tracker fires."""
        time.sleep(BATCH_INTERVAL_SEC)

    def _scroll_to(self, driver: webdriver.Chrome, y: int) -> None:
        driver.execute_script(f"window.scrollTo(0, {y});")

    def _scroll_by(self, driver: webdriver.Chrome, delta: int) -> None:
        driver.execute_script(f"window.scrollBy(0, {delta});")

    def _js_click(self, driver: webdriver.Chrome, element) -> None:
        driver.execute_script("arguments[0].click();", element)

    def _find_category_links(self, driver: webdriver.Chrome) -> list:
        try:
            return driver.find_elements(By.CSS_SELECTOR, "[data-category], .category-link, nav a")
        except NoSuchElementException:
            return []

    def _find_products(self, driver: webdriver.Chrome) -> list:
        try:
            return driver.find_elements(By.CSS_SELECTOR, ".product, .product-card, [data-product-id]")
        except NoSuchElementException:
            return []

    @abstractmethod
    def _run_session(self, driver: webdriver.Chrome) -> None: ...


# ─────────────────────────────────────────────────────────────────────────────
# Persona 1: DirectBot
# Bot signature: zero mouse movement, no delta_time variance, teleport events
# Distinct features: move_event_rate≈0, jitter≈0, direction_changes≈0
# ─────────────────────────────────────────────────────────────────────────────

class DirectBot(BotPersona):
    """Teleports directly to elements using JS clicks. No mouse events at all."""

    source_label = "bot_direct"

    def _run_session(self, driver: webdriver.Chrome) -> None:
        for batch in range(self.cfg.batches):
            logger.info(f"[{self.source_label}] Batch {batch + 1}/{self.cfg.batches}")

            # Navigate around using JS clicks only
            categories = self._find_category_links(driver)
            if categories:
                target = random.choice(categories)
                self._js_click(driver, target)
                time.sleep(0.5)

            # Click products via JS (no mouse movement)
            products = self._find_products(driver)
            for product in random.sample(products, min(3, len(products))):
                self._js_click(driver, product)
                time.sleep(0.1)  # identical interval — bot signature

            # Instant scroll via JS
            for y in range(0, 2000, 200):
                self._scroll_to(driver, y)
                time.sleep(0.05)  # perfectly uniform scroll timing

            self._wait_batch()


# ─────────────────────────────────────────────────────────────────────────────
# Persona 2: LinearBot
# Bot signature: constant speed, perfectly straight paths, no direction changes
# Distinct features: constant_speed_ratio≈1, direction_changes≈0, std_speed≈0
# ─────────────────────────────────────────────────────────────────────────────

class LinearBot(BotPersona):
    """Uses ActionChains to move in perfectly straight lines at constant speed."""

    source_label = "bot_linear"

    def _run_session(self, driver: webdriver.Chrome) -> None:
        vp_width = driver.execute_script("return window.innerWidth")
        vp_height = driver.execute_script("return window.innerHeight")

        for batch in range(self.cfg.batches):
            logger.info(f"[{self.source_label}] Batch {batch + 1}/{self.cfg.batches}")

            # Dispatch synthetic mousemove events in perfectly straight horizontal
            # lines — uses JS to avoid ActionChains coordinate bounds issues while
            # still feeding events into the tracker (isTrusted=false is fine).
            y_positions = [int(vp_height * r) for r in [0.2, 0.4, 0.6, 0.8]]
            step = max(1, vp_width // 12)
            for y in y_positions:
                for x in range(step, vp_width - step, step):
                    driver.execute_script(
                        "document.dispatchEvent(new MouseEvent('mousemove',"
                        "{bubbles:true,clientX:arguments[0],clientY:arguments[1]}));",
                        x, y,
                    )
                    time.sleep(0.05)  # perfectly uniform 50ms steps — bot signature

            # Click a product with zero hesitation
            products = self._find_products(driver)
            if products:
                target = random.choice(products)
                try:
                    ActionChains(driver).move_to_element(target).click().perform()
                except (ElementNotInteractableException, Exception):
                    self._js_click(driver, target)
                time.sleep(0.1)

            # Uniform scroll
            for _ in range(5):
                self._scroll_by(driver, 300)
                time.sleep(0.2)  # constant 200ms interval

            self._wait_batch()


# ─────────────────────────────────────────────────────────────────────────────
# Persona 3: ScanBot
# Bot signature: scroll-only, no clicks, perfectly uniform scroll intervals
# Distinct features: scroll_event_rate=high, click_count=0, constant_scroll_delta
# ─────────────────────────────────────────────────────────────────────────────

class ScanBot(BotPersona):
    """Scrolls through every page systematically. Never clicks."""

    source_label = "bot_scan"

    def _run_session(self, driver: webdriver.Chrome) -> None:
        page_height = driver.execute_script("return document.body.scrollHeight")

        for batch in range(self.cfg.batches):
            logger.info(f"[{self.source_label}] Batch {batch + 1}/{self.cfg.batches}")

            # Scroll down the full page in perfectly uniform steps
            step = 150
            for y in range(0, page_height, step):
                self._scroll_to(driver, y)
                time.sleep(0.08)   # perfectly uniform 80ms — bot signature

            # Scroll back to top identically
            for y in range(page_height, 0, -step):
                self._scroll_to(driver, y)
                time.sleep(0.08)

            # Load a different AJAX category without mouse movement
            categories = self._find_category_links(driver)
            if categories:
                self._js_click(driver, random.choice(categories))
                time.sleep(0.3)
                page_height = driver.execute_script("return document.body.scrollHeight")

            self._wait_batch()


# ─────────────────────────────────────────────────────────────────────────────
# Persona 4: BurstBot
# Bot signature: rapid click bursts with identical intervals, then idle
# Distinct features: rapid_burst_count=high, identical_interval_ratio=high
# ─────────────────────────────────────────────────────────────────────────────

class BurstBot(BotPersona):
    """Fires rapid click bursts with identical timing — classic scraper pattern."""

    source_label = "bot_burst"
    BURST_INTERVAL = 0.12   # exactly 120ms between every click

    def _run_session(self, driver: webdriver.Chrome) -> None:
        for batch in range(self.cfg.batches):
            logger.info(f"[{self.source_label}] Batch {batch + 1}/{self.cfg.batches}")

            # Burst click all visible products with identical intervals
            products = self._find_products(driver)
            for product in products[:8]:
                self._js_click(driver, product)
                time.sleep(self.BURST_INTERVAL)  # perfectly identical intervals

            # Rapid category cycling
            categories = self._find_category_links(driver)
            for cat in categories:
                try:
                    self._js_click(driver, cat)
                    time.sleep(self.BURST_INTERVAL)  # same interval everywhere
                except Exception:
                    continue

            # Idle for the remainder of the batch (no movement, no interaction).
            # Clamp to zero to prevent negative sleep if clicking takes longer than batch_t.
            clicks_time = (len(products[:8]) + len(categories)) * self.BURST_INTERVAL
            idle = max(0.0, BATCH_INTERVAL_SEC - clicks_time)
            if idle:
                time.sleep(idle)


# ─────────────────────────────────────────────────────────────────────────────
# Persona 5: CautiousBot
# Bot signature: slow, uniform ActionChains moves, suspiciously low variance
# Distinct features: std_speed≈0, constant_speed_ratio≈1, predictable turning angles
# ─────────────────────────────────────────────────────────────────────────────

class CautiousBot(BotPersona):
    """Moves slowly and uniformly — tries to look human but has zero speed variance."""

    source_label = "bot_cautious"
    MOVE_STEP_PX = 8    # pixels per step
    MOVE_DELAY = 0.03   # exactly 30ms per step — giveaway uniform timing

    def _run_session(self, driver: webdriver.Chrome) -> None:
        vp_width = driver.execute_script("return window.innerWidth")
        vp_height = driver.execute_script("return window.innerHeight")

        for batch in range(self.cfg.batches):
            logger.info(f"[{self.source_label}] Batch {batch + 1}/{self.cfg.batches}")

            # Move toward a product using JS-dispatched events at constant speed.
            # We compute the in-viewport path after scrolling the element into view,
            # which keeps all coordinates inside the visible area.
            products = self._find_products(driver)
            if products:
                target = random.choice(products)
                # Bring element into viewport center before computing coordinates
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center',inline:'center'});",
                    target,
                )
                time.sleep(0.1)
                rect = driver.execute_script(
                    "var r=arguments[0].getBoundingClientRect();"
                    "return {x:r.left+r.width/2, y:r.top+r.height/2};",
                    target,
                )
                target_x = int(rect["x"])
                target_y = int(rect["y"])
                start_x, start_y = vp_width // 2, vp_height // 2
                dx = target_x - start_x
                dy = target_y - start_y
                steps = max(1, max(abs(dx), abs(dy)) // self.MOVE_STEP_PX)
                for i in range(steps):
                    x = start_x + int(dx * i / steps)
                    y = start_y + int(dy * i / steps)
                    driver.execute_script(
                        "document.dispatchEvent(new MouseEvent('mousemove',"
                        "{bubbles:true,clientX:arguments[0],clientY:arguments[1]}));",
                        x, y,
                    )
                    time.sleep(self.MOVE_DELAY)  # exactly 30ms — uniform bot signature

                # Click with no hold time
                try:
                    ActionChains(driver).move_to_element(target).click().perform()
                except Exception:
                    self._js_click(driver, target)

            # Uniform scrolling
            for _ in range(8):
                self._scroll_by(driver, 200)
                time.sleep(0.5)  # constant 500ms interval

            self._wait_batch()


# ─────────────────────────────────────────────────────────────────────────────
# Persona registry
# ─────────────────────────────────────────────────────────────────────────────

PERSONAS: dict[str, type[BotPersona]] = {
    "direct": DirectBot,
    "linear": LinearBot,
    "scan": ScanBot,
    "burst": BurstBot,
    "cautious": CautiousBot,
}


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Selenium bot personas against the app")
    parser.add_argument(
        "--persona",
        choices=list(PERSONAS) + ["all"],
        default="all",
        help="Which bot persona to run (default: all)",
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=1,
        help="Number of sessions per persona (default: 1)",
    )
    parser.add_argument(
        "--batches",
        type=int,
        default=DEFAULT_BATCHES_PER_SESSION,
        help=f"Batches per session — each is {BATCH_INTERVAL_SEC}s (default: {DEFAULT_BATCHES_PER_SESSION})",
    )
    parser.add_argument(
        "--url",
        default=BASE_URL,
        help=f"App base URL (default: {BASE_URL})",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show the browser window (useful for debugging)",
    )
    args = parser.parse_args()

    cfg = RunConfig(
        base_url=args.url,
        batches=args.batches,
        headless=not args.no_headless,
    )

    targets = list(PERSONAS.keys()) if args.persona == "all" else [args.persona]
    total = len(targets) * args.sessions
    duration_min = (total * args.batches * BATCH_INTERVAL_SEC) / 60

    logger.info(f"Running {len(targets)} persona(s) × {args.sessions} session(s) = {total} sessions")
    logger.info(f"Estimated time: ~{duration_min:.1f} min  ({total * args.batches} batches × {BATCH_INTERVAL_SEC}s)")

    for persona_name in targets:
        persona_cls = PERSONAS[persona_name]
        for session_num in range(1, args.sessions + 1):
            logger.info(f"──── {persona_name.upper()}  session {session_num}/{args.sessions} ────")
            try:
                persona_cls(cfg).run()
            except Exception as e:
                logger.error(f"Session failed: {e}", exc_info=True)

    logger.info("All sessions complete. Data stored in data/features.jsonl")
    logger.info("Use DataConnector.get_training_data() to filter by source.")


if __name__ == "__main__":
    main()
