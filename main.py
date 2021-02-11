"""General-purpose Discord bot designed for SlateStarCodex Discord server"""
import logging
import os
import random
import sqlite3
import string

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
SERVER_ID = int(os.getenv("DISCORD_SERVER_ID"))
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GITHUB_PAT = os.getenv("GITHUB_PAT")
REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")
MOD_CHAT = int(os.getenv("MOD_CHANNEL_ID"))
PLAYGROUND = int(os.getenv("BOT_PLAYGROUND_CHANNEL_ID"))


class CustomBot(commands.Bot):
    """Custom subclass of discord.py's Bot class that loads the database"""

    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.conn = sqlite3.connect("omega.db")
        self.cur = self.conn.cursor()
        logging.info("Connected to omega.db")
        self.cur.executescript(open("tables.sql", "r").read())
        self.conn.commit()
        self.cur.execute(
            "SELECT user_id, word FROM watchword where guild_id = (?);", (SERVER_ID,)
        )
        word_data = self.cur.fetchall()
        self.user_words = {}
        for pair in word_data:
            if pair[1] in self.user_words.keys():
                self.user_words[pair[1]].add(pair[0])
            else:
                self.user_words[pair[1]] = {pair[0]}
        logging.info("Bot initialization complete.")


OMEGA = CustomBot(
    command_prefix="!o ", intents=discord.Intents.all(), case_insensitive=True
)


# Checks
def is_in_playground(ctx):
    """Returns True if called from bot playground channel"""
    return ctx.channel == OMEGA.get_channel(PLAYGROUND)


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
            "Based on the inability to follow the simple usage instructions for this command, and "
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
        roll = (int(roll[0]), int(roll[1]))
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


@OMEGA.command(
    help="Start watching a word or phrase when it's used.", aliases=["watch"]
)
async def watchword(ctx, word):
    """Adds user, word, and server to a dictionary to be notified on matching message"""
    word = word.lower().translate(str.maketrans("", "", string.punctuation))
    logging.info("watchword command invocation: %s", word)
    if not ctx.message.guild:
        await ctx.send("This operation does not work in private message contexts.")
        return
    if not word or word.startswith(OMEGA.command_prefix):
        await ctx.send(
            f"That command contains an error. The syntax is as follows:\n`{OMEGA.command_prefix}"
            f'watchword "lorem ipsum"`\n`{OMEGA.command_prefix}watchword lorem`\nNote that '
            "watchwords that can never trigger, such as those beginning "
            "with a bot prefix, are automatically rejected."
        )
        return
    OMEGA.cur.execute(
        "SELECT EXISTS(SELECT 1 FROM user WHERE user_id=?);", (ctx.message.author.id,)
    )
    if not OMEGA.cur.fetchone():
        OMEGA.cur.execute(
            "INSERT INTO user (user_id) VALUES (?);", (ctx.message.author.id,)
        )
        OMEGA.conn.commit()
    OMEGA.cur.execute(
        "INSERT INTO watchword (guild_id, user_id, word) VALUES (?, ?, ?);",
        (ctx.message.guild.id, ctx.message.author.id, word),
    )
    OMEGA.conn.commit()
    if word in OMEGA.user_words:
        OMEGA.user_words[word].add(ctx.message.author.id)
    else:
        OMEGA.user_words[word] = {ctx.message.author.id}
    await ctx.send(f"You are now watching this server for {word}.")


@OMEGA.command(
    name="delete_word",
    help="Remove a word from the user's watchword list",
    aliases=["del_watchword", "unwatch"],
)
async def delete_watchword(ctx, word):
    """Removes user/word/server combination from watchword notification dictionary"""
    word = word.lower().translate(str.maketrans("", "", string.punctuation))
    logging.info("del_watchword command invocation: %s", word)
    if not ctx.message.guild:
        await ctx.send("This operation does not work in private message contexts.")
        return
    if not word or word.startswith(OMEGA.command_prefix):
        await ctx.send(
            f"That command contains an error. The syntax is as follows:\n`{OMEGA.command_prefix}"
            f'watchword "lorem ipsum"`\n`{OMEGA.command_prefix}watchword lorem`\nNote that '
            "watchwords that can never trigger, such as those beginning "
            "with a bot prefix, are automatically rejected."
        )
        return
    OMEGA.cur.execute(
        "DELETE FROM watchword WHERE guild_id = ? AND user_id = ? AND word = ?;",
        (ctx.message.guild.id, ctx.message.author.id, word),
    )
    OMEGA.conn.commit()
    if word in OMEGA.user_words and ctx.message.author.id in OMEGA.user_words[word]:
        OMEGA.user_words[word].remove(ctx.message.author.id)
        await ctx.send(f"You are no longer watching this server for {word}.")
    else:
        await ctx.send(f"You were not watching this server for {word}.")


