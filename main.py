"""General-purpose Discord bot designed for SlateStarCodex Discord server"""
import asyncio
import logging
import os
import random
import re
import sqlite3
import string

import discord
import emojis
import requests
import ujson
from discord.ext import commands
from dotenv import load_dotenv

# Logging setup
logging.basicConfig(level=logging.INFO)

# Initialize global variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SERVER = os.getenv("DISCORD_SERVER_NAME")
SERVER_SHORT = os.getenv("DISCORD_SERVER_NAME_SHORT")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GITHUB_PAT = os.getenv("GITHUB_PAT")
REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")
USER_WORDS_FILE = os.getenv("USER_WORDS_FILE")
PLAYGROUND = int(os.getenv("BOT_PLAYGROUND_CHANNEL_ID"))


class CustomBot(commands.Bot):
    """Custom subclass of discord.py's Bot class that loads the JSON file for the user watchwords"""

    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.inv = None
        self.shutting_up = None
        if os.path.isfile(USER_WORDS_FILE):
            with open(USER_WORDS_FILE) as word_data:
                self.user_words = ujson.load(word_data)
            logging.info("Data loaded successfully.")
        else:
            logging.warning("No data file provided. No user data loaded.")


OMEGA = CustomBot(
    command_prefix="!o ", intents=discord.Intents.all(), case_insensitive=True
)


connection = sqlite3.connect("omega.db")
cursor = connection.cursor()
logging.info("Connected to omega.db")

# Create the tables if they don't already exist
cursor.executescript(open("tables.sql", "r").read())
connection.commit()

# Feed in the data that needs to be there at startup no matter what
cursor.executescript(open("contents.sql", "r").read())
connection.commit()


# Checks
def is_in_playground(ctx):
    """Returns True if called from bot playground channel"""
    return ctx.channel == OMEGA.get_channel(PLAYGROUND)


# utility functions


def size():
    """Returns the size of Omega's inventory"""
    cursor.execute("SELECT COUNT(*) FROM inventory LIMIT 1;")
    return int(cursor.fetchone()[0])


def add(item: str):
    """Adds an item to Omega's inventory"""
    cursor.execute("INSERT INTO inventory (item) VALUES (?);", (item,))
    connection.commit()


def pop() -> str:
    """
    Randomly removes and returns one of the items Omega's inventory.
    """
    cursor.execute("SELECT id FROM inventory ORDER BY RANDOM() LIMIT 1;")
    popped_item = cursor.fetchone()[0]
    cursor.execute("DELETE FROM inventory WHERE id=?;", [popped_item])
    connection.commit()
    return popped_item


def inventory_list():
    """Returns a list of items in Omega's inventory"""
    cursor.execute("SELECT item FROM inventory;")
    return [item_tuple[0] for item_tuple in cursor.fetchall()]


@OMEGA.event
async def on_ready():
    """Startup stuff: Redundant atm but here as a placeholder for future init stuff"""
    logging.info("%s is connected to the following servers:", OMEGA.user.name)
    for guild in OMEGA.guilds:
        logging.info("%s(id: %s)", guild.name, guild.id)
    guild = discord.utils.get(OMEGA.guilds, name=SERVER)
    logging.info("Currently selected server: %s", guild.name)
    await OMEGA.change_presence(
        activity=discord.Game(name=f"Questions? Type {OMEGA.command_prefix}help")
    )
    # members = "\n - ".join([member.name for member in guild.members])
    # logging.debug(f"Guild Members:\n - {members}")


# Commands
@OMEGA.command(
    name="search",
    help="Responds with an article from the rationality community based on the arguments provided",
)
async def rat_search(ctx, *args):
    """Grabs an SSC article at random if no arguments, else results of a Google search"""
    logging.info("search command invocation: %s", args)
    await ctx.send(search_helper(args, "7e281d64bc7d22cb7"))


@OMEGA.command(
    name="scott",
    help="Responds with a Scott article (based on the arguments provided or random otherwise)",
)
async def scott_search(ctx, *args):
    """Grabs an SSC article at random if no arguments, else results of a Google search"""
    logging.info("scott command invocation: %s", args)
    await ctx.send(search_helper(args, "7e281d64bc7d22cb7"))


