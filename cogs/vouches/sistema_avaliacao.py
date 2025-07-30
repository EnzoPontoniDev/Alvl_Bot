import discord
from discord.ext import commands
from discord import app_commands, ui, ButtonStyle, Color
from datetime import datetime
import os

ROLE_CLIENTE = "Cliente"
VOUCH_CATEGORY_NAME = "AVALIAÇÕES / VOUCHES"
APPROVAL_CHANNEL_NAME = "aprovar-avaliacao"
PUBLIC_VOUCHES_CHANNEL_NAME = "avaliacoes-vouches"


async def get_or_create_vouch_channel(guild: discord.Guild, channel_name: str):
    category = discord.utils.get(guild.categories, name=VOUCH_CATEGORY_NAME)
    if not category:
        overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
        category = await guild.create_category(VOUCH_CATEGORY_NAME, overwrites=overwrites)

    channel = discord.utils.get(category.text_channels, name=channel_name)
    if not channel:
        if channel_name == PUBLIC_VOUCHES_CHANNEL_NAME:
            channel_overwrites = {guild.default_role: discord.PermissionOverwrite(send_messages=False)}
            channel = await category.create_text_channel(channel_name, overwrites=channel_overwrites)
        else:
            channel = await category.create_text_channel(channel_name)
    return channel


class ApprovalView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Aprovar", style=ButtonStyle.success, custom_id="vouch_approve")
    async def approve_button(self, interaction: discord.Interaction, button: ui.Button):
        original_embed = interaction.message.embeds[0]

        public_embed = original_embed.copy()
        public_embed.title = "Nova Avaliação de Cliente!"
        public_embed.color = Color.blue()

        vouch_channel = await get_or_create_vouch_channel(interaction.guild, PUBLIC_VOUCHES_CHANNEL_NAME)

        await vouch_channel.send(embed=public_embed)
        await interaction.message.delete()
        await interaction.response.send_message("✅ Avaliação aprovada e publicada!", ephemeral=True)

    @ui.button(label="Reprovar", style=ButtonStyle.danger, custom_id="vouch_reject")
    async def reject_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.delete()
        await interaction.response.send_message("🗑️ Avaliação reprovada e excluída.", ephemeral=True)


class VouchModal(ui.Modal, title="Deixe seu Feedback"):
    comment = ui.TextInput(label="Deixe um comentário sobre o serviço", style=discord.TextStyle.paragraph,
                           placeholder="Seu feedback é muito importante...", required=True, max_length=1024)

    def __init__(self, star_rating: int):
        super().__init__()
        self.star_rating = star_rating

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Obrigado pelo seu feedback! Ele foi enviado para análise.",
                                                ephemeral=True)

        approval_channel = await get_or_create_vouch_channel(interaction.guild, APPROVAL_CHANNEL_NAME)

        stars_text = "⭐" * self.star_rating
        star_label = "estrela" if self.star_rating == 1 else "estrelas"

        embed = discord.Embed(
            title="Nova Avaliação para Aprovação",
            color=Color.orange(),
            timestamp=datetime.now()
        )
        embed.set_author(name=f"De: {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Avaliador", value=interaction.user.mention, inline=False)
        embed.add_field(name=f"Avaliação ({self.star_rating} {star_label})", value=stars_text, inline=False)
        embed.add_field(name="Comentário", value=f"> {self.comment.value}", inline=False)

        await approval_channel.send(embed=embed, view=ApprovalView())


class StarButton(ui.Button['StarRatingView']):
    def __init__(self, stars: int):
        super().__init__(label="⭐" * stars, style=ButtonStyle.secondary, custom_id=f"vouch_stars_{stars}")
        self.stars = stars

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(VouchModal(star_rating=self.stars))


class StarRatingView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        for i in range(1, 6):
            self.add_item(StarButton(i))


class VouchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="avaliar", description="Deixe uma avaliação sobre um serviço prestado.")
    async def avaliar_vouch(self, interaction: discord.Interaction):
        cliente_role = discord.utils.get(interaction.guild.roles, name=ROLE_CLIENTE)
        if cliente_role is None or cliente_role not in interaction.user.roles:
            await interaction.response.send_message(
                f"❌ Apenas membros com o cargo **{ROLE_CLIENTE}** podem deixar uma avaliação.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Como você avalia o serviço prestado?",
            view=StarRatingView(),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(VouchCog(bot))