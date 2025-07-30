import discord
from discord.ext import commands
from discord import app_commands, ui, ButtonStyle, Color
from datetime import datetime
import os
import io
import asyncio

# Tente importar o chat_exporter, se não funcionar, usaremos uma alternativa
try:
    import chat_exporter
except ImportError:
    chat_exporter = None

OWNER_USER_ID = 1186410533335863403
TICKET_CATEGORY_NAME = "Orçamentos"
LOG_TICKETS_CHANNEL_NAME = "logs-tickets"


class ConfirmCloseView(ui.View):
    def __init__(self, log_channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.log_channel = log_channel

    @ui.button(label="Confirmar Fechamento", style=ButtonStyle.danger, custom_id="confirm_close_ticket_html")
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Fechando o ticket e gerando a transcrição...", ephemeral=True)
        ticket_channel = interaction.channel

        if self.log_channel:
            try:
                # Primeira tentativa com chat_exporter
                if chat_exporter:
                    transcript = await chat_exporter.export(
                        ticket_channel,
                        limit=None,
                        tz_info="UTC",
                        guild=interaction.guild,
                        bot=interaction.client
                    )

                    if transcript:
                        transcript_file = discord.File(
                            io.BytesIO(transcript.encode()),
                            filename=f"transcript-{ticket_channel.name}.html"
                        )
                        await self.log_channel.send(
                            content=f"📋 Transcrição do ticket fechado `{ticket_channel.name}` por {interaction.user.mention}:",
                            file=transcript_file
                        )
                    else:
                        # Fallback para transcrição manual
                        await self.create_manual_transcript(ticket_channel, interaction.user)
                else:
                    # Fallback para transcrição manual
                    await self.create_manual_transcript(ticket_channel, interaction.user)

            except Exception as e:
                print(f"Erro ao criar transcrição: {e}")
                await self.create_manual_transcript(ticket_channel, interaction.user)

        await ticket_channel.delete(reason=f"Ticket fechado por {interaction.user.name}")

    async def create_manual_transcript(self, channel, closed_by):
        """Cria uma transcrição manual simples"""
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.strftime("%d/%m/%Y %H:%M:%S")
            content = message.clean_content or "[Embed/Anexo]"
            messages.append(f"[{timestamp}] {message.author.name}: {content}")

        transcript_content = f"=== TRANSCRIÇÃO DO TICKET {channel.name.upper()} ===\n"
        transcript_content += f"Fechado por: {closed_by.name}\n"
        transcript_content += f"Data de fechamento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        transcript_content += "=" * 50 + "\n\n"
        transcript_content += "\n".join(messages)

        transcript_file = discord.File(
            io.BytesIO(transcript_content.encode('utf-8')),
            filename=f"transcript-{channel.name}.txt"
        )

        await self.log_channel.send(
            content=f"📋 Transcrição do ticket fechado `{channel.name}` por {closed_by.mention}:",
            file=transcript_file
        )

    @ui.button(label="Cancelar", style=ButtonStyle.secondary, custom_id="cancel_close_ticket_html")
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.delete()
        await interaction.response.send_message("Ação cancelada.", ephemeral=True, delete_after=5)


class TicketActionsView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Timeout None para persistência

    @ui.button(label="Fechar Ticket", style=ButtonStyle.danger, custom_id="ticket_close_html", emoji="🔒")
    async def close_ticket_button(self, interaction: discord.Interaction, button: ui.Button):
        # Verificar se é realmente um canal de ticket
        if not interaction.channel.name.startswith("orcamento-"):
            await interaction.response.send_message("❌ Este comando só pode ser usado em canais de ticket!",
                                                    ephemeral=True)
            return

        category = discord.utils.get(interaction.guild.categories, name=TICKET_CATEGORY_NAME)
        log_channel = discord.utils.get(category.text_channels, name=LOG_TICKETS_CHANNEL_NAME) if category else None

        if not log_channel and category:
            try:
                log_channel = await category.create_text_channel(
                    LOG_TICKETS_CHANNEL_NAME,
                    overwrites={
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                    }
                )
            except Exception as e:
                print(f"Erro ao criar canal de logs: {e}")

        elif not log_channel and not category:
            try:
                overwrites = {interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False)}
                category = await interaction.guild.create_category(TICKET_CATEGORY_NAME, overwrites=overwrites)
                log_channel = await category.create_text_channel(
                    LOG_TICKETS_CHANNEL_NAME,
                    overwrites={
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                    }
                )
            except Exception as e:
                print(f"Erro ao criar categoria e canal de logs: {e}")

        await interaction.response.send_message(
            "🚨 **Você tem certeza que deseja fechar este ticket?**\n\n"
            "✅ Uma transcrição completa será salva nos logs\n"
            "❌ O canal será **permanentemente deletado**\n"
            "⏰ Esta confirmação expira em 60 segundos",
            view=ConfirmCloseView(log_channel=log_channel),
            ephemeral=True
        )

    @ui.button(label="Adicionar Membro", style=ButtonStyle.primary, custom_id="ticket_add_member", emoji="➕")
    async def add_member_button(self, interaction: discord.Interaction, button: ui.Button):
        # Verificar se é realmente um canal de ticket
        if not interaction.channel.name.startswith("orcamento-"):
            await interaction.response.send_message("❌ Este comando só pode ser usado em canais de ticket!",
                                                    ephemeral=True)
            return

        await interaction.response.send_modal(AddMemberModal())

    @ui.button(label="Remover Membro", style=ButtonStyle.secondary, custom_id="ticket_remove_member", emoji="➖")
    async def remove_member_button(self, interaction: discord.Interaction, button: ui.Button):
        # Verificar se é realmente um canal de ticket
        if not interaction.channel.name.startswith("orcamento-"):
            await interaction.response.send_message("❌ Este comando só pode ser usado em canais de ticket!",
                                                    ephemeral=True)
            return

        await interaction.response.send_modal(RemoveMemberModal())


