import asyncio
import logging
import os
import random
import sqlite3
import datetime
import discord
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


# Custom subclass of discord.py's Bot class that loads the JSON file for the user watchwords to a user_words attribute
class CustomBot(commands.Bot):
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


class Database:
    def __init__(self, db):
        self.db = db
        self.connection = sqlite3.connect(self.db)
        self.cursor = self.connection.cursor()
        logging.info(f"Connected to {self.db}")

        # Create the triggers table if it doesn't already exist
        self.cursor.executescript(open("triggers.sql", "r").read())
        self.connection.commit()

        self.cursor.executescript(open("sample.sql", "r").read())
        self.connection.commit()


Triggers = Database("triggers.db")


class Inventory:
    def __init__(self, cursor):
        self.cursor = cursor
        self.size = None
        self.popped_item = None
        self.list = None

    def size(self):
        self.size = Triggers.cursor.execute("SELECT COUNT(*) FROM inventory LIMIT 1;")
        return self.size

    def pop(self) -> str:
        """
        Randomly removes and returns one of the items in inventory.
        :return: randomly selected item from inventory
        """
        Triggers.cursor.execute("SELECT id FROM inventory ORDER BY RANDOM() LIMIT 1;")
        self.popped_item = Triggers.cursor.fetchone()[0]
        Triggers.cursor.execute("DELETE FROM inventory WHERE id=?;", [self.popped_item])
        Triggers.connection.commit()
        return self.popped_item

    def list(self):
        Triggers.cursor.execute("SELECT item FROM inventory;")
        self.list = [item_list[0] for item_list in Triggers.cursor.fetchall()]
        return self.list


OMEGA.inv = Inventory(Triggers.cursor)


class UpShutter:
    """
    Stops Omega from using triggered responses.
    """

    def __init__(self):
        self.shut_up_durations = {
            "for a bit": ("be back in a minute.", 60),
            "for a while": ("be back in five or so.", 300),
            "for now": ("be back in ten minutes.", 600),
        }
        self.shut_up_till = datetime.datetime.now() - datetime.timedelta(
            seconds=5
        )  # Default value: five seconds ago.
        self.parting_shot = (
            False  # Flag: if true, then allow a message past the shutting up.
        )

    def shut_up(self, for_how_long: str) -> str:
        try:
            response, duration = (
                self.shut_up_durations[for_how_long]
                if for_how_long in self.shut_up_durations
                else (
                    f"be back in {str(int(for_how_long))} seconds.",
                    for_how_long,
                )
            )
        except TypeError:
            response, duration = ("be back in 10 seconds.", 10)
        logging.info(f'"{str(duration)}"')
        self.shut_up_till = datetime.datetime.now() + datetime.timedelta(
            seconds=duration
        )
        return response

    def open_up(self):
        self.shut_up_till = datetime.datetime.now() - datetime.timedelta(seconds=5)

    def get_last_word(self):
        self.parting_shot = True

    def is_shut(self) -> bool:
        if self.parting_shot:
            self.parting_shot = False
            return False
        return False if self.shut_up_till < datetime.datetime.now() else True


OMEGA.shutting_up = UpShutter()


# Checks
def is_in_playground(ctx):
    return ctx.channel == OMEGA.get_channel(PLAYGROUND)


# Miscellaneous helper functions I need to move or eliminate in a refactor
def add(item: str):
    Triggers.cursor.execute("INSERT INTO inventory (item) VALUES (?);", (item,))
    Triggers.connection.commit()


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


# Startup stuff that's pretty much redundant atm but leaving this block here in case I need more startup stuff
@OMEGA.event
async def on_ready():
    logging.info(f"{OMEGA.user.name} is connected to the following servers:")
    for guild in OMEGA.guilds:
        logging.info(f"{guild.name}(id: {guild.id})")
    guild = discord.utils.get(OMEGA.guilds, name=SERVER)
    logging.info(f"Currently selected server: {guild.name}")
    await OMEGA.change_presence(
        activity=discord.Game(name=f"Questions? Type {OMEGA.command_prefix}help")
    )
    # members = "\n - ".join([member.name for member in guild.members])
    # logging.debug(f"Guild Members:\n - {members}")


# Commands
@OMEGA.command(
    name="scott",
    help="Responds with a Scott article (based on the arguments provided or random otherwise)",
)
async def scott_post(ctx, *args):
    logging.info(f"scott command invocation: {scott_post_helper(args)}")
    await ctx.send(scott_post_helper(args))


@OMEGA.command(
    name="iq",
    help="Takes a username, analyzes their post history to generate an estimate of their IQ",
)
@commands.check_any(
    commands.has_any_role("Regular", "Admin"), commands.check(is_in_playground)
)
async def estimate_iq(ctx, *args):
    if len(args) >= 1:
        queried_username = args[0]
        queried_iq_estimate = random.randint(25, 100)
        requester_iq_estimate = queried_iq_estimate - random.randint(5, 30)
        requester_username = ctx.message.author
        response = (
            f"Based on post history, {queried_username} has an IQ of approximately {queried_iq_estimate} "
            f"(which is {queried_iq_estimate - requester_iq_estimate} points higher than the estimated "
            f"value of {requester_iq_estimate} for {requester_username})."
        )
    else:
        requester_iq_estimate = random.randint(5, 65)
        requester_username = ctx.message.author
        response = (
            f"Based on the inability to follow the simple usage instructions for this command, and their post "
            f"history, the IQ of {requester_username} is estimated at {requester_iq_estimate}. "
        )
    await ctx.send(response)


