"""General-purpose Discord bot designed for SlateStarCodex Discord server"""
import datetime
import html.parser
import logging
import os
import random
import re
import sqlite3
import string
import time
from abc import ABC

import discord
import markdown
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
OMEGA = commands.Bot(command_prefix="!o ",
                     intents=discord.Intents.all(),
                     case_insensitive=True)
OMEGA.conn = None
OMEGA.cur = None
OMEGA.inventory_size = 20
OMEGA.user_words = {}
OMEGA.shut_up_durations = {
    "for a bit": ("be back in a minute.", 60),
    "for a while": ("be back in five or so.", 300),
    "for now": ("be back in ten minutes.", 600),
}
OMEGA.shut_up_til = datetime.datetime.now() - datetime.timedelta(
    seconds=5)  # Five seconds ago
OMEGA.parting_shot = False
OMEGA.logs = {}
OMEGA.logs_max = 100
OMEGA.slowmode_check_frequency = 600
OMEGA.slowmode_time_configs = {
    30: 600,
    26.25: 300,
    22.5: 120,
    18.75: 60,
    15: 30,
    11.25: 15,
    7.5: 10,
    3.75: 5,
}
OMEGA.message_cache = 0
OMEGA.user_cache = set()
OMEGA.last_updated = 0


class MessageJanitor(html.parser.HTMLParser, ABC):
    """
    Class to strip text out of HTML,
    to be used to strip the text out of the Markdown-turned-HTML.
    Make sure not to strip out HTML-looking markup, ie <reply>.
    """

    def __init__(self, message: str):
        super().__init__()
        self.reset()

        self.message = message
        self.replying = False
        self.sanitized = []

        # Start the sanitizing
        self.feed(markdown.markdown(message))

    def handle_starttag(self, tag, attrs):
        # Not very long-term if planning to add more attributes.
        if tag == "reply":
            self.sanitized.append("<reply>")
            self.replying = True

    def handle_data(self, data):
        if not self.replying:
            self.sanitized.append(data)

    def get_data(self):
        """
        If is a tidbit, then keep the markdown for the rest of the message.
        """
        if "<reply>" in self.message:
            offset = self.message.index("<reply>") + 6
            self.sanitized.append(self.message[offset:])
        return "".join(self.sanitized)


@OMEGA.event
async def on_ready():
    """Initialization"""
    OMEGA.conn = sqlite3.connect("omega.db")
    OMEGA.cur = OMEGA.conn.cursor()
    logging.info("Connected to omega.db")
    OMEGA.cur.executescript(open("tables.sql").read())
    OMEGA.conn.commit()
    logging.info("Logged in as %s (%s)", OMEGA.user.name, OMEGA.user.id)
    # Ignore self, or else Omega would respond to himself
    logging.info("Adding user: %s, id: %s to ignore list", OMEGA.user.name,
                 OMEGA.user.id)
    OMEGA.cur.execute(
        "INSERT OR IGNORE INTO user (user_id, ignoramus) VALUES (?, ?);",
        (OMEGA.user.id, True),
    )
    OMEGA.conn.commit()
    OMEGA.cur.execute(
        "SELECT user_id, word, channels FROM watchword where guild_id = (?);",
        (SERVER_ID,),
    )
    word_data = OMEGA.cur.fetchall()
    for triplet in word_data:
        channels = ujson.loads(triplet[2]) if triplet[2] else []
        OMEGA.user_words[triplet[1]] = {triplet[0]: {"channels": channels}}
    await OMEGA.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="- react 📢 to report a post, "
        "or DM me and react 📢 to your message for mod mail",
    ))
    logging.info("Bot initialization complete.")


# Checks
def is_in_playground(ctx):
    """Returns True if called from bot playground channel"""
    return ctx.channel == OMEGA.get_channel(PLAYGROUND)


# Checks
def is_in_silliness(ctx):
    """Returns True if called from silliness channel"""
    return ctx.channel == OMEGA.get_channel(465999263059673088)


# Commands
# @OMEGA.command(
#     name="search",
#     help="Responds with an article from the rationality community "
#     "based on the arguments provided",
# )
async def rat_search(ctx, *args):
    """Grabs an SSC article at random if no arguments,
    else results of a Google search"""
    logging.info("search command invocation: %s", args)
    await ctx.send(search_helper(args, "7e281d64bc7d22cb7"))


