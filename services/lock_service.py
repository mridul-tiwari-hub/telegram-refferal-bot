"""Group Content Locks Service."""
from typing import Tuple
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.admin_repo import AdminRepository
from services.content_filter_service import URL_REGEX


class LockService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.admin_repo = AdminRepository(session)

    async def is_message_locked(self, group_id: int, message: Message) -> Tuple[bool, str]:
        """
        Determines if the given message violates any content lock set for the group.
        Returns (True, reason) if locked, or (False, "") if allowed.
        """
        locks = await self.admin_repo.get_or_create_locks(group_id)

        if locks.lock_all:
            return True, "All messages and media are currently locked in this group."

        # Check media types
        if locks.lock_photos and message.photo:
            return True, "Photos are locked in this group."

        if locks.lock_videos and message.video:
            return True, "Videos are locked in this group."

        if locks.lock_gifs and message.animation:
            return True, "GIFs are locked in this group."

        if locks.lock_stickers and message.sticker:
            return True, "Stickers are locked in this group."

        if locks.lock_voice and (message.voice or message.video_note):
            return True, "Voice messages and video notes are locked in this group."

        if locks.lock_audio and message.audio:
            return True, "Audio files are locked in this group."

        if locks.lock_documents and message.document:
            return True, "Documents and files are locked in this group."

        if locks.lock_polls and message.poll:
            return True, "Polls are locked in this group."

        # Check links lock
        if locks.lock_links:
            text = message.text or message.caption or ""
            if URL_REGEX.search(text):
                return True, "Links are locked in this group."

        # Check text-only lock (if pure text message)
        if locks.lock_text and message.text and not any([
            message.photo, message.video, message.document,
            message.audio, message.voice, message.sticker, message.animation
        ]):
            return True, "Text messages are locked in this group."

        return False, ""