def search_helper(args, pseid):
    """Logic for the search commands"""
    response = random.choice(open("scott_links.txt").read().splitlines())
    if args:
        query = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
        try:
            response = requests.get(
                "https://www.googleapis.com/customsearch/v1"
                f"?key={GOOGLE_API_KEY}&cx={pseid}&q={query}"
            ).json()["items"][0]["link"]
        except KeyError:
            response = "No matches found."
    return response


@OMEGA.command(
    name="iq",
    help="Takes a username, analyzes their post history to generate an estimate of their IQ",
)
@commands.check_any(
    commands.has_any_role("Regular", "Admin"), commands.check(is_in_playground)
)
async def estimate_iq(ctx, *args):
    """Returns Omega's most accurate possible estimate of given username's IQ"""
    if len(args) >= 1:
        queried_username = args[0]
        queried_iq_estimate = random.randint(25, 100)
        requester_iq_estimate = queried_iq_estimate - random.randint(5, 30)
        requester_username = ctx.message.author
        response = (
            f"Based on post history, {queried_username} has an IQ of approximately "
            f"{queried_iq_estimate} (which is {queried_iq_estimate - requester_iq_estimate} points "
            f"higher than the estimated value of {requester_iq_estimate} for {requester_username})."
        )
    else:
        requester_iq_estimate = random.randint(5, 65)
        requester_username = ctx.message.author
        response = (
            f"Based on the inability to follow the simple usage instructions for this command, and "
            f"their post history, the IQ of {requester_username} is estimated at "
            f"{requester_iq_estimate}."
        )
    await ctx.send(response)


@estimate_iq.error
async def estimate_iq_error(ctx, error):
    """Error function for IQ command"""
    if isinstance(error, commands.errors.CheckAnyFailure):
        await ctx.send(
            "Sorry, you lack any of the roles required to run this command "
            f"outside of {OMEGA.get_channel(PLAYGROUND).mention}. "
        )


@OMEGA.command(
    name="dev",
    help="Create a GitHub issue for feature requests, bug fixes, and other dev requests)",
)
@commands.has_any_role("Emoji Baron", "Admin")
async def create_github_issue(
    ctx, *args: commands.clean_content(fix_channel_mentions=True)
):
    """Creates a Github issue (for bug reports and feature requests)"""
    issue = " ".join(list(args))
    logging.info("dev command invocation: %s", issue)
    answer = create_github_issue_helper(ctx, issue)
    await ctx.send(answer)


def create_github_issue_helper(ctx, issue):
    """Logic for dev command"""
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
        answer = (
            f"Successfully created Issue: '{issue}'You can add more detail here: "
            f"{response.json()['html_url']}"
        )
    else:
        answer = f"Could not create Issue: '{issue}'\nResponse: {response.content}"
    return answer


@create_github_issue.error
async def create_github_issue_error(ctx, error):
    """Error function for dev command"""
    if isinstance(error, commands.errors.MissingAnyRole):
        await ctx.send("Sorry, you lack any of the roles required to run this command.")


@OMEGA.command(name="roll", help="Accepts rolls in the form #d#")
async def roll_dice(ctx, arg: commands.clean_content(fix_channel_mentions=True)):
    """Rolls #d# dice"""
    roll = arg.split("d")
    logging.info("dice command invocation: %s", roll)
    answer = roll_dice_helper(roll)
    await ctx.send(answer)


def roll_dice_helper(roll):
    """Logic for roll command"""
    if len(roll) != 2:
        answer = (
            "Your format should be '#d#', with the first '#' representing how many dice you'd like "
            "to roll and the second '#' representing the number of sides on the die."
        )
        return answer
    if roll[0] == "":
        roll[0] = 1
    try:
        roll = [int(roll[0]), int(roll[1])]
    except ValueError:
        answer = (
            "Your format should be '#d#', with the first '#' representing how many dice you'd like "
            "to roll and the second '#' representing the number of sides on the die."
        )
        return answer
    if roll[0] < 1 or roll[0] > 100:
        answer = (
            "Your format should be '#d#' with the first '#' representing how many dice you'd like "
            "to roll. Please pick a number between 1 and 100 for it. "
        )
        return answer
    if roll[1] < 2 or roll[1] > 1000000:
        answer = (
            "Your format should be '#d#' with the second '#' representing the number of sides on "
            "the die. Please pick a number between 2 and 1000000 for it. "
        )
        return answer
    results = [(random.randint(1, roll[1])) for _ in range(roll[0])]
    answer = f"You rolled: {results}"
    if len(results) > 1:
        total = sum(results)
        answer = f"You rolled {total}: {results}"
    return answer


