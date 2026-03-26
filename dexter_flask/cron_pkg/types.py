"""Cron types — mirror src/cron/types.ts."""
from __future__ import annotations

from typing import Literal, TypedDict


class CronScheduleAt(TypedDict):
    kind: Literal["at"]
    at: str


class CronScheduleEvery(TypedDict, total=False):
    kind: Literal["every"]
    everyMs: int
    anchorMs: int


class CronScheduleCron(TypedDict, total=False):
    kind: Literal["cron"]
    expr: str
    tz: str


CronSchedule = CronScheduleAt | CronScheduleEvery | CronScheduleCron


class CronPayload(TypedDict, total=False):
    message: str
    model: str
    modelProvider: str


class CronJobState(TypedDict, total=False):
    nextRunAtMs: int
    lastRunAtMs: int
    lastRunStatus: str
    lastError: str
    lastDurationMs: int
    consecutiveErrors: int
    scheduleErrorCount: int


class CronJob(TypedDict, total=False):
    id: str
    name: str
    description: str
    enabled: bool
    createdAtMs: int
    updatedAtMs: int
    schedule: CronSchedule
    payload: CronPayload
    fulfillment: str
    state: CronJobState


class CronStore(TypedDict):
    version: int
    jobs: list[CronJob]
