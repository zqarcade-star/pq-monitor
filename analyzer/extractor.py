"""
파일 텍스트 추출
- .hwp  : hwp5txt CLI
- .hwpx : ZIP + XML 파싱
- .pdf  : pdfplumber
- .xlsx/.xls : openpyxl / xlrd
"""
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
import tempfile
import os


def extract_hwp(file_bytes: bytes, filename: str) -> str:
    """HWP → 텍스트 (hwp5txt CLI, 임시 파일 경유)"""
    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            ["hwp5txt", tmp_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        if result.returncode != 0:
            return f"[HWP 추출 실패: {result.stderr[:200]}]"
        return result.stdout.strip()
    except FileNotFoundError:
        return "[오류: hwp5txt 미설치. pip install pyhwp]"
    except subprocess.TimeoutExpired:
        return "[오류: HWP 추출 시간 초과]"
    finally:
        os.unlink(tmp_path)


def extract_hwpx(file_bytes: bytes) -> str:
    """HWPX → 텍스트 (ZIP 해제 + XML 파싱)"""
    texts = []
    try:
        with tempfile.NamedTemporaryFile(suffix=".hwpx", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            with zipfile.ZipFile(tmp_path, "r") as z:
                sections = sorted(
                    n for n in z.namelist()
                    if "section" in n.lower() and n.endswith(".xml")
                )
                for name in sections:
                    with z.open(name) as f:
                        try:
                            root = ET.parse(f).getroot()
                            chunk = " ".join(root.itertext()).strip()
                            if chunk:
                                texts.append(chunk)
                        except ET.ParseError:
                            pass
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        return f"[HWPX 추출 실패: {e}]"
    return "\n".join(texts)


def extract_pdf(file_bytes: bytes) -> str:
    """PDF → 텍스트 (pdfplumber)"""
    try:
        import pdfplumber
        import io
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        result = "\n".join(text_parts).strip()
        if not result:
            return "[PDF 텍스트 없음 — 스캔 이미지 PDF일 수 있음]"
        return result
    except ImportError:
        return "[오류: pdfplumber 미설치. pip install pdfplumber]"
    except Exception as e:
        return f"[PDF 추출 실패: {e}]"


def extract_excel(file_bytes: bytes, suffix: str) -> str:
    """Excel → 텍스트 (openpyxl)"""
    try:
        import openpyxl
        import io
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        lines = []
        for ws in wb.worksheets:
            lines.append(f"[시트: {ws.title}]")
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    lines.append("\t".join(cells))
        return "\n".join(lines)
    except ImportError:
        return "[오류: openpyxl 미설치. pip install openpyxl]"
    except Exception as e:
        return f"[Excel 추출 실패: {e}]"


def extract_text(file_bytes: bytes, filename: str) -> str:
    """파일 형식에 따라 적절한 추출기 호출"""
    suffix = Path(filename).suffix.lower()
    if suffix == ".hwp":
        return extract_hwp(file_bytes, filename)
    elif suffix == ".hwpx":
        return extract_hwpx(file_bytes)
    elif suffix == ".pdf":
        return extract_pdf(file_bytes)
    elif suffix in (".xlsx", ".xls"):
        return extract_excel(file_bytes, suffix)
    else:
        return f"[지원하지 않는 형식: {suffix}]"
