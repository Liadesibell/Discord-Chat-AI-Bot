import asyncio
import json
from pathlib import Path

from ink_ai_discord.local_ai import LocalAIClient, MODEL_FILES, heuristic_route


class FakeEngine:
    def __init__(
        self,
        model_id: str,
        fail: bool = False,
        overflow_once: bool = False,
    ) -> None:
        self.model_id = model_id
        self.fail = fail
        self.overflow_once = overflow_once
        self.closed = False

    def create_chat_completion(self, *, messages, **_kwargs):
        if self.fail:
            raise RuntimeError("simulated model load/inference failure")
        if self.overflow_once:
            self.overflow_once = False
            raise ValueError("Requested tokens exceed context window")
        if self.model_id == "router":
            content = json.dumps({"model": "deepseek"})
        else:
            content = f"{self.model_id} answer"
        return {
            "choices": [
                {"message": {"content": content}},
            ],
        }

    def close(self) -> None:
        self.closed = True


def create_models_directory(tmp_path: Path) -> Path:
    models_directory = tmp_path / "models"
    models_directory.mkdir()
    for filename in MODEL_FILES.values():
        (models_directory / filename).write_bytes(b"gguf")
    return models_directory


def test_heuristic_router_sends_requests_to_matching_specialists():
    assert heuristic_route("Hesapla: karmaşık matematik denklemi") == "deepseek"
    assert heuristic_route("10x10 kaç eder?") == "deepseek"
    assert heuristic_route("Python kod hatasının kök nedenini bul") == "deepseek"
    assert heuristic_route("Bu büyük projeyi analiz et") == "deepseek"
    assert heuristic_route("Geçerli JSON şeması üret") == "gpt_oss"
    assert heuristic_route("Yeni API özelliği için kod yaz") == "qwen35b"
    assert heuristic_route("Bunu Türkçe özetle") == "gemma4"


def test_auto_router_uses_9b_classifier_then_selected_expert(tmp_path):
    models_directory = create_models_directory(tmp_path)
    created = []

    def engine_factory(model_path, **_kwargs):
        model_id = next(
            key for key, filename in MODEL_FILES.items() if Path(model_path).name == filename
        )
        created.append(model_id)
        return FakeEngine(model_id)

    client = LocalAIClient(models_directory, engine_factory)
    answer = asyncio.run(
        client.complete(
            [
                {"role": "system", "content": "Answer in Turkish."},
                {"role": "user", "content": "2 + 2 kaç eder?"},
            ],
            "auto",
        )
    )

    assert answer == "deepseek answer"
    assert created == ["router", "deepseek"]
    assert client.last_model == "deepseek"


def test_failed_specialist_falls_back_without_losing_following_requests(tmp_path):
    models_directory = create_models_directory(tmp_path)
    created = []

    def engine_factory(model_path, **_kwargs):
        model_id = next(
            key for key, filename in MODEL_FILES.items() if Path(model_path).name == filename
        )
        created.append(model_id)
        return FakeEngine(model_id, fail=model_id == "deepseek")

    client = LocalAIClient(models_directory, engine_factory)
    answer = asyncio.run(
        client.complete(
            [{"role": "user", "content": "Analyze this math problem."}],
            "deepseek",
        )
    )

    assert answer == "gemma4 answer"
    assert created == ["deepseek", "gemma4"]
    assert client.last_model == "gemma4"


def test_three_sequential_auto_requests_recover_and_release_each_engine(tmp_path):
    models_directory = create_models_directory(tmp_path)
    created = []

    def engine_factory(model_path, **_kwargs):
        model_id = next(
            key for key, filename in MODEL_FILES.items() if Path(model_path).name == filename
        )
        engine = FakeEngine(model_id)
        created.append(engine)
        return engine

    client = LocalAIClient(models_directory, engine_factory)

    async def ask_three_times():
        results = []
        for prompt in ("1 + 2?", "3 + 4?", "5 + 6?"):
            results.append(
                await client.complete(
                    [{"role": "user", "content": prompt}],
                    "auto",
                )
            )
        return results

    results = asyncio.run(ask_three_times())

    assert results == ["deepseek answer"] * 3
    assert len(created) == 6
    assert all(engine.closed for engine in created[:-1])
    client.close()
    assert all(engine.closed for engine in created)


def test_context_overflow_retries_with_shorter_history(tmp_path):
    models_directory = create_models_directory(tmp_path)
    created = []

    def engine_factory(model_path, **_kwargs):
        model_id = next(
            key for key, filename in MODEL_FILES.items() if Path(model_path).name == filename
        )
        engine = FakeEngine(model_id, overflow_once=True)
        created.append(engine)
        return engine

    client = LocalAIClient(models_directory, engine_factory)
    answer = asyncio.run(
        client.complete(
            [
                {"role": "system", "content": "Answer in Turkish."},
                {"role": "user", "content": "Earlier question"},
                {"role": "assistant", "content": "Earlier answer"},
                {"role": "user", "content": "Current question"},
            ],
            "gemma4",
        )
    )

    assert answer == "gemma4 answer"
    assert created[0].closed is False