class AddMemberModal(ui.Modal, title="Adicionar Membro ao Ticket"):
    member_input = ui.TextInput(
        label="ID ou @menção do usuário",
        placeholder="Ex: 1234567890 ou @usuario",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Tentar extrair ID do usuário
            user_input = self.member_input.value.strip()
            if user_input.startswith('<@') and user_input.endswith('>'):
                user_id = int(user_input[2:-1].replace('!', ''))
            else:
                user_id = int(user_input)

            member = interaction.guild.get_member(user_id)
            if not member:
                await interaction.response.send_message("❌ Usuário não encontrado no servidor!", ephemeral=True)
                return

            # Adicionar permissões
            await interaction.channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

            embed = discord.Embed(
                title="✅ Membro Adicionado",
                description=f"{member.mention} foi adicionado ao ticket por {interaction.user.mention}",
                color=Color.green(),
                timestamp=datetime.now()
            )

            await interaction.response.send_message(embed=embed)

        except ValueError:
            await interaction.response.send_message("❌ ID inválido! Use o ID numérico ou @menção.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao adicionar membro: {str(e)}", ephemeral=True)


class RemoveMemberModal(ui.Modal, title="Remover Membro do Ticket"):
    member_input = ui.TextInput(
        label="ID ou @menção do usuário",
        placeholder="Ex: 1234567890 ou @usuario",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Tentar extrair ID do usuário
            user_input = self.member_input.value.strip()
            if user_input.startswith('<@') and user_input.endswith('>'):
                user_id = int(user_input[2:-1].replace('!', ''))
            else:
                user_id = int(user_input)

            member = interaction.guild.get_member(user_id)
            if not member:
                await interaction.response.send_message("❌ Usuário não encontrado no servidor!", ephemeral=True)
                return

            # Remover permissões
            await interaction.channel.set_permissions(member, overwrite=None)

            embed = discord.Embed(
                title="✅ Membro Removido",
                description=f"{member.mention} foi removido do ticket por {interaction.user.mention}",
                color=Color.red(),
                timestamp=datetime.now()
            )

            await interaction.response.send_message(embed=embed)

        except ValueError:
            await interaction.response.send_message("❌ ID inválido! Use o ID numérico ou @menção.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao remover membro: {str(e)}", ephemeral=True)


class BriefingModal(ui.Modal, title="Formulário de Orçamento"):
    project_type = ui.TextInput(
        label="Qual o tipo de projeto?",
        style=discord.TextStyle.short,
        placeholder="Ex: Bot para Discord, Website, Sistema...",
        required=True,
        max_length=100
    )
    description = ui.TextInput(
        label="Descreva seu projeto em detalhes",
        style=discord.TextStyle.paragraph,
        placeholder="Explique a ideia central, o objetivo e como deve funcionar.",
        required=True,
        max_length=1000
    )
    features = ui.TextInput(
        label="Quais são as funcionalidades essenciais?",
        style=discord.TextStyle.paragraph,
        placeholder="Liste as funções essenciais. Ex: 1. Tickets, 2. Auto-role...",
        required=True,
        max_length=1000
    )
    budget = ui.TextInput(
        label="Orçamento (Opcional)",
        style=discord.TextStyle.short,
        placeholder="Você tem uma faixa de orçamento em mente?",
        required=False,
        max_length=100
    )
    deadline = ui.TextInput(
        label="Prazo Desejado (Opcional)",
        style=discord.TextStyle.short,
        placeholder="Existe um prazo final para a entrega?",
        required=False,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔄 Seu pedido está sendo processado...", ephemeral=True, delete_after=5)

        try:
            guild = interaction.guild
            category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)

            if not category:
                overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
                category = await guild.create_category(TICKET_CATEGORY_NAME, overwrites=overwrites)

            # Verificar se já existe um ticket para este usuário
            existing_ticket = discord.utils.get(
                category.text_channels,
                name=f"orcamento-{interaction.user.name.lower()}"
            )

            if existing_ticket:
                await interaction.followup.send(
                    f"❌ Você já possui um ticket aberto: {existing_ticket.mention}",
                    ephemeral=True
                )
                return

            ticket_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True
                )
            }

            ticket_channel = await category.create_text_channel(
                name=f"orcamento-{interaction.user.name.lower()}",
                overwrites=ticket_overwrites
            )

            embed = discord.Embed(
                title=f"📝 Novo Pedido de Orçamento #{ticket_channel.name.split('-')[1]}",
                description=f"**Solicitante:** {interaction.user.mention}\n**Canal:** {ticket_channel.mention}",
                color=Color.dark_teal(),
                timestamp=datetime.now()
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="🎯 Tipo de Projeto", value=f"```{self.project_type.value}```", inline=False)
            embed.add_field(name="📋 Descrição Detalhada", value=f"```{self.description.value}```", inline=False)
            embed.add_field(name="⚙️ Funcionalidades Essenciais", value=f"```{self.features.value}```", inline=False)

            if self.budget.value:
                embed.add_field(name="💰 Orçamento", value=f"```{self.budget.value}```", inline=True)
            if self.deadline.value:
                embed.add_field(name="⏰ Prazo", value=f"```{self.deadline.value}```", inline=True)

            embed.set_footer(text=f"ID do Usuário: {interaction.user.id}")

            # Mensagem de boas-vindas no ticket
            welcome_embed = discord.Embed(
                title="🎉 Bem-vindo ao seu ticket de orçamento!",
                description=f"Olá {interaction.user.mention}! Seu pedido foi recebido com sucesso.\n\n"
                            f"**📌 Próximos passos:**\n"
                            f"• Nossa equipe analisará seu projeto\n"
                            f"• Entraremos em contato em breve\n"
                            f"• Use os botões abaixo para gerenciar o ticket\n\n"
                            f"**⚠️ Importante:** Mantenha este canal para futuras comunicações.",
                color=Color.blue()
            )

            await ticket_channel.send(
                content=f"🔔 <@{OWNER_USER_ID}>, novo pedido de orçamento!",
                embeds=[welcome_embed, embed],
                view=TicketActionsView()
            )

            await interaction.followup.send(
                f"✅ **Ticket criado com sucesso!**\n"
                f"📍 Acesse seu canal: {ticket_channel.mention}\n"
                f"🔔 Nossa equipe foi notificada automaticamente.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ **Erro ao criar o ticket:** {str(e)}\n"
                f"Por favor, tente novamente ou contate um administrador.",
                ephemeral=True
            )