@estimate_iq.error
async def estimate_iq_error(ctx, error):
    if isinstance(error, commands.errors.CheckAnyFailure):
        await ctx.send(
            f"Sorry, you don't have permission to use this command. "
            f"You can still use it in {OMEGA.get_channel(PLAYGROUND).mention}."
        )


@OMEGA.command(
    name="dev",
    help="Create a GitHub issue for feature requests, bug fixes, and other dev requests)",
)
@commands.has_any_role("Emoji Baron", "Admin")
async def create_github_issue(
    ctx, *args: commands.clean_content(fix_channel_mentions=True)
):
    issue = " ".join(list(args))
    logging.info(f"dev command invocation: {issue}")
    answer = create_github_issue_helper(ctx, issue)
    await ctx.send(answer)


@create_github_issue.error
async def create_github_issue_error(ctx, error):
    if isinstance(error, commands.errors.MissingAnyRole):
        await ctx.send("Sorry, you don't have permission to use this command.")


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
    logging.info(f"dice command invocation: {roll}")
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
    logging.info(f"watchword command invocation: {word}")
    try:
        server, member = process_watchword_input(ctx, word)
        answer = watchword_helper(server, member, word.lower())
    except commands.CommandError:
        answer = (
            f"Your format should be like {OMEGA.command_prefix}watchword cookie, "
            "where 'cookie' is replaced with the word you'd like to watch."
        )
    except commands.NoPrivateMessage:
        answer = "You may only use this command in servers."
    await ctx.send(answer)


def watchword_helper(server, member, word):
    if server not in OMEGA.user_words:
        OMEGA.user_words[server] = dict()
    if word not in OMEGA.user_words[server]:
        # TODO: check for chicanery
        OMEGA.user_words[server][word] = dict()
    if member in OMEGA.user_words[server][word]:
        answer = f'You are already watching "{word}".'
    else:
        OMEGA.user_words[server][word][member] = 1
        answer = f'You are now watching this server for "{word}".'
    return answer


# TODO: refactor watchword functions into one function as they have very similar logic
@OMEGA.command(
    name="del_watchword", help="Remove a word from the user's watchword list"
)
async def delete_watchword(ctx, word):
    logging.info(f"del_watchword command invocation: {word}")
    try:
        server, member = process_watchword_input(ctx, word)
        answer = delete_watchword_helper(server, member, word.lower())
    except commands.CommandError:
        answer = (
            f"Your format should be like {OMEGA.command_prefix}del_watchword cookie, "
            "where 'cookie' is replaced with the word you'd like to watch."
        )
    except commands.NoPrivateMessage:
        answer = "You may only use this command in servers."
    await ctx.send(answer)


def delete_watchword_helper(server, member, word):
    try:
        if OMEGA.user_words[server][word].pop(member, None):
            answer = f'You are no longer watching "{word}".'
        else:
            answer = f'You are not watching this server for "{word}".'
    except KeyError:
        answer = f'You are not watching this server for "{word}".'
    return answer


def process_watchword_input(ctx, word):
    if not word:
        raise commands.CommandError
    elif not ctx.message.guild:
        raise commands.NoPrivateMessage
    server = str(ctx.message.guild.id)
    member = str(ctx.message.author.id)
    return server, member


# Listeners
@OMEGA.listen("on_message")
async def notify_on_watchword(message):
    if message.author == OMEGA.user:
        return
    if message.content.startswith(OMEGA.command_prefix):
        return
    content = message.content.lower()
    content_list = message.content.lower().split()
    to_be_notified = set()
    for keyword in OMEGA.user_words[str(message.guild.id)].keys():
        if " " in keyword and keyword in content:
            for user in OMEGA.user_words[str(message.guild.id)][keyword]:
                to_be_notified.add(user)
                logging.info(
                    f"Sending {message.jump_url} to {OMEGA.get_user(int(user))} for watchword {keyword}"
                )
        elif " " not in keyword and keyword in content_list:
            for user in OMEGA.user_words[str(message.guild.id)][keyword]:
                to_be_notified.add(user)
                logging.info(
                    f"Sending {message.jump_url} to {OMEGA.get_user(int(user))} for watchword {keyword}"
                )
    await notify_users(message, to_be_notified)


async def notify_users(message, to_be_notified):
    for user in to_be_notified:
        await OMEGA.get_user(int(user)).send(
            "A watched word/phrase was detected!\n"
            f"Server: {message.guild}\n"
            f"Channel: {message.channel}\n"
            f"Author: {message.author}\n"
            f"Content: {message.content}\n"
            f"Link: {message.jump_url}"
        )


# Tasks
async def save_json():
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
