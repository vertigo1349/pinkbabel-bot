"""Persistence adapters for chat preferences."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .languages import LanguageError, resolve_language_code


class StorageError(RuntimeError):
    """Raised when a preference backend cannot complete an operation."""


@dataclass(slots=True)
class JsonPreferenceStore:
    """Persist chat preferences in a local JSON file."""

    path: Path
    _data: dict[str, Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self._data = self._load()

    def get_chat_language(self, chat_id: int, default_language: str) -> str:
        chat_data = self._chat_data(chat_id)
        raw_language = chat_data.get("target_language", default_language)

        try:
            return resolve_language_code(raw_language)
        except LanguageError:
            return resolve_language_code(default_language)

    def set_chat_language(self, chat_id: int, target_language: str) -> str:
        language_code = resolve_language_code(target_language)
        self._chat_data(chat_id)["target_language"] = language_code
        self.save()
        return language_code

    def set_user_language(self, chat_id: int, user_id: int, language: str) -> str:
        language_code = resolve_language_code(language)
        users = self._chat_data(chat_id).setdefault("users", {})
        users[str(user_id)] = language_code
        self.save()
        return language_code

    def get_user_language(self, chat_id: int, user_id: int) -> str | None:
        raw_language = self._chat_data(chat_id).get("users", {}).get(str(user_id))
        if not isinstance(raw_language, str):
            return None

        try:
            return resolve_language_code(raw_language)
        except LanguageError:
            return None

    def get_group_target_languages(self, chat_id: int, sender_user_id: int) -> list[str]:
        chat_data = self._chat_data(chat_id)
        users = chat_data.get("users", {})
        sender_language = self.get_user_language(chat_id, sender_user_id)
        target_languages: set[str] = set()

        if not isinstance(users, dict):
            return []

        for raw_language in users.values():
            if not isinstance(raw_language, str):
                continue
            try:
                language_code = resolve_language_code(raw_language)
            except LanguageError:
                continue
            if language_code != sender_language:
                target_languages.add(language_code)

        return sorted(target_languages)

    def set_auto_translation(self, chat_id: int, enabled: bool) -> None:
        self._chat_data(chat_id)["auto_translate"] = enabled
        self.save()

    def is_auto_translation_enabled(self, chat_id: int) -> bool:
        return self._chat_data(chat_id).get("auto_translate") is True

    def get_group_languages(self, chat_id: int) -> list[str]:
        users = self._chat_data(chat_id).get("users", {})
        if not isinstance(users, dict):
            return []

        languages: set[str] = set()
        for raw_language in users.values():
            if not isinstance(raw_language, str):
                continue
            try:
                languages.add(resolve_language_code(raw_language))
            except LanguageError:
                continue

        return sorted(languages)

    def _chat_data(self, chat_id: int) -> dict[str, Any]:
        chats = self._data.setdefault("chats", {})
        chat_data = chats.setdefault(str(chat_id), {})
        if not isinstance(chat_data, dict):
            chat_data = {}
            chats[str(chat_id)] = chat_data
        return chat_data

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"chats": {}}

        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {"chats": {}}

        if not isinstance(data, dict):
            return {"chats": {}}
        if not isinstance(data.get("chats"), dict):
            data["chats"] = {}

        return data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")

        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(self._data, file, ensure_ascii=False, indent=2)

        os.replace(temp_path, self.path)


@dataclass(slots=True)
class SupabasePreferenceStore:
    """Persist preferences through Supabase's generated REST API."""

    url: str
    api_key: str
    timeout: float = 10.0

    def __post_init__(self) -> None:
        self.url = self.url.rstrip("/")
        if not self.url or not self.api_key:
            raise ValueError("Supabase URL and API key are required.")

    def get_chat_language(self, chat_id: int, default_language: str) -> str:
        rows = self._request(
            "pinkbabel_chats",
            query={
                "select": "target_language",
                "chat_id": f"eq.{chat_id}",
                "limit": "1",
            },
        )
        raw_language = rows[0].get("target_language") if rows else None
        if not isinstance(raw_language, str):
            return resolve_language_code(default_language)

        try:
            return resolve_language_code(raw_language)
        except LanguageError:
            return resolve_language_code(default_language)

    def set_chat_language(self, chat_id: int, target_language: str) -> str:
        language_code = resolve_language_code(target_language)
        self._upsert(
            "pinkbabel_chats",
            {"chat_id": chat_id, "target_language": language_code},
            "chat_id",
        )
        return language_code

    def set_user_language(self, chat_id: int, user_id: int, language: str) -> str:
        language_code = resolve_language_code(language)
        self._ensure_chat(chat_id)
        self._upsert(
            "pinkbabel_users",
            {
                "chat_id": chat_id,
                "user_id": user_id,
                "language": language_code,
            },
            "chat_id,user_id",
        )
        return language_code

    def get_user_language(self, chat_id: int, user_id: int) -> str | None:
        rows = self._request(
            "pinkbabel_users",
            query={
                "select": "language",
                "chat_id": f"eq.{chat_id}",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
        )
        raw_language = rows[0].get("language") if rows else None
        if not isinstance(raw_language, str):
            return None

        try:
            return resolve_language_code(raw_language)
        except LanguageError:
            return None

    def get_group_target_languages(self, chat_id: int, sender_user_id: int) -> list[str]:
        rows = self._group_user_rows(chat_id)
        sender_language: str | None = None
        languages: set[str] = set()

        for row in rows:
            raw_language = row.get("language")
            if not isinstance(raw_language, str):
                continue
            try:
                language_code = resolve_language_code(raw_language)
            except LanguageError:
                continue
            languages.add(language_code)
            if row.get("user_id") == sender_user_id:
                sender_language = language_code

        if sender_language is not None:
            languages.discard(sender_language)
        return sorted(languages)

    def set_auto_translation(self, chat_id: int, enabled: bool) -> None:
        self._upsert(
            "pinkbabel_chats",
            {"chat_id": chat_id, "auto_translate": enabled},
            "chat_id",
        )

    def is_auto_translation_enabled(self, chat_id: int) -> bool:
        rows = self._request(
            "pinkbabel_chats",
            query={
                "select": "auto_translate",
                "chat_id": f"eq.{chat_id}",
                "limit": "1",
            },
        )
        return bool(rows and rows[0].get("auto_translate") is True)

    def get_group_languages(self, chat_id: int) -> list[str]:
        languages: set[str] = set()
        for row in self._group_user_rows(chat_id):
            raw_language = row.get("language")
            if not isinstance(raw_language, str):
                continue
            try:
                languages.add(resolve_language_code(raw_language))
            except LanguageError:
                continue
        return sorted(languages)

    def _ensure_chat(self, chat_id: int) -> None:
        self._upsert("pinkbabel_chats", {"chat_id": chat_id}, "chat_id")

    def _group_user_rows(self, chat_id: int) -> list[dict[str, Any]]:
        rows = self._request(
            "pinkbabel_users",
            query={
                "select": "user_id,language",
                "chat_id": f"eq.{chat_id}",
            },
        )
        return rows if isinstance(rows, list) else []

    def _upsert(
        self,
        table: str,
        payload: dict[str, Any],
        conflict_columns: str,
    ) -> None:
        self._request(
            table,
            method="POST",
            query={"on_conflict": conflict_columns},
            payload=payload,
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def _request(
        self,
        table: str,
        *,
        method: str = "GET",
        query: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> Any:
        endpoint = f"{self.url}/rest/v1/{table}"
        if query:
            endpoint = f"{endpoint}?{urlencode(query)}"

        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        if prefer:
            headers["Prefer"] = prefer

        request = Request(endpoint, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise StorageError(
                f"Supabase request failed with HTTP {exc.code}: {details}"
            ) from exc
        except (URLError, OSError) as exc:
            raise StorageError(f"Could not connect to Supabase: {exc}") from exc

        if not body:
            return []
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise StorageError("Supabase returned an invalid JSON response.") from exc


def create_preference_store(
    data_file: Path,
    *,
    supabase_url: str | None = None,
    supabase_key: str | None = None,
) -> JsonPreferenceStore | SupabasePreferenceStore:
    """Select durable Supabase storage when its credentials are configured."""

    if supabase_url and supabase_key:
        return SupabasePreferenceStore(supabase_url, supabase_key)
    return JsonPreferenceStore(data_file)
