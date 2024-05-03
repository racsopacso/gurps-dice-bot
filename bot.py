
import os

from collections import defaultdict
import asyncio

import discord
from discord.ext import commands, tasks

from pydantic import ValidationError

import discord.types
import discord.types.emoji
from player_defn import Player, Skill, PlayerManager, to_comp_name, format_skill_list, load_from_files
from sheets_request import get_sheet_for_user

playerdict = load_from_files()

DISCORD_TOKEN_FILE = "disc.tok"

try:
    with open(DISCORD_TOKEN_FILE, "r") as f:
        token = f.read()  

except:
    raise RuntimeError("Discord token file not found")

#real
GUILD_ID = 1221442571965038763

#testing
GUILD_ID = 723899751732346960

GUILD = discord.Object(id=GUILD_ID)

class Client(discord.Client):
    def __init__(self, intents):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self):
        self.tree.copy_global_to(guild=GUILD)

        # self.guild = self.get_guild(GUILD_ID)

        # self.noodles = discord.utils.get(self.guild.emojis, name="noodles")

        await self.tree.sync(guild=GUILD)

intents = discord.Intents.default()
intents.message_content = True

client = Client(intents=intents)

# async def reaction_task(msg: discord.webhook.WebhookMessage, timeout: int, user_id: int, *reactions: discord.Emoji | str):
#     reactions_set = {reaction for reaction in reactions}
    
#     for reaction in reactions:
#         await msg.add_reaction(reaction)

#     for _ in range(timeout * 5):
#         await asyncio.sleep(0.2)

#         for reaction in msg.reactions:
#             if reaction.emoji in reactions_set:
#                 async for react_user in reaction.users():
#                     if react_user.id == user_id:
#                         return reaction
    
#     return None

# def get_emoji(msg: discord.webhook.WebhookMessage, emoji: str):
#     return discord.utils.get(msg.guild.emojis, name="reaction")

# def reaction_check(msg: discord.webhook.WebhookMessage, timeout: int, user_id: int, *reactions: str | discord.Emoji):
#     return asyncio.create_task(reaction_task(msg, timeout, user_id, *reactions))


async def update_from_sheet_func(interaction: discord.Interaction, google_sheets_id: str):
    await interaction.followup.send("Trying to fetch your sheet...", ephemeral=True)
    
    skills = get_sheet_for_user(google_sheets_id)

    if skills == None:
        await interaction.followup.send(f"Failed to reach url {google_sheets_id}", ephemeral=True)
        
        return

    else:
        skillstr = format_skill_list(skills)
        await interaction.followup.send(f"Contacted sheet. Pulled the following skills: {skillstr}", ephemeral=True)

        skilldict = {skill.comp_name: skill for skill in skills}

    async with playerdict[interaction.user.id] as player_obj:
        player_obj.skills = skilldict

@client.tree.command()
async def update_from_sheet(interaction: discord.Interaction, google_sheets_id: str):
    if interaction.user.id not in playerdict:
        await interaction.response.send_message("Unrecognised user", ephemeral=True)

    else:
        await interaction.response.send_message("Recognised user", ephemeral=True)
    await update_from_sheet_func(interaction, google_sheets_id)

@client.tree.command()
async def register(interaction: discord.Interaction, google_sheets_id: str | None = None):
    """
    Use this to add yourself to the system, and maybe pull information from a sheet
    """
    if interaction.user.id not in playerdict:
        playerdict[interaction.user.id] = PlayerManager.from_id(discord_id=interaction.user.id, google_sheets_id=google_sheets_id)

        await interaction.response.send_message("Adding you to list of users...", ephemeral=True)
    
    else:
        await interaction.response.send_message("User already recognises", ephemeral=True)

        return

    if google_sheets_id:
        await update_from_sheet_func(interaction, google_sheets_id)
        
    
    # playerdict[interaction.user.id] = Player(
    #     discord_id=interaction.user.id, 
    #     google_sheets_id=google_sheets_id,
    #     skills=skilldict,
    #     timers=[])

@client.tree.command()
async def modify_skill(interaction: discord.Interaction, skill_name: str, skill_level: int):
    skill_name = skill_name.lower()

    if interaction.user.id not in playerdict:
        await interaction.response.send_message("You're not registered. Use /register first.", ephemeral=True)
        return

    async with playerdict[interaction.user.id] as player_obj:
        # if skill_name in player_obj.skills:
        #     await interaction.response.send_message(f"Skill {skill_name} already present! ", ephemeral=True)
        #     return

        try:
            new_skill = Skill(
                name = skill_name,
                value= skill_level
            )
        
        except ValidationError:
            await interaction.response.send_message(f"Failure validating skill", ephemeral=True)
            return

        player_obj.add_skill(new_skill)

    await interaction.response.send_message("Succesfully added skill", ephemeral=True)

@client.tree.command()
async def list_skills(interaction: discord.Interaction, skill_name: str | None = None):
    async with playerdict[interaction.user.id] as player_obj:
        if skill_name is not None:
            skill_name = to_comp_name(skill_name)

            if skill_name in player_obj.skills:
                await interaction.response.send_message(str(player_obj.skills[skill_name]), ephemeral=True)

            else:
                await interaction.response.send_message(f"Skill `{skill_name}` not found", ephemeral=True)
        
        else:
            await interaction.response.send_message(format_skill_list(player_obj.skills.values()), ephemeral=True)

@client.tree.command()
async def roll(interaction: discord.Interaction, skill_name: str):
    skill_name = skill_name.lower()

    if interaction.user.id not in playerdict:
        await interaction.response.send_message("You're not registered. Use /register first.", ephemeral=True)
        return
    
    async with playerdict[interaction.user.id] as player_obj:
        if skill_name not in player_obj.skills:
            await interaction.response.send_message(f"Skill `{skill_name}` not recognised", ephemeral=True)
            return
        
        roll = player_obj.skills[skill_name].roll()

        await interaction.response.send_message(roll.markdown_obj)

@client.tree.command()
async def delete_skill(interaction: discord.Interaction, skill_name: str):
    skill_name = skill_name.lower()

    if interaction.user.id not in playerdict:
        await interaction.response.send_message("You're not registered. Use /register first.", ephemeral=True)
        return

    async with playerdict[interaction.user.id] as player_obj:
        if skill_name not in player_obj.skills:
            await interaction.response.send_message(f"Skill `{skill_name}` not present! ", ephemeral=True)
            return

        player_obj.remove_skill(skill_name)

    await interaction.response.send_message("Succesfully added skill", ephemeral=True)

client.run(token)
