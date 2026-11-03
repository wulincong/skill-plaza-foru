"""Render a report with one browser process and measured element screenshots.

Uses Playwright's documented BrowserContext / Locator screenshot APIs. The
existing CLI backend remains available for installations without this package.
No report generation model or external image service is involved.
"""
import json
from pathlib import Path


class ReportBrowser:
    def __init__(self, executable, width, scale=1):
        self.executable=executable
        self.width=width
        self.scale=scale
        self.runtime=self.browser=self.context=None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self.runtime=sync_playwright().start()
        try:
            self.browser=self.runtime.chromium.launch(executable_path=self.executable,headless=True,
                args=['--disable-gpu','--hide-scrollbars','--allow-file-access-from-files'])
            self.context=self.browser.new_context(viewport={'width':self.width,'height':1000},
                device_scale_factor=self.scale,color_scheme='light',reduced_motion='reduce')
            self.page=self.context.new_page()
            self.page.set_default_timeout(15000)
            return self
        except BaseException:
            self.__exit__(None,None,None)
            raise

    def capture(self, html_path, png_path):
        errors=[]
        def on_error(error):errors.append(str(error))
        self.page.on('pageerror',on_error)
        try:
            self.page.goto(Path(html_path).resolve().as_uri(),wait_until='load')
            self.page.wait_for_function('Boolean(document.documentElement.dataset.reportAudit)')
            audit=json.loads(self.page.locator('html').get_attribute('data-report-audit'))
            if errors or audit.get('errors'):
                raise RuntimeError('报告布局或脚本检查失败：'+str(errors+audit.get('errors',[])))
            element=self.page.locator('.page, .cover')
            if element.count()!=1:raise RuntimeError('报告页面根节点必须唯一')
            element.screenshot(path=str(png_path),animations='disabled')
            return audit['height'],audit
        finally:
            self.page.remove_listener('pageerror',on_error)

    def __exit__(self,*_):
        try:
            if self.context:self.context.close()
        finally:
            try:
                if self.browser:self.browser.close()
            finally:
                if self.runtime:self.runtime.stop()
