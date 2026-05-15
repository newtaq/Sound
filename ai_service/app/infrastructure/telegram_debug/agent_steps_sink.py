import html
import json
import re
from pathlib import Path
from typing import Any

from app.application.agent_core.models import (
    AgentRun,
    AgentStep,
    AgentStepType,
    AgentToolCall,
    AgentToolResult,
)
from app.infrastructure.telegram_debug.config import (
    TelegramVisualDebugConfig,
    load_telegram_visual_debug_config,
)
from app.infrastructure.telegram_debug.models import (
    TelegramDebugMessage,
    TelegramDebugMessageKind,
)
from app.infrastructure.telegram_debug.sink import TelegramVisualDebugSink


class TelegramAgentRunDebugSink:
    def __init__(
        self,
        config: TelegramVisualDebugConfig | None = None,
        telegram_sink: TelegramVisualDebugSink | None = None,
    ) -> None:
        self._config = config or load_telegram_visual_debug_config()
        self._telegram_sink = telegram_sink or TelegramVisualDebugSink(
            config=self._config,
        )

    def emit_agent_run(
        self,
        run: AgentRun,
    ) -> None:
        if not self._config.enabled:
            return

        total = len(run.steps)

        for step in run.steps:
            self._telegram_sink.emit_background(
                self._build_step_message(
                    run=run,
                    step=step,
                    total=total,
                )
            )

        if run.final_result is not None and not self._has_final_step(run):
            self._telegram_sink.emit_background(
                self._build_standalone_final_message(run)
            )

        event_summary_text = self._read_event_summary_text(run)

        if event_summary_text:
            self._telegram_sink.emit_background(
                self._build_event_summary_message(
                    run=run,
                    event_summary_text=event_summary_text,
                )
            )

    def _has_final_step(
        self,
        run: AgentRun,
    ) -> bool:
        return any(
            step.step_type == AgentStepType.FINAL
            for step in run.steps
        )

    def _build_step_message(
        self,
        run: AgentRun,
        step: AgentStep,
        total: int,
    ) -> TelegramDebugMessage:
        return TelegramDebugMessage(
            kind=self._map_kind(step.step_type),
            session_id=run.session_id,
            request_id=run.request_id,
            provider_name=self._read_provider_name(run),
            event_title=self._read_event_title(run),
            text=self._build_step_text(
                run=run,
                step=step,
                total=total,
            ),
            metadata=self._build_step_metadata(
                run=run,
                step=step,
                total=total,
            ),
        )

    def _build_standalone_final_message(
        self,
        run: AgentRun,
    ) -> TelegramDebugMessage:
        return TelegramDebugMessage(
            kind=TelegramDebugMessageKind.INFO,
            session_id=run.session_id,
            request_id=run.request_id,
            provider_name=self._read_provider_name(run),
            event_title=self._read_event_title(run),
            text=self._build_standalone_final_text(run),
            metadata={
                **self._build_run_metadata(run),
                **self._build_minimal_metadata(
                    step_type="final_result",
                    skip_pin=True,
                ),
                "summary_ready": True,
            },
        )

    def _build_event_summary_message(
        self,
        run: AgentRun,
        event_summary_text: str,
    ) -> TelegramDebugMessage:
        return TelegramDebugMessage(
            kind=TelegramDebugMessageKind.INFO,
            session_id=run.session_id,
            request_id=run.request_id,
            provider_name=self._read_provider_name(run),
            event_title=self._read_event_title(run),
            text=self._prepare_visible_text(event_summary_text),
            metadata={
                **self._build_run_metadata(run),
                **self._build_minimal_metadata(
                    step_type="event_summary",
                    skip_pin=True,
                ),
                "summary_ready": True,
                "poster_event_summary": True,
                "telegram_debug_send_photo": bool(
                    self._read_run_media_paths(run)
                ),
                "telegram_debug_media_paths": self._read_run_media_paths(run),
                "media_paths": self._read_run_media_paths(run),
                "telegram_debug_photo_path": self._read_first_run_media_path(run),
            },
        )

    def _build_step_metadata(
        self,
        run: AgentRun,
        step: AgentStep,
        total: int,
    ) -> dict[str, Any]:
        metadata = {
            **self._build_run_metadata(run),
            **self._build_minimal_metadata(
                step_type=step.step_type.value,
                skip_pin=True,
            ),
            "step_index": step.index,
            "step_total": total,
        }

        tool_name = self._read_step_tool_name(step)

        if tool_name:
            metadata["tool_name"] = tool_name

        tool_call = self._tool_call_to_dict(step.tool_call)

        if tool_call:
            metadata["tool_call"] = tool_call

        tool_result = self._tool_result_to_dict(step.tool_result)

        if tool_result:
            metadata["tool_result"] = tool_result

        content = step.content.strip()

        if content:
            metadata["step_content"] = self._short_text(content, limit=500)

        step_media_paths = self._read_step_media_paths(step)

        if (
            not step_media_paths
            and step.step_type in {AgentStepType.TOOL_CALL, AgentStepType.TOOL_RESULT}
        ):
            step_media_paths = self._read_run_media_paths(run)

        if step_media_paths:
            metadata["telegram_debug_send_photo"] = True
            metadata["telegram_debug_send_media_as_document"] = (
                Path(step_media_paths[0]).suffix.lower()
                not in {".jpg", ".jpeg", ".png", ".webp"}
            )
            metadata["telegram_debug_media_paths"] = step_media_paths
            metadata["media_paths"] = step_media_paths
            metadata["telegram_debug_photo_path"] = step_media_paths[0]

        if step.step_type == AgentStepType.FINAL:
            metadata["summary_ready"] = True

        return self._drop_empty(metadata)

    def _should_send_debug_media_file_for_step(
        self,
        run: AgentRun,
        step: AgentStep,
    ) -> bool:
        media_path = (
            run.metadata.get("telegram_debug_photo_path")
            or run.metadata.get("poster_path")
        )

        if not isinstance(media_path, str) or not media_path.strip():
            return False

        if step.step_type != AgentStepType.THINK:
            return False

        provider_name = self._read_provider_name(run)

        if provider_name != "groq_vision":
            return False

        content = getattr(step, "content", None)

        if isinstance(content, str) and "стартовый план" in content.lower():
            return True

        return step.index == 1


    def _read_run_media_paths(
        self,
        run: AgentRun,
    ) -> list[str]:
        result: list[str] = []

        for key in [
            "poster_agent_media_paths",
            "poster_media_paths",
            "telegram_debug_media_paths",
            "media_paths",
            "photo_paths",
            "image_paths",
        ]:
            self._collect_existing_file_paths(result, run.metadata.get(key))

        for key in [
            "telegram_debug_photo_path",
            "poster_path",
            "photo_path",
            "image_path",
            "media_path",
        ]:
            self._collect_existing_file_paths(result, run.metadata.get(key))

        return self._unique_paths(result)

    def _read_first_run_media_path(
        self,
        run: AgentRun,
    ) -> str | None:
        media_paths = self._read_run_media_paths(run)

        if not media_paths:
            return None

        return media_paths[0]

    def _read_step_media_paths(
        self,
        step: AgentStep,
    ) -> list[str]:
        if step.step_type not in {
            AgentStepType.TOOL_CALL,
            AgentStepType.TOOL_RESULT,
        }:
            return []

        result: list[str] = []

        self._collect_existing_file_paths(result, step.metadata)

        if step.tool_call is not None:
            self._collect_existing_file_paths(result, step.tool_call.arguments)

        if step.tool_result is not None:
            self._collect_existing_file_paths(result, step.tool_result.data)
            self._collect_existing_file_paths(result, step.tool_result.metadata)

        return self._unique_paths(result)

    def _collect_existing_file_paths(
        self,
        result: list[str],
        value: Any,
    ) -> None:
        if value is None:
            return

        if isinstance(value, str):
            self._append_existing_file_path(result, value)
            return

        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key).lower()

                if self._looks_like_file_path_key(key_text):
                    self._collect_existing_file_paths(result, item)
                    continue

                if isinstance(item, dict | list | tuple | set):
                    self._collect_existing_file_paths(result, item)

            return

        if isinstance(value, list | tuple | set):
            for item in value:
                self._collect_existing_file_paths(result, item)

    def _looks_like_file_path_key(
        self,
        key: str,
    ) -> bool:
        return any(
            marker in key
            for marker in [
                "path",
                "file",
                "media",
                "image",
                "photo",
                "poster",
                "attachment",
                "document",
            ]
        )

    def _append_existing_file_path(
        self,
        result: list[str],
        value: str,
    ) -> None:
        text = value.strip()

        if not text:
            return

        if text.startswith(("http://", "https://", "tg://")):
            return

        path = Path(text)

        if not path.exists() or not path.is_file():
            return

        result.append(text)

    def _unique_paths(
        self,
        paths: list[str],
    ) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for path in paths:
            normalized = str(Path(path))

            if normalized in seen:
                continue

            seen.add(normalized)
            result.append(path)

        return result

    def _debug_media_file_for_step(
        self,
        run: AgentRun,
        step: AgentStep,
    ) -> str | None:
        if step.step_type not in {AgentStepType.TOOL_CALL, AgentStepType.TOOL_RESULT}:
            return None

        step_media_path = self._debug_media_file_from_value(step.metadata)

        if step_media_path is not None:
            return step_media_path

        if step.tool_call is not None:
            step_media_path = self._debug_media_file_from_value(step.tool_call.arguments)

            if step_media_path is not None:
                return step_media_path

        if step.tool_result is not None:
            step_media_path = self._debug_media_file_from_value(step.tool_result.data)

            if step_media_path is not None:
                return step_media_path

            step_media_path = self._debug_media_file_from_value(step.tool_result.metadata)

            if step_media_path is not None:
                return step_media_path

        return self._debug_media_file_from_value(run.metadata)

    def _debug_media_file_from_value(
        self,
        value: Any,
    ) -> str | None:
        for media_path in self._iter_debug_media_files(value):
            return media_path

        return None

    def _iter_debug_media_files(
        self,
        value: Any,
    ):
        if value is None:
            return

        if isinstance(value, dict):
            for key in (
                "telegram_debug_photo_path",
                "poster_path",
                "poster_image_path",
                "photo_path",
                "image_path",
                "media_path",
                "file_path",
                "path",
            ):
                item = value.get(key)

                if isinstance(item, str) and self._is_existing_debug_media_file(item):
                    yield item.strip()

            for item in value.values():
                yield from self._iter_debug_media_files(item)

            return

        if isinstance(value, list | tuple | set):
            for item in value:
                yield from self._iter_debug_media_files(item)

            return

        for attr_name in (
            "path",
            "file_path",
            "photo_path",
            "image_path",
        ):
            item = getattr(value, attr_name, None)

            if isinstance(item, str) and self._is_existing_debug_media_file(item):
                yield item.strip()
                return

        if isinstance(value, str) and self._is_existing_debug_media_file(value):
            yield value.strip()

    def _is_existing_debug_media_file(
        self,
        value: str,
    ) -> bool:
        value = value.strip()

        if not value:
            return False

        if value.startswith(("http://", "https://", "data:")):
            return False

        if len(value) > 500:
            return False

        try:
            path = Path(value)
        except Exception:
            return False

        try:
            return path.is_file()
        except OSError:
            return False

    def _build_tool_media_caption(
        self,
        step: AgentStep,
        media_path: str,
    ) -> str:
        tool_name = self._read_step_tool_name(step) or "unknown"
        filename = Path(media_path).name

        if step.step_type == AgentStepType.TOOL_CALL:
            label = "Файл передан в инструмент"
        else:
            label = "Файл относится к результату инструмента"

        return f"{label}: {tool_name}\n{filename}"

    def _build_run_metadata(
        self,
        run: AgentRun,
    ) -> dict[str, Any]:
        return self._drop_empty(
            {
                "agent_run": True,
                "agent_status": run.status.value,
                "event_title": self._read_event_title(run),
                "event_date": self._read_event_date(run),
                "poster_agent_pipeline": (
                    run.metadata.get("poster_agent_pipeline") is True
                ),
                "poster_agent_draft_status": run.metadata.get(
                    "poster_agent_draft_status"
                ),
                "poster_agent_decision_status": run.metadata.get(
                    "poster_agent_decision_status"
                ),
                "poster_agent_can_publish": run.metadata.get(
                    "poster_agent_can_publish"
                ),
                "telegram_debug_photo_path": run.metadata.get(
                    "telegram_debug_photo_path"
                ),
                "poster_path": run.metadata.get("poster_path"),
                "evidence_count": len(run.evidence.items),
                "verified_evidence_count": len(run.evidence.verified_items()),
                "unverified_evidence_count": len(run.evidence.unverified_items()),
                "conflicted_evidence_count": len(run.evidence.conflicted_items()),
            }
        )

    def _build_minimal_metadata(
        self,
        step_type: str,
        skip_pin: bool,
    ) -> dict[str, Any]:
        return {
            "agent_step": True,
            "step_type": step_type,
            "status": "finished",
            "skip_pin": skip_pin,
        }

    def _build_step_text(
        self,
        run: AgentRun,
        step: AgentStep,
        total: int,
    ) -> str:
        title = self._build_step_title(
            step=step,
            total=total,
        )

        if step.step_type == AgentStepType.FINAL:
            visible_text = self._build_final_visible_text(
                run=run,
                step=step,
            )
        elif step.step_type == AgentStepType.TOOL_CALL:
            visible_text = self._build_tool_call_visible_text(step)
        elif step.step_type == AgentStepType.TOOL_RESULT:
            visible_text = self._build_tool_result_visible_text(step)
        else:
            visible_text = self._build_think_visible_text(step)

        full_info = self._build_full_info(
            run=run,
            step=step,
            total=total,
        )

        return "\n\n".join(
            part
            for part in [
                title,
                visible_text.strip(),
                self._build_full_info_block(full_info),
            ]
            if part.strip()
        )

    def _build_standalone_final_text(
        self,
        run: AgentRun,
    ) -> str:
        if run.final_result is not None and run.final_result.text.strip():
            visible_text = self._strip_markdown_fence(run.final_result.text)
        else:
            visible_text = "Финальный результат агента получен."

        full_info = {
            "run": self._build_run_info(run),
            "final": self._build_compact_final_info(run),
        }

        return "\n\n".join(
            part
            for part in [
                "FINAL",
                self._prepare_visible_text(visible_text),
                self._build_full_info_block(full_info),
            ]
            if part.strip()
        )

    def _build_step_title(
        self,
        step: AgentStep,
        total: int,
    ) -> str:
        if step.step_type in {AgentStepType.TOOL_CALL, AgentStepType.TOOL_RESULT}:
            tool_name = self._read_step_tool_name(step)

            if tool_name:
                return f"TOOL #{step.index}/{total}: {tool_name}"

            return f"TOOL #{step.index}/{total}"

        return f"{step.step_type.value.upper()} #{step.index}/{total}"

    def _build_think_visible_text(
        self,
        step: AgentStep,
    ) -> str:
        content = step.content.strip() or "Внутренний шаг анализа."

        return "\n".join(
            [
                "Кратко:",
                self._short_text(content, limit=900),
                "",
                "Итог:",
                "ℹ️ Агент обновил внутреннее состояние выполнения.",
            ]
        )

    def _build_tool_call_visible_text(
        self,
        step: AgentStep,
    ) -> str:
        tool_name = self._read_step_tool_name(step) or "unknown"
        reason = self._read_metadata_string(step.metadata, "reason")

        lines = [
            "Кратко:",
            f"Запланировал вызов инструмента {tool_name}.",
        ]

        if reason:
            lines.append(f"Причина: {reason}")

        lines.extend(
            [
                "",
                "Итог:",
                "⏳ Ожидаю результат инструмента.",
            ]
        )

        return "\n".join(lines)

    def _build_tool_result_visible_text(
        self,
        step: AgentStep,
    ) -> str:
        tool_result = step.tool_result
        tool_name = self._read_step_tool_name(step) or "unknown"

        if tool_result is None:
            return "\n".join(
                [
                    "Кратко:",
                    self._short_text(
                        step.content or "Результат инструмента получен.",
                        limit=900,
                    ),
                    "",
                    "Итог:",
                    "⚠️ Подробный результат инструмента не приложен к шагу.",
                ]
            )

        if not tool_result.ok:
            return "\n".join(
                [
                    "Кратко:",
                    f"Инструмент {tool_name} завершился ошибкой.",
                    "",
                    "Итог:",
                    f"⚠️ {tool_result.error or 'Ошибка без текста.'}",
                ]
            )

        if self._looks_like_url_tool(tool_name):
            lines = self._build_url_tool_summary(tool_result)
        else:
            lines = [
                "Кратко:",
                f"Инструмент {tool_name} успешно вернул данные.",
            ]

            if self._looks_like_search_tool(tool_name):
                lines.append("Получены кандидаты для проверки.")
                lines.append("Данные ещё нужно подтвердить URL/БД/manual.")
            elif self._contains_key(tool_result.data, "evidence"):
                lines.append("Получены данные для evidence-проверки.")

        lines.extend(
            [
                "",
                "Итог:",
                self._build_tool_result_outcome(tool_result),
            ]
        )

        return "\n".join(lines)

    def _build_url_tool_summary(
        self,
        tool_result: AgentToolResult,
    ) -> list[str]:
        lines = ["Кратко:"]

        if self._looks_like_ticket_data(tool_result.data):
            lines.append("Проверил ссылку на билеты.")
        else:
            lines.append("Проверил ссылку через URL-инструмент.")

        if self._contains_any_key(
            tool_result.data,
            ["final_url", "redirects", "redirect_chain"],
        ):
            lines.append("Ссылка раскрылась.")

        if self._contains_any_key(
            tool_result.data,
            ["title", "description", "page_title", "text_preview"],
        ):
            lines.append("Страница прочитана, есть базовые данные.")

        found_parts = []

        if self._contains_any_key(
            tool_result.data,
            ["date", "event_date", "datetime", "start_date"],
        ):
            found_parts.append("дата")

        if self._contains_any_key(
            tool_result.data,
            ["venue", "venue_name", "place", "location"],
        ):
            found_parts.append("площадка")

        if self._contains_any_key(
            tool_result.data,
            ["price", "min_price", "cost"],
        ):
            found_parts.append("цена")

        if found_parts:
            lines.append("На странице найдены: " + ", ".join(found_parts) + ".")

        if self._contains_truthy_key(
            tool_result.data,
            "blocked_by_antibot",
        ):
            lines.append("Источник похож на заблокированный антиботом.")

        return lines

    def _build_final_visible_text(
        self,
        run: AgentRun,
        step: AgentStep,
    ) -> str:
        review_text = run.metadata.get("poster_agent_review_text")

        if isinstance(review_text, str) and review_text.strip():
            return self._prepare_visible_text(review_text)

        if run.final_result is not None and run.final_result.text.strip():
            return self._prepare_visible_text(run.final_result.text)

        if step.content.strip():
            return self._prepare_visible_text(step.content)

        return "Финальный ответ агента получен."

    def _build_tool_result_outcome(
        self,
        tool_result: AgentToolResult,
    ) -> str:
        if not tool_result.ok:
            return "⚠️ Инструмент не смог завершить проверку."

        if self._contains_truthy_key(tool_result.data, "verified"):
            return "✅ Данные выглядят подтверждёнными результатом инструмента."

        if self._contains_truthy_key(tool_result.data, "blocked_by_antibot"):
            return "⚠️ Прямое чтение источника ограничено антиботом."

        if self._contains_any_key(
            tool_result.data,
            [
                "final_url",
                "title",
                "description",
                "text_preview",
                "date",
                "event_date",
                "venue",
            ],
        ):
            return "⚠️ Данные получены, но их ещё должен оценить verifier-agent."

        return "ℹ️ Инструмент вернул технический результат для дальнейшей обработки."

    def _build_full_info_block(
        self,
        value: Any,
    ) -> str:
        compact_value = self._drop_empty(self._to_jsonable(value))
        text = self._format_as_bullets(compact_value)

        if not text.strip():
            return ""

        return "\n".join(
            [
                "Полная информация:",
                "",
                text,
            ]
        )

    def _build_full_info(
        self,
        run: AgentRun,
        step: AgentStep,
        total: int,
    ) -> dict[str, Any]:
        if step.step_type == AgentStepType.FINAL:
            return self._drop_empty(
                {
                    "run": self._build_run_info(run),
                    "step": self._build_compact_step_info(
                        step=step,
                        total=total,
                    ),
                    "final": self._build_compact_final_info(run),
                }
            )

        return self._drop_empty(
            {
                "run": self._build_run_info(run),
                "step": self._build_full_step_info(
                    step=step,
                    total=total,
                ),
            }
        )

    def _build_full_step_info(
        self,
        step: AgentStep,
        total: int,
    ) -> dict[str, Any]:
        return self._drop_empty(
            {
                "index": step.index,
                "total": total,
                "type": step.step_type.value,
                "content": self._short_text(step.content, limit=1200),
                "metadata": self._compact_step_metadata(step.metadata),
                "tool_call": self._tool_call_to_dict(step.tool_call),
                "tool_result": self._tool_result_to_dict(step.tool_result),
            }
        )

    def _build_compact_step_info(
        self,
        step: AgentStep,
        total: int,
    ) -> dict[str, Any]:
        return self._drop_empty(
            {
                "index": step.index,
                "total": total,
                "type": step.step_type.value,
                "metadata": self._compact_step_metadata(step.metadata),
                "tool_call": self._tool_call_to_dict(step.tool_call),
                "tool_result": self._tool_result_to_dict(step.tool_result),
            }
        )

    def _compact_step_metadata(
        self,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        keep_keys = [
            "provider_name",
            "tool_name",
            "reason",
            "action",
            "adaptive_step_count",
            "tool_result_count",
            "media_count",
            "evidence_count",
            "verified_evidence_count",
            "unverified_evidence_count",
            "conflicted_evidence_count",
            "custom_final_prompt",
            "custom_final_prompt_builder",
            "final_response_format",
        ]

        for key in keep_keys:
            if key in metadata:
                result[key] = self._to_jsonable(metadata[key])

        response_metadata = metadata.get("response_metadata")

        if isinstance(response_metadata, dict):
            result["response_metadata"] = self._compact_response_metadata(
                response_metadata
            )

        return self._drop_empty(result)

    def _compact_response_metadata(
        self,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        keep_keys = [
            "provider",
            "model",
            "key_index",
            "key_count",
            "media_count",
            "usage",
            "finish_reason",
            "request_id",
            "session_id",
            "requested_provider",
            "fallback_allowed",
        ]

        return self._drop_empty(
            {
                key: self._to_jsonable(metadata[key])
                for key in keep_keys
                if key in metadata
            }
        )

    def _build_run_info(
        self,
        run: AgentRun,
    ) -> dict[str, Any]:
        return self._drop_empty(
            {
                "status": run.status.value,
                "session": run.session_id,
                "request": run.request_id,
                "provider": self._read_provider_name(run),
                "event": self._read_event_title(run),
                "date": self._read_event_date(run),
                "poster_pipeline": run.metadata.get("poster_agent_pipeline") is True,
                "draft_status": run.metadata.get("poster_agent_draft_status"),
                "decision_status": run.metadata.get("poster_agent_decision_status"),
                "can_publish": run.metadata.get("poster_agent_can_publish"),
                "evidence": {
                    "total": len(run.evidence.items),
                    "verified": len(run.evidence.verified_items()),
                    "unverified": len(run.evidence.unverified_items()),
                    "conflicted": len(run.evidence.conflicted_items()),
                },
            }
        )

    def _build_compact_final_info(
        self,
        run: AgentRun,
    ) -> dict[str, Any] | None:
        if run.final_result is None:
            return None

        verification = self._read_verification_data(
            run.final_result.structured_data
        )

        return self._drop_empty(
            {
                "summary": self._build_final_summary_info(run),
                "metadata": self._compact_final_metadata(
                    run.final_result.metadata
                ),
                "verification": (
                    self._compact_final_verification_summary(verification)
                    if verification is not None
                    else None
                ),
            }
        )

    def _build_final_summary_info(
        self,
        run: AgentRun,
    ) -> dict[str, Any]:
        return self._drop_empty(
            {
                "event": self._read_event_title(run),
                "date": self._read_event_date(run),
                "draft_status": run.metadata.get("poster_agent_draft_status"),
                "decision_status": run.metadata.get(
                    "poster_agent_decision_status"
                ),
                "can_publish": run.metadata.get("poster_agent_can_publish"),
                "verified_occurrences": run.metadata.get(
                    "verified_occurrence_count"
                ),
                "verified_ticket_links": run.metadata.get(
                    "verified_ticket_link_count"
                ),
                "verified_official_links": run.metadata.get(
                    "verified_official_link_count"
                ),
                "unverified_ticket_links": run.metadata.get(
                    "unverified_ticket_link_count"
                ),
            }
        )

    def _compact_final_verification_summary(
        self,
        value: Any,
    ) -> dict[str, Any]:
        data = self._to_jsonable(value)

        if not isinstance(data, dict):
            return {"value": self._short_unknown_value(data)}

        links = data.get("links")
        if not isinstance(links, list):
            links = []

        occurrences = data.get("occurrences")
        if not isinstance(occurrences, list):
            occurrences = []

        warnings = data.get("warnings")
        if not isinstance(warnings, list):
            warnings = []

        conflicts = data.get("conflicts")
        if not isinstance(conflicts, list):
            conflicts = []

        missing_fields = data.get("missing_fields")
        if not isinstance(missing_fields, list):
            missing_fields = []

        return self._drop_empty(
            {
                "title": data.get("title"),
                "event_type": data.get("event_type"),
                "artists": data.get("artists"),
                "recommendation": data.get("recommendation"),
                "overall_confidence": data.get("overall_confidence"),
                "occurrences": len(occurrences),
                "verified_occurrences": self._count_verified_items(
                    occurrences
                ),
                "links": len(links),
                "verified_ticket_links": self._count_links(
                    links=links,
                    kind="ticket",
                    verified=True,
                ),
                "unverified_ticket_links": self._count_links(
                    links=links,
                    kind="ticket",
                    verified=False,
                ),
                "verified_official_links": self._count_links(
                    links=links,
                    kind="official",
                    verified=True,
                ),
                "missing_fields": missing_fields,
                "warning_count": len(warnings),
                "conflict_count": len(conflicts),
                "explanation": data.get("explanation"),
            }
        )

    def _count_verified_items(
        self,
        items: list[Any],
    ) -> int:
        result = 0

        for item in items:
            if isinstance(item, dict) and item.get("verified") is True:
                result += 1

        return result

    def _count_links(
        self,
        links: list[Any],
        kind: str,
        verified: bool,
    ) -> int:
        result = 0

        for link in links:
            if not isinstance(link, dict):
                continue

            link_kind = str(link.get("kind") or "").strip().lower()

            if link_kind != kind:
                continue

            if bool(link.get("verified")) is not verified:
                continue

            result += 1

        return result

    def _compact_final_metadata(
        self,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        keep_keys = [
            "provider_name",
            "request_id",
            "session_id",
            "poster_verification_sanitized",
        ]

        result = {
            key: self._to_jsonable(metadata[key])
            for key in keep_keys
            if key in metadata
        }

        response_metadata = metadata.get("response_metadata")

        if isinstance(response_metadata, dict):
            result["response_metadata"] = self._compact_response_metadata(
                response_metadata
            )

        return self._drop_empty(result)

    def _compact_verification(
        self,
        value: Any,
    ) -> Any:
        data = self._to_jsonable(value)

        if not isinstance(data, dict):
            return data

        result: dict[str, Any] = {}

        for key in [
            "title",
            "event_type",
            "artists",
            "organizers",
            "age_limit",
            "description",
            "overall_confidence",
            "recommendation",
            "explanation",
        ]:
            if key in data:
                result[key] = data[key]

        occurrences = data.get("occurrences")

        if isinstance(occurrences, list):
            result["occurrences"] = [
                self._compact_occurrence(item)
                for item in occurrences
                if isinstance(item, dict)
            ]

        links = data.get("links")

        if isinstance(links, list):
            result["links"] = [
                self._compact_link(item)
                for item in links
                if isinstance(item, dict)
            ]

        facts = data.get("facts")

        if isinstance(facts, list):
            result["facts"] = [
                self._compact_fact(item)
                for item in facts
                if isinstance(item, dict)
            ]

        warnings = data.get("warnings")

        if isinstance(warnings, list):
            result["warnings"] = warnings

        conflicts = data.get("conflicts")

        if isinstance(conflicts, list):
            result["conflicts"] = conflicts

        missing_fields = data.get("missing_fields")

        if isinstance(missing_fields, list):
            result["missing_fields"] = missing_fields

        return self._drop_empty(result)

    def _compact_occurrence(
        self,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        return self._drop_empty(
            {
                "date": value.get("event_date") or value.get("date"),
                "city": value.get("city_name") or value.get("city"),
                "venue": value.get("venue_name") or value.get("venue"),
                "address": value.get("address"),
                "start_time": value.get("start_time"),
                "doors_time": value.get("doors_time"),
                "verified": value.get("verified"),
                "confidence": value.get("confidence"),
                "source_url": value.get("source_url"),
                "explanation": value.get("explanation"),
            }
        )

    def _compact_link(
        self,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        return self._drop_empty(
            {
                "kind": value.get("kind") or value.get("link_type"),
                "url": value.get("url"),
                "title": value.get("title"),
                "verified": value.get("verified"),
                "confidence": value.get("confidence"),
                "source_type": value.get("source_type") or value.get("source"),
                "explanation": value.get("explanation"),
            }
        )

    def _compact_fact(
        self,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        return self._drop_empty(
            {
                "field": value.get("field"),
                "value": value.get("value"),
                "status": value.get("status"),
                "source_type": value.get("source_type"),
                "confidence": value.get("confidence"),
                "source_url": value.get("source_url"),
                "source_title": value.get("source_title"),
                "explanation": value.get("explanation"),
            }
        )

    def _read_verification_data(
        self,
        structured_data: dict[str, Any],
    ) -> Any:
        if not isinstance(structured_data, dict):
            return None

        value = structured_data.get("poster_verification_result")

        if value is not None:
            return value

        value = structured_data.get("poster_verification")

        if value is not None:
            return value

        return None

    def _read_tool_results(
        self,
        structured_data: dict[str, Any],
    ) -> list[Any]:
        if not isinstance(structured_data, dict):
            return []

        value = structured_data.get("tool_results")

        if not isinstance(value, list):
            return []

        result: list[Any] = []

        for item in value:
            compact_item = self._compact_tool_output_data(item)

            if compact_item:
                result.append(compact_item)

        return result

    def _compact_tool_output_data(
        self,
        value: Any,
    ) -> Any:
        data = self._to_jsonable(value)

        if not isinstance(data, dict):
            return self._short_unknown_value(data)

        return self._drop_empty(
            {
                "tool_name": data.get("tool_name"),
                "ok": data.get("ok"),
                "error": data.get("error"),
                "data": self._compact_tool_data(
                    tool_name=str(data.get("tool_name") or ""),
                    data=data.get("data"),
                ),
                "metadata": self._compact_tool_metadata(data.get("metadata")),
            }
        )

    def _compact_tool_metadata(
        self,
        value: Any,
    ) -> Any:
        if not isinstance(value, dict):
            return None

        keep_keys = [
            "url_count",
            "successful_count",
            "blocked_by_antibot_count",
            "response_status",
        ]

        result = {
            key: self._to_jsonable(value[key])
            for key in keep_keys
            if key in value
        }

        response_metadata = value.get("response_metadata")

        if isinstance(response_metadata, dict):
            result["response_metadata"] = self._compact_response_metadata(
                response_metadata
            )

        return self._drop_empty(result)

    def _compact_tool_data(
        self,
        tool_name: str,
        data: Any,
    ) -> Any:
        if self._looks_like_url_tool(tool_name):
            return self._compact_url_tool_data(data)

        if self._looks_like_search_tool(tool_name):
            return self._compact_search_tool_data(data)

        return self._compact_unknown_tool_data(data)

    def _compact_url_tool_data(
        self,
        data: Any,
    ) -> Any:
        value = self._to_jsonable(data)

        if not isinstance(value, dict):
            return self._short_unknown_value(value)

        pages = value.get("pages")

        if isinstance(pages, list):
            return self._drop_empty(
                {
                    "pages": [
                        self._compact_url_page(page)
                        for page in pages[:8]
                        if isinstance(page, dict)
                    ],
                }
            )

        return self._compact_unknown_tool_data(value)

    def _compact_url_page(
        self,
        page: dict[str, Any],
    ) -> dict[str, Any]:
        return self._drop_empty(
            {
                "url": page.get("url"),
                "ok": page.get("ok"),
                "status_code": page.get("status_code"),
                "blocked_by_antibot": page.get("blocked_by_antibot"),
                "final_url": page.get("final_url"),
                "content_type": page.get("content_type"),
                "title": page.get("title") or page.get("page_title"),
                "description": self._short_optional_text(
                    page.get("description"),
                    limit=350,
                ),
                "text_preview": self._short_optional_text(
                    page.get("text_preview"),
                    limit=900,
                ),
                "error": page.get("error"),
            }
        )

    def _compact_search_tool_data(
        self,
        data: Any,
    ) -> Any:
        value = self._to_jsonable(data)

        if not isinstance(value, dict):
            return self._short_unknown_value(value)

        text = value.get("text")
        result: dict[str, Any] = {
            "provider_name": value.get("provider_name"),
            "request_id": value.get("request_id"),
        }

        if isinstance(text, str) and text.strip():
            result["text_preview"] = self._short_text(
                self._format_markdown_tables_for_telegram(text),
                limit=1800,
            )

        return self._drop_empty(result)

    def _compact_unknown_tool_data(
        self,
        data: Any,
    ) -> Any:
        value = self._to_jsonable(data)

        if isinstance(value, dict):
            return self._drop_empty(
                self._limit_mapping(
                    value=value,
                    depth=0,
                    max_depth=3,
                    max_items=18,
                )
            )

        if isinstance(value, list):
            return [
                self._limit_mapping(
                    value=item,
                    depth=0,
                    max_depth=3,
                    max_items=12,
                )
                for item in value[:12]
            ]

        return self._short_unknown_value(value)

    def _limit_mapping(
        self,
        value: Any,
        depth: int,
        max_depth: int,
        max_items: int,
    ) -> Any:
        if depth >= max_depth:
            return self._short_unknown_value(value)

        if isinstance(value, dict):
            result: dict[str, Any] = {}

            for index, (key, item) in enumerate(value.items()):
                if index >= max_items:
                    result["more"] = "..."
                    break

                if self._is_empty_value(item):
                    continue

                result[str(key)] = self._limit_mapping(
                    value=item,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_items=max_items,
                )

            return self._drop_empty(result)

        if isinstance(value, list):
            return [
                self._limit_mapping(
                    value=item,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_items=max_items,
                )
                for item in value[:max_items]
                if not self._is_empty_value(item)
            ]

        return self._short_unknown_value(value)

    def _short_unknown_value(
        self,
        value: Any,
    ) -> Any:
        if isinstance(value, str):
            return self._short_text(value, limit=500)

        return value

    def _map_kind(
        self,
        step_type: AgentStepType,
    ) -> TelegramDebugMessageKind:
        if step_type == AgentStepType.TOOL_CALL:
            return TelegramDebugMessageKind.TOOL_CALL

        if step_type == AgentStepType.TOOL_RESULT:
            return TelegramDebugMessageKind.TOOL_RESULT

        return TelegramDebugMessageKind.INFO

    def _read_step_tool_name(
        self,
        step: AgentStep,
    ) -> str | None:
        if step.tool_call is not None and step.tool_call.tool_name.strip():
            return step.tool_call.tool_name.strip()

        if step.tool_result is not None and step.tool_result.tool_name.strip():
            return step.tool_result.tool_name.strip()

        return self._read_metadata_string(step.metadata, "tool_name")

    def _tool_call_to_dict(
        self,
        tool_call: AgentToolCall | None,
    ) -> dict[str, Any] | None:
        if tool_call is None:
            return None

        return self._drop_empty(
            {
                "tool_name": tool_call.tool_name,
                "arguments": self._to_jsonable(tool_call.arguments),
            }
        )

    def _tool_result_to_dict(
        self,
        tool_result: AgentToolResult | None,
    ) -> dict[str, Any] | None:
        if tool_result is None:
            return None

        return self._drop_empty(
            {
                "tool_name": tool_result.tool_name,
                "ok": tool_result.ok,
                "error": tool_result.error,
                "data": self._compact_tool_data(
                    tool_name=tool_result.tool_name,
                    data=tool_result.data,
                ),
                "metadata": self._compact_tool_metadata(tool_result.metadata),
            }
        )

    def _read_provider_name(
        self,
        run: AgentRun,
    ) -> str | None:
        value = run.metadata.get("provider_name")

        if isinstance(value, str) and value.strip():
            return value.strip()

        return None

    def _read_event_title(
        self,
        run: AgentRun,
    ) -> str | None:
        return self._read_metadata_string(run.metadata, "event_title")

    def _read_event_date(
        self,
        run: AgentRun,
    ) -> str | None:
        return self._read_metadata_string(run.metadata, "event_date")

    def _read_event_summary_text(
        self,
        run: AgentRun,
    ) -> str | None:
        for key in [
            "poster_agent_event_summary_text",
            "event_summary_text",
            "poster_event_summary_text",
        ]:
            value = run.metadata.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

        if run.final_result is None:
            return None

        structured_data = run.final_result.structured_data

        if not isinstance(structured_data, dict):
            return None

        for key in [
            "event_summary_text",
            "poster_agent_event_summary_text",
            "poster_event_summary_text",
        ]:
            value = structured_data.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

        return None

    def _read_metadata_string(
        self,
        metadata: dict[str, Any],
        key: str,
    ) -> str | None:
        value = metadata.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

        return None

    def _looks_like_url_tool(
        self,
        tool_name: str,
    ) -> bool:
        normalized = tool_name.strip().lower()

        return "url" in normalized or "link" in normalized or "reader" in normalized

    def _looks_like_search_tool(
        self,
        tool_name: str,
    ) -> bool:
        normalized = tool_name.strip().lower()

        return "search" in normalized or "поиск" in normalized

    def _looks_like_ticket_data(
        self,
        value: Any,
    ) -> bool:
        for found_key, found_value in self._walk_key_values(value):
            key = found_key.lower()

            if "ticket" in key or "билет" in key:
                return True

            if isinstance(found_value, str):
                text = found_value.lower()

                if "ticket" in text or "билет" in text:
                    return True

        return False

    def _contains_truthy_key(
        self,
        value: Any,
        key: str,
    ) -> bool:
        for found_key, found_value in self._walk_key_values(value):
            if found_key.lower() != key.lower():
                continue

            if isinstance(found_value, bool):
                return found_value

            if isinstance(found_value, str):
                return found_value.strip().lower() in {"true", "yes", "1", "да"}

            if isinstance(found_value, int | float):
                return found_value > 0

            return found_value is not None

        return False

    def _contains_any_key(
        self,
        value: Any,
        keys: list[str],
    ) -> bool:
        normalized = {key.lower() for key in keys}

        return any(
            found_key.lower() in normalized
            for found_key, _ in self._walk_key_values(value)
        )

    def _contains_key(
        self,
        value: Any,
        key: str,
    ) -> bool:
        return self._contains_any_key(value, [key])

    def _walk_key_values(
        self,
        value: Any,
    ) -> list[tuple[str, Any]]:
        result: list[tuple[str, Any]] = []
        self._collect_key_values(value, result, depth=0)
        return result

    def _collect_key_values(
        self,
        value: Any,
        result: list[tuple[str, Any]],
        depth: int,
    ) -> None:
        if depth > 8:
            return

        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                result.append((key_text, item))
                self._collect_key_values(item, result, depth + 1)

            return

        if isinstance(value, list | tuple):
            for item in value:
                self._collect_key_values(item, result, depth + 1)

    def _prepare_visible_text(
        self,
        text: str,
    ) -> str:
        return self._format_markdown_tables_for_telegram(
            self._strip_markdown_fence(text).strip()
        )

    def _format_markdown_tables_for_telegram(
        self,
        text: str,
    ) -> str:
        lines = text.splitlines()
        result: list[str] = []
        index = 0

        while index < len(lines):
            if self._is_markdown_table_start(lines, index):
                table_lines = [lines[index], lines[index + 1]]
                index += 2

                while index < len(lines) and self._looks_like_table_row(lines[index]):
                    table_lines.append(lines[index])
                    index += 1

                table_text = "\n".join(table_lines)

                result.append(
                    "<code>"
                    + html.escape(table_text, quote=False)
                    + "</code>"
                )

                continue

            result.append(lines[index])
            index += 1

        return "\n".join(result)

    def _is_markdown_table_start(
        self,
        lines: list[str],
        index: int,
    ) -> bool:
        if index + 1 >= len(lines):
            return False

        return (
            self._looks_like_table_row(lines[index])
            and self._looks_like_table_separator(lines[index + 1])
        )

    def _looks_like_table_row(
        self,
        line: str,
    ) -> bool:
        stripped = line.strip()

        return stripped.startswith("|") and stripped.endswith("|") and "|" in stripped[1:-1]

    def _looks_like_table_separator(
        self,
        line: str,
    ) -> bool:
        stripped = line.strip()

        if not self._looks_like_table_row(stripped):
            return False

        normalized = stripped.replace("|", "").replace(":", "").replace("-", "").strip()

        return normalized == ""

    def _short_optional_text(
        self,
        value: Any,
        limit: int,
    ) -> str | None:
        if not isinstance(value, str):
            return None

        if not value.strip():
            return None

        return self._short_text(value, limit=limit)

    def _short_text(
        self,
        text: str,
        limit: int,
    ) -> str:
        value = self._strip_markdown_fence(text).strip()

        if len(value) <= limit:
            return value

        return value[: max(0, limit - 4)].rstrip() + "..."

    def _strip_markdown_fence(
        self,
        text: str,
    ) -> str:
        value = text.strip()

        if not value.startswith("```"):
            return text

        lines = value.splitlines()

        if len(lines) < 2:
            return text

        first = lines[0].strip()
        last = lines[-1].strip()

        if not first.startswith("```"):
            return text

        if last != "```":
            return text

        return "\n".join(lines[1:-1]).strip()

    def _format_as_bullets(
        self,
        value: Any,
        indent: int = 0,
    ) -> str:
        value = self._drop_empty(value)

        if self._is_empty_value(value):
            return ""

        lines: list[str] = []
        prefix = "  " * indent

        if isinstance(value, dict):
            for key, item in value.items():
                if self._is_empty_value(item):
                    continue

                label = str(key)

                if self._is_scalar(item):
                    lines.append(f"{prefix}• {label}: {self._format_scalar(item)}")
                    continue

                lines.append(f"{prefix}• {label}:")
                nested = self._format_as_bullets(item, indent=indent + 1)

                if nested:
                    lines.append(nested)

            return "\n".join(lines)

        if isinstance(value, list):
            for index, item in enumerate(value, start=1):
                if self._is_empty_value(item):
                    continue

                if self._is_scalar(item):
                    lines.append(f"{prefix}• {self._format_scalar(item)}")
                    continue

                lines.append(f"{prefix}• item {index}:")
                nested = self._format_as_bullets(item, indent=indent + 1)

                if nested:
                    lines.append(nested)

            return "\n".join(lines)

        return f"{prefix}• {self._format_scalar(value)}"

    def _format_scalar(
        self,
        value: Any,
    ) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"

        if isinstance(value, str):
            return self._short_text(value, limit=1800)

        return str(value)

    def _is_scalar(
        self,
        value: Any,
    ) -> bool:
        return value is None or isinstance(value, str | int | float | bool)

    def _drop_empty(
        self,
        value: Any,
    ) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}

            for key, item in value.items():
                cleaned = self._drop_empty(item)

                if self._is_empty_value(cleaned):
                    continue

                result[key] = cleaned

            return result

        if isinstance(value, list):
            result_list = []

            for item in value:
                cleaned = self._drop_empty(item)

                if self._is_empty_value(cleaned):
                    continue

                result_list.append(cleaned)

            return result_list

        if isinstance(value, tuple):
            result_list = []

            for item in value:
                cleaned = self._drop_empty(item)

                if self._is_empty_value(cleaned):
                    continue

                result_list.append(cleaned)

            return result_list

        return value

    def _is_empty_value(
        self,
        value: Any,
    ) -> bool:
        if value is None:
            return True

        if isinstance(value, str):
            return not value.strip()

        if isinstance(value, list | tuple | dict | set):
            return len(value) == 0

        return False

    def _stable_json(
        self,
        value: Any,
    ) -> str:
        return json.dumps(
            self._to_jsonable(value),
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    def _to_jsonable(
        self,
        value: Any,
    ) -> Any:
        if value is None:
            return None

        if isinstance(value, str):
            return self._strip_markdown_fence(value)

        if isinstance(value, int | float | bool):
            return value

        if isinstance(value, list):
            return [
                self._to_jsonable(item)
                for item in value
            ]

        if isinstance(value, tuple):
            return [
                self._to_jsonable(item)
                for item in value
            ]

        if isinstance(value, dict):
            return {
                str(key): self._to_jsonable(item)
                for key, item in value.items()
            }

        if hasattr(value, "value"):
            return value.value

        return str(value)
    
    