"""Render with the shipped maxGraph bundle and append a diagram to an Office copy."""
import base64
import os
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, BadZipFile


def _docx_move_before(paragraphs, anchor_p) -> None:
    """Move each newly-added paragraph's XML element to just before anchor_p,
    preserving their relative order. anchor_p=None means leave them at the
    end (nothing to move in front of)."""
    if anchor_p is None:
        return
    for paragraph in paragraphs:
        anchor_p.addprevious(paragraph._p)


def _docx_find_insertion_point(doc, heading: str):
    """First paragraph whose text contains `heading` (case-insensitive), and
    the element right after it (None if it's the last paragraph)."""
    target = heading.strip().lower()
    for paragraph in doc.paragraphs:
        if target and target in paragraph.text.strip().lower():
            return paragraph._p.getnext()
    raise ValueError(f"No heading or paragraph matching '{heading}' was found in the document.")


def _docx_body_start_anchor(doc):
    """First real content paragraph, skipping a bare trailing sectPr with no
    content before it (a brand-new empty document)."""
    from docx.oxml.ns import qn
    body = doc.element.body
    for child in body:
        if child.tag != qn("w:sectPr"):
            return child
    return None


def _pptx_move_slide(prs, from_index: int, to_index: int) -> None:
    slide_ids = prs.slides._sldIdLst
    entries = list(slide_ids)
    slide_ids.remove(entries[from_index])
    slide_ids.insert(to_index, entries[from_index])


def insert_diagram_png(
    png: bytes,
    title: str,
    kind: str,
    existing: bytes | None = None,
    attribution: str = "",
    location: dict | None = None,
) -> bytes:
    """Insert at the requested location (default: end); never modify input bytes.

    location: {"position": "end" | "start" | "after_heading" | "after_slide",
               "heading": str,        # docx, position=after_heading
               "slide_index": int,    # pptx, position=after_slide (0-based, existing slides)
               "slide_title": str}    # pptx, position=after_slide, alternative to slide_index
    """
    location = location or {}
    position = location.get("position", "end")
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

        insert_before = None
        if position == "start":
            insert_before = _docx_body_start_anchor(doc)
        elif position == "after_heading":
            heading = location.get("heading")
            if not heading:
                raise ValueError("position 'after_heading' requires a 'heading' value.")
            insert_before = _docx_find_insertion_point(doc, heading)
        elif position != "end":
            raise ValueError(f"Unsupported docx insert position: {position!r}.")

        if position == "end" and existing:
            doc.add_page_break()

        heading_para = doc.add_heading(title, level=1)
        section = doc.sections[-1]
        maxw = section.page_width-section.left_margin-section.right_margin
        maxh = section.page_height-section.top_margin-section.bottom_margin-914400
        scale = min(maxw/width, maxh/height)
        doc.add_picture(BytesIO(png), width=int(width*scale), height=int(height*scale))
        picture_para = doc.paragraphs[-1]
        new_paragraphs = [heading_para, picture_para]
        if attribution:
            new_paragraphs.append(doc.add_paragraph(attribution))

        if position in ("start", "after_heading"):
            _docx_move_before(new_paragraphs, insert_before)

        doc.save(output)
    elif kind == "pptx":
        from pptx import Presentation
        from pptx.util import Inches, Pt
        doc = Presentation(BytesIO(existing)) if existing else Presentation()
        existing_slide_count = len(doc.slides._sldIdLst)
        slide = doc.slides.add_slide(doc.slide_layouts[min(6, len(doc.slide_layouts)-1)])

        if position == "start":
            _pptx_move_slide(doc, existing_slide_count, 0)
        elif position == "after_slide":
            slide_title = location.get("slide_title")
            slide_index = location.get("slide_index")
            target = None
            if slide_title:
                query = slide_title.strip().lower()
                for i in range(existing_slide_count):
                    title_shape = doc.slides[i].shapes.title
                    text = (title_shape.text if title_shape is not None else "").strip().lower()
                    if query in text:
                        target = i
                        break
                if target is None:
                    raise ValueError(f"No slide with a title matching '{slide_title}' was found.")
            elif slide_index is not None:
                if not (0 <= slide_index < existing_slide_count):
                    raise ValueError(
                        f"slide_index {slide_index} is out of range for the existing presentation."
                    )
                target = slide_index
            else:
                raise ValueError("position 'after_slide' requires slide_index or slide_title.")
            _pptx_move_slide(doc, existing_slide_count, target + 1)
        elif position != "end":
            raise ValueError(f"Unsupported pptx insert position: {position!r}.")

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
