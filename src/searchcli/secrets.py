from __future__ import annotations

import os
from dataclasses import dataclass

import keyring
from keyring.errors import InitError, KeyringError, NoKeyringError

from searchcli.errors import SearchCliError


SERVICE_NAME = "searchcli"


@dataclass(slots=True)
class SecretLookup:
    api_key: str | None
    source: str | None


def env_var_name(provider: str) -> str:
    return f"SEARCHCLI_{provider.upper()}_API_KEY"


def get_api_key(provider: str) -> SecretLookup:
    env_name = env_var_name(provider)
    env_value = os.getenv(env_name)
    if env_value:
        return SecretLookup(api_key=env_value, source=f"env:{env_name}")

    try:
        stored = keyring.get_password(SERVICE_NAME, provider)
    except (NoKeyringError, InitError, KeyringError) as exc:
        raise SearchCliError(
            code="keyring_unavailable",
            message="OS キーチェーンへアクセスできませんでした。",
            recovery=[
                "一時利用なら環境変数で API キーを設定する",
                f"例: export {env_name}=<your_key>",
                "恒久利用なら keyring が利用できるバックエンドをセットアップする",
            ],
            details={"reason": str(exc)},
        ) from exc

    if stored:
        return SecretLookup(api_key=stored, source="keyring")
    return SecretLookup(api_key=None, source=None)


def require_api_key(provider: str) -> SecretLookup:
    lookup = get_api_key(provider)
    if lookup.api_key:
        return lookup

    env_name = env_var_name(provider)
    raise SearchCliError(
        code="auth_missing",
        message=f"{provider} 用の API キーが未設定です。",
        recovery=[
            f"searchcli auth set {provider} を実行して保存する",
            f"または環境変数 {env_name} を設定する",
            "searchcli providers で登録先 URL を確認する",
        ],
    )


def set_api_key(provider: str, api_key: str) -> None:
    try:
        keyring.set_password(SERVICE_NAME, provider, api_key)
    except (NoKeyringError, InitError, KeyringError) as exc:
        raise SearchCliError(
            code="auth_store_failed",
            message="API キーをキーチェーンへ保存できませんでした。",
            recovery=[
                "環境変数での利用に切り替える",
                f"例: export {env_var_name(provider)}=<your_key>",
                "keyring バックエンドを設定した後に再実行する",
            ],
            details={"reason": str(exc)},
        ) from exc


def delete_api_key(provider: str) -> bool:
    try:
        current = keyring.get_password(SERVICE_NAME, provider)
        if current is None:
            return False
        keyring.delete_password(SERVICE_NAME, provider)
        return True
    except keyring.errors.PasswordDeleteError:
        return False
    except (NoKeyringError, InitError, KeyringError) as exc:
        raise SearchCliError(
            code="auth_delete_failed",
            message="API キーの削除に失敗しました。",
            recovery=["keyring バックエンドの状態を確認する", "環境変数も併用している場合はそちらも確認する"],
            details={"reason": str(exc)},
        ) from exc


def keyring_backend_name() -> str:
    return keyring.get_keyring().__class__.__name__