@OMEGA.command(
    name="scott",
    help="Responds with a Scott article "
    "(based on the arguments provided or random otherwise)",
)
async def scott_search(ctx, *args):
    """Grabs an SSC article at random if no arguments,
    else results of a Google search"""
    logging.info("scott command invocation: %s", args)
    if args:
        await ctx.send(search_helper(args, "2befc5589b259ca98"))
    else:
        await ctx.send(
            random.choice(open("scott_links.txt").read().splitlines()))


@OMEGA.command(
    name="xkcd",
    help="Responds with a relevant xkcd comic "
    "(based on the arguments provided or random otherwise)",
)
async def xkcd_search(ctx, *args):
    """Grabs an xkcd article at random if no arguments,
    else results of a Google search"""
    logging.info("xkcd command invocation: %s", args)
    if args:
        await ctx.send(search_helper(args, "e58fafa0a295b814c"))
    else:
        await ctx.send(
            f"http://xkcd.com/{random.randint(1, requests.get(f'http://xkcd.com/info.0.json').json().get('num'))}"
        )


def search_helper(args, pseid):
    """Logic for the search commands"""
    query = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
    response = "No matches found."
    try:
        response = requests.get("https://www.googleapis.com/customsearch/v1"
                                f"?key={GOOGLE_API_KEY}&cx={pseid}&q={query}"
                               ).json()["items"][0]["link"]
    except KeyError:
        pass
    return response


@OMEGA.command(
    name="iq",
    help="Takes a username, "
    "analyzes their post history to generate an estimate of their IQ",
)
@commands.check_any(commands.has_any_role("Regular", "Administrator"),
                    commands.check(is_in_playground))
async def estimate_iq(ctx, *args):
    """Returns Omega's most accurate possible estimate of given username's IQ"""
    requester_username = ctx.message.author.name
    if len(args) >= 1:
        queried_username = args[0]
        random.seed(queried_username)
        queried_iq_estimate = random.randint(25, 100)
        random.seed(requester_username)
        requester_iq_estimate = queried_iq_estimate - random.randint(5, 30)
        response = (
            f"Based on post history, {queried_username} has an IQ of "
            f"approximately {queried_iq_estimate} (which is "
            f"{queried_iq_estimate - requester_iq_estimate} points higher than "
            f"the estimated value of {requester_iq_estimate} for "
            f"{requester_username}).")
    else:
        random.seed(requester_username)
        requester_iq_estimate = random.randint(25, 100)
        response = (f"Based on post history, {requester_username} has an IQ of "
                    f"approximately {requester_iq_estimate}.")
    random.seed()
    await ctx.send(response)


@estimate_iq.error
async def estimate_iq_error(ctx, error):
    """Error function for IQ command"""
    if isinstance(error, commands.errors.CheckAnyFailure):
        await ctx.send(
            "Sorry, you lack any of the roles required to run this command "
            f"outside of {OMEGA.get_channel(PLAYGROUND).mention}. ")


@OMEGA.command(
    name="dev",
    help="Create a GitHub issue for feature requests, "
    "bug fixes, and other dev requests)",
)
@commands.has_any_role("Veteran", "Administrator")
async def create_github_issue(
    ctx, *args: commands.clean_content(fix_channel_mentions=True)):
    """Creates a Github issue (for bug reports and feature requests)"""
    issue = " ".join(list(args))
    logging.info("dev command invocation: %s", issue)
    answer = create_github_issue_helper(ctx, issue)
    await ctx.send(answer)


def create_github_issue_helper(ctx, issue):
    """Logic for dev command"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = dict(Authorization=f"token {GITHUB_PAT}",
                   Accept="application/vnd.github.v3+json")
    data = {
        "title": issue,
        "body": f"Issue created by {ctx.message.author}.",
    }
    payload = ujson.dumps(data)
    response = requests.request("POST", url, data=payload, headers=headers)
    if response.status_code == 201:
        answer = (f"Successfully created Issue: '{issue}'\n"
                  "You can add more detail here: "
                  f"{response.json()['html_url']}")
    else:
        answer = f"Could not create Issue: '{issue}'\n Response: {response.content}"
    return answer


@create_github_issue.error
async def create_github_issue_error(ctx, error):
    """Error function for dev command"""
    if isinstance(error, commands.errors.MissingAnyRole):
        await ctx.send(
            "Sorry, you lack any of the roles required to run this command.")


@OMEGA.command(name="roll", help="Accepts rolls in the form #d#")
async def roll_dice(ctx,
                    arg: commands.clean_content(fix_channel_mentions=True)):
    """Rolls #d# dice"""
    roll = arg.lower().split("d")
    logging.info("dice command invocation: %s", roll)
    answer = roll_dice_helper(roll)
    await ctx.send(answer)


