from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIRECTORY = PROJECT_ROOT / "models"
HF_CACHE_DIRECTORY = MODEL_DIRECTORY / ".hf-cache"
os.environ["HF_HOME"] = str(HF_CACHE_DIRECTORY)
os.environ["HF_HUB_CACHE"] = str(HF_CACHE_DIRECTORY / "hub")
os.environ["HF_XET_CACHE"] = str(HF_CACHE_DIRECTORY / "xet")

MODEL_DOWNLOADS = (
    (
        "router",
        "unsloth/Qwen3.5-9B-GGUF",
        "Qwen3.5-9B-Q4_K_M.gguf",
        5_680_522_464,
    ),
    (
        "deepseek",
        "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF",
        "DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf",
        8_988_110_240,
    ),
    (
        "qwen35b",
        "unsloth/Qwen3.5-35B-A3B-GGUF",
        "Qwen3.5-35B-A3B-Q4_K_M.gguf",
        22_016_023_168,
    ),
    (
        "gpt_oss",
        "unsloth/gpt-oss-20b-GGUF",
        "gpt-oss-20b-Q4_K_M.gguf",
        11_624_759_488,
    ),
    (
        "gemma4",
        "unsloth/gemma-4-E4B-it-GGUF",
        "gemma-4-E4B-it-Q4_K_M.gguf",
        4_977_171_584,
    ),
)


def main() -> None:
    from huggingface_hub import hf_hub_download

    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for role, repository, filename, expected_size in MODEL_DOWNLOADS:
        destination = MODEL_DIRECTORY / filename
        if destination.is_file() and destination.stat().st_size == expected_size:
            print(f"{role}: model zaten doğrulanmış durumda: {destination}")
            continue

        print(f"{role}: {repository}/{filename} indiriliyor: {destination}")
        downloaded = Path(
            hf_hub_download(
                repo_id=repository,
                filename=filename,
                local_dir=str(MODEL_DIRECTORY),
            )
        )
        if downloaded.resolve() != destination.resolve():
            downloaded.replace(destination)
        if not destination.is_file() or destination.stat().st_size != expected_size:
            raise RuntimeError(
                f"{role} model dosyası boyut doğrulamasından geçemedi: "
                f"{destination}"
            )
        print(f"{role}: model doğrulandı ({destination.stat().st_size:,} bayt).")


if __name__ == "__main__":
    main()
