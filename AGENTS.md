# docling-scripts

Python 3.14 project. Managed with [`uv`](https://github.com/astral-sh/uv).

## Setup

```
uv venv --python 3.14
uv sync
source .venv/bin/activate
```

> **Note:** PyTorch comes from AMD's ROCm 10 wheel index (`https://stable.repo.amd.com/rocm/whl-next/`) via `[tool.uv.sources]`, per the [AMD install docs](https://rocm.docs.amd.com/) — PyPI only hosts CUDA builds. The `index-strategy = "unsafe-best-match"` setting is required: AMD's `torch` depends on `rocm`, `triton`, and `amd-torch-device-*` packages, and since `rocm`/`triton` also exist on PyPI, uv's default `first-index` strategy would resolve them to the incompatible PyPI versions. `uv sync` handles everything; no manual wheel installation is needed.

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