def roll_dice_helper(roll):
    """Logic for roll command"""
    if len(roll) != 2:
        answer = (
            "Your format should be '#d#', with the first '#' representing how "
            "many dice you'd like to roll and the second '#' representing the "
            "number of sides on the die.")
        return answer
    if roll[0] == "":
        roll[0] = 1
    try:
        roll = (int(roll[0]), int(roll[1]))
    except ValueError:
        answer = (
            "Your format should be '#d#', with the first '#' representing how "
            "many dice you'd like to roll and the second '#' representing the "
            "number of sides on the die.")
        return answer
    if roll[0] < 1 or roll[0] > 100:
        answer = (
            "Your format should be '#d#' with the first '#' representing how "
            "many dice you'd like to roll. Please pick a number between 1 and "
            "100 for it. ")
        return answer
    if roll[1] < 2 or roll[1] > 1000000:
        answer = (
            "Your format should be '#d#' with the second '#' representing the "
            "number of sides on the die. Please pick a number between 2 and "
            "1000000 for it. ")
        return answer
    results = [(random.randint(1, roll[1])) for _ in range(roll[0])]
    answer = f"You rolled: {results}"
    if len(results) > 1:
        total = sum(results)
        answer = f"You rolled {total}: {results}"
    return answer


@OMEGA.command(
    help="Start watching a word or phrase to be alerted when it's used, with "
    f'an optional channel filter\n`{OMEGA.command_prefix}watchword "lorem '
    f'ipsum" #general #community`\n`{OMEGA.command_prefix}watchword lorem`.'
    f"\nCan input multiple watch words/phrases with one command (space separated).  For a phrase, use quotes.",
    aliases=["watch"],
)
async def watchword(ctx, word, *args):
    """Adds user, word, and server to a dictionary
    to be notified on matching message"""

    words = [word] + list(args)
    words = [
        word.lower().translate(str.maketrans("", "", string.punctuation))
        for word in words
    ]
    logging.info("watchword command invocation: %s", word)
    logging.info(
        "Current value for %s in dictionary prior to add: %s",
        word,
        OMEGA.user_words.get(word, -1),
    )
    if not ctx.message.guild:
        await ctx.send(
            "This operation does not work in private message contexts.")
        return
    if not word or word.startswith(OMEGA.command_prefix):
        await ctx.send(
            "That command contains an error. The syntax is as follows:\n"
            f'`{OMEGA.command_prefix} watchword "lorem ipsum"`\n'
            f"`{OMEGA.command_prefix}watchword lorem`\n"
            "Note that watchwords that can never trigger, "
            "such as those beginning with a bot prefix, "
            "are automatically rejected.")
        return
    for word in words:
        if word not in OMEGA.user_words:
            OMEGA.user_words[word] = dict()
        if ctx.message.author.id in OMEGA.user_words[word]:
            await ctx.send(f'You are already watching "{word}"')
            continue
        OMEGA.user_words[word][ctx.message.author.id] = dict()

        OMEGA.cur.execute(
            "SELECT EXISTS(SELECT 1 FROM user WHERE user_id=?);",
            (ctx.message.author.id,),
        )
        if not OMEGA.cur.fetchone():
            OMEGA.cur.execute("INSERT INTO user (user_id) VALUES (?);",
                              (ctx.message.author.id,))
            OMEGA.conn.commit()
        OMEGA.cur.execute(
            "INSERT INTO watchword (guild_id, user_id, word) VALUES (?, ?, ?);",
            (ctx.message.guild.id, ctx.message.author.id, word),
        )
        OMEGA.conn.commit()
        logging.info(
            "Added word if not present. Current value for %s in dictionary: %s",
            word,
            OMEGA.user_words[word],
        )
        await ctx.send(f"You are now watching this server for {word}.")