@OMEGA.command(help="Replies with a list of all watchwords on this server.")
async def watched(ctx):
    """Gives user list of all watched words/phrases on the server."""
    logging.info("watched command invocation")
    if not ctx.message.guild:
        await ctx.send("This operation does not work in private message contexts.")
        return
    OMEGA.cur.execute(
        "SELECT word FROM watchword WHERE user_id=?;", (ctx.message.author.id,)
    )
    result = OMEGA.cur.fetchall()
    watched_str = ""
    for watched_word in result:
        watched_str += '"' + watched_word[0] + '", '
    watched_str = watched_str[:-2]
    await ctx.send(f"{ctx.author.name}'s watched words/phrases:\n{watched_str}")


@OMEGA.command(help="Toggle whether specified channel is in radio mode", hidden=True)
@commands.has_permissions(manage_messages=True)
async def radio(ctx):
    """Puts a channel into bot-enforced text-only mode"""
    logging.info("radio command invocation: %s", ctx.channel.name)
    await ctx.send(radio_helper(ctx.channel))


def radio_helper(channel):
    """Logic for radio command"""
    OMEGA.cur.execute(
        "SELECT EXISTS(SELECT 1 FROM radio WHERE channel_id=?);", (channel.id,)
    )
    if OMEGA.cur.fetchall()[0][0]:
        OMEGA.cur.execute("DELETE FROM radio WHERE channel_id=?;", (channel.id,))
        OMEGA.conn.commit()
        answer = "Radio mode is now off in this channel."
    else:
        OMEGA.cur.execute("INSERT INTO radio (channel_id) VALUES (?);", (channel.id,))
        OMEGA.conn.commit()
        answer = "Radio mode is now on in this channel."
    return answer


@radio.error
async def radio_error(ctx, error):
    """Error handling for radio command"""
    if isinstance(error, commands.errors.MissingPermissions):
        await ctx.send("Sorry, you lack the permissions to run this command.")


# @OMEGA.listen("on_command_error")
# async def on_command_error(ctx, error):
#     """Error handling for nonexistent commands"""
#     if isinstance(error, commands.CommandNotFound):
#         command_list = []
#         command_names = []
#         for command in OMEGA.walk_commands():
#             command_list.append(command)
#             command_names.append(command.name)
#             if command.aliases:
#                 command_names.extend(command.aliases)
#         (prefix, attempt, *args) = ctx.message.content.split()
#         distance, closest = min(
#             (textdistance.damerau_levenshtein.distance(attempt, elem), elem)
#             for elem in command_names
#         )
#         response = (
#             "A command was attempted to be invoked "
#             f"but no command under that name ({attempt}) is found. "
#         )
#         response += (
#             f'I think you meant "{prefix} {closest} {" ".join(args)}" '
#             # "- attempting to invoke that command now." TODO: Make this work
#             if distance < 2
#             else f'Did you mean "{prefix} {closest} {" ".join(args)}"?'
#             if distance == 2
#             else ""
#         )
#         await ctx.send(response)
#         if distance < 2:
#             await ctx.invoke(OMEGA.get_command(closest)(" ".join(args)))


