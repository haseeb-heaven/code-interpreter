"""
Image loading helpers for multimodal (vision) LLM messages.

Converts local paths and remote URLs into OpenAI-compatible ``image_url``
content blocks that LiteLLM can route across providers.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def load_image_as_content_block(image_source: str) -> dict:
	"""
	Convert an image path or URL into an OpenAI-compatible image_url content block.

	Returns:
		dict: e.g. ``{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}``
	"""
	if not image_source or not str(image_source).strip():
		raise ValueError("image_source is required")

	source = str(image_source).strip()
	if source.startswith(("http://", "https://")):
		return {
			"type": "image_url",
			"image_url": {"url": source, "detail": "auto"},
		}

	path = Path(source)
	if not path.exists():
		raise FileNotFoundError(f"Image file not found: {image_source}")
	if not path.is_file():
		raise ValueError(f"Image path is not a file: {image_source}")

	suffix = path.suffix.lower()
	if suffix not in SUPPORTED_EXTENSIONS:
		raise ValueError(
			f"Unsupported image format: {suffix}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
		)

	mime_type, _ = mimetypes.guess_type(str(path))
	mime_type = mime_type or "image/png"

	with open(path, "rb") as handle:
		encoded = base64.b64encode(handle.read()).decode("utf-8")

	data_url = f"data:{mime_type};base64,{encoded}"
	logger.info("[Vision] Loaded image: %s (%sKB)", path.name, path.stat().st_size // 1024)
	return {
		"type": "image_url",
		"image_url": {"url": data_url, "detail": "auto"},
	}


def build_multimodal_message(text: str, image_sources: Iterable[str]) -> dict:
	"""
	Build a user message with both text and one or more images.

	Images are placed first (preferred by most vision models), then the text query.
	"""
	content: list[dict] = []

	for src in image_sources or []:
		try:
			content.append(load_image_as_content_block(str(src)))
		except Exception as exc:
			logger.error("[Vision] Failed to load image %s: %s", src, exc)
			content.append({"type": "text", "text": f"[Image load failed: {src} - {exc}]"})

	content.append({"type": "text", "text": text or ""})
	return {"role": "user", "content": content}


def is_vision_model(model: str) -> bool:
	"""Heuristic check whether a model id likely supports image inputs."""
	if not model:
		return False
	vision_keywords = [
		"gpt-4o",
		"gpt-4-vision",
		"gpt-4.1",
		"gpt-5",
		"gemini",
		"claude-3",
		"claude-3-5",
		"claude-sonnet",
		"claude-opus",
		"claude-haiku",
		"llava",
		"vision",
		"pixtral",
		"qwen-vl",
		"qwen2-vl",
	]
	model_lower = str(model).lower()
	return any(keyword in model_lower for keyword in vision_keywords)


def inject_images_into_messages(messages: list, text: str, image_sources: list[str]) -> list:
	"""
	Return a copy of ``messages`` with a multimodal user turn for ``image_sources``.

	If the last message is already a user turn, it is replaced; otherwise a new
	user message is appended.
	"""
	if not image_sources:
		return messages

	multimodal = build_multimodal_message(text, image_sources)
	if not messages:
		return [multimodal]

	updated = list(messages)
	# Prefer replacing the last user message so system/assistant history remains.
	for index in range(len(updated) - 1, -1, -1):
		if updated[index].get("role") == "user":
			# Keep prior text if caller passed empty text and content was a string
			prior = updated[index].get("content")
			if not text and isinstance(prior, str) and prior.strip():
				multimodal = build_multimodal_message(prior, image_sources)
			updated[index] = multimodal
			return updated

	updated.append(multimodal)
	return updated
