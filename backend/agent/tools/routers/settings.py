from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

import backend.config as config_module
from backend.agent.tools.utils import (
    _coerce_bool,
    _default_system_settings,
    clear_system_settings_for_provider,
    save_system_settings,
)
from backend.provider_settings import delete_provider_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class CustomProviderPayload(BaseModel):
    provider_name: str
    base_url: str
    api_key: str | None = None
    model_name: str | None = None


class SystemSettingsPayload(BaseModel):
    generation_model: str | None = None
    validation_model: str | None = None
    validation_enabled: bool | None = None


class ProviderUpdatePayload(BaseModel):
    base_url: str | None = None
    api_key: str | None = None


class ModelRequestKwargsPayload(BaseModel):
    provider_name: str
    model_id: str
    request_kwargs: dict[str, Any]


def _provider_response(provider, *, model_value: str | None = None) -> dict:
    return {
        "custom_provider": config_module.provider_settings_public_payload(provider),
        "custom_providers": config_module.list_public_custom_provider_settings(),
        "providers": config_module.list_selectable_providers(),
        "model_value": model_value,
    }


@router.get("")
async def get_settings():
    settings = _default_system_settings()
    return {
        "providers": config_module.list_selectable_providers(),
        "generation_model": settings["generation_model"],
        "validation_model": settings["validation_model"],
        "validation_enabled": settings["validation_enabled"],
        "custom_providers": config_module.list_public_custom_provider_settings(),
        "custom_provider": config_module.default_public_custom_provider_settings(),
    }


@router.post("/system")
async def save_system_settings_route(payload: SystemSettingsPayload):
    try:
        generation_model = (
            config_module.normalize_selectable_model_name(payload.generation_model, default=None)
            if payload.generation_model
            else None
        )
        validation_model = (
            config_module.normalize_selectable_model_name(payload.validation_model, default=None)
            if payload.validation_model
            else None
        )
        settings = {
            "generation_model": generation_model,
            "validation_model": validation_model,
            "validation_enabled": _coerce_bool(payload.validation_enabled, False),
        }
        save_system_settings(settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return settings


@router.post("/custom-provider")
async def save_custom_provider(payload: CustomProviderPayload):
    try:
        models = await config_module.fetch_provider_models(
            payload.base_url,
            payload.api_key,
        )
        provider = config_module.save_custom_provider_settings(
            provider_name=payload.provider_name,
            base_url=payload.base_url,
            api_key=payload.api_key,
            default_model=payload.model_name,
            models=models,
        )
        model_value = (
            config_module.custom_provider_model_value(
                provider.provider_name,
                provider.default_model,
            )
            if provider.default_model
            else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _provider_response(provider, model_value=model_value)


@router.post("/providers/{provider_name}/refresh")
async def refresh_provider_models(provider_name: str):
    provider = config_module.get_provider_settings(provider_name)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' is not configured.")
    try:
        models = await config_module.fetch_provider_models(
            provider.base_url,
            provider.api_key,
        )
        returned_ids = {str(model.get("id") or "") for model in models}
        default_model = provider.default_model if provider.default_model in returned_ids else None
        refreshed = config_module.save_custom_provider_settings(
            provider_name=provider.provider_name,
            base_url=provider.base_url,
            api_key=None,
            default_model=default_model,
            models=models,
            make_default=provider.is_default,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _provider_response(refreshed)


@router.patch("/providers/{provider_name}")
async def update_provider_settings(provider_name: str, payload: ProviderUpdatePayload):
    """Update an existing provider's base URL and/or API key.

    Saved models are preserved as-is so the key can be fixed even when the
    current one is broken (model refresh is a separate action).
    """
    provider = config_module.get_provider_settings(provider_name)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' is not configured.")
    try:
        updated = config_module.save_custom_provider_settings(
            provider_name=provider.provider_name,
            base_url=payload.base_url or provider.base_url,
            api_key=payload.api_key,
            default_model=provider.default_model,
            models=[
                {
                    "id": model.model_id,
                    "name": model.model_name,
                    "request_kwargs": model.request_kwargs,
                }
                for model in provider.models
            ],
            make_default=provider.is_default,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _provider_response(updated)


@router.delete("/providers/{provider_name}")
async def delete_provider_settings_route(provider_name: str):
    """Delete a provider, its saved models, and any model selections referencing it."""
    provider = config_module.get_provider_settings(provider_name)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' is not configured.")
    delete_provider_settings(provider.provider_name)
    clear_system_settings_for_provider(provider.provider_name)
    return {
        "providers": config_module.list_selectable_providers(),
        "custom_providers": config_module.list_public_custom_provider_settings(),
        "custom_provider": config_module.default_public_custom_provider_settings(),
    }


@router.post("/model-request-kwargs")
async def save_model_request_kwargs(payload: ModelRequestKwargsPayload):
    try:
        provider = config_module.save_custom_provider_model_request_kwargs(
            provider_name=payload.provider_name,
            model_id=payload.model_id,
            request_kwargs=payload.request_kwargs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _provider_response(provider)
