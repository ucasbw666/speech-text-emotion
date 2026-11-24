#!/usr/bin/env python
"""Real upload/button/result browser smoke using the installed Microsoft Edge."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1180}, device_scale_factor=1)
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto("http://127.0.0.1:7860", wait_until="networkidle", timeout=60000)
            expect(page.get_by_role("heading", name="语音文字与情绪联合识别", exact=True)).to_be_visible()
            path = ROOT / "assets" / "emotion_samples" / "liuchanhg_angry_236.wav"
            page.locator('input[type="file"]').first.set_input_files(str(path))
            expect(page.get_by_role("button", name=__import__("re").compile("^(Play|播放)$"))).to_be_visible(timeout=30000)
            page.get_by_role("button", name="开始联合分析", exact=True).click()
            expect(page.get_by_label("识别文本", exact=True)).not_to_have_value("", timeout=240000)
            expect(page.get_by_label("主要情绪", exact=True)).not_to_have_value("", timeout=240000)
            expect(page.get_by_label("系统状态", exact=True)).to_have_value(__import__("re").compile(".*情绪识别完成.*"), timeout=240000)
            result = {"status": "passed", "text": page.get_by_label("识别文本", exact=True).input_value(),
                      "emotion": page.get_by_label("主要情绪", exact=True).input_value(), "page_errors": errors}
            assert not errors, errors
            (ROOT / "results" / "joint_browser_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False), flush=True)
        finally:
            page.screenshot(path=str(ROOT / "report" / "figures" / "joint_ui_screenshot.png"), full_page=True)
            browser.close()


if __name__ == "__main__":
    main()
