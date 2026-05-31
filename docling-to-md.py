"""
Convert PDF documents to Markdown using Docling, with VLM-generated picture
descriptions.

This script uses the Docling document conversion pipeline with a Vision
Language Model (VLM) to generate detailed descriptions of images within
PDF files.
It monkey-patches the VLM engine to resize small images before sending them
to the model, ensuring the Qwen3.6-35B-A3B-MTP-GGUF model receives images
large enough to produce output.

Usage:
    python docling-to-md.py <source.pdf>

Requirements:
    - A VLM endpoint running at http://10.8.0.210:13305
      (configurable via ENDPOINT_URL)
"""

import logging
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    PictureDescriptionVlmEngineOptions,
)
from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions
from docling.datamodel.stage_model_specs import VlmEngineType
from docling_core.types.doc import DocItemLabel

# Monkey-patch BEFORE creating the converter
from docling.models.stages.picture_description \
    import picture_description_vlm_engine_model as _pd_vlm_mod

# Qwen3.6-35B-A3B-MTP-GGUF requires large images and specific conditions
# to produce output
MIN_IMAGE_SIZE = 2048


def _annotate_images_patched(
    self, images: Iterable[Image.Image]
) -> Iterable[str]:
    """Generate descriptions using temperature from generation_config."""
    if self.engine is None:
        raise RuntimeError("Engine not initialized")

    prompt = self.options.prompt
    image_list = list(images)

    if not image_list:
        return

    try:
        gen_config = self.options.generation_config
        temperature = gen_config.get("temperature", 0.2)
        max_new_tokens = gen_config.get("max_new_tokens", 500)

        # Resize images to minimum size the VLM can handle
        resized_images = []
        for img in image_list:
            original_size = img.size
            if max(img.size) < MIN_IMAGE_SIZE:
                # Scale up to MIN_IMAGE_SIZE while preserving aspect ratio
                scale = MIN_IMAGE_SIZE / max(img.size)
                new_size = (int(img.width * scale), int(img.height * scale))
                img = img.resize(new_size, Image.LANCZOS)
                logging.info(
                    f"Resized image from {original_size} to {img.size}"
                )
            resized_images.append(img)

        engine_inputs = [
            _pd_vlm_mod.VlmEngineInput(
                image=image,
                prompt=prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
            )
            for image in resized_images
        ]

        outputs = self.engine.predict_batch(engine_inputs)

        for output in outputs:
            description = output.text.strip()
            yield description

    except Exception as e:
        logging.error(f"Error generating picture descriptions: {e}")
        for _ in image_list:
            yield ""


_pd_vlm_mod.PictureDescriptionVlmEngineModel._annotate_images = (
    _annotate_images_patched
)

ENDPOINT_URL = "http://10.8.0.210:13305/v1/chat/completions"
MODEL_NAME = "Qwen3.6-35B-A3B-MTP-GGUF"

VL_PROMPT = (
    "Describe this image."
    "If there are charts, graphs or diagrams, explain what they show."
    "If there is text, transcribe it verbatim. ")

def build_converter() -> DocumentConverter:
    engine_options = ApiVlmEngineOptions(
        engine_type=VlmEngineType.API,
        url=ENDPOINT_URL,
        params={"model": MODEL_NAME},
    )

    picture_description_options = (
        PictureDescriptionVlmEngineOptions.from_preset(
            "qwen",
            engine_options=engine_options,
            prompt=VL_PROMPT,
            generation_config={
                "max_new_tokens": 2000,
                "do_sample": True,
                "temperature": 0.2,
            },
        )
    )

    pipeline_options = PdfPipelineOptions(
        generate_page_images=True,
        generate_picture_images=True,
        ocr="skip",
        do_picture_description=True,
        picture_description_options=picture_description_options,
        enable_remote_services=True,
    )

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options
            ),
        }
    )


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <source.pdf>")
        sys.exit(1)

    source = Path(sys.argv[1])
    output = source.with_suffix(".md")

    if not source.exists():
        print(f"Error: {source} not found.")
        sys.exit(1)

    converter = build_converter()
    result = converter.convert(source=str(source))

    doc = result.document

    # Print VLM picture descriptions
    for item, _level in doc.iterate_items():
        if item.label == DocItemLabel.PICTURE:
            if item.meta and item.meta.description:
                desc = item.meta.description.text.strip()
                if desc:
                    print(f"[Picture] {desc}\n")
                else:
                    print("[Picture] (VLM returned empty description)\n")
            else:
                print("[Picture] No description generated.\n")

    # Export full document as markdown
    md = doc.export_to_markdown()
    output.write_text(md, encoding="utf-8")
    print(f"Written to {output}")


if __name__ == "__main__":
    main()