@OMEGA.command(help="Start watching a word or phrase when it's used.")
async def watchword(ctx, word):
    """Adds user, word, and server to a dictionary to be notified on matching message"""
    logging.info("watchword command invocation: %s", word)
    try:
        server, member = process_watchword_input(ctx, word)
        answer = watchword_helper(server, member, word.lower())
    except commands.NoPrivateMessage:
        answer = "This operation does not work in private message contexts."
    except commands.CommandError:
        answer = (
            f"That command contains an error. The syntax is as follows:\n`{OMEGA.command_prefix}"
            f"watchword 'lorem ipsum'`\n`{OMEGA.command_prefix}watchword lorem`\nNote that "
            "watchwords that can never trigger, such as those containing punctuation or beginning "
            "with a bot prefix, are automatically rejected."
        )
    await ctx.send(answer)


def watchword_helper(server, member, word):
    """Logic for watchword command"""
    if server not in OMEGA.user_words:
        OMEGA.user_words[server] = dict()
    if word not in OMEGA.user_words[server]:
        OMEGA.user_words[server][word] = dict()
    if member in OMEGA.user_words[server][word]:
        answer = f'You are already watching "{word}".'
    else:
        OMEGA.user_words[server][word][member] = 1
        answer = f'You are now watching this server for "{word}".'
    return answer


@OMEGA.command(
    name="delete_word",
    help="Remove a word from the user's watchword list",
    aliases=["del_watchword", "unwatch"],
)
async def delete_watchword(ctx, word):
    """Removes user/word/server combination from watchword notification dictionary"""
    logging.info("del_watchword command invocation: %s", word)
    try:
        server, member = process_watchword_input(ctx, word)
        answer = delete_watchword_helper(server, member, word.lower())
    except commands.NoPrivateMessage:
        answer = "This operation does not work in private message contexts."
    except commands.CommandError:
        answer = (
            f"That command contains an error. The syntax is as follows:\n`{OMEGA.command_prefix}"
            f"watchword 'lorem ipsum'`\n`{OMEGA.command_prefix}watchword lorem`\nNote that "
            "watchwords that can never trigger, such as those containing punctuation or beginning "
            "with a bot prefix, are automatically rejected."
        )
    await ctx.send(answer)


def delete_watchword_helper(server, member, word):
    """Logic for unwatch command"""
    try:
        if OMEGA.user_words[server][word].pop(member, None):
            answer = f'You are no longer watching "{word}".'
        else:
            answer = f'You are not watching this server for "{word}".'
    except KeyError:
        answer = f'"{word}" was not found in your set of existing watched words.'
    return answer


def process_watchword_input(ctx, word):
    """helper function for processing watchword input for related commands"""
    if (
        not word
        or word.startswith(OMEGA.command_prefix)
        or any(char in string.punctuation for char in word)
    ):
        raise commands.CommandError
    if not ctx.message.guild:
        raise commands.NoPrivateMessage
    server = str(ctx.message.guild.id)
    member = str(ctx.message.author.id)
    return server, member


@OMEGA.command(help="Toggle whether specified channel is in radio mode", hidden=True)
@commands.has_permissions(manage_messages=True)
async def radio(ctx):
    """Puts a channel into bot-enforced text-only mode"""
    logging.info("radio command invocation: %s", ctx.channel.name)
    await ctx.send(radio_helper(ctx.channel))


def radio_helper(channel):
    """Logic for radio command"""
    cursor.execute(
        "SELECT EXISTS(SELECT 1 FROM radio WHERE channel_id=?);", [channel.id]
    )
    if cursor.fetchall()[0][0]:
        cursor.execute("DELETE FROM radio WHERE channel_id=?;", [channel.id])
        connection.commit()
        answer = "Radio mode is now off in this channel."
    else:
        cursor.execute("INSERT INTO radio (channel_id) VALUES (?);", [channel.id])
        connection.commit()
        answer = "Radio mode is now on in this channel."
    return answer


