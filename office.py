"""Render with the shipped maxGraph bundle and append a diagram to an Office copy."""
import base64
import os
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, BadZipFile


def insert_diagram_png(png: bytes, title: str, kind: str, existing: bytes | None = None, attribution: str = "") -> bytes:
    """Append at document end or on a new last slide; never modify input bytes."""
    from PIL import Image
    with Image.open(BytesIO(png)) as image:
        width, height = image.size
    if existing:
        if len(existing) > 20_000_000:
            raise ValueError("Existing Office file exceeds 20 MB.")
        try:
            with ZipFile(BytesIO(existing)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 100_000_000:
                    raise ValueError("Office file expands beyond 100 MB.")
                required = 'word/document.xml' if kind == 'docx' else 'ppt/presentation.xml'
                if required not in archive.namelist():
                    raise ValueError("Existing document type does not match output format.")
        except BadZipFile as exc:
            raise ValueError("Existing file is not a valid DOCX/PPTX.") from exc
    output = BytesIO()
    if kind == "docx":
        from docx import Document
        doc = Document(BytesIO(existing)) if existing else Document()
        if existing: doc.add_page_break()
        doc.add_heading(title, level=1)
        section = doc.sections[-1]
        maxw = section.page_width-section.left_margin-section.right_margin
        maxh = section.page_height-section.top_margin-section.bottom_margin-914400
        scale = min(maxw/width, maxh/height)
        doc.add_picture(BytesIO(png), width=int(width*scale), height=int(height*scale))
        if attribution: doc.add_paragraph(attribution)
        doc.save(output)
    elif kind == "pptx":
        from pptx import Presentation
        from pptx.util import Inches, Pt
        doc = Presentation(BytesIO(existing)) if existing else Presentation()
        slide = doc.slides.add_slide(doc.slide_layouts[min(6, len(doc.slide_layouts)-1)])
        box = slide.shapes.add_textbox(Inches(.4), Inches(.15), doc.slide_width-Inches(.8), Inches(.5))
        box.text_frame.text = title
        box.text_frame.paragraphs[0].font.size = Pt(22)
        maxw, maxh = doc.slide_width-Inches(.8), doc.slide_height-Inches(1.6)
        scale = min(maxw/width, maxh/height)
        w,h = int(width*scale), int(height*scale)
        slide.shapes.add_picture(BytesIO(png), int((doc.slide_width-w)/2), Inches(.8), width=w, height=h)
        if attribution:
            credit = slide.shapes.add_textbox(Inches(.4),doc.slide_height-Inches(.65),maxw,Inches(.6))
            credit.text_frame.text=attribution
            for para in credit.text_frame.paragraphs: para.font.size=Pt(8)
        doc.save(output)
    else:
        raise ValueError("format must be docx or pptx")
    return output.getvalue()


async def render_diagram_png(body, bundle_path: Path) -> bytes:
    from playwright.async_api import async_playwright, Error as PlaywrightError
    from canvas_diagram.editor import build_canvas_editor_html
    import re
    html = build_canvas_editor_html(body)
    bundle = bundle_path.read_text().replace('</script', '<\\/script')
    html = re.sub(r'<script\s+src="[^"]+"\s*>\s*</script>', lambda _: '<script>'+bundle+'</script>', html, count=1)
    async with async_playwright() as pw:
        executable = os.getenv("CANVAS_CHROMIUM_EXECUTABLE")
        try:
            browser = await pw.chromium.launch(executable_path=executable or None, headless=True)
        except PlaywrightError as exc:
            raise RuntimeError("Office renderer could not start. Install Playwright Chromium and its system dependencies in Workbench.") from exc
        try:
            page = await browser.new_page(viewport={"width":1600,"height":1000}, device_scale_factor=2, color_scheme="light")
            # All icons and scripts are embedded; disallow outbound requests.
            await page.route("**/*", lambda route: route.abort())
            await page.set_content(html, wait_until="load")
            await page.wait_for_function("window.CanvasDiagramExport && document.querySelector('#preview-image').src", timeout=15000)
            uri = await page.evaluate("""async () => {
              const svg=window.CanvasDiagramExport.svg();
              const url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));
              try {
                const image=new Image(); image.src=url; await image.decode();
                const canvas=document.createElement('canvas');
                const scale=Math.min(2,4096/Math.max(image.width,image.height));
                canvas.width=Math.max(1,Math.ceil(image.width*scale)); canvas.height=Math.max(1,Math.ceil(image.height*scale));
                const ctx=canvas.getContext('2d');ctx.fillStyle='#ffffff';ctx.fillRect(0,0,canvas.width,canvas.height);
                ctx.drawImage(image,0,0,canvas.width,canvas.height);return canvas.toDataURL('image/png').split(',')[1];
              } finally { URL.revokeObjectURL(url); }
            }""")
            return base64.b64decode(uri)
        finally:
            await browser.close()
