import os
import re
import time
import json
import base64
import tempfile
import requests
import pandas as pd
import pdfplumber
from playwright.sync_api import sync_playwright

class QuizSolver:
    def __init__(self, email: str, secret: str):
        self.email = email
        self.secret = secret

    def _find_submit_url(self, html_text: str):
        m = re.search(r"https?://[^\"]+/submit[^\"]*", html_text)
        if m:
            return m.group(0)
        # broader search
        m2 = re.search(r"https?://[^\"]*(?:submit)[^\s'\"<>]*", html_text)
        return m2.group(0) if m2 else None

    def _extract_atob(self, html_text: str):
        chunks = []
        for m in re.finditer(r'atob\(\s*`([^`]*)`\s*\)|atob\(\s*"([^"]*)"\s*\)|atob\(\s*\'([^\']*)\'\s*\)', html_text):
            payload = next(g for g in m.groups() if g)
            chunks.append(payload)
        return chunks

    def _decode_base64(self, s: str):
        try:
            return base64.b64decode(s).decode('utf-8', errors='ignore')
        except Exception:
            return None

    def _download_file(self, page, href):
        # if absolute url
        url = href if href.startswith('http') else None
        if not url:
            return None
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            tmp = tempfile.NamedTemporaryFile(delete=False)
            tmp.write(r.content); tmp.close()
            return tmp.name
        return None

    def _sum_value_in_pdf_page2(self, pdf_path: str):
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if len(pdf.pages) < 2:
                    return None
                page = pdf.pages[1]
                tables = page.extract_tables()
                if not tables:
                    return None
                for table in tables:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    for col in df.columns:
                        if col.strip().lower() == 'value':
                            numeric = pd.to_numeric(df[col], errors='coerce')
                            return float(numeric.sum())
        except Exception:
            return None

    def solve_and_submit(self, url: str, time_budget_sec: int = 170):
        start = time.time()
        result = {
            'submissions': [],
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=120000)
            html = page.content()

            submit_url = self._find_submit_url(html)
            atob_chunks = self._extract_atob(html)
            decoded = [self._decode_base64(c) for c in atob_chunks if self._decode_base64(c)]

            # find obvious downloadable links
            file_path = None
            anchors = page.query_selector_all('a')
            for a in anchors:
                href = a.get_attribute('href') or ''
                if any(href.lower().endswith(ext) for ext in ['.pdf', '.csv', '.xlsx', '.json']):
                    file_path = self._download_file(page, href)
                    if file_path:
                        break

            answer = None
            # heuristic: if decoded contains JSON with "answer"
            for txt in decoded:
                try:
                    j = json.loads(txt)
                    if 'answer' in j:
                        answer = j['answer']
                        break
                except Exception:
                    pass

            if file_path and file_path.lower().endswith('.pdf') and answer is None:
                s = self._sum_value_in_pdf_page2(file_path)
                if s is not None:
                    answer = s

            if answer is None:
                # fallback: pick last number on page
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", html)
                if nums:
                    val = nums[-1]
                    answer = float(val) if '.' in val else int(val)

            submission_payload = {
                'email': self.email,
                'secret': self.secret,
                'url': url,
                'answer': answer
            }

            submit_resp = None
            if submit_url:
                try:
                    r = requests.post(submit_url, json=submission_payload, timeout=60)
                    try:
                        submit_resp = r.json()
                    except Exception:
                        submit_resp = {'status_code': r.status_code, 'text': r.text}
                except Exception as e:
                    submit_resp = {'error': str(e)}

            result['first'] = {
                'url': url,
                'submit_url': submit_url,
                'answer': answer,
                'submit_response': submit_resp
            }

            # If server returned a next url, follow it (simple loop, obey time budget)
            next_url = None
            if isinstance(submit_resp, dict) and submit_resp.get('url'):
                next_url = submit_resp.get('url')

            # loop to follow next urls while time permits
            while next_url and (time.time() - start) < time_budget_sec:
                page.goto(next_url, timeout=120000)
                html = page.content()
                submit_url = self._find_submit_url(html)
                # attempt same heuristics
                atob_chunks = self._extract_atob(html)
                decoded = [self._decode_base64(c) for c in atob_chunks if self._decode_base64(c)]
                file_path = None
                anchors = page.query_selector_all('a')
                for a in anchors:
                    href = a.get_attribute('href') or ''
                    if any(href.lower().endswith(ext) for ext in ['.pdf', '.csv', '.xlsx', '.json']):
                        file_path = self._download_file(page, href)
                        if file_path:
                            break

                answer = None
                for txt in decoded:
                    try:
                        j = json.loads(txt)
                        if 'answer' in j:
                            answer = j['answer']
                            break
                    except Exception:
                        pass

                if file_path and file_path.lower().endswith('.pdf') and answer is None:
                    s = self._sum_value_in_pdf_page2(file_path)
                    if s is not None:
                        answer = s

                if answer is None:
                    nums = re.findall(r"[-+]?\d*\.\d+|\d+", html)
                    if nums:
                        val = nums[-1]
                        answer = float(val) if '.' in val else int(val)

                submission_payload = {
                    'email': self.email,
                    'secret': self.secret,
                    'url': next_url,
                    'answer': answer
                }
                try:
                    r = requests.post(submit_url, json=submission_payload, timeout=60)
                    try:
                        submit_resp = r.json()
                    except Exception:
                        submit_resp = {'status_code': r.status_code, 'text': r.text}
                except Exception as e:
                    submit_resp = {'error': str(e)}

                result['submissions'].append({
                    'url': next_url,
                    'answer': answer,
                    'submit_response': submit_resp
                })

                if isinstance(submit_resp, dict) and submit_resp.get('url'):
                    next_url = submit_resp.get('url')
                else:
                    next_url = None

            browser.close()

        return result