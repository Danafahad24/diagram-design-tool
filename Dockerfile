FROM python:3.12-slim

# THE ONE CUSTOM IMAGE THAT STAYS ROOT, deliberately. Every other service in
# this stack got a `USER` line; this one cannot have it yet. The `bash` tool's
# whole isolation story is that the container creates a Linux account per user
# on first access (`useradd`), chowns that person's workspace to it (0700) and
# drops privileges with `su` for the command itself - see
# workspace_agent/editor.py and docs/security/trust-boundaries.md. useradd,
# chown on the /workspaces volume, and su all need root, so uvicorn keeps it
# and each command runs as the caller instead. Making this non-root means
# moving bash to per-request containers (NOTES.md "Multi-user isolation"),
# not adding a USER line.

# System deps. The second group is there because this container has no route to
# its outbound traffic pointed at `egress-proxy`, where every request is
# logged. `pip install` works through it. It is an audit trail rather than a
# barrier today - see the egress-proxy note in compose/tools.yaml - so a tool
# that is not baked in can sometimes be fetched, and sometimes cannot.
#
# So a tool that is not baked in is effectively unavailable, and the failure is
# silent - the model runs the command a skill told it to run, gets "No such
# file", and quietly does something worse instead. Everything the shipped skills
# name is installed, and `scripts/tests/test_skill_commands.py` fails the build
# if a skill ever names something that is not.
#
#   - fonts-dejavu-core: matplotlib fallback fonts
#   - curl: healthchecks
#   - libreoffice-core, calc, writer, impress: PDF conversion + xlsx recalc
#     (used by workspace_agent's pdf/excel modules and the /skills scripts)
#   - fonts-liberation: ships Liberation Sans/Serif/Mono (Calibri/Times/Courier
#     fallbacks for Office docs)
#   - poppler-utils: pdftotext / pdftoppm / pdfinfo / pdffonts, named throughout
#     skills/pdf and skills/pdf-reading, and the reason /skills/scripts/thumbnail.py
#     used to fail (it shells out to pdftoppm)
#   - qpdf: merge / split / rotate / decrypt in skills/pdf
#   - unzip: raw OOXML inspection
#   - file: skills/file-reading uses it to check what an upload really is when
#     the extension lies
#
# NOT installed, though the vendored skills name them: **pandoc**, **pdftk**
# (pdftk-java drags in a whole JRE) and **Node** with docx-js/PptxGenJS. They
# were about 180 MB between them and the bulk of a very slow apt layer — on the
# connection this is built from, that layer took over an hour, which is a real
# cost paid on every rebuild by every developer.
#
# Each has a substitute already in this image, so nothing is actually lost:
#   pandoc                -> python-docx, or pymupdf for PDFs
#   pdftk                 -> qpdf (merge, split, rotate, decrypt)
#   docx-js / PptxGenJS   -> generate_document, python-docx, python-pptx
#
# The skills that mention them say so at the top, and
# scripts/tests/test_skill_commands.py fails the build if a skill starts naming
# one again without that note. To bring one back, add it here and delete the
# corresponding note.
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    fonts-liberation \
    curl \
    libcairo2 \
    libreoffice-core \
    libreoffice-calc \
    libreoffice-writer \
    libreoffice-impress \
    poppler-utils \
    qpdf \
    unzip \
    file \
    && rm -rf /var/lib/apt/lists/*

# Build context is services/workbench/ (see compose/tools.yaml), so workspace_agent/
# is reachable here as a subdirectory. Installed as a real Python
# package (its own pyproject.toml declares the document-processing deps —
# python-docx, docxtpl, openpyxl, python-pptx, matplotlib, pillow, cairosvg,
# lxml, defusedxml, jsonschema, pymupdf); tool-bridge never calls it over
# HTTP, only imports it.
#
# matplotlib >= 3.10 is REQUIRED, not cosmetic: it is the first release that
# reorders bidirectional text, and every chart in an Arabic deck is a
# matplotlib PNG. On 3.9 the letters join but the glyph order is reversed, so
# Arabic titles, legends and axis labels come out backwards while the rest of
# the slide is correct. Verified: 3.9.4 reversed, 3.11.1 pixel-correct across
# bar/line/pie/hbar/area/scatter and the hero line chart. Do not downgrade
# the matplotlib pin in workspace_agent/pyproject.toml.
#
# Layer ordering matters: only pyproject.toml is copied here, and only the
# DEPENDENCIES are installed. The source itself is copied and installed
# (--no-deps) at the very bottom, so editing any workspace_agent/*.py file
# rebuilds one cheap final layer instead of invalidating every dependency
# install below.
COPY workspace_agent/pyproject.toml /workspace-agent/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/pip \
    python -c "import tomllib; \
print('\n'.join(tomllib.load(open('/workspace-agent/pyproject.toml','rb'))['project']['dependencies']))" \
    > /tmp/workspace-agent-deps.txt \
    && pip install --retries 10 --timeout 120 -r /tmp/workspace-agent-deps.txt

# Layer 1: tool-bridge's own API deps (small, change rarely) + the
# data-science stack the LLM uses via the bash tool (workspace_agent.editor's
# `bash` tool). These are the libraries Claude reaches for when given a CSV /
# Excel / JSON to analyse. Add to this list rather than editing inline if
# your team needs domain-specific packages (e.g. statsmodels, prophet, networkx).
COPY requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 10 --timeout 120 -r /app/requirements.txt

# `pip install playwright` (above, via requirements.txt) only installs the
# Python driver - it does not fetch a browser. canvas_diagram/office.py's
# render_diagram_png() launches Chromium specifically, so without this step
# pw.chromium.launch() has no binary to run and raises "Office renderer
# could not start" for every DOCX/PPTX export. --with-deps also pulls in
# Chromium's OS-level shared libraries (libnss3, libatk, etc.), which this
# image does not otherwise install.
RUN --mount=type=cache,target=/root/.cache/ms-playwright \
    playwright install --with-deps chromium

# pdf.js for the artifact viewer: routes/artifacts.py serves these files under
# /artifacts/-/pdfjs/<version>/ and workspace_agent.viewer's PDF page loads
# them. Fetched at build time and pinned twice - by version and by the sha256
# of the npm tarball - rather than vendored: 1.7 MB of minified JavaScript in
# git is unreviewable and trips gitleaks. The version here must equal
# workspace_agent.viewer.PDFJS_VERSION (tests/test_image_contents.py checks).
ARG PDFJS_VERSION=6.3.289
ARG PDFJS_SHA256=06f25e887adc6489f04c9fcb14198c77e4e5623a59a0bba5c4cea5838a4f1241
RUN --mount=type=bind,source=build/fetch_pdfjs.py,target=/tmp/fetch_pdfjs.py \
    python /tmp/fetch_pdfjs.py "$PDFJS_VERSION" "$PDFJS_SHA256" /app/static/pdfjs

# Source layers last — these are the ones that change many times a day, and
# everything above stays cached. workspace_agent's deps were installed from
# its pyproject.toml earlier, so --no-deps makes this install near-instant.
COPY workspace_agent /workspace-agent
RUN pip install --no-deps /workspace-agent

# tool-bridge itself: FastAPI host, local routes/API schemas, middleware, and
# environment/workflow configuration. Reusable editor and
# document processing implementation comes from workspace_agent.
# The brand faces are NOT baked in. They ship with the theme and arrive on the
# /templates bind mount, so this only tells fontconfig where to look. Keeping
# them out of the image is what lets a second theme bring its own faces without
# a rebuild, and keeps a licensed font out of a pushed image layer.
#
# Placed after every dependency layer on purpose: it is a config file that will
# be edited far more often than requirements.txt, and higher up it invalidated
# the whole pip install on every touch.
COPY fontconfig/60-brand-fonts.conf /etc/fonts/conf.d/60-brand-fonts.conf

WORKDIR /app
COPY app.py /app/app.py
COPY config.py /app/config.py
COPY settings.py /app/settings.py
COPY schemas.py /app/schemas.py
COPY errors.py /app/errors.py
COPY routes /app/routes
COPY canvas_diagram /app/canvas_diagram
COPY workflows.yaml /app/workflows.yaml

# HITL approval gate for sensitive tools (gates.py) and its async
# client to mcp-broker's approval endpoint (hitl.py).
COPY security /app/security

EXPOSE 8000

# Healthcheck so compose knows when we're ready
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
