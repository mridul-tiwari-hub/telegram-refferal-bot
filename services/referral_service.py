"""Referral Service for handling attribution, requirements, and referral trees."""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.referral_repo import ReferralRepository
from database.repositories.user_repo import UserRepository
from database.repositories.group_repo import GroupRepository
from database.repositories.moderation_repo import ModerationRepository
from database.models.user import User
from database.models.group import Group
from database.models.referral_link import ReferralInviteLink
from database.models.referral_requirement import ReferralRequirement
from services.invite_link_service import InviteLinkService
from utils.logging import get_logger

logger = get_logger(__name__)


class ReferralService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.referral_repo = ReferralRepository(session)
        self.user_repo = UserRepository(session)
        self.group_repo = GroupRepository(session)
        self.mod_repo = ModerationRepository(session)
        self.invite_service = InviteLinkService(session, bot)

    async def handle_new_member_join(
        self,
        group: Group,
        new_user: User,
        telegram_invite_link_str: Optional[str] = None
    ) -> Tuple[Optional[ReferralRequirement], Optional[ReferralInviteLink], Optional[User]]:
        """
        Processes a member join:
        1. Checks if joined via a bot-generated referral invite link.
        2. Attributes referral credit to referrer without duplicate counts.
        3. Generates the new member's personal referral link.
        4. Initializes the new member's referral requirement.
        """
        settings = await self.group_repo.get_settings(group.id)
        referrer_user: Optional[User] = None

        # STEP 2 & 3: Referral attribution check
        if telegram_invite_link_str and settings.referral_enabled:
            link_record = await self.referral_repo.get_by_link_str(telegram_invite_link_str)
            if link_record and link_record.user_id != new_user.id:
                referrer = await self.user_repo.get_by_id(link_record.user_id)
                if referrer:
                    # Record relationship (enforces uniqueness per group & user)
                    rel, is_new = await self.referral_repo.record_referral(
                        group_id=group.id,
                        referrer_user_id=referrer.id,
                        referred_user_id=new_user.id,
                        invite_link_id=link_record.id
                    )

                    if is_new:
                        referrer_user = referrer
                        updated_req = await self.referral_repo.increment_completed_referral(
                            user_id=referrer.id,
                            group_id=group.id
                        )

                        await self.mod_repo.add_log(
                            action="REFERRAL",
                            group_id=group.id,
                            user_id=referrer.id,
                            details=f"Referred user {new_user.first_name} (ID: {new_user.telegram_user_id}). Status: {updated_req.status if updated_req else 'N/A'}"
                        )

                        # Try notifying referrer privately if possible
                        try:
                            req_info = f"{updated_req.completed_referrals}/{updated_req.required_referrals}" if updated_req else "1"
                            status_str = "🎉 Requirement Completed!" if updated_req and updated_req.status == "COMPLETED" else "⏳ Still in progress"
                            await self.bot.send_message(
                                chat_id=referrer.telegram_user_id,
                                text=(
                                    f"✨ <b>New Referral!</b>\n"
                                    f"<b>{new_user.first_name}</b> just joined {group.group_name} using your invite link!\n"
                                    f"Progress: <b>{req_info}</b>\n"
                                    f"Status: <b>{status_str}</b>"
                                ),
                                parse_mode="HTML"
                            )
                        except Exception:
                            # Expected if user hasn't initiated bot in DM
                            pass

        # STEP 4 & 5: Generate unique personal referral link for new member
        new_link = await self.invite_service.get_or_create_referral_link(new_user, group)

        # STEP 6: Create requirement for new member if referral is enabled
        deadline = datetime.now(timezone.utc) + timedelta(hours=settings.referral_deadline_hours)
        requirement = None
        if settings.referral_enabled:
            requirement = await self.referral_repo.create_requirement(
                user_id=new_user.id,
                group_id=group.id,
                deadline=deadline,
                required_referrals=settings.required_referrals
            )

        await self.mod_repo.add_log(
            action="JOIN",
            group_id=group.id,
            user_id=new_user.id,
            details=f"Joined group. Referrer: {referrer_user.first_name if referrer_user else 'None'}"
        )

        return requirement, new_link, referrer_user

    async def generate_referral_tree_text(
        self,
        group_id: int,
        root_user_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 15
    ) -> Tuple[str, int, int]:
        """
        Generates an ASCII tree diagram representing referral relationships.
        Returns: (text, current_page, total_pages)
        """
        # Fetch all referral edges (parent, child)
        edges = await self.referral_repo.get_referral_tree_nodes(group_id)
        if not edges:
            return "No referral relationships recorded in this group yet.", 1, 1

        # Build adjacency mapping
        adj: Dict[int, List[int]] = {}
        all_children = set()
        all_parents = set()
        for p, c in edges:
            adj.setdefault(p, []).append(c)
            all_children.add(c)
            all_parents.add(p)

        # Determine roots
        if root_user_id:
            roots = [root_user_id] if root_user_id in adj or root_user_id in all_children else []
        else:
            # Roots are parents that are not children of anyone in this group
            roots = sorted(list(all_parents - all_children))
            if not roots and all_parents:
                roots = sorted(list(all_parents))[:5]

        if not roots:
            return "No referral trees found.", 1, 1

        # Fetch user details cache
        all_user_ids = set()
        for p, c in edges:
            all_user_ids.add(p)
            all_user_ids.add(c)
        for r in roots:
            all_user_ids.add(r)

        users_dict: Dict[int, str] = {}
        for uid in all_user_ids:
            u = await self.user_repo.get_by_id(uid)
            if u:
                name = u.username and f"@{u.username}" or u.first_name or f"User #{u.telegram_user_id}"
                users_dict[uid] = name
            else:
                users_dict[uid] = f"User #{uid}"

        lines: List[str] = []

        def build_branch(node_id: int, prefix: str = "", is_last: bool = True, depth: int = 0):
            if depth > 10:  # Prevent infinite loops
                return
            node_name = users_dict.get(node_id, f"User {node_id}")
            connector = "└── " if is_last else "├── "
            if depth == 0:
                lines.append(f"<b>{node_name}</b>")
            else:
                lines.append(f"{prefix}{connector}{node_name}")

            children = adj.get(node_id, [])
            new_prefix = prefix + ("    " if is_last else "│   ") if depth > 0 else ""
            for idx, child in enumerate(children):
                is_child_last = (idx == len(children) - 1)
                build_branch(child, new_prefix, is_child_last, depth + 1)

        for r in roots:
            build_branch(r)

        # Paginate lines to prevent telegram message overflow
        total_lines = len(lines)
        total_pages = max(1, (total_lines + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_lines = lines[start_idx:end_idx]

        header = f"🌳 <b>Referral Tree (Page {page}/{total_pages})</b>\n\n<pre>"
        footer = "</pre>"
        return header + "\n".join(page_lines) + footer, page, total_pages