class BriefingView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Timeout None para persistência

    @ui.button(label="📝 Solicitar Orçamento", style=ButtonStyle.success, custom_id="briefing_start", emoji="🚀")
    async def start_briefing(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(BriefingModal())


class FormsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Registrar views persistentes
        self.bot.add_view(BriefingView())
        self.bot.add_view(TicketActionsView())

    @app_commands.command(name="forms", description="Cria o painel para solicitação de orçamentos.")
    @app_commands.default_permissions(administrator=True)
    async def forms(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏢 Central de Orçamentos Profissionais",
            description="**Transforme sua ideia em realidade!**\n\n"
                        "💡 Desenvolvemos soluções personalizadas para suas necessidades\n"
                        "🚀 Clique no botão abaixo para iniciar seu projeto\n"
                        "📋 Um formulário detalhado será apresentado\n"
                        "🎯 Receba um orçamento personalizado rapidamente\n\n"
                        "**⭐ Nossos serviços incluem:**\n"
                        "• Bots para Discord\n"
                        "• Websites e aplicações web\n"
                        "• Sistemas personalizados\n"
                        "• Automações e integrações",
            color=Color.from_rgb(47, 49, 54)
        )
        embed.set_footer(
            text="🔒 Ao solicitar um orçamento, um canal privado será criado exclusivamente para você.",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)

        await interaction.channel.send(embed=embed, view=BriefingView())
        await interaction.response.send_message("✅ Painel de formulários criado com sucesso!", ephemeral=True)

    @app_commands.command(name="add_persistent_views",
                          description="Adiciona views persistentes (usar após reiniciar o bot)")
    @app_commands.default_permissions(administrator=True)
    async def add_persistent_views(self, interaction: discord.Interaction):
        """Comando para recarregar views persistentes após reiniciar o bot"""
        self.bot.add_view(BriefingView())
        self.bot.add_view(TicketActionsView())
        await interaction.response.send_message("✅ Views persistentes adicionadas com sucesso!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(FormsCog(bot))