import pytest

from reminder_agent.config import ConfigurationError, Settings


def test_configuration_defaults_match_approved_local_runtime() -> None:
    settings = Settings.from_env({})
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ollama_model == "qwen3.5:9b"
    assert settings.ollama_timeout == 120
    assert settings.model_temperature == 0.2
    assert settings.model_top_p == 0.9
    assert settings.model_context_length == 4096
    assert settings.endpoint_mode == "loopback"


def test_configuration_values_are_overridable() -> None:
    settings = Settings.from_env(
        {
            "OLLAMA_MODEL": "local-model:latest",
            "OLLAMA_TIMEOUT": "45",
            "MODEL_TEMPERATURE": "0.5",
            "MODEL_TOP_P": "0.8",
            "MODEL_CONTEXT_LENGTH": "2048",
        }
    )
    assert settings.ollama_model == "local-model:latest"
    assert settings.ollama_timeout == 45
    assert settings.model_temperature == 0.5
    assert settings.model_top_p == 0.8
    assert settings.model_context_length == 2048


@pytest.mark.parametrize(
    "environment",
    [
        {"OLLAMA_TIMEOUT": "0"},
        {"MODEL_TEMPERATURE": "-0.1"},
        {"MODEL_TOP_P": "1.1"},
        {"MODEL_CONTEXT_LENGTH": "0"},
        {"OLLAMA_MODEL": "qwen3.5:9b-cloud"},
        {"OLLAMA_BASE_URL": "http://127.0.0.1:not-a-port"},
    ],
)
def test_invalid_or_cloud_configuration_is_rejected(environment) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_env(environment)


def test_non_loopback_endpoint_is_explicitly_identified() -> None:
    settings = Settings.from_env(
        {"OLLAMA_BASE_URL": "http://192.168.1.10:11434"}
    )
    assert settings.endpoint_mode == "non_loopback"
