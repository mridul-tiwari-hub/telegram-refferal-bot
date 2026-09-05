"""Content Filter Service for Banned Words and Link Domain Inspection."""
import re
from urllib.parse import urlparse
from typing import Tuple, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.group import Group
from database.repositories.admin_repo import AdminRepository
from database.repositories.group_repo import GroupRepository

URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?:\/[^\s]*)?",
    re.IGNORECASE
)


class ContentFilterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.admin_repo = AdminRepository(session)
        self.group_repo = GroupRepository(session)

    def extract_domains(self, text: str) -> List[str]:
        """Extracts unique lowercase domain names from message text."""
        if not text:
            return []
        matches = URL_REGEX.findall(text)
        domains = []
        for m in matches:
            domain = m.lower().strip(".")
            if domain:
                domains.append(domain)
        return list(set(domains))

    async def check_banned_words(self, group_id: int, text: str) -> Tuple[bool, Optional[str]]:
        """
        Checks if text contains any banned words or phrases.
        Supports exact word boundary match or substring match.
        """
        if not text:
            return False, None

        banned_words = await self.admin_repo.list_banned_words(group_id)
        if not banned_words:
            return False, None

        text_lower = text.lower()

        for bw in banned_words:
            target = bw.word.lower()
            if bw.is_substring:
                if target in text_lower:
                    return True, target
            else:
                # Word boundary check
                pattern = r"\b" + re.escape(target) + r"\b"
                if re.search(pattern, text_lower):
                    return True, target

        return False, None

    async def check_links(self, group_id: int, text: str) -> Tuple[bool, Optional[str]]:
        """
        Inspects links according to group link filter mode and whitelisted/blacklisted domains.
        Guarantees legitimate Telegram invite links are not blocked.
        """
        domains = self.extract_domains(text)
        if not domains:
            return False, None

        settings = await self.group_repo.get_settings(group_id)
        mode = settings.link_filter_mode if settings else "ALLOW_ALL"

        all_domain_rules = await self.admin_repo.list_domains(group_id)
        whitelist = {d.domain.lower() for d in all_domain_rules if d.is_allowed}
        blacklist = {d.domain.lower() for d in all_domain_rules if not d.is_allowed}

        for domain in domains:
            # Check domain or parent domain against blacklist
            if domain in blacklist or any(domain.endswith("." + b) for b in blacklist):
                return True, f"Domain {domain} is blacklisted."

            # Check domain against whitelist
            if domain in whitelist or any(domain.endswith("." + w) for w in whitelist):
                continue

            if mode == "BLOCK_ALL":
                # If block all, any non-whitelisted link is violation
                return True, f"External links are blocked in this group ({domain})."

            elif mode == "TELEGRAM_ONLY":
                # Allow telegram domains
                if domain in ["t.me", "telegram.me", "telegram.dog"]:
                    continue
                return True, f"Only Telegram links are permitted ({domain} is blocked)."

        return False, None
