"""Statistics Service for aggregating group referral analytics and leaderboards."""
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.referral_repo import ReferralRepository
from database.repositories.group_repo import GroupRepository
from database.models.group import Group


class StatisticsService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.referral_repo = ReferralRepository(session)
        self.group_repo = GroupRepository(session)

    async def get_formatted_stats(self, group: Group) -> str:
        """Formats comprehensive group referral statistics and leaderboard."""
        settings = await self.group_repo.get_settings(group.id)
        raw_stats = await self.referral_repo.get_referral_stats(group.id)
        top_referrers = await self.referral_repo.get_top_referrers(group.id, limit=5)

        system_status = "ENABLED ✅" if settings.referral_enabled else "DISABLED ❌"

        # Try to get total chat member count from telegram
        try:
            tg_member_count = await self.bot.get_chat_member_count(group.telegram_group_id)
        except Exception:
            tg_member_count = "N/A"

        leaderboard_lines = []
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for idx, (user, count) in enumerate(top_referrers):
            medal = medals[idx] if idx < len(medals) else "▫️"
            name = f"@{user.username}" if user.username else (user.first_name or f"User #{user.telegram_user_id}")
            leaderboard_lines.append(f"{medal} {name} — <b>{count}</b> referral(s)")

        if not leaderboard_lines:
            leaderboard_lines.append("<i>No referral activity recorded yet.</i>")

        leaderboard_text = "\n".join(leaderboard_lines)

        text = (
            f"📊 <b>GROUP STATISTICS</b>\n"
            f"👥 <b>Group:</b> {group.group_name}\n"
            f"👥 <b>Total Members:</b> {tg_member_count}\n"
            f"⚙️ <b>Referral System:</b> {system_status}\n\n"
            f"⏳ <b>Pending Requirements:</b> {raw_stats['pending']}\n"
            f"✅ <b>Completed Requirements:</b> {raw_stats['completed']}\n"
            f"❌ <b>Failed Requirements:</b> {raw_stats['failed']}\n"
            f"🛡 <b>Exempt Members:</b> {raw_stats['exempt']}\n"
            f"🔗 <b>Total Successful Referrals:</b> {raw_stats['total_referrals']}\n\n"
            f"🏆 <b>TOP REFERRERS</b>\n"
            f"{leaderboard_text}"
        )
        return text
