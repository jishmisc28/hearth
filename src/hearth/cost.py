"""Cost model computing provider call costs in exact Decimal arithmetic (INV-13)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass(frozen=True)
class ModelPricing:
    input_price_per_token: Decimal
    output_price_per_token: Decimal
    read_multiplier: Decimal
    write_multiplier: Decimal
    min_prefix_tokens: int


@dataclass(frozen=True)
class CallCost:
    actual_cost: Decimal
    uncached_baseline: Decimal
    savings_amount: Decimal
    cost_ratio: Decimal


_providers_cache: dict[str, Any] | None = None


def load_providers_toml(path: str | Path | None = None) -> dict[str, Any]:
    global _providers_cache
    if path is None and _providers_cache is not None:
        return _providers_cache

    if path is None:
        data_path = Path(__file__).parent / "data" / "providers.toml"
    else:
        data_path = Path(path)

    with open(data_path, "rb") as f:
        loaded: Any = tomllib.load(f)
    data = {str(key): value for key, value in loaded.items()}

    if path is None:
        _providers_cache = data
    return data


def get_model_pricing(provider: str, model: str) -> ModelPricing:
    """Lookup pricing parameters for a given provider and model from providers.toml."""
    providers_data = load_providers_toml()
    providers_dict = providers_data.get("providers", {})
    if provider not in providers_dict:
        raise KeyError(
            f"Provider '{provider}' not found in providers.toml. Configured providers: {list(providers_dict.keys())}"
        )

    provider_info = providers_dict[provider]
    models_dict = provider_info.get("models", {})
    if model not in models_dict:
        # Cross-provider model lookup fallback
        for alt_prov, alt_info in providers_dict.items():
            if model in alt_info.get("models", {}):
                provider = alt_prov
                provider_info = alt_info
                models_dict = alt_info.get("models", {})
                break
        else:
            raise KeyError(
                f"Model '{model}' not configured for provider '{provider}' in providers.toml. Configured models: {list(models_dict.keys())}"
            )

    model_info = models_dict[model]

    # Multipliers & minimums: model-level override or provider-level default
    if "read_multiplier" in model_info:
        read_mult = Decimal(str(model_info["read_multiplier"]))
    elif "read_multiplier" in provider_info:
        read_mult = Decimal(str(provider_info["read_multiplier"]))
    else:
        raise KeyError(f"read_multiplier missing for {provider}/{model} in providers.toml")

    if "write_multiplier" in model_info:
        write_mult = Decimal(str(model_info["write_multiplier"]))
    elif "write_multiplier" in provider_info:
        write_mult = Decimal(str(provider_info["write_multiplier"]))
    else:
        raise KeyError(f"write_multiplier missing for {provider}/{model} in providers.toml")

    if "min_prefix_tokens" in model_info:
        min_prefix = int(model_info["min_prefix_tokens"])
    elif "min_prefix_tokens" in provider_info:
        min_prefix = int(provider_info["min_prefix_tokens"])
    else:
        raise KeyError(f"min_prefix_tokens missing for {provider}/{model} in providers.toml")

    # Prices in toml are per million tokens
    if "input_price_per_million" not in model_info or "output_price_per_million" not in model_info:
        raise KeyError(
            f"Pricing per million tokens missing for {provider}/{model} in providers.toml"
        )

    in_per_m = Decimal(str(model_info["input_price_per_million"]))
    out_per_m = Decimal(str(model_info["output_price_per_million"]))

    million = Decimal("1000000")
    p_in = in_per_m / million
    p_out = out_per_m / million

    return ModelPricing(
        input_price_per_token=p_in,
        output_price_per_token=p_out,
        read_multiplier=read_mult,
        write_multiplier=write_mult,
        min_prefix_tokens=min_prefix,
    )


def compute_call_cost(
    provider: str,
    model: str,
    read_tokens: int,
    write_tokens: int,
    uncached_tokens: int,
    output_tokens: int,
) -> CallCost:
    """Compute exact cost in USD for a single call and its uncached baseline (INV-13).

    Formula (BUILD_HANDBOOK §5.3):
    call_cost = p_in * (r * read + w * write + uncached) + p_out * output
    uncached_baseline = p_in * (read + write + uncached) + p_out * output
    """
    pricing = get_model_pricing(provider, model)

    read_dec = Decimal(read_tokens)
    write_dec = Decimal(write_tokens)
    uncached_dec = Decimal(uncached_tokens)
    output_dec = Decimal(output_tokens)

    # Actual cost with caching discounts and write premiums
    effective_input_tokens = (
        pricing.read_multiplier * read_dec + pricing.write_multiplier * write_dec + uncached_dec
    )
    actual_cost = (pricing.input_price_per_token * effective_input_tokens) + (
        pricing.output_price_per_token * output_dec
    )

    # Uncached baseline (no cache hits or writes)
    total_input_tokens = read_dec + write_dec + uncached_dec
    uncached_baseline = (pricing.input_price_per_token * total_input_tokens) + (
        pricing.output_price_per_token * output_dec
    )

    savings_amount = max(Decimal("0"), uncached_baseline - actual_cost)
    cost_ratio = (
        actual_cost / uncached_baseline if uncached_baseline > Decimal("0") else Decimal("1")
    )

    return CallCost(
        actual_cost=actual_cost.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        uncached_baseline=uncached_baseline.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        savings_amount=savings_amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        cost_ratio=cost_ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
    )
