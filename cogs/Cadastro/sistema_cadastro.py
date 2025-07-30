import discord
from discord.ext import commands
from discord import app_commands, ui, ButtonStyle, Color
import os
import json
from datetime import datetime

DATA_DIR = os.path.join("data", "cadastros")
NAO_CADASTRADOS_FILE = os.path.join(DATA_DIR, "naocadastrados.json")
CADASTRADOS_FILE = os.path.join(DATA_DIR, "cadastrados.json")
CLIENTES_FILE = os.path.join(DATA_DIR, "clientes.json")

ROLE_NAO_CADASTRADO = "Não Cadastrado"
ROLE_CADASTRADO = "Cadastrado"
ROLE_CLIENTE = "Cliente"

LOG_CATEGORY_NAME = "Logs Cadastro"
LOG_ENTRADA_CHANNEL = "logs-entrada"
LOG_NAO_CLIENTE_CHANNEL = "logs-nao-sou-cliente"
LOG_CLIENTE_CHANNEL = "logs-sou-cliente"

def setup_data_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    for file_path in [NAO_CADASTRADOS_FILE, CADASTRADOS_FILE, CLIENTES_FILE]:
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f: json.dump({}, f)

def read_data(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def write_data(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

async def get_or_create_role(guild: discord.Guild, role_name: str, **kwargs):
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        role = await guild.create_role(name=role_name, **kwargs)
    return role

async def get_or_create_log_channel(guild: discord.Guild, channel_name: str):
    category = discord.utils.get(guild.categories, name=LOG_CATEGORY_NAME)
    if not category:
        overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
        category = await guild.create_category(LOG_CATEGORY_NAME, overwrites=overwrites)

    channel = discord.utils.get(category.text_channels, name=channel_name)
    if not channel:
        channel = await category.create_text_channel(channel_name)
    return channel

class NewUserModal(ui.Modal, title="Questionário de Cadastro"):
    source_info = ui.TextInput(label="Onde ouviu falar da Alvl Lab?", style=discord.TextStyle.short,
                               placeholder="Ex: YouTube, um amigo, outro servidor...", required=True, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        user_id_str = str(member.id)

        cadastrado_role = await get_or_create_role(guild, ROLE_CADASTRADO, color=Color.light_grey())
        nao_cadastrado_role = await get_or_create_role(guild, ROLE_NAO_CADASTRADO)
        await member.add_roles(cadastrado_role)
        await member.remove_roles(nao_cadastrado_role)

        cadastrados_data = read_data(CADASTRADOS_FILE)
        nao_cadastrados_data = read_data(NAO_CADASTRADOS_FILE)
        cadastrados_data[user_id_str] = {"username": member.name, "source": self.source_info.value,
                                         "registration_date": datetime.utcnow().isoformat()}
        if user_id_str in nao_cadastrados_data: del nao_cadastrados_data[user_id_str]
        write_data(CADASTRADOS_FILE, cadastrados_data)
        write_data(NAO_CADASTRADOS_FILE, nao_cadastrados_data)

        log_channel = await get_or_create_log_channel(guild, LOG_NAO_CLIENTE_CHANNEL)
        embed = discord.Embed(title="📝 Novo Cadastro", color=Color.green(), timestamp=datetime.now())
        embed.set_author(name=f"{member.name} ({member.id})", icon_url=member.display_avatar.url)
        embed.add_field(name="Como nos conheceu?", value=self.source_info.value, inline=False)
        await log_channel.send(embed=embed)

        await interaction.response.send_message("🎉 Bem-vindo(a)! Seu cadastro foi concluído.", ephemeral=True)

class ClientModal(ui.Modal, title="Verificação de Cliente"):
    project_info = ui.TextInput(label="Escreva aqui o projeto que fez comigo", style=discord.TextStyle.paragraph,
                                placeholder="Ex: Bot de moderação para o servidor X...", required=True, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        user_id_str = str(member.id)

        cliente_role = await get_or_create_role(guild, ROLE_CLIENTE, color=Color.gold())
        cadastrado_role = await get_or_create_role(guild, ROLE_CADASTRADO)
        nao_cadastrado_role = await get_or_create_role(guild, ROLE_NAO_CADASTRADO)
        await member.add_roles(cliente_role)
        await member.remove_roles(cadastrado_role, nao_cadastrado_role)

        clientes_data, cadastrados_data, nao_cadastrados_data = read_data(CLIENTES_FILE), read_data(
            CADASTRADOS_FILE), read_data(NAO_CADASTRADOS_FILE)
        clientes_data[user_id_str] = {"username": member.name, "project_info": self.project_info.value,
                                      "registration_date": datetime.utcnow().isoformat()}
        if user_id_str in cadastrados_data: del cadastrados_data[user_id_str]
        if user_id_str in nao_cadastrados_data: del nao_cadastrados_data[user_id_str]
        write_data(CLIENTES_FILE, clientes_data);
        write_data(CADASTRADOS_FILE, cadastrados_data);
        write_data(NAO_CADASTRADOS_FILE, nao_cadastrados_data)

        log_channel = await get_or_create_log_channel(guild, LOG_CLIENTE_CHANNEL)
        embed = discord.Embed(title="⭐ Novo Cliente Verificado", color=Color.gold(), timestamp=datetime.now())
        embed.set_author(name=f"{member.name} ({member.id})", icon_url=member.display_avatar.url)
        embed.add_field(name="Projeto Informado", value=self.project_info.value, inline=False)
        await log_channel.send(embed=embed)

        await interaction.response.send_message("✅ Upgrade concluído! Seu acesso como **Cliente** foi liberado.",
                                                ephemeral=True)

class RegistrationView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Não sou Cliente", style=ButtonStyle.secondary, custom_id="reg_new_user")
    async def new_user_button(self, interaction: discord.Interaction, button: ui.Button):
        if str(interaction.user.id) in read_data(CADASTRADOS_FILE) or str(interaction.user.id) in read_data(
                CLIENTES_FILE):
            await interaction.response.send_message("Você já concluiu seu cadastro.", ephemeral=True)
            return
        await interaction.response.send_modal(NewUserModal())

    @ui.button(label="Já sou Cliente", style=ButtonStyle.primary, custom_id="reg_existing_client")
    async def existing_client_button(self, interaction: discord.Interaction, button: ui.Button):
        if str(interaction.user.id) in read_data(CLIENTES_FILE):
            await interaction.response.send_message("Você já possui o status de Cliente.", ephemeral=True)
            return
        await interaction.response.send_modal(ClientModal())

class RegistrationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        setup_data_files()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        guild = member.guild
        user_id_str = str(member.id)

        try:
            role = await get_or_create_role(guild, ROLE_NAO_CADASTRADO, permissions=discord.Permissions.none())
            await member.add_roles(role)

            nao_cadastrados_data = read_data(NAO_CADASTRADOS_FILE)
            nao_cadastrados_data[user_id_str] = {"username": member.name, "join_date": datetime.utcnow().isoformat()}
            write_data(NAO_CADASTRADOS_FILE, nao_cadastrados_data)

            log_channel = await get_or_create_log_channel(guild, LOG_ENTRADA_CHANNEL)
            embed = discord.Embed(title="📥 Novo Membro Entrou", description=f"{member.mention} se juntou ao servidor.",
                                  color=Color.blue(), timestamp=datetime.now())
            embed.set_author(name=f"{member.name} ({member.id})", icon_url=member.display_avatar.url)
            embed.add_field(name="Data da Conta", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
            embed.set_footer(text=f"Total de membros: {guild.member_count}")
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Ocorreu um erro ao processar a entrada do membro {member.name}: {e}")


    @app_commands.command(name="cadastro_painel", description="Cria o painel de boas-vindas e cadastro.")
    @app_commands.default_permissions(administrator=True)
    async def registration_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(title=f"👋 Bem-vindo(a) ao {interaction.guild.name}!",
                              description="Para ter acesso completo aos nossos canais, por favor, identifique-se abaixo.",
                              color=Color.blurple())
        await interaction.channel.send(embed=embed, view=RegistrationView())
        await interaction.response.send_message("✅ Painel de cadastro criado com sucesso!", ephemeral=True)

async def setup(bot: commands.Cog):
    await bot.add_cog(RegistrationCog(bot))