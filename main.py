import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if not BOT_TOKEN:
    raise ValueError("O TOKEN do bot não foi encontrado no arquivo .env")
if not GUILD_ID:
    raise ValueError("O ID do servidor (GUILD_ID) não foi encontrado no arquivo .env")


class MeuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(command_prefix="!", intents=intents)
        self.guild_id = discord.Object(id=int(GUILD_ID))

    async def setup_hook(self):
        from cogs.Cadastro.sistema_cadastro import RegistrationView
        from cogs.vouches.sistema_avaliacao import ApprovalView
        from cogs.brefing.forms import BriefingView

        self.add_view(RegistrationView())
        self.add_view(ApprovalView())
        self.add_view(BriefingView())

        print("Carregando Cogs...")
        for root, dirs, files in os.walk('./cogs'):
            for filename in files:
                if filename.endswith('.py') and filename != '__init__.py':
                    module_path = os.path.join(root, filename)[:-3].replace(os.path.sep, '.').replace('./', '', 1)
                    try:
                        await self.load_extension(module_path)
                        print(f"  -> Cog '{module_path}' carregado com sucesso.")
                    except Exception as e:
                        print(f"Erro ao carregar o Cog '{module_path}': {e}")

        self.tree.copy_global_to(guild=self.guild_id)
        await self.tree.sync(guild=self.guild_id)
        print("Árvore de comandos sincronizada com o servidor.")

    async def on_ready(self):
        activity = discord.Streaming(name="Feito por alvl_dev", url="https://www.twitch.tv/placeholder")
        await self.change_presence(activity=activity)

        print("-" * 30)
        print(f'Bot {self.user} conectado ao Discord!')
        print(f'Operando no servidor: {self.get_guild(int(GUILD_ID)).name} (ID: {GUILD_ID})')
        print("-" * 30)


if __name__ == "__main__":
    bot = MeuBot()
    bot.run(BOT_TOKEN)