# Listeners
@OMEGA.listen("on_message")
async def notify_on_watchword(message):
    """Listens to messages and notifies members when watchword conditions are met"""
    if message.author == OMEGA.user or message.content.startswith(OMEGA.command_prefix):
        return
    content = message.content.lower().translate(
        str.maketrans("", "", string.punctuation)
    )
    content_list = content.split()
    to_be_notified = set()
    for keyword in OMEGA.user_words:
        if " " in keyword and keyword in content:
            for user in OMEGA.user_words[keyword]:
                if (
                    discord.utils.get(message.channel.members, id=user)
                    and message.author.id != user
                ):
                    to_be_notified.add(user)
                    logging.info(
                        "Sending %s to %s for watchword %s",
                        message.jump_url,
                        OMEGA.get_user(user),
                        keyword,
                    )
        elif " " not in keyword and keyword in content_list:
            for user in OMEGA.user_words[keyword]:
                if (
                    discord.utils.get(message.channel.members, id=user)
                    and message.author.id != user
                ):
                    to_be_notified.add(user)
                    logging.info(
                        "Sending %s to %s for watchword %s",
                        message.jump_url,
                        OMEGA.get_user(user),
                        keyword,
                    )
    await notify_users(message, to_be_notified)


async def notify_users(message, to_be_notified):
    """Sends the watchword notification message to users in the notify set"""
    for user in to_be_notified:
        await OMEGA.get_user(user).send(
            "A watched word/phrase was detected! "
            f"{message.author.mention} in {message.channel.mention}\n"
            f"> {message.content}\n"
            f"Link: {message.jump_url}"
        )


# @OMEGA.listen("on_message")
# async def radio_mode_message(message):
#     """Listens to messages and deletes them if they're not text-only in a radio channel"""
#     if message.author == OMEGA.user:
#         return
#     cur.execute(
#         "SELECT EXISTS(SELECT 1 FROM radio WHERE channel_id=?);", (message.channel.id,)
#     )
#     if cur.fetchall()[0][0] and (
#         message.attachments
#         or emojis.count(message.content)
#         or any(
#             re.search(expression, message.content)
#             for expression in [
#                 r"<:\w*:\d*>",
#                 r"(([\w]+:)?//)?(([\d\w]|%[a-fA-f\d]{2})+(:([\d\w]|%[a-fA-f\d]{2})+)?@)"
#                 r"?([\d\w][-\d\w]{0,253}[\d\w]\.)+[\w]{2,63}(:[\d]+)?"
#                 r"(/([-+_~.\d\w]|%[a-fA-f\d]{2})*)"
#                 r"*(\?(&?([-+_~.\d\w]|%[a-fA-f\d]{2})=?)*)?(#([-+_~.\d\w]|%[a-fA-f\d]{2})*)?",
#             ]
#         )
#     ):
#         await message.delete()


@OMEGA.listen("on_reaction_add")
async def berk_inflation(reaction, user):
    """Adjusts for berk inflation"""
    if user == OMEGA.user:
        return
    try:
        if reaction.emoji.name not in ("3berk", "omniberk"):
            return
    except AttributeError:
        return
    inflated = True
    if reaction.emoji.name == "3berk":
        for react in reaction.message.reactions:
            if react.emoji.name == "berk" and react.count > 2:
                inflated = False
                break

    if reaction.emoji.name == "omniberk":
        for react in reaction.message.reactions:
            if react.emoji.name == "3berk" and react.count > 2:
                inflated = False
                break
    if inflated:
        await reaction.remove(user)


@OMEGA.listen("on_reaction_add")
async def report_mode(reaction, user):
    """Reports a post to the mod team"""
    if user == OMEGA.user:
        return
    if reaction.emoji == "📢":
        await OMEGA.get_channel(int(MOD_CHAT)).send(
            f"{reaction.message.author.mention} in {reaction.message.channel.mention} (reported by: {user.mention})\n"
            f"> {reaction.message.content}\n"
            f"Link: {reaction.message.jump_url}"
        )
        await reaction.remove(user)


# @OMEGA.listen("on_reaction_add")
# async def radio_mode_reaction(reaction, user):
#     """Listens to reactions and clears them if they're in a radio channel"""
#     if user == OMEGA.user:
#         return
#     cur.execute(
#         "SELECT COUNT(1) FROM radio WHERE channel_id=?;", (reaction.message.channel.id,)
#     )
#     if cur.fetchall()[0][0]:
#         await reaction.clear()


# Flipping the switch
if __name__ == "__main__":
    OMEGA.run(TOKEN)
