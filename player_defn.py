from __future__ import annotations

import os

import json
from typing import Any, Annotated, Iterable
from dataclasses import dataclass
from enum import Enum, auto

from pydantic import BaseModel, ValidationError, BeforeValidator, ConfigDict, model_validator, Field, StringConstraints, field_validator
from random import randrange

from asyncio import Lock

validate_assignment = ConfigDict(validate_assignment=True)

class Difficulty(Enum):
    Easy = auto()
    Average = auto()
    Hard = auto()
    Very_Hard = auto()
    Wildcard = auto()

def format_skill_list(skills: Iterable[Skill]):
  return "\n- " + "\n- ".join(str(skill) for skill in skills)

def match_str_to_difficulty(v: Any):
    if isinstance(v, Difficulty):
        return v
    
    if isinstance(v, int) and v in Difficulty:
        return Difficulty(v)
    
    if isinstance(v, str):
        match v.lower():
            case "e" | "easy" | "esy": 
                return Difficulty.Easy
            
            case "a" | "avg" | "average":
                return Difficulty.Average
            
            case "h" | "hard" | "hrd":
                return Difficulty.Hard
            
            case "vh" | "very hard" | "very_hard" | "v hard" | "v. hard":
                return Difficulty.Very_Hard
            
            case "wildcard" | "wldcrd" | "wild":
                return Difficulty.Wildcard
            
            case _:
                raise ValidationError(f"Could not match string: {v}")
            
    raise ValidationError(f"Unrecognised object type: {v}")

CoercingDifficulty = Annotated[Difficulty, BeforeValidator(match_str_to_difficulty)]

class RollResult(Enum):
    crit_fail = auto()
    failure = auto()
    success = auto()
    crit_success = auto()

    def __gt__(self, other):
        if isinstance(other, RollResult):
            return self.value > other.value
        
        return NotImplemented
    
    def __lt__(self, other):
        if isinstance(other, RollResult):
            return self.value < other.value
        
        return NotImplemented
    
    @property
    def str(self):
        match self:
            case RollResult.crit_fail:
                return "CRITICAL FAILURE"
            
            case RollResult.failure:
                return "FAILURE"
            
            case RollResult.success:
                return "SUCCESS"
            
            case RollResult.crit_success:
                return "CRITICAL SUCCESS"


@dataclass
class Roll:
    rolls: tuple[int, int, int]
    status: RollResult

    @property
    def sum(self):
        return sum(self.rolls)
    
    def __gt__(self, other):
        if isinstance(other, Roll):
            if self.status > other.status:
                return True
            
            return self.sum < other.sum
        
        return NotImplemented
    
    def __lt__(self, other):
        if isinstance(other, Roll):
            if self.status < other.status:
                return True
            
            return self.sum > other.sum
        
        return NotImplemented
    
    @property
    def markdown_obj(self):
        commastr = ", ".join(str(roll) for roll in self.rolls)
        return f"`{self.status.str}: {commastr}`"

class Timer(BaseModel):
    description: str
    trigger_time: int

def to_comp_name(name: str):
    return name.lower()


class Player(BaseModel):
    model_config = validate_assignment

    discord_id: int = Field(..., frozen=True)

    google_sheets_id: str | None = None

    skills: dict[str, Skill] = {}
    timers: list[Timer] = []

    def roll_skill(self, skill: str):
        if skill in self.skills:
            return self.skills[skill].roll()
        
        return None

    def luck_roll(self, skill: str):
        if skill in self.skills:
            skill_obj = self.skills[skill]
            return max(skill_obj.roll() for _ in range(3))
        
    @model_validator(mode="after")
    def write_on_edit(self):
        self.write_to_file()
        return self

    def write_to_file(self):
        writestr = self.model_dump_json()

        with open(f"players/{self.discord_id}.json", "w") as f:
            f.write(writestr)

        return self

    def add_skill(self, skill: Skill):
        self.skills[skill.comp_name] = skill
        self.write_to_file()

    def remove_skill(self, skill_name: str):
        del self.skills[skill_name]
        self.write_to_file()

class PlayerManager:
    def __init__(self, player: Player):
        self.player = player
        self.lock = Lock()

    @classmethod
    def from_id(cls, **kwargs):
        return cls(
            player=Player(
                **kwargs
            )
        )

    async def __aenter__(self):
        await self.lock.acquire()
        return self.player

    async def __aexit__(self, *args):
        self.player.write_to_file()
        self.lock.release()

class Skill(BaseModel):
    name: str = Field(..., frozen=True)
    value: int

    note: str | None = None

    crit_success_override: int | None = None
    crit_fail_override: int | None = None

    def __str__(self):
        return f"{self.name}: {self.value}"
    
    @field_validator("name", mode="after")
    def strip_field(name: str):
        name = name.strip()
        return name

    @property
    def comp_name(self):
        return to_comp_name(self.name)
    
    @property
    def crit_fail_thresh(self):
        if self.crit_fail_override is not None:
            return self.crit_fail_override

        skill_value: int = self.value

        if skill_value < 7:
            return 10 + skill_value
        
        if skill_value < 16:
            return 17
        
        return 18
    
    @property
    def crit_success_thresh(self):   
        if self.crit_success_override is not None:
            return self.crit_success_override
     
        skill_value: int = self.value

        return max(4, min(skill_value-10, 6))

    def roll(self):
        rolls = tuple(randrange(1, 7) for _ in range(3))
        
        total = sum(rolls)

        if total <= self.crit_success_thresh:
            status = RollResult.crit_success
        
        elif total <= self.value:
            status = RollResult.success

        elif total >= self.crit_fail_thresh:
            status = RollResult.crit_fail

        else:
            status = RollResult.failure

        return Roll(rolls=rolls, status=status)
    

def load_from_files():
    dirpath, _, json_files = next(os.walk("players/"))

    playerdict: dict[int, PlayerManager] = {}

    for file in json_files:
        full_name = os.path.join(dirpath, file)

        with open(full_name, "r") as f:
            json_obj = json.load(f)

        player_obj = Player.model_validate(json_obj)

        manager = PlayerManager(player_obj)

        playerdict[player_obj.discord_id] = manager
    
    return playerdict

