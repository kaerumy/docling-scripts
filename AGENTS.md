# docling-scripts

Python 3.12 project. Managed with [`uv`](https://github.com/astral-sh/uv).

## Setup

```
uv venv
uv sync
uv pip install --no-deps \
  "https://download-r2.pytorch.org/whl/rocm7.2/torch-2.11.0%2Brocm7.2-cp312-cp312-manylinux_2_28_x86_64.whl" \
  "https://download-r2.pytorch.org/whl/rocm7.2/torchvision-0.26.0%2Brocm7.2-cp312-cp312-manylinux_2_28_x86_64.whl"
source .venv/bin/activate
```

> **Note:** `torch`/`torchvision` ROCm wheels depend on `triton-rocm==3.6.0`, which is not on PyPI. They must be installed separately with `--no-deps` after `uv sync`. `uv sync` alone would pull in the CUDA build of PyTorch, which is incompatible with ROCm.

## Tooling

- [`docling`](https://github.com/DS4SD/docling) — document conversion pipeline
- `docling`, `docling-serialize`, `docling-tools`, `docling-view` — CLI entrypoints in `.venv/bin/`

## Docling API

### Core conversion flow

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("path/to/file.pdf")        # file path or URL
# or: result = converter.convert(stream)              # DocumentStream for in-memory
# or: for result in converter.convert_all(paths):     # batch

doc = result.document            # DoclingDocument
status = result.status           # ConversionStatus enum
```

### Key imports

```python
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat, DocumentStream, ConversionStatus
from docling.datamodel.pipeline_options import PdfPipelineOptions, ConvertPipelineOptions
from docling_core.types.doc import DoclingDocument, DocItemLabel
```

### Supported formats

`InputFormat`: `PDF`, `DOCX`, `PPTX`, `HTML`, `IMAGE`, `MD`, `CSV`, `XLSX`, `XML_USPTO`, `XML_JATS`, `XML_XBRL`, `METS_GBS`, `JSON_DOCLING`, `AUDIO`, `VTT`, `LATEX`, `ASCIIDOC`

### DoclingDocument — navigating output

```python
# Iterate all items in reading order
for item, level in doc.iterate_items():
    label = item.label       # DocItemLabel enum (TEXT, TABLE, TITLE, SECTION_HEADER, LIST_ITEM, CODE, FORMULA, PICTURE, etc.)
    # item.text for TextItem, item.table for TableItem, etc.

# Export
md = doc.export_to_markdown()
dct = doc.export_to_dict()
html = doc.export_to_html()

# Page info
for page_no, page_item in doc.pages.items():
    ...
```

### Configuring the converter

```python
from docling.document_converter import PdfFormatOption

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=PdfPipelineOptions(
                generate_page_images=True,
                generate_picture_images=True,
                generate_table_images=False,
            )
        ),
    }
)
```

### Conversion limits

```python
result = converter.convert(
    source,
    raises_on_error=True,
    max_num_pages=100,
    max_file_size=50_000_000,
    page_range=(1, 10),
)
```

### Building documents programmatically

```python
from docling_core.types.doc import DoclingDocument, DocItemLabel

doc = DoclingDocument(name="my-doc")
doc.add_text(label=DocItemLabel.TITLE, text="Title")
doc.add_heading(text="Section 1")
doc.add_text(label=DocItemLabel.PARAGRAPH, text="Content...")
doc.add_list_item(text="Item 1")
doc.add_code(text="print('hello')")
doc.add_formula(text="E = mc^2")
```