@OMEGA.command(
    name="delete_word",
    help="Remove a word from the user's watchword list",
    aliases=["del_watchword", "unwatch"],
)
async def delete_watchword(ctx, word):
    """Removes user/word/server combo from watchword notification dictionary"""
    word = word.lower().translate(str.maketrans("", "", string.punctuation))
    logging.info(
        "del_watchword command invocation: %s\n"
        "Current value for that word in dictionary: %s",
        word,
        OMEGA.user_words[word],
    )
    if not ctx.message.guild:
        await ctx.send(
            "This operation does not work in private message contexts.")
        return
    if not word or word.startswith(OMEGA.command_prefix):
        await ctx.send(
            "That command contains an error. The syntax is as follows:\n"
            f'`{OMEGA.command_prefix} watchword "lorem ipsum"`\n'
            f"`{OMEGA.command_prefix}watchword lorem`\n"
            "Note that watchwords that can never trigger, "
            "such as those beginning with a bot prefix, "
            "are automatically rejected.")
        return
    OMEGA.cur.execute(
        "DELETE FROM watchword WHERE guild_id = ? "
        "AND user_id = ? AND word = ?;",
        (ctx.message.guild.id, ctx.message.author.id, word),
    )
    OMEGA.conn.commit()
    if word in OMEGA.user_words and ctx.message.author.id in OMEGA.user_words[
            word]:
        del OMEGA.user_words[word][ctx.message.author.id]
        await ctx.send(f"You are no longer watching this server for {word}.")
        logging.info(
            "Removed word. Current value for %s in dictionary: %s",
            word,
            OMEGA.user_words.get(word, -1),
        )
    else:
        await ctx.send(f"You were not watching this server for {word}.")
        logging.info(
            "Did not detect word. Current value for %s in dictionary: %s",
            word,
            OMEGA.user_words[word],
        )


@OMEGA.command(help="Replies with a list of all your watchwords on this server."
              )
async def watched(ctx):
    """Gives user list of all watched words/phrases on the server."""
    logging.info("watched command invocation")
    if not ctx.message.guild:
        await ctx.send(
            "This operation does not work in private message contexts.")
        return
    OMEGA.cur.execute("SELECT word FROM watchword WHERE user_id=?;",
                      (ctx.message.author.id,))
    result = OMEGA.cur.fetchall()
    watched_str = ""
    for watched_word in result:
        watched_str += '"' + watched_word[0] + '", '
    watched_str = watched_str[:-2]
    await ctx.send(f"{ctx.author.name}'s watched words/phrases:\n{watched_str}")


