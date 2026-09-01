from pathlib import Path
from typing import Any

from backend.tools.collection.read_datasheet_common import (
    build_langchain_chat_model,
    image_path_to_data_url,
    llm_debug_identity,
    response_text,
    safe_filename,
)
from backend.data.Component.KiCadComponent import get_kicad_component_by_library_and_name
from backend.tools.collection.collectComponentInfo import _download_datasheet_for_component
import backend.config as config_module
from tqdm.auto import tqdm
import fitz
import time
from typing import Annotated
from backend.runtime_paths import cache_dir

CHUNK_INSTRUCTIONS = """
    You are analyzing only a subset of datasheet pages.
    Extract all information from these pages that is necessary when designing a schematic using this component.
    Be precise when describing reference schematics, required external parts, values, connections, and pin behavior.
    Include:
    1. Component purpose and important operating context.
    2. Pin-by-pin behavior and configuration options.
    3. Required and recommended external components with values or ranges when available.
    4. Reference or typical application schematics with detailed connections.Be precise about which exact components to use (e.g. capacitor vs polarized capacitor) and their values, and how to connect them.
    5. Constraints, warnings, sequencing, layout, or usage notes that affect schematic design.
    If something is not visible in these pages, do not infer it.
    Preserve page-specific detail that could matter later in a final merged summary.
"""

FINAL_SYNTHESIS_INSTRUCTIONS = """
    Merge the following partial datasheet summaries into one final schematic-design knowledge summary. 
    These are all the pages of the datasheet, so the final summary should be comprehensive and include all relevant information for schematic design.
    Deduplicate repeated information and keep the most specific version when multiple chunks overlap.
    Organize the result so another agent can use it directly for circuit design.
    Include:
    1. Component purpose and important operating context.
    2. Pin-by-pin behavior and configuration options.
    3. Required and recommended external components with values or ranges when available.
    4. Reference or typical application schematics with detailed connections. Be precise about which exact components to use (e.g. capacitor vs polarized capacitor) and their values, and how to connect them.
    5. Constraints, warnings, sequencing, layout, or usage notes that affect schematic design.
    Do not invent missing details.
"""

CACHE_DIR = cache_dir() / "datasheet_knowledge"
MAX_IMAGES_PER_REQUEST = 45
TEXT_MODE_BATCH_SIZE = 150
MAX_PAGE_TEXT_CHARS = 6000
RETRY_DELAY_S = 3.0


def _render_preview(doc: fitz.Document, page_number: int, output_path: Path, *, dpi: int) -> str:
    """Render one page for the active full-datasheet vision summary flow."""
    if output_path.exists():
        return str(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72
    page = doc.load_page(page_number)
    pix = page.get_pixmap(
        matrix=fitz.Matrix(scale, scale),
        colorspace=fitz.csRGB,
        alpha=False,
        annots=False,
    )
    pix.save(str(output_path))
    return str(output_path)


def _chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _is_timeout_error(exc: Exception) -> bool:
    name = type(exc).__name__
    if "Timeout" in name:
        return True
    message = str(exc).lower()
    return "timed out" in message or "timeout" in message


def _invoke_with_retry(llm, messages: list[dict[str, Any]], *, label: str) -> Any:
    for attempt in range(2):
        try:
            if attempt:
                print(f"[obtain_needed_information] retrying {label} after timeout (attempt {attempt + 1}/2)")
            return llm.invoke(messages)
        except Exception as exc:
            if attempt == 0 and _is_timeout_error(exc):
                time.sleep(RETRY_DELAY_S)
                continue
            raise


def _datasheet_cache_model_key(model_name: str) -> str:
    resolved = config_module.resolve_model_config(model_name)
    canonical = resolved.model_name.strip().lower()

    # Treat equivalent OpenAI-family identifiers from different compatible
    # providers as one cache namespace, e.g. azure.gpt-5.1 and openai/gpt-5.1.
    if canonical.startswith("azure."):
        canonical = canonical[len("azure.") :]
    elif canonical.startswith("openai/"):
        canonical = canonical[len("openai/") :]
    elif canonical.startswith("openai."):
        canonical = canonical[len("openai.") :]

    return safe_filename(canonical)


def _invoke_vision_summary(
    llm,
    page_payloads: list[dict[str, Any]],
    *,
    instructions: str,
    max_page_text_chars: int = MAX_PAGE_TEXT_CHARS,
) -> str:
    content: list[dict[str, Any]] = [{"type": "text", "text": instructions}]
    for page_payload in page_payloads:
        page_number = int(page_payload["page_number"])
        image_path = str(page_payload["image_path"])
        extracted_text = str(page_payload["page_text"]).strip()

        content.append({"type": "text", "text": f"Datasheet page {page_number}"})
        if extracted_text:
            content.append(
                {
                    "type": "text",
                    "text": (
                        f"Extracted text for page {page_number}:\n"
                        f"{extracted_text[:max_page_text_chars]}"
                    ),
                }
            )
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": image_path_to_data_url(image_path)},
            }
        )
    response = _invoke_with_retry(
        llm,
        [{"role": "user", "content": content}],
        label="vision summary batch",
    )
    return response_text(getattr(response, "content", response))