@radio.error
async def radio_error(ctx, error):
    """Error handling for radio command"""
    if isinstance(error, commands.errors.MissingPermissions):
        await ctx.send("Sorry, you lack the permissions to run this command.")


# Listeners
@OMEGA.listen("on_message")
async def notify_on_watchword(message):
    """Listens to messages and notifies members when watchword conditions are met"""
    if message.author == OMEGA.user:
        return
    if message.content.startswith(OMEGA.command_prefix):
        return
    content = message.content.lower().translate(
        str.maketrans("", "", string.punctuation)
    )
    content_list = content.split()
    to_be_notified = set()
    for keyword in OMEGA.user_words[str(message.guild.id)].keys():
        if " " in keyword and keyword in content:
            for user in OMEGA.user_words[str(message.guild.id)][keyword]:
                if discord.utils.get(message.channel.members, id=int(user)):
                    to_be_notified.add(user)
                    logging.info(
                        "Sending %s to %s for watchword %s",
                        message.jump_url,
                        OMEGA.get_user(int(user)),
                        keyword,
                    )
        elif " " not in keyword and keyword in content_list:
            for user in OMEGA.user_words[str(message.guild.id)][keyword]:
                if discord.utils.get(message.channel.members, id=int(user)):
                    to_be_notified.add(user)
                    logging.info(
                        "Sending %s to %s for watchword %s",
                        message.jump_url,
                        OMEGA.get_user(int(user)),
                        keyword,
                    )
    await notify_users(message, to_be_notified)


async def notify_users(message, to_be_notified):
    """Sends the watchword notification message to users in the notify set"""
    for user in to_be_notified:
        if message.author.id != user:
            await OMEGA.get_user(int(user)).send(
                "A watched word/phrase was detected!\n"
                f"Server: {message.guild}\n"
                f"Channel: {message.channel}\n"
                f"Author: {message.author}\n"
                f"Content: {message.content}\n"
                f"Link: {message.jump_url}"
            )


@OMEGA.listen("on_message")
async def radio_mode_message(message):
    """Listens to messages and deletes them if they're not text-only in a radio channel"""
    if message.author == OMEGA.user:
        return
    cursor.execute(
        "SELECT EXISTS(SELECT 1 FROM radio WHERE channel_id=?);", [message.channel.id]
    )
    if cursor.fetchall()[0][0] and (
        message.attachments
        or emojis.count(message.content)
        or any(
            re.search(expression, message.content)
            for expression in [
                r"<:\w*:\d*>",
                r"(([\w]+:)?//)?(([\d\w]|%[a-fA-f\d]{2})+(:([\d\w]|%[a-fA-f\d]{2})+)?@)"
                r"?([\d\w][-\d\w]{0,253}[\d\w]\.)+[\w]{2,63}(:[\d]+)?"
                r"(/([-+_~.\d\w]|%[a-fA-f\d]{2})*)"
                r"*(\?(&?([-+_~.\d\w]|%[a-fA-f\d]{2})=?)*)?(#([-+_~.\d\w]|%[a-fA-f\d]{2})*)?",
            ]
        )
    ):
        await message.delete()


@OMEGA.listen("on_reaction_add")
async def radio_mode_reaction(reaction, user):
    """Listens to reactions and clears them if they're in a radio channel"""
    if user == OMEGA.user:
        return
    cursor.execute(
        "SELECT COUNT(1) FROM radio WHERE channel_id=?;", [reaction.message.channel.id]
    )
    if cursor.fetchall()[0][0]:
        await reaction.clear()


# Tasks
async def save_json():
    """Saves watchword dictionary to JSON file"""
    await OMEGA.wait_until_ready()
    while not OMEGA.is_closed():
        await asyncio.sleep(900)
        file = open(USER_WORDS_FILE, "w+")
        file.write(ujson.dumps(OMEGA.user_words))
        file.close()
        logging.info("Saving user data!")


# Flipping the switch
if __name__ == "__main__":
    OMEGA.loop.create_task(save_json())
    OMEGA.run(TOKEN)
