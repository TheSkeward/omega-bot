import asyncio
import os
import random
import discord
import requests
import ujson
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SERVER = os.getenv("DISCORD_SERVER_NAME")
SERVER_SHORT = os.getenv("DISCORD_SERVER_NAME_SHORT")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GITHUB_PAT = os.getenv("GITHUB_PAT")
REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")
USER_WORDS_FILE = os.getenv("USER_WORDS_FILE")


class CustomBot(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        if os.path.isfile(USER_WORDS_FILE):
            with open(USER_WORDS_FILE) as word_data:
                self.user_words = ujson.load(word_data)
            print("Data loaded successfully.")
        else:
            print("No data file provided. No user data loaded.")


OMEGA = CustomBot(command_prefix="!o ", intents=discord.Intents.all())


def random_line(filename):
    lines = open(filename).read().splitlines()
    return random.choice(lines)


def ssc_search_query(search):
    api_endpoint = "https://www.googleapis.com/customsearch/v1"
    return f"{api_endpoint}?key={GOOGLE_API_KEY}&cx=7e281d64bc7d22cb7&q={search}"


def scott_post_helper(args):
    response = random_line("scott_links.txt")
    if args:
        query = ""
        for item in args:
            if " " in item:
                query += f'"{item}" '
            else:
                query += f"{item} "
        try:
            response = requests.get(ssc_search_query(query)).json()["items"][0]["link"]
        except KeyError:
            response = "No matches found."
    return response


@OMEGA.event
async def on_ready():
    print(f"{OMEGA.user.name} is connected to the following servers:")
    for guild in OMEGA.guilds:
        print(f"{guild.name}(id: {guild.id})")
    guild = discord.utils.get(OMEGA.guilds, name=SERVER)
    print(f"Currently selected server: {guild.name}")
    await OMEGA.change_presence(
        activity=discord.Game(name=f"Questions? Type {OMEGA.command_prefix}help")
    )
    # members = "\n - ".join([member.name for member in guild.members])
    # print(f"Guild Members:\n - {members}")


@OMEGA.command(
    name="scott",
    help="Responds with a Scott article (based on the arguments provided or random otherwise)",
)
async def scott_post(ctx, *args):
    print("scott command invocation:")
    print(scott_post_helper(args))
    await ctx.send(scott_post_helper(args))


@OMEGA.command(
    name="iq",
    help="Takes a username, analyzes their post history to generate an estimate of their IQ",
)
async def estimate_iq(ctx, *args):
    if len(args) >= 1:
        queried_username = args[0]
        queried_iq_estimate = random.randint(25, 100)
        requester_iq_estimate = queried_iq_estimate - random.randint(5, 30)
        requester_username = ctx.message.author
        response = f"Based on post history, {queried_username} has an IQ of approximately {queried_iq_estimate} (which is {queried_iq_estimate - requester_iq_estimate} points higher than the estimated value of {requester_iq_estimate} for {requester_username}) "
    else:
        requester_iq_estimate = random.randint(5, 65)
        requester_username = ctx.message.author
        response = (
            f"Based on the inability to follow the simple usage instructions for this command, and their post "
            f"history, the IQ of {requester_username} is estimated at {requester_iq_estimate}. "
        )
    await ctx.send(response)


@OMEGA.command(
    name="dev",
    help="Create a GitHub issue for feature requests, bug fixes, and other dev requests)",
)
async def create_github_issue(
    ctx, *args: commands.clean_content(fix_channel_mentions=True)
):
    issue = " ".join(list(args))
    print(f"dev command invocation: {issue}")
    answer = create_github_issue_helper(ctx, issue)
    await ctx.send(answer)


def create_github_issue_helper(ctx, issue):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = dict(
        Authorization=f"token {GITHUB_PAT}", Accept="application/vnd.github.v3+json"
    )
    data = {
        "title": issue,
        "body": f"Issue created by {ctx.message.author}.",
    }
    payload = ujson.dumps(data)
    response = requests.request("POST", url, data=payload, headers=headers)
    if response.status_code == 201:
        answer = f"Successfully created Issue: '{issue}'\nYou can add more detail here: {response.json()['html_url']}"
    else:
        answer = f"Could not create Issue: '{issue}'\nResponse: {response.content}"
    return answer


@OMEGA.command(name="roll", help="Accepts rolls in the form #d#")
async def roll_dice(ctx, arg: commands.clean_content(fix_channel_mentions=True)):
    roll = arg.split("d")
    print(f"dice command invocation: {roll}")
    answer = roll_dice_helper(roll)
    await ctx.send(answer)


def roll_dice_helper(roll):
    results = []
    if len(roll) != 2:
        answer = (
            "Your format should be '#d#', with the first '#' representing how many dice you'd like to roll and "
            "the second '#' representing the number of sides on the die. "
        )
        return answer
    if roll[0] == "":
        roll[0] = 1
    try:
        roll = [int(roll[0]), int(roll[1])]
    except ValueError:
        answer = (
            "Your format should be '#d#', with the first '#' representing how many dice you'd like to roll and "
            "the second '#' representing the number of sides on the die. "
        )
        return answer
    if roll[0] < 1 or roll[0] > 100:
        answer = (
            "Your format should be '#d#' with the first '#' representing how many dice you'd like to roll. "
            "Please pick a number between 1 and 100 for it. "
        )
        return answer
    if roll[1] < 2 or roll[1] > 1000000:
        answer = (
            "Your format should be '#d#' with the second '#' representing the number of sides on the die. "
            "Please pick a number between 2 and 1000000 for it. "
        )
        return answer
    for die in range(roll[0]):
        results.append(random.randint(1, roll[1]))
    answer = f"You rolled: {results}"
    if len(results) > 1:
        total = sum(results)
        answer = f"You rolled {total}: {results}"
    return answer


@OMEGA.command(
    help="Start watching a word to be alerted every time that phrase is used."
)
async def watchword(ctx, word):
    print(f"watchword command invocation: {word}")
    if not word:
        answer = (
            f"Your format should be like {OMEGA.command_prefix}watchword cookie, "
            "where 'cookie' is replaced with the word you'd like to watch."
        )
    elif not ctx.message.server:
        answer = "You may only use this command in servers."
    else:
        answer = watchword_helper(ctx, word.lower())
    await ctx.send(answer)


def watchword_helper(ctx, word):
    server_id = ctx.message.server.id
    member = ctx.message.author
    if server_id not in OMEGA.user_words:
        OMEGA.user_words[server_id] = dict()
    if word not in OMEGA.user_words[server_id]:
        # TODO: check for chicanery
        OMEGA.user_words[server_id][word] = set()
    if member.id in OMEGA.user_words[server_id][word]:
        answer = f'You are already watching "{word}".'
    else:
        answer = f"You are now watching this server for {word}."
    OMEGA.user_words[server_id][word].add(member.id)
    return answer


@OMEGA.event
async def on_message(message):
    if message.author == OMEGA.user:
        return
    if message.content.startswith(OMEGA.command_prefix):
        return
    content = message.content.lower()
    for member, servers in OMEGA.user_words.items():
        if message.server.id not in servers:
            continue
        user = OMEGA.get_user(member)
        # this command has to be run like this from the OMEGA object because it's the client that the commands are
        # attached to - if you try to do discord.Client.get_user it will be missing the self parameter.
        for keyword in servers[message.server.id].items():
            if keyword in content:
                await user.send(
                    "A watched word/phrase was detected!"
                    f"Server: {message.server}"
                    f"Channel: {message.channel}"
                    f"Author: {message.author}"
                    f"Content: {message.content}"
                    f"Link: {message.channel.mention}"
                )


async def save_json():
    await OMEGA.wait_until_ready()
    while not OMEGA.is_closed():
        await asyncio.sleep(900)
        file = open(USER_WORDS_FILE)
        file.write(ujson.dumps(OMEGA.user_words))
        file.close()
        print(f"Saving user data!")


if __name__ == "__main__":
    OMEGA.run(TOKEN)
