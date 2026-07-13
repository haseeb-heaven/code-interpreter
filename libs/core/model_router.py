"""LLM provider routing, client init, and content generation."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Callable, Optional

import requests

from libs.model_utils import normalize_model_name


class ModelRouter:
	"""Owns API-key validation and litellm/provider dispatch.

	Patched symbols from ``libs.interpreter_lib`` (``litellm.completion``,
	``load_dotenv``, ``os.getenv``, ``time.sleep``, ``display_markdown_message``)
	are passed in at call time so existing unit-test patches keep working.
	"""

	def __init__(self, interp):
		self.interp = interp

	# ── Client initialization ──────────────────────────────────────────

	def initialize_client(self, *, load_dotenv_fn, getenv_fn, environ) -> None:
		interp = self.interp
		env_path = os.path.join(os.getcwd(), ".env")
		load_dotenv_fn(dotenv_path=env_path, override=True)
		interp.logger.info("Initializing Client")

		interp.logger.info(f"Interpreter model selected is '{interp.INTERPRETER_MODEL}'")
		if interp.INTERPRETER_MODEL is None or interp.INTERPRETER_MODEL == "":
			interp.logger.info("Model is not provided, using default model.")
			interp.INTERPRETER_MODEL = interp.utility_manager.get_default_model_name()
			interp.INTERPRETER_MODEL_LABEL = interp.INTERPRETER_MODEL
		else:
			interp.INTERPRETER_MODEL_LABEL = interp.INTERPRETER_MODEL

		interp.logger.info(f"Reading model registry entry '{interp.INTERPRETER_MODEL}'")
		interp.config_values = interp.utility_manager.read_config_file(interp.INTERPRETER_MODEL)
		interp.INTERPRETER_MODEL = str(interp.config_values.get("model", interp.INTERPRETER_MODEL))
		model_name = interp.INTERPRETER_MODEL.strip().split("/")[-1]

		# skip init client for local models.(Bug#10)
		# Prefer config provider so models like llama3.1:8b with provider=local skip HF key checks.
		_local_providers = ("local", "ollama", "lmstudio")
		_cfg_provider = str(interp.config_values.get("provider", "")).strip().lower()
		if (
			"local" in interp.INTERPRETER_MODEL
			or "ollama" in interp.INTERPRETER_MODEL
			or _cfg_provider in _local_providers
		):
			interp.logger.info("Skipping client initialization for local model.")
			api_key = getenv_fn("OPENAI_API_KEY")

			if api_key:
				interp.logger.info("Using local API key from environment variables.")

			if api_key is None:
				load_dotenv_fn(dotenv_path=env_path, override=True)
				api_key = getenv_fn("OPENAI_API_KEY")
				if api_key is None:
					interp.logger.info("Setting default local API key for local models.")
					environ["OPENAI_API_KEY"] = "sk-1234567890"
			return

		interp.logger.info(f"Using model {model_name}")

		config_provider = str(interp.config_values.get("provider", "")).strip().lower()

		# Provider field wins over model-id heuristics (OpenRouter may use nvidia/... ids).
		if config_provider == "nvidia":
			api_key_info = {"key_name": "NVIDIA_API_KEY", "prefix": "nvapi-"}
		elif config_provider in ("z-ai", "zai"):
			api_key_info = {"key_name": "Z_AI_API_KEY", "prefix": None, "length": 10}
		elif config_provider in ("browser-use", "browser_use"):
			api_key_info = {"key_name": "BROWSER_USE_API_KEY", "prefix": "bu_"}
		elif config_provider == "openrouter":
			api_key_info = {"key_name": "OPENROUTER_API_KEY", "prefix": "sk-or-v1-"}
		elif config_provider == "cerebras":
			api_key_info = {"key_name": "CEREBRAS_API_KEY", "prefix": "csk-"}
		elif interp.INTERPRETER_MODEL.startswith("nvidia/"):
			api_key_info = {"key_name": "NVIDIA_API_KEY", "prefix": "nvapi-"}
		elif interp.INTERPRETER_MODEL.startswith(("glm-", "z-ai/", "zai/")):
			api_key_info = {"key_name": "Z_AI_API_KEY", "prefix": None, "length": 10}
		elif interp.INTERPRETER_MODEL.startswith(("bu-", "browser-use/")):
			api_key_info = {"key_name": "BROWSER_USE_API_KEY", "prefix": "bu_"}
		elif interp.INTERPRETER_MODEL.startswith("cerebras/"):
			api_key_info = {"key_name": "CEREBRAS_API_KEY", "prefix": "csk-"}
		elif interp.INTERPRETER_MODEL.startswith(("gpt", "o1", "o3", "o4")):
			api_key_info = {"key_name": "OPENAI_API_KEY", "prefix": "sk-"}
		elif interp.INTERPRETER_MODEL.startswith("groq/") or "groq" in interp.INTERPRETER_MODEL:
			api_key_info = {"key_name": "GROQ_API_KEY", "prefix": "gsk"}
		elif "claude" in interp.INTERPRETER_MODEL:
			api_key_info = {"key_name": "ANTHROPIC_API_KEY", "prefix": "sk-ant-"}
		elif "gemini" in interp.INTERPRETER_MODEL:
			api_key_info = {"key_name": "GEMINI_API_KEY", "prefix": None, "length": 15}
		elif "deepseek" in interp.INTERPRETER_MODEL:
			api_key_info = {"key_name": "DEEPSEEK_API_KEY", "prefix": None, "length": 10}
		else:
			api_key_info = {"key_name": "HUGGINGFACE_API_KEY", "prefix": "hf_"}

		api_key_name = api_key_info["key_name"]
		from libs.key_manager import KeyManager, provider_from_api_key_name

		# Merge config into KeyManager for RPM / circuit settings
		km = KeyManager(getenv_fn=getenv_fn, config=interp.config_values or {})
		# Ensure pools see latest dotenv + any getenv override from callers/tests
		load_dotenv_fn(dotenv_path=env_path, override=True)
		km._getenv = getenv_fn
		km.reload(config=interp.config_values or {})
		interp._key_manager = km

		provider = provider_from_api_key_name(api_key_name)
		key_state = km.acquire_key(provider)
		if key_state is None:
			# Backwards compatible fallback to bare getenv (no pool / all exhausted at init)
			api_key = getenv_fn(api_key_name)
			if api_key is None:
				load_dotenv_fn(dotenv_path=env_path, override=True)
				api_key = getenv_fn(api_key_name)
			if not api_key:
				raise Exception(f"{api_key_name} not found in .env file.")
			environ[api_key_name] = api_key
		else:
			api_key = key_state.value
			interp._active_provider = provider
			interp._active_key_state = key_state
			environ[api_key_name] = api_key

		if api_key_info.get("prefix") and not api_key.startswith(api_key_info["prefix"]):
			raise Exception(
				f"{api_key_name} should start with '{api_key_info['prefix']}'. Please check your .env file."
			)
		if api_key_info.get("length") and len(api_key) <= api_key_info["length"]:
			raise Exception(
				f"{api_key_name} should have length greater than {api_key_info['length']}. Please check your .env file."
			)

	# ── Error helpers ──────────────────────────────────────────────────

	@staticmethod
	def is_recoverable_runtime_error(error_text) -> bool:
		from libs.core.error_classification import BILLING_AUTH_MARKERS, is_billing_or_auth_condition

		error_text = (error_text or "").lower()
		if is_billing_or_auth_condition(error_text):
			return True
		extra_recoverable_errors = [
			"credits",
			"requires more credits",
			"temporarily rate-limited",
			"402",
			"model_not_found",
			"not found",
			"timeout",
			"connection",
		]
		return any(error in error_text for error in extra_recoverable_errors)

	@staticmethod
	def format_runtime_error_message(error_text) -> str:
		message = error_text or "Unknown error"
		message = re.sub(r"https?://\S+", "", message)
		message = re.sub(r"litellm\.[A-Za-z]+Error:\s*", "", message)
		message = re.sub(r"\b[A-Za-z]+Error:\s*", "", message)
		message = re.sub(r"\b[A-Za-z]+Exception\s*-\s*", "", message)
		message = re.sub(r"For more information on this error.*", "", message, flags=re.IGNORECASE)
		message = re.sub(r"\s+", " ", message).strip(" .")
		return message

	@staticmethod
	def is_retryable_request_error(error_text) -> bool:
		error_text = (error_text or "").lower()
		retryable_markers = [
			"rate limit",
			"ratelimit",
			"timeout",
			"temporarily unavailable",
			"temporarily rate-limited",
			"connection",
			"503",
			"502",
			"429",
			"overloaded",
			"provider returned error",
			"try again",
		]
		non_retryable_markers = [
			"quota",
			"credits",
			"requires more credits",
			"billing",
			"api key",
			"authentication",
			"unauthorized",
			"model_not_found",
		]
		if any(marker in error_text for marker in non_retryable_markers):
			return False
		return any(marker in error_text for marker in retryable_markers)

	# ── Browser Use / OpenAI-compatible helpers ────────────────────────

	@staticmethod
	def extract_latest_user_text(message, messages) -> str:
		if isinstance(message, str) and message.strip():
			return message.strip()
		if isinstance(messages, list):
			for item in reversed(messages):
				if not isinstance(item, dict) or item.get("role") != "user":
					continue
				content = item.get("content")
				if isinstance(content, str) and content.strip():
					return content.strip()
				if isinstance(content, list):
					text_parts = []
					for chunk in content:
						if isinstance(chunk, dict) and chunk.get("type") == "text":
							text_parts.append(str(chunk.get("text", "")).strip())
					joined = " ".join(part for part in text_parts if part)
					if joined:
						return joined
		return "Help with this request."

	def run_openai_compatible_completion(
		self,
		api_key_name,
		messages,
		temperature,
		max_tokens,
		api_base,
		extra_headers=None,
		*,
		completion_fn: Callable,
		getenv_fn: Callable,
	):
		api_key = getenv_fn(api_key_name)
		if not api_key:
			raise Exception(f"{api_key_name} not found in .env file.")
		if api_base == "None":
			raise Exception("Exception api base not set for custom model")
		custom_llm_provider = "openai"
		completion_kwargs = {
			"messages": messages,
			"temperature": temperature,
			"max_tokens": max_tokens,
			"api_base": api_base,
			"api_key": api_key,
			"custom_llm_provider": custom_llm_provider,
		}
		if extra_headers:
			completion_kwargs["extra_headers"] = extra_headers
		return completion_fn(self.interp.INTERPRETER_MODEL, **completion_kwargs)

	def generate_browser_use_content(self, message, messages, config_values, *, getenv_fn: Callable):
		interp = self.interp
		api_key = getenv_fn("BROWSER_USE_API_KEY")
		if not api_key:
			raise Exception("BROWSER_USE_API_KEY not found in .env file.")

		base_url = str(config_values.get("api_base", "https://api.browser-use.com/api/v3")).rstrip("/")
		model = interp.INTERPRETER_MODEL
		task = self.extract_latest_user_text(message, messages)
		timeout_seconds = int(config_values.get("browser_use_timeout", 150))
		poll_interval = int(config_values.get("browser_use_poll_interval", 3))

		headers = {
			"X-Browser-Use-API-Key": api_key,
			"Content-Type": "application/json",
		}
		payload = {
			"task": task,
			"model": model,
			"keepAlive": False,
		}
		interp.logger.info(f"Starting Browser Use session with model={model}")
		create_response = requests.post(f"{base_url}/sessions", headers=headers, json=payload, timeout=45)
		create_response.raise_for_status()
		create_data = create_response.json()
		session_id = create_data.get("id")
		if not session_id:
			raise Exception("Browser Use session creation failed: missing session id")

		end_time = time.time() + timeout_seconds
		while time.time() < end_time:
			status_response = requests.get(f"{base_url}/sessions/{session_id}", headers=headers, timeout=30)
			status_response.raise_for_status()
			status_data = status_response.json()
			status = str(status_data.get("status", "")).lower()
			live_url = status_data.get("liveUrl")

			if status in {"finished", "completed", "stopped", "done", "success"}:
				output = status_data.get("output")
				if output is None:
					output = status_data.get("result")
				if output is None:
					output = status_data.get("finalResult")
				if output is None and live_url:
					output = f"Browser Use session completed. Live URL: {live_url}"
				if output is None:
					output = f"Browser Use session completed. Session ID: {session_id}"
				if isinstance(output, (dict, list)):
					return json.dumps(output, ensure_ascii=False)
				return str(output)

			if status in {"failed", "error", "cancelled"}:
				raise Exception(f"Browser Use session failed with status '{status}'")

			time.sleep(poll_interval)

		raise Exception("Browser Use session timed out.")

	async def generate_browser_use_content_async(self, message, messages, config_values, *, getenv_fn: Callable):
		interp = self.interp
		api_key = getenv_fn("BROWSER_USE_API_KEY")
		if not api_key:
			raise Exception("BROWSER_USE_API_KEY not found in .env file.")

		base_url = str(config_values.get("api_base", "https://api.browser-use.com/api/v3")).rstrip("/")
		model = interp.INTERPRETER_MODEL
		task = self.extract_latest_user_text(message, messages)
		timeout_seconds = int(config_values.get("browser_use_timeout", 150))
		poll_interval = int(config_values.get("browser_use_poll_interval", 3))

		headers = {
			"X-Browser-Use-API-Key": api_key,
			"Content-Type": "application/json",
		}
		payload = {
			"task": task,
			"model": model,
			"keepAlive": False,
		}
		interp.logger.info(f"Starting Browser Use session with model={model}")
		create_response = requests.post(f"{base_url}/sessions", headers=headers, json=payload, timeout=45)
		create_response.raise_for_status()
		create_data = create_response.json()
		session_id = create_data.get("id")
		if not session_id:
			raise Exception("Browser Use session creation failed: missing session id")

		end_time = time.time() + timeout_seconds
		while time.time() < end_time:
			status_response = requests.get(f"{base_url}/sessions/{session_id}", headers=headers, timeout=30)
			status_response.raise_for_status()
			status_data = status_response.json()
			status = str(status_data.get("status", "")).lower()
			live_url = status_data.get("liveUrl")

			if status in {"finished", "completed", "stopped", "done", "success"}:
				output = status_data.get("output")
				if output is None:
					output = status_data.get("result")
				if output is None:
					output = status_data.get("finalResult")
				if output is None and live_url:
					output = f"Browser Use session completed. Live URL: {live_url}"
				if output is None:
					output = f"Browser Use session completed. Session ID: {session_id}"
				if isinstance(output, (dict, list)):
					return json.dumps(output, ensure_ascii=False)
				return str(output)

			if status in {"failed", "error", "cancelled"}:
				raise Exception(f"Browser Use session failed with status '{status}'")

			await asyncio.sleep(poll_interval)

		raise Exception("Browser Use session timed out.")

	# ── Content generation ─────────────────────────────────────────────

	def generate_content(
		self,
		message,
		chat_history,
		temperature=0.1,
		max_tokens=1024,
		config_values=None,
		image_file=None,
		*,
		completion_fn: Callable,
		getenv_fn: Callable,
	):
		from libs.llm_dispatcher import build_completion_kwargs

		interp = self.interp
		interp.logger.info(
			f"Generating content with args: message={message}, chat_history={chat_history}, "
			f"temperature={temperature}, max_tokens={max_tokens}, config_values={config_values}, "
			f"image_file={image_file}"
		)
		interp.logger.info(f"Interpreter model selected is '{interp.INTERPRETER_MODEL}'")
		api_base = "None"
		config_provider = ""

		if config_values:
			temperature = float(config_values.get("temperature", temperature))
			max_tokens = int(config_values.get("max_tokens", max_tokens))
			api_base = str(config_values.get("api_base", None))
			config_provider = str(config_values.get("provider", "")).strip().lower()

		messages = interp.get_prompt(message, chat_history)

		# Multimodal: --image / pending /image REPL / legacy image_file
		from libs.vision.image_handler import (
			image_file_arg_for_path,
			inject_images_into_messages,
			is_image_source_path,
			is_vision_model,
		)

		image_sources = []
		if image_file:
			filtered = image_file_arg_for_path(str(image_file))
			if filtered:
				image_sources.append(filtered)
			elif image_file:
				interp.logger.info(
					"Ignoring non-image extracted path for multimodal: %s",
					image_file,
				)
		cli_images = getattr(getattr(interp, "args", None), "image", None) or []
		image_sources.extend(
			str(src) for src in cli_images if is_image_source_path(str(src))
		)
		pending = getattr(interp, "_pending_images", None) or []
		if pending:
			image_sources.extend(
				str(src) for src in pending if is_image_source_path(str(src))
			)
			interp._pending_images = []
		# De-dupe while preserving order
		seen = set()
		unique_images = []
		for src in image_sources:
			if src not in seen:
				seen.add(src)
				unique_images.append(src)
		image_sources = unique_images

		if image_sources and isinstance(messages, list):
			model_label = str(getattr(interp, "INTERPRETER_MODEL", "") or "")
			if not is_vision_model(model_label):
				interp.logger.warning(
					"Model '%s' may not support image inputs; sending multimodal payload anyway.",
					model_label,
				)
				print(f"WARNING: Model '{model_label}' may not support image inputs.")
			messages = inject_images_into_messages(messages, str(message or ""), image_sources)

		if config_provider in ("browser-use", "browser_use") or interp.INTERPRETER_MODEL.startswith(("bu-", "browser-use/")):
			interp.logger.info("Model is Browser Use session model.")
			response_text = interp._generate_browser_use_content(message, messages, config_values or {})
			interp.logger.info("Response received from Browser Use session.")
			return response_text

		if "gemini" in interp.INTERPRETER_MODEL and interp.INTERPRETER_MODE == "vision":
			try:
				from libs.gemini_vision import GeminiVision
				interp.gemini_vision = GeminiVision()
			except Exception as exception:
				interp.logger.error(f"Error importing Gemini Vision: {exception}")
				raise

			interp.logger.info("Model is Gemini Pro Vision.")
			vision_image = image_sources[0] if image_sources else image_file
			if not vision_image:
				interp.logger.error("Image file is not valid or Corrupted.")
				raise ValueError("Image file is not valid or Corrupted.")

			if "http" in vision_image or "https" in vision_image or "www." in vision_image:
				interp.logger.info("Image contains URL.")
				response = interp.gemini_vision.gemini_vision_url(prompt=messages, image_url=vision_image)
			else:
				interp.logger.info("Image contains file.")
				response = interp.gemini_vision.gemini_vision_path(prompt=messages, image_path=vision_image)

			interp.logger.info("Response received from completion function.")
			return response

		interp.INTERPRETER_MODEL = normalize_model_name(interp.INTERPRETER_MODEL)

		use_stream = bool(getattr(getattr(interp, "args", None), "stream", False))
		kwargs = build_completion_kwargs(
			model=interp.INTERPRETER_MODEL,
			messages=messages,
			temperature=temperature,
			max_tokens=max_tokens,
			config_provider=config_provider,
			api_base=api_base,
			stream=use_stream,
		)
		interp.logger.info(
			f"Calling litellm.completion for provider-resolved kwargs "
			f"(keys: {list(kwargs.keys())}, stream={use_stream})"
		)

		if use_stream:
			from libs.streaming import StreamingPrinter, looks_like_completion_response

			interp._last_response_was_streamed = False
			response = completion_fn(interp.INTERPRETER_MODEL, **kwargs)
			if looks_like_completion_response(response):
				generated_text = interp.utility_manager._extract_content(response)
				if generated_text:
					print(generated_text)
					interp._last_response_was_streamed = True
			else:
				try:
					generated_text, _ = StreamingPrinter(show_stream=True).print_stream(response)
					interp._last_response_was_streamed = True
				except Exception as stream_exc:
					interp.logger.warning(f"Streaming failed, falling back: {stream_exc}")
					kwargs_ns = dict(kwargs)
					kwargs_ns["stream"] = False
					response = completion_fn(interp.INTERPRETER_MODEL, **kwargs_ns)
					generated_text = interp.utility_manager._extract_content(response)
					interp._last_response_was_streamed = False
			interp.logger.info(f"Generated content {generated_text}")
			return generated_text

		interp._last_response_was_streamed = False
		response = completion_fn(interp.INTERPRETER_MODEL, **kwargs)
		interp.logger.info("Response received from completion function.")

		interp.logger.info(f"Generated text {response}")
		generated_text = interp.utility_manager._extract_content(response)
		interp.logger.info(f"Generated content {generated_text}")
		return generated_text

	def route(self, messages, config_values=None, *, completion_fn=None, getenv_fn=None):
		"""Agent-facing completion helper: messages in → text out.

		Unlike ``generate_content``, this does not rebuild Interpreter system
		prompts; agents supply their own message lists. Falls back to
		``litellm.completion`` when no ``completion_fn`` is provided.
		"""
		import litellm

		interp = self.interp
		config_values = config_values or {}
		temperature = float(config_values.get("temperature", 0.1))
		max_tokens = int(config_values.get("max_tokens", 1024))
		api_base = str(config_values.get("api_base", (interp.config_values or {}).get("api_base", "None")))
		config_provider = str(
			config_values.get("provider", (interp.config_values or {}).get("provider", ""))
		).strip().lower()

		from libs.llm_dispatcher import build_completion_kwargs

		completion_fn = completion_fn or litellm.completion
		model = normalize_model_name(interp.INTERPRETER_MODEL)
		kwargs = build_completion_kwargs(
			model=model,
			messages=messages,
			temperature=temperature,
			max_tokens=max_tokens,
			config_provider=config_provider,
			api_base=api_base,
		)
		# Agents often pass plain system/user messages; drop empty assistant noise.
		kwargs["messages"] = messages
		self._log_route(model, list(kwargs.keys()))
		response = completion_fn(model, **kwargs)
		return interp.utility_manager._extract_content(response)

	async def route_async(self, messages, config_values=None, *, acompletion_fn=None, getenv_fn=None):
		"""Async agent-facing completion helper using ``litellm.acompletion``."""
		import litellm

		interp = self.interp
		config_values = config_values or {}
		temperature = float(config_values.get("temperature", 0.1))
		max_tokens = int(config_values.get("max_tokens", 1024))
		api_base = str(config_values.get("api_base", (interp.config_values or {}).get("api_base", "None")))
		config_provider = str(
			config_values.get("provider", (interp.config_values or {}).get("provider", ""))
		).strip().lower()

		from libs.llm_dispatcher import build_completion_kwargs

		acompletion_fn = acompletion_fn or litellm.acompletion
		model = normalize_model_name(interp.INTERPRETER_MODEL)
		kwargs = build_completion_kwargs(
			model=model,
			messages=messages,
			temperature=temperature,
			max_tokens=max_tokens,
			config_provider=config_provider,
			api_base=api_base,
		)
		# Agents often pass plain system/user messages; drop empty assistant noise.
		kwargs["messages"] = messages
		self._log_route(model, list(kwargs.keys()))
		response = await acompletion_fn(model, **kwargs)
		return interp.utility_manager._extract_content(response)

	def _log_route(self, model, keys):
		self.interp.logger.info(f"ModelRouter.route model={model} kwargs_keys={keys}")

	def _prepare_retry_key(self, km, provider: str, api_key_name: str, last_exception):
		"""Acquire a healthy key or decide whether to proceed / raise exhausted."""
		key_state = km.acquire_key(provider)
		if key_state is not None:
			self.interp._active_provider = provider
			self.interp._active_key_state = key_state
			os.environ[api_key_name] = key_state.value
			if key_state.bucket is not None:
				try:
					key_state.bucket.acquire(timeout=2.0)
				except Exception:
					pass
			return key_state

		# Pool exists but every key is unavailable → surface exhaustion (with ETA)
		if km.has_pool(provider):
			km.raise_if_exhausted(provider)
		# No managed pool: backwards-compatible bare-env path
		return None

	def _record_retry_failure(self, km, provider, key_state, exception, latency_ms):
		"""Classify failure, update key state, return (err_type, should_retry)."""
		from libs.key_manager import ErrorClassifier, ErrorType

		err_type = ErrorClassifier.classify(exception)
		error_text = str(exception)
		if key_state is not None:
			km.metrics.log(
				provider=provider,
				key_index=key_state.index,
				latency_ms=latency_ms,
				success=False,
				error_type=err_type.value,
			)
			if err_type == ErrorType.AUTH:
				# Permanently isolate this key; caller may rotate to another key.
				km.record_failure(provider, key_state.index, is_auth=True)
			elif err_type == ErrorType.FATAL:
				pass
			elif err_type == ErrorType.QUOTA:
				km.record_failure(provider, key_state.index, is_quota=True)
			elif err_type == ErrorType.TRANSIENT:
				km.record_failure(
					provider,
					key_state.index,
					is_rate_limit=("429" in error_text.lower() or "rate" in error_text.lower()),
				)

		# FATAL always surfaces; AUTH retries only when another key may be healthy
		if err_type == ErrorType.FATAL:
			return err_type, False
		if err_type == ErrorType.AUTH:
			if km.has_pool(provider) and km.get_pool(provider).available_count() > 0:
				return err_type, True
			return err_type, False
		return err_type, True

	@staticmethod
	def _jitter_backoff_seconds(attempt: int) -> float:
		import random

		cap = min(30.0, 1.0 * (2 ** attempt))
		return random.uniform(0.0, cap)

	def generate_content_with_retries(
		self,
		message,
		chat_history,
		config_values=None,
		image_file=None,
		*,
		sleep_fn: Callable,
		display_fn: Callable,
	):
		from libs.key_manager import KeyManager, provider_from_api_key_name

		interp = self.interp
		last_exception = None
		config_values = config_values or interp.config_values or {}
		km = getattr(interp, "_key_manager", None) or KeyManager(config=config_values)
		interp._key_manager = km

		api_key_name = self._resolve_api_key_name(config_values)
		provider = provider_from_api_key_name(api_key_name)

		for attempt in range(1, interp.MAX_LLM_RETRIES + 1):
			key_state = self._prepare_retry_key(km, provider, api_key_name, last_exception)

			started = time.time()
			try:
				result = interp.generate_content(
					message, chat_history, config_values=config_values, image_file=image_file
				)
				latency_ms = (time.time() - started) * 1000.0
				if key_state is not None:
					km.record_success(provider, key_state.index)
					km.metrics.log(
						provider=provider,
						key_index=key_state.index,
						latency_ms=latency_ms,
						success=True,
					)
				return result
			except Exception as exception:
				last_exception = exception
				latency_ms = (time.time() - started) * 1000.0
				err_type, should_retry = self._record_retry_failure(
					km, provider, key_state, exception, latency_ms
				)

				if attempt >= interp.MAX_LLM_RETRIES or not should_retry:
					# Prefer AllKeysExhaustedError (with ETA) when the pool is fully dark
					if km.has_pool(provider):
						from libs.key_manager import AllKeysExhaustedError

						try:
							km.raise_if_exhausted(provider)
						except AllKeysExhaustedError:
							raise
					raise

				display_fn(
					f"LLM request retry {attempt}/{interp.MAX_LLM_RETRIES} "
					f"({err_type.value}) — rotating key / backoff."
				)
				sleep_fn(self._jitter_backoff_seconds(attempt))

		if last_exception:
			raise last_exception

	def _resolve_api_key_name(self, config_values) -> str:
		"""Mirror initialize_client provider → env key mapping."""
		interp = self.interp
		config_provider = str((config_values or {}).get("provider", "")).strip().lower()
		model = interp.INTERPRETER_MODEL or ""
		if config_provider == "nvidia":
			return "NVIDIA_API_KEY"
		if config_provider in ("z-ai", "zai"):
			return "Z_AI_API_KEY"
		if config_provider in ("browser-use", "browser_use"):
			return "BROWSER_USE_API_KEY"
		if config_provider == "openrouter":
			return "OPENROUTER_API_KEY"
		if config_provider == "cerebras":
			return "CEREBRAS_API_KEY"
		if model.startswith("nvidia/"):
			return "NVIDIA_API_KEY"
		if model.startswith(("glm-", "z-ai/", "zai/")):
			return "Z_AI_API_KEY"
		if model.startswith(("bu-", "browser-use/")):
			return "BROWSER_USE_API_KEY"
		if model.startswith("cerebras/"):
			return "CEREBRAS_API_KEY"
		if model.startswith(("gpt", "o1", "o3", "o4")):
			return "OPENAI_API_KEY"
		if model.startswith("groq/") or "groq" in model:
			return "GROQ_API_KEY"
		if "claude" in model:
			return "ANTHROPIC_API_KEY"
		if "gemini" in model:
			return "GEMINI_API_KEY"
		if "deepseek" in model:
			return "DEEPSEEK_API_KEY"
		return "HUGGINGFACE_API_KEY"

	async def generate_content_with_retries_async(
		self,
		message,
		chat_history,
		config_values=None,
		image_file=None,
		*,
		sleep_fn: Optional[Callable] = None,
		display_fn: Optional[Callable] = None,
	):
		"""Async retry loop with the same key-rotation / jitter resilience as sync."""
		from libs.key_manager import KeyManager, provider_from_api_key_name

		interp = self.interp
		last_exception = None
		config_values = config_values or interp.config_values or {}
		km = getattr(interp, "_key_manager", None) or KeyManager(config=config_values)
		interp._key_manager = km
		api_key_name = self._resolve_api_key_name(config_values)
		provider = provider_from_api_key_name(api_key_name)
		_display = display_fn or (lambda *_: None)

		for attempt in range(1, interp.MAX_LLM_RETRIES + 1):
			key_state = self._prepare_retry_key(km, provider, api_key_name, last_exception)

			started = time.time()
			try:
				generate_async = getattr(interp, "generate_content_async", None)
				if generate_async:
					result = await generate_async(
						message, chat_history, config_values=config_values, image_file=image_file
					)
				else:
					result = await asyncio.to_thread(
						interp.generate_content,
						message,
						chat_history,
						config_values=config_values,
						image_file=image_file,
					)
				latency_ms = (time.time() - started) * 1000.0
				if key_state is not None:
					km.record_success(provider, key_state.index)
					km.metrics.log(
						provider=provider,
						key_index=key_state.index,
						latency_ms=latency_ms,
						success=True,
					)
				return result
			except Exception as exception:
				last_exception = exception
				latency_ms = (time.time() - started) * 1000.0
				err_type, should_retry = self._record_retry_failure(
					km, provider, key_state, exception, latency_ms
				)

				if attempt >= interp.MAX_LLM_RETRIES or not should_retry:
					if km.has_pool(provider):
						from libs.key_manager import AllKeysExhaustedError

						try:
							km.raise_if_exhausted(provider)
						except AllKeysExhaustedError:
							raise
					raise

				_display(
					f"LLM request retry {attempt}/{interp.MAX_LLM_RETRIES} "
					f"({err_type.value}) — rotating key / backoff."
				)
				delay = self._jitter_backoff_seconds(attempt)
				if sleep_fn is None:
					await asyncio.sleep(delay)
				else:
					await asyncio.to_thread(sleep_fn, delay)

		if last_exception:
			raise last_exception