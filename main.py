import os
import random
import discord
import requests
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv('DISCORD_GUILD')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

OMEGA = commands.Bot(command_prefix='!o ', intents=discord.Intents.all())


def random_line(filename):
    lines = open(filename).read().splitlines()
    return random.choice(lines)


def ssc_search_query(search):
    api_endpoint = 'https://www.googleapis.com/customsearch/v1'
    return f'{api_endpoint}?key={GOOGLE_API_KEY}&cx=7e281d64bc7d22cb7&q={search}'


@OMEGA.event
async def on_ready():
    print(f'{OMEGA.user.name} is connected to the following servers:')
    for guild in OMEGA.guilds:
        print(f'{guild.name}(id: {guild.id})')
    guild = discord.utils.get(OMEGA.guilds, name=GUILD)
    print(f'Currently selected server: {guild.name}')

    members = '\n - '.join([member.name for member in guild.members])
    print(f'Guild Members:\n - {members}')


@OMEGA.command(name='scott', help='Responds with a Scott article (based on the arguments provided or random otherwise)')
async def scott_post(ctx, *args):
    print('scott command invocation:')
    if args == ():
        print('Served the following random article:')
        response = random_line('../../Desktop/Omega/scott_links.txt')
    else:
        query = ""
        for item in args:
            if " " in item:
                query += f'"{item}" '
            else:
                query += f'{item} '
        print(f"Served the following article based on the search query {query}:")
        response = requests.get(ssc_search_query(query)).json()['items'][0]['link']
    print(response)
    await ctx.send(response)

OMEGA.run(TOKEN)