#!/usr/bin/env python3
"""Run the repository's loopback Qwen vLLM deployment.

Arguments not listed below are forwarded verbatim to the vLLM API server so the
systemd unit can add engine flags without touching this launcher.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from _bootstrap import add_repo_src

REPO_ROOT = add_repo_src(__file__)

from autotrade.environment.llm import LOCAL_QWEN_MODEL, load_env_value, model_profile

DEFAULT_MODEL_PATH = Path("/Data/public/Qwen3.8-27B")
DEFAULT_PORT = 8010
DEFAULT_TENSOR_PARALLEL_SIZE = 2
DEFAULT_CONTEXT_LENGTH = model_profile(LOCAL_QWEN_MODEL).context_window_tokens
assert DEFAULT_CONTEXT_LENGTH is not None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--tensor-parallel-size",
        type=int,
        default=DEFAULT_TENSOR_PARALLEL_SIZE,
    )
    parser.add_argument("--max-model-len", type=int, default=DEFAULT_CONTEXT_LENGTH)
    parser.add_argument("--tool-call-parser", default="qwen3_coder")
    parser.add_argument(
        "--quantization",
        default=None,
        help="Optional weight quantization, e.g. 'fp8' for online W8A8. "
        "Default keeps the checkpoint dtype (bfloat16).",
    )
    parser.add_argument(
        "--reasoning-parser",
        default="qwen3",
        help="Qwen reasoning parser; override only for a verified vLLM release.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args, vllm_extra_args = build_parser().parse_known_args(argv)
    model_path = args.model_path.resolve(strict=True)
    if not model_path.is_dir():
        raise ValueError("--model-path must be a model directory")
    if not 1 <= args.port <= 65_535:
        raise ValueError("--port must be between 1 and 65535")
    if args.tensor_parallel_size <= 0:
        raise ValueError("tensor parallel size must be positive")
    if args.max_model_len < DEFAULT_CONTEXT_LENGTH:
        raise ValueError(
            f"--max-model-len must be at least {DEFAULT_CONTEXT_LENGTH} "
            "to preserve the configured local model profile"
        )
    # vLLM authenticates every /v1 request, local callers included, against the
    # same VLLM_API_KEY the gateway and the repository client use.
    api_key = load_env_value("VLLM_API_KEY", args.env_file)
    if not api_key:
        raise ValueError(
            f"VLLM_API_KEY is required in the environment or {args.env_file}"
        )
    os.environ["VLLM_API_KEY"] = api_key
    for name in ("HF_TOKEN", "HF_ENDPOINT"):
        value = load_env_value(name, args.env_file)
        if value:
            os.environ.setdefault(name, value)

    # Starting inference is resource-intensive; repository policy requires
    # these checks immediately before the service takes ownership of the GPUs.
    subprocess.run(["nvidia-smi"], check=True)
    subprocess.run(["free", "-h"], check=True)

    command = [
        sys.executable,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        str(model_path),
        "--served-model-name",
        LOCAL_QWEN_MODEL,
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--tensor-parallel-size",
        str(args.tensor_parallel_size),
        "--max-model-len",
        str(args.max_model_len),
        "--kv-cache-dtype",
        "fp8",
        "--enable-auto-tool-choice",
        "--tool-call-parser",
        args.tool_call_parser,
    ]
    if args.quantization:
        command.extend(["--quantization", args.quantization])
    if args.reasoning_parser:
        command.extend(["--reasoning-parser", args.reasoning_parser])
    command.extend(vllm_extra_args)
    executable_dir = str(Path(sys.executable).parent.resolve())
    inherited_path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join(
        part for part in (executable_dir, inherited_path) if part
    )
    os.execv(sys.executable, command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
