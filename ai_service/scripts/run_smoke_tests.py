import subprocess
import sys


TEST_MODULES = [
    "scripts.test_mock_provider",
    "scripts.test_analyze_content_result",
    "scripts.test_analysis_result_db_save",
    "scripts.test_analysis_result_cache",
    "scripts.test_ai_service_cache_events",
    "scripts.test_database_context_prompt",
    "scripts.test_database_context_events",
    "scripts.test_ai_service_generate_events",
    "scripts.test_ai_service_stream_events",
    "scripts.test_provider_config",
    "scripts.test_sql_plan_validator",
    "scripts.test_message_splitter",
    "scripts.test_provider_request_builder",
    "scripts.test_multipart_provider",
    "scripts.test_media_multipart_provider",
    "scripts.test_large_text_as_file",
    "scripts.test_provider_fallback",
    "scripts.test_provider_fallback_disabled",
    "scripts.test_provider_unavailable_fallback",
    "scripts.test_provider_exception_fallback",
    "scripts.test_provider_timeout_fallback",
    "scripts.test_provider_retry_success",
    "scripts.test_message_count_limit",
    "scripts.test_custom_content_registry",
    "scripts.test_registry_extension",
    "scripts.test_analysis_result_validator",
    "scripts.test_analysis_result_serializer",
    "scripts.test_analysis_cache_key_builder",
    "scripts.test_json_extraction_parser",
    "scripts.test_json_repair_flow",
    "scripts.test_evidence_parser",
    "scripts.test_stream_fallback_non_streaming",
    "scripts.test_stream_fallback_exception",
    "scripts.test_cache_and_db_stubs",
    "scripts.test_result_attachment_exporters",
    "scripts.test_result_auto_exporter",
    "scripts.test_ai_event_logger",
]


def run_module(module: str) -> bool:
    print("=" * 80)
    print(f"RUN: {module}")
    print("=" * 80)

    result = subprocess.run(
        [sys.executable, "-m", module],
        text=True,
    )

    if result.returncode != 0:
        print(f"FAILED: {module}")
        return False

    print(f"OK: {module}")
    return True


def main() -> None:
    failed: list[str] = []

    compile_result = subprocess.run(
        [sys.executable, "-m", "compileall", "app"],
        text=True,
    )

    if compile_result.returncode != 0:
        failed.append("compileall app")

    for module in TEST_MODULES:
        if not run_module(module):
            failed.append(module)

    print("=" * 80)

    if failed:
        print("FAILED TESTS:")
        for item in failed:
            print(f"- {item}")
        raise SystemExit(1)

    print("ALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
    