@OMEGA.command(help="Bans user with provided reason.")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    logging.info(
        'Ban command invocation - ctx:"%s", member:"%s", reason:"%s"',
        ctx,
        member,
        reason,
    )
    if reason is None:
        embed = discord.Embed(
            title=f"Make sure you provide a ban reason, {ctx.author.name}",
            color=int("b3b3b3", 16),
        )
        await ctx.send(embed=embed)
    else:
        try:
            await member.send(
                f"You have been banned from {ctx.guild.name} for '{reason}'.")
            logging.info(
                "Just sent ban message to %s for %s",
                member.name,
                reason,
            )
        except discord.Forbidden:
            logging.info(
                "Attempted to send ban message to %s but failed as they have the bot blocked",
                member.name,
            )
        await ctx.guild.ban(discord.Object(id=member.id),
                            delete_message_days=0,
                            reason=reason)
        await ctx.guild.ban(
            discord.Object(id=member.id),
            delete_message_days=0,
            reason=ctx.message.jump_url,
        )
        if len(reason) < 256:
            embed = discord.Embed(
                title=f"{member.name} has been banned from "
                f"{ctx.guild.name} for {reason}",
                color=int("B37AE8", 16),
            )
            embed.add_field(name=f":newspaper: {reason}",
                            value=f"User id: {member.id}",
                            inline=True)
            embed.add_field(name="User joined:",
                            value=member.joined_at,
                            inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(
                f"{member.name} has been banned from {ctx.guild.name} for {reason}"
            )


@ban.error
async def ban_error(ctx, error):
    """Error handling for ban command"""
    if isinstance(error, commands.errors.MissingPermissions):
        await ctx.send(
            "You are missing Ban Members permission(s) to run this command.")


@OMEGA.command(help="Mutes user in #silliness", hidden=True)
@commands.has_permissions(manage_messages=True)
async def cw(ctx, member: discord.Member):
    if ctx.channel != OMEGA.get_channel(465999263059673088):
        await ctx.send("This command can only be run in #silliness.")
        return
    try:
        await member.send(
            "You have been muted in #silliness for posting CW content. "
            "Contact Bolas#6942 and see https://discord.com/channels/289207224075812864/465999263059673088/764871448929107998 for more information."
        )
        logging.info("CW ban message has been sent to user: %s", member.name)
    except discord.Forbidden:
        logging.info(
            "CW ban message not sent to user %s, because they have the bot blocked.",
            member.name,
        )
    await member.add_roles(
        discord.utils.get(member.guild.roles, name="No-Nonsense"))
    await ctx.send(
        f"{member.name} has been muted in #silliness for posting CW content.")


@cw.error
async def cw_error(ctx, error):
    """Error handling for cw command"""
    logging.info("Error: %s", error)
    if isinstance(error, commands.errors.MissingPermissions):
        await ctx.send(
            "You are missing Manage Messages permission(s) to run this command."
        )


@OMEGA.command(help="Toggle whether specified channel is in radio mode",
               hidden=True)
@commands.has_permissions(manage_messages=True)
async def radio(ctx):
    """Puts a channel into bot-enforced text-only mode"""
    logging.info("radio command invocation: %s", ctx.channel.name)
    await ctx.send(radio_helper(ctx.channel))


def radio_helper(channel):
    """Logic for radio command"""
    OMEGA.cur.execute("SELECT EXISTS(SELECT 1 FROM radio WHERE channel_id=?);",
                      (channel.id,))
    if OMEGA.cur.fetchall()[0][0]:
        OMEGA.cur.execute("DELETE FROM radio WHERE channel_id=?;",
                          (channel.id,))
        OMEGA.conn.commit()
        answer = "Radio mode is now off in this channel."
    else:
        OMEGA.cur.execute("INSERT INTO radio (channel_id) VALUES (?);",
                          (channel.id,))
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
async def notify_on_watchword(message: discord.Message):
    """Listens to messages
    and notifies members when watchword conditions are met"""
    if message.author == OMEGA.user or message.content.startswith(
            OMEGA.command_prefix):
        return
    content = message.content.lower().translate(
        str.maketrans("", "", string.punctuation))
    content_list = content.split()
    to_be_notified = set()
    for keyword in OMEGA.user_words:
        if " " in keyword and keyword in content:
            for user in OMEGA.user_words[keyword]:
                if (discord.utils.get(message.channel.members, id=user) and
                        message.author.id != user):
                    to_be_notified.add(user)
                    logging.info(
                        "Sending %s to %s for watchword %s",
                        message.jump_url,
                        OMEGA.get_user(user),
                        keyword,
                    )
        elif " " not in keyword and keyword in content_list:
            for user in OMEGA.user_words[keyword]:
                if (discord.utils.get(message.channel.members, id=user) and
                        message.author.id != user):
                    to_be_notified.add(user)
                    logging.info(
                        "Sending %s to %s for watchword %s",
                        message.jump_url,
                        OMEGA.get_user(user),
                        keyword,
                    )
    await notify_users(message, to_be_notified)


async def notify_users(message: discord.Message, to_be_notified):
    """Sends the watchword notification message to users in the notify set"""
    for user in to_be_notified:
        await OMEGA.get_user(user).send(
            "A watched word/phrase was detected! "
            f"{message.author.mention} in {message.channel.mention}\n"
            f"> {message.content}\n"
            f"Link: {message.jump_url}")


def sanitize_message(message: str) -> str:
    """
    Cleans up the message of markdown and end punctuation.
    """
    for outlawed in [
            re.compile(r"([^?]+)\?"),
            re.compile("([^!]+)!"),
            re.compile(r"([^.]+)\."),
    ]:
        convicted = outlawed.match(message)
        if convicted:
            message = outlawed.sub(
                convicted.group(1),
                message)  # Removes end punctuation IIF there's other text.
    return message


@OMEGA.listen("on_reaction_add")
async def berk_inflation(reaction: discord.Reaction, user: discord.User):
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
        try:
            await OMEGA.get_channel(int(MOD_CHAT)).send(
                f"{reaction.message.author.mention} "
                f"in {reaction.message.channel.mention} "
                f"(reported by: {user.mention})\n"
                f"> {reaction.message.content}\n"
                f"Link: {reaction.message.jump_url}")
            await reaction.remove(user)
            await user.send(
                "Thank you for your report! "
                "It has been sent to the mod team. "
                "You can type a response to me in this DM and react to your "
                "own message with 📢 if you want to add additional information.")
        except AttributeError:  # this means it's a DM
            await OMEGA.get_channel(int(MOD_CHAT)).send(
                f"Modmail from {reaction.message.channel}\n"
                f"> {reaction.message.content}")
            await reaction.message.channel.send(
                "Mod mail was sent to the mod team. "
                "Please wait for one of the mods to get back to you.")


# @OMEGA.listen("on_message")
# async def worthless_reply(message):
#     if message.reference is None or message.type == discord.MessageType.pins_add:
#         return
#     async for m in message.channel.history(limit=1, before=message):
#         if m.id == message.reference.message_id:
#             await message.add_reaction(OMEGA.get_emoji(625126592103972915))
#         break


@OMEGA.listen("on_message")
async def auto_slowmode(message):
    if time.time() >= OMEGA.last_updated + OMEGA.slowmode_check_frequency:
        delay = get_delay(OMEGA.message_cache, max(len(OMEGA.user_cache), 1))
        channel = OMEGA.get_channel(290695292964306948)
        if channel is not None:
            await channel.edit(slowmode_delay=delay)
        OMEGA.message_cache = 0
        OMEGA.user_cache = set()
        OMEGA.last_updated = time.time()
    if message.channel.id != 290695292964306948:
        return
    OMEGA.message_cache += 1
    OMEGA.user_cache.add(message.author)
    logging.info(f"{OMEGA.message_cache=}, {len(OMEGA.user_cache)=}, "
                 f"{OMEGA.message_cache / max(len(OMEGA.user_cache), 1)=}")


def get_delay(message_count, distinct_user_count):
    for limit in OMEGA.slowmode_time_configs:
        if message_count / distinct_user_count >= limit:
            return OMEGA.slowmode_time_configs[limit]
    return 0


# on_reaction_add doesn't work with old messages, and this is specifically going to be used on old messages a lot
# so let's just bypass its cleverness
@OMEGA.listen("on_raw_reaction_add")
async def workshop_pinbot(payload):
    """Watches for ZorbaTHut to pin-react things in #workshop, then pins them, removing a pin if necessary, because Zorba is lazy and hates removing pins manually"""

    # ZorbaTHut#4936
    if payload.user_id != 180974399543967744:
        return

    # #workshop
    if payload.channel_id != 832840713758441494:
        return

    # a pushpin, obviously
    if payload.emoji.name != "📌":
        return

    # Get the channel object, which isn't provided for us with on_raw_reaction_add
    channel = await OMEGA.fetch_channel(payload.channel_id)

    # Get the list of pins
    pins = await channel.pins()
    if len(pins) == 50:
        # too many pins, gonna have to remove one
        # but don't remove the sticky post that Zorba made at the beginning!
        if len(pins) > 0 and pins[-1].id == 832841374809849877:
            pins.pop()

        # found a pin to remove, do it
        if len(pins) > 0:
            await pins[-1].unpin()

    # Actually pin the thing we've been told to pin
    message = await channel.fetch_message(payload.message_id)
    await message.pin()


# @OMEGA.listen("on_reaction_add")
# async def radio_mode_reaction(reaction, user):
#     """Listens to reactions and clears them if they're in a radio channel"""
#     if user == OMEGA.user:
#         return
#     cur.execute(
#         "SELECT COUNT(1) FROM radio WHERE channel_id=?;",
#         (reaction.message.channel.id,)
#     )
#     if cur.fetchall()[0][0]:
#         await reaction.clear()

# Flipping the switch
if __name__ == "__main__":
    OMEGA.run(TOKEN)
