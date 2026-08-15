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
    python docling-to-md.py <source.pdf>          # embeds images (default)
    python docling-to-md.py --vlm <source.pdf>    # VLM descriptions

Requirements (for --vlm):
    - A VLM endpoint running at http://10.8.0.210:13305
      (configurable via ENDPOINT_URL)
"""

import argparse
import logging
import sys
from pathlib import Path

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc import DocItemLabel, ImageRefMode

def build_converter(use_vlm: bool = False) -> DocumentConverter:
    if use_vlm:
        from typing import Iterable

        from PIL import Image

        from docling.datamodel.pipeline_options import (
            PictureDescriptionVlmEngineOptions,
        )
        from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions
        from docling.models.inference_engines.vlm import (
            VlmEngineInput,
            VlmEngineType,
        )
        from docling.models.stages.picture_description \
            import picture_description_vlm_engine_model as _pd_vlm_mod

        MIN_IMAGE_SIZE = 2048

        def _annotate_images_patched(
            self, images: Iterable[Image.Image]
        ) -> Iterable[str]:
            if self.engine is None:
                raise RuntimeError("Engine not initialized")

            prompt = self.options.prompt
            image_list = list(images)

            if not image_list:
                return

            try:
                gen_cfg = self.options.generation_config or {}
                temperature = gen_cfg.get("temperature", 0.2)
                max_new_tokens = gen_cfg.get("max_new_tokens", 500)

                resized_images = []
                for img in image_list:
                    original_size = img.size
                    if max(img.size) < MIN_IMAGE_SIZE:
                        scale = MIN_IMAGE_SIZE / max(img.size)
                        new_size = (int(img.width * scale), int(img.height * scale))
                        img = img.resize(new_size, Image.LANCZOS)
                        logging.info(
                            f"Resized image from {original_size} to {img.size}"
                        )
                    resized_images.append(img)

                engine_inputs = [
                    VlmEngineInput(
                        image=image,
                        prompt=prompt,
                        temperature=float(temperature),
                        max_new_tokens=int(max_new_tokens),
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
    else:
        pipeline_options = PdfPipelineOptions(
            generate_page_images=True,
            generate_picture_images=True,
            ocr="skip",
            do_picture_description=False,
        )

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options
            ),
        }
    )


def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF to Markdown using Docling."
    )
    parser.add_argument("source", help="Path to the source PDF file")
    parser.add_argument(
        "--embed-images",
        action="store_true",
        default=True,
        help=(
            "Skip VLM picture descriptions and embed images as "
            "base64 data URIs instead. (default)"
        ),
    )
    parser.add_argument(
        "--vlm",
        action="store_true",
        help="Use VLM to generate picture descriptions instead of embedding.",
    )
    args = parser.parse_args()

    source = Path(args.source)
    output = source.with_suffix(".md")

    if not source.exists():
        print(f"Error: {source} not found.")
        sys.exit(1)

    if args.vlm:
        converter = build_converter(use_vlm=True)
        result = converter.convert(source=str(source))
        doc = result.document

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

        md = doc.export_to_markdown()
    else:
        converter = build_converter(use_vlm=False)
        result = converter.convert(source=str(source))
        doc = result.document
        md = doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)

    output.write_text(md, encoding="utf-8")
    print(f"Written to {output}")


if __name__ == "__main__":
    main()