def _invoke_text_summary(
    llm,
    page_payloads: list[dict[str, Any]],
    *,
    instructions: str,
    max_page_text_chars: int = MAX_PAGE_TEXT_CHARS,
) -> str:
    content = [instructions.strip()]
    for page_payload in page_payloads:
        page_number = int(page_payload["page_number"])
        extracted_text = str(page_payload["page_text"]).strip()
        content.append(f"Datasheet page {page_number}")
        if extracted_text:
            content.append(
                f"Extracted text for page {page_number}:\n"
                f"{extracted_text[:max_page_text_chars]}"
            )
        else:
            content.append(f"Extracted text for page {page_number}:\n<no text extracted>")
    response = _invoke_with_retry(
        llm,
        [{"role": "user", "content": "\n\n".join(content)}],
        label="text summary batch",
    )
    return response_text(response.content)


def _synthesize_chunk_summaries(llm, chunk_summaries: list[str]) -> str:
    if len(chunk_summaries) == 1:
        return response_text(chunk_summaries[0])

    content = FINAL_SYNTHESIS_INSTRUCTIONS.strip() + "\n\n"
    for idx, summary in enumerate(chunk_summaries, start=1):
        content += f"Chunk {idx} summary:\n{summary.strip()}\n\n"

    response = _invoke_with_retry(
        llm,
        [{"role": "user", "content": content.strip()}],
        label="final synthesis",
    )
    return response_text(getattr(response, "content", response))


def _is_generic_component_library(component_library: str) -> bool:
    normalized = component_library.strip().lower()
    if normalized in {"device", "switch"}:
        return True
    return normalized.startswith("connector")


def obtain_needed_information(
    component_library: str,
    component_name: str,
    cache_override: bool = False,
    model: str | None = None,
    mode: str | None = None,
    max_batch_size: int = MAX_IMAGES_PER_REQUEST,
    max_page_text_chars: int = MAX_PAGE_TEXT_CHARS,
) -> str:
    if _is_generic_component_library(component_library):
        return f"No additional information available for the component {component_library}:{component_name} as this is a generic component."


    normalized_mode = (mode or config_module.get_datasheet_tool_mode()).strip().lower()
    if normalized_mode not in {"vision", "text"}:
        raise ValueError(f"Unsupported obtain_needed_information mode: {mode!r}")
    effective_model = model
    if not effective_model:
        raise ValueError("No LLM configured for obtain_needed_information.")
    cache_model_key = _datasheet_cache_model_key(effective_model)

    # First check if we have cached information for this component
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / (
        f"{component_library}_{component_name}_{cache_model_key}_{normalized_mode}.md"
    )
    print(
        f"Checking cache for {component_library}:{component_name} "
        f"(model={effective_model}, mode={normalized_mode}) at {cache_file}"
    )
    if cache_file.exists() and not cache_override:
        print(
            "Loading cached information for "
            f"{component_library}:{component_name} "
            f"(model={effective_model}, mode={normalized_mode}) from {cache_file}"
        )
        return cache_file.read_text(encoding="utf-8")

    component = get_kicad_component_by_library_and_name(component_library, component_name)
    if component is None:
        raise ValueError(f"Could not find component {component_library}:{component_name}")

    # Download the datasheet
    pdf_path = _download_datasheet_for_component(
        f"{component_library}:{component_name}",
        component.datasheet,
        use_selenium=True,
    )
    pdf_path = Path(pdf_path)
    print(f"Downloaded datasheet to: {pdf_path}")

    doc = fitz.open(pdf_path)
    page_payloads: list[dict[str, Any]] = []
    preview_dir = CACHE_DIR / f"{safe_filename(pdf_path.stem)}_previews_300dpi"
    progress_desc = (
        "Generating image previews" if normalized_mode == "vision" else "Extracting datasheet text"
    )
    for page_num in tqdm(range(len(doc)), desc=progress_desc):
        image_path = None
        if normalized_mode == "vision":
            image_path = _render_preview(
                doc,
                page_num,
                preview_dir / f"page_{page_num:04d}.png",
                dpi=300,
            )
        extracted_text = doc.load_page(page_num).get_text("text")
        page_payloads.append(
            {
                "page_number": page_num + 1,
                "image_path": image_path,
                "page_text": extracted_text,
            }
        )
    doc.close()

    llm = build_langchain_chat_model(model=effective_model)
    llm_model_name, llm_base_url = llm_debug_identity(llm)
    print(
        f"[obtain_needed_information] running for {component_library}:{component_name} "
        f"with model {llm_model_name} (base={llm_base_url}, mode={normalized_mode})"
    )

    chunk_summaries: list[str] = []
    batch_size = TEXT_MODE_BATCH_SIZE if normalized_mode == "text" else max_batch_size
    page_chunks = _chunked(page_payloads, batch_size)
    for chunk_idx, page_chunk in enumerate(
        tqdm(page_chunks, desc="Analyzing datasheet page batches", leave=False)
    ):
        start_page = chunk_idx * batch_size + 1
        end_page = start_page + len(page_chunk) - 1
        chunk_instructions = (
            f"{CHUNK_INSTRUCTIONS.strip()}\n"
            f"This batch covers datasheet pages {start_page}-{end_page}."
        )
        if normalized_mode == "vision":
            chunk_summaries.append(
                _invoke_vision_summary(
                    llm,
                    page_chunk,
                    instructions=chunk_instructions,
                    max_page_text_chars=max_page_text_chars,
                )
            )
        else:
            chunk_summaries.append(
                _invoke_text_summary(
                    llm,
                    page_chunk,
                    instructions=chunk_instructions,
                    max_page_text_chars=max_page_text_chars,
                )
            )

    response_text = _synthesize_chunk_summaries(llm, chunk_summaries)

    # Cache the response
    cache_file.write_text(response_text, encoding="utf-8")

    return response_text